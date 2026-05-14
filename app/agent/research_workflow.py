from __future__ import annotations

from typing import Any, Literal, TypedDict


Intent = Literal["news_recommendation", "document_qa", "article_analysis", "evaluation"]


class ResearchAgentState(TypedDict, total=False):
    user_id: str
    query: str
    top_k: int
    intent: Intent
    news_items: list[dict[str, Any]]
    rag_result: dict[str, Any]
    answer: str
    workflow_trace: list[dict[str, Any]]


class MultiAgentResearchWorkflow:
    """LangGraph-compatible deterministic multi-agent workflow for demo use."""

    def __init__(self, container) -> None:
        self.container = container
        self.graph = self._build_graph()

    def run(self, user_id: str, query: str, top_k: int = 5) -> ResearchAgentState:
        state: ResearchAgentState = {"user_id": user_id, "query": query, "top_k": top_k, "workflow_trace": []}
        if self.graph is None:
            state = self._router_agent(state)
            state = self._retriever_agent(state)
            state = self._rerank_agent(state)
            state = self._answer_agent(state)
            state = self._verifier_agent(state)
            return state
        return self.graph.invoke(state)

    def _build_graph(self):
        try:
            from langgraph.graph import END, StateGraph
        except ImportError:  # pragma: no cover - optional dependency
            return None

        graph = StateGraph(ResearchAgentState)
        graph.add_node("RouterAgent", self._router_agent)
        graph.add_node("RetrieverAgent", self._retriever_agent)
        graph.add_node("RerankAgent", self._rerank_agent)
        graph.add_node("AnswerAgent", self._answer_agent)
        graph.add_node("VerifierAgent", self._verifier_agent)
        graph.set_entry_point("RouterAgent")
        graph.add_edge("RouterAgent", "RetrieverAgent")
        graph.add_edge("RetrieverAgent", "RerankAgent")
        graph.add_edge("RerankAgent", "AnswerAgent")
        graph.add_edge("AnswerAgent", "VerifierAgent")
        graph.add_edge("VerifierAgent", END)
        return graph.compile()

    def _router_agent(self, state: ResearchAgentState) -> ResearchAgentState:
        query = state["query"]
        lowered = query.lower()
        if any(word in query for word in ("资料", "文档", "报告", "论文", "引用", "依据")):
            intent: Intent = "document_qa"
        elif any(word in query for word in ("评估", "指标", "HitRate", "MRR", "NDCG")):
            intent = "evaluation"
        else:
            intent = "news_recommendation"
        state["intent"] = intent
        state["workflow_trace"].append({"agent": "RouterAgent", "output": f"识别意图：{intent}"})
        return state

    def _retriever_agent(self, state: ResearchAgentState) -> ResearchAgentState:
        intent = state["intent"]
        top_k = state.get("top_k", 5)
        query = state["query"]
        if intent == "document_qa":
            state["rag_result"] = self.container.rag_service.query(state["user_id"], query, top_k=top_k)
        elif intent == "evaluation":
            result = self.container.evaluator.evaluate(k=top_k)
            state["rag_result"] = {"answer": f"当前评估结果：{result.to_dict()}", "citations": [], "confidence": 1.0}
        else:
            state["news_items"] = [item.to_dict() for item in self.container.recommender.search(query, top_k=top_k)]
            if any(word in query for word in ("结合", "资料", "依据")):
                state["rag_result"] = self.container.rag_service.query(state["user_id"], query, top_k=3)
        state["workflow_trace"].append({"agent": "RetrieverAgent", "output": "完成新闻库/资料库检索"})
        return state

    def _rerank_agent(self, state: ResearchAgentState) -> ResearchAgentState:
        items = state.get("news_items", [])
        state["news_items"] = sorted(items, key=lambda item: item.get("score", 0), reverse=True)
        state["workflow_trace"].append({"agent": "RerankAgent", "output": f"重排候选新闻 {len(items)} 条"})
        return state

    def _answer_agent(self, state: ResearchAgentState) -> ResearchAgentState:
        if state.get("intent") == "document_qa":
            state["answer"] = state.get("rag_result", {}).get("answer", "")
        elif state.get("intent") == "evaluation":
            state["answer"] = state.get("rag_result", {}).get("answer", "")
        else:
            count = len(state.get("news_items", []))
            state["answer"] = f"已根据你的需求找到 {count} 篇相关新闻。"
            if state.get("rag_result", {}).get("citations"):
                state["answer"] += " 同时参考了你的本地资料库作为补充依据。"
        state["workflow_trace"].append({"agent": "AnswerAgent", "output": "生成最终回答"})
        return state

    def _verifier_agent(self, state: ResearchAgentState) -> ResearchAgentState:
        rag = state.get("rag_result") or {}
        citations = rag.get("citations", [])
        if state.get("intent") == "document_qa" and not citations:
            output = "资料库证据不足，已触发幻觉控制。"
        elif citations:
            output = f"检查到 {len(citations)} 条引用来源。"
        else:
            output = "当前回答不依赖本地资料引用。"
        state["workflow_trace"].append({"agent": "VerifierAgent", "output": output})
        return state
