from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models import Article
from app.services.database import Database
from app.services.document_service import DocumentHit, DocumentService
from app.services.llm_service import LLMService


MIN_USEFUL_SCORE = 0.05


@dataclass
class RAGService:
    database: Database
    document_service: DocumentService
    llm_service: LLMService

    def query(self, user_id: str, question: str, top_k: int = 5, document_id: str | None = None) -> dict[str, Any]:
        question = question.strip()
        hits = self.document_service.search(user_id=user_id, query=question, top_k=top_k, document_id=document_id)
        useful_hits = [hit for hit in hits if hit.score >= MIN_USEFUL_SCORE]
        citations = [self._citation_from_hit(hit) for hit in useful_hits]
        contexts = [self._context_from_hit(hit) for hit in useful_hits]

        if not useful_hits:
            answer = "本地资料中没有找到足够依据回答这个问题。你可以上传更相关的资料，或换一个更具体的问题。"
            confidence = 0.15
            missing_evidence = True
        else:
            generated = self.llm_service.grounded_answer(question, contexts)
            answer = generated or self._fallback_grounded_answer(question, citations)
            confidence = min(0.92, 0.45 + sum(hit.score for hit in useful_hits[:3]) / max(len(useful_hits[:3]), 1))
            missing_evidence = False

        evaluation = evaluate_answer(answer, question, citations, missing_evidence)
        trace = [
            {"agent": "RouterAgent", "output": "资料库问答"},
            {"agent": "RetrieverAgent", "output": f"召回 {len(hits)} 个资料片段"},
            {"agent": "RerankAgent", "output": f"保留 {len(useful_hits)} 个可引用片段"},
            {"agent": "AnswerAgent", "output": "基于引用片段生成回答" if useful_hits else "证据不足，返回保护性回答"},
            {"agent": "VerifierAgent", "output": evaluation["notes"]},
        ]
        query_id = self.database.record_rag_query(user_id, question, answer, confidence, trace)
        self.database.record_rag_citations(query_id, citations)
        self.database.record_answer_evaluation(query_id, evaluation)

        return {
            "query_id": query_id,
            "question": question,
            "answer": answer,
            "citations": citations,
            "confidence": round(confidence, 4),
            "missing_evidence": missing_evidence,
            "evaluation": evaluation,
            "workflow_trace": trace,
        }

    def analyze_article(self, user_id: str, article: Article, top_k: int = 5) -> dict[str, Any]:
        question = (
            f"请结合我的本地资料，解释这篇新闻《{article.title}》和资料库内容有什么关系。"
            f"新闻摘要：{article.abstract}"
        )
        result = self.query(user_id=user_id, question=question, top_k=top_k)
        result["article"] = article.to_dict()
        return result

    def _citation_from_hit(self, hit: DocumentHit) -> dict[str, Any]:
        citation = hit.chunk.to_dict(score=hit.score)
        citation["score"] = round(hit.score, 4)
        return citation

    def _context_from_hit(self, hit: DocumentHit) -> dict[str, Any]:
        return {
            "chunk_id": hit.chunk.chunk_id,
            "document_id": hit.chunk.document_id,
            "filename": hit.chunk.filename,
            "page": hit.chunk.page,
            "heading_path": hit.chunk.heading_path,
            "text": hit.chunk.text,
            "score": hit.score,
        }

    def _fallback_grounded_answer(self, question: str, citations: list[dict[str, Any]]) -> str:
        lines = ["根据本地资料库中检索到的片段，可以得到以下参考结论："]
        for index, citation in enumerate(citations[:3], start=1):
            location = citation.get("page") or citation.get("heading_path") or f"chunk {citation.get('chunk_index')}"
            lines.append(f"[{index}] {citation['filename']}（{location}）提到：{citation['snippet']}")
        lines.append("以上回答只基于已检索到的本地资料片段，建议继续补充更完整的资料以提高可信度。")
        return "\n".join(lines)


def evaluate_answer(
    answer: str,
    question: str,
    citations: list[dict[str, Any]],
    missing_evidence: bool,
) -> dict[str, Any]:
    if missing_evidence:
        return {
            "faithfulness": 1.0,
            "answer_relevance": 0.5,
            "citation_coverage": 0.0,
            "notes": "资料不足时已返回保护性回答，没有强行编造。",
        }

    has_citation_marker = any(f"[{index}]" in answer for index in range(1, len(citations) + 1))
    question_terms = {term for term in question.lower().split() if len(term) > 1}
    answer_terms = set(answer.lower().split())
    relevance = len(question_terms & answer_terms) / max(len(question_terms), 1) if question_terms else 0.7
    coverage = min(1.0, len(citations) / 3)
    faithfulness = 0.9 if has_citation_marker else 0.65
    return {
        "faithfulness": round(faithfulness, 4),
        "answer_relevance": round(max(0.5, min(1.0, relevance)), 4),
        "citation_coverage": round(coverage, 4),
        "notes": "回答包含引用来源。" if has_citation_marker else "回答缺少显式引用编号，建议检查提示词或模型输出。",
    }
