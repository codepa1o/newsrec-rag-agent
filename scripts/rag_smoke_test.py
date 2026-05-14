from __future__ import annotations

import os
from pathlib import Path

import httpx


API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
ROOT = Path(__file__).resolve().parents[1]
CASE_DIR = ROOT / "docs" / "rag_test_cases"
USERNAME = os.getenv("RAG_TEST_USERNAME", "U100")
PASSWORD = os.getenv("RAG_TEST_PASSWORD", "demo123456")


def main() -> None:
    with httpx.Client(base_url=API_BASE_URL, timeout=120) as client:
        health = client.get("/health")
        health.raise_for_status()
        print(f"[health] {health.json()['message']}")

        login = client.post("/auth/login", json={"username": USERNAME, "password": PASSWORD})
        login.raise_for_status()
        token = login.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        print(f"[login] {USERNAME}")

        for path in [
            CASE_DIR / "ai_recommendation_governance.md",
            CASE_DIR / "local_rag_policy_notes.txt",
            CASE_DIR / "news_recommendation_research.md",
        ]:
            with path.open("rb") as handle:
                response = client.post(
                    "/me/documents/upload",
                    headers=headers,
                    files={"file": (path.name, handle, content_type_for(path))},
                )
            response.raise_for_status()
            payload = response.json()
            print(f"[upload] {payload['filename']} -> {payload['status']} ({payload['chunk_count']} chunks)")

        documents = client.get("/me/documents", headers=headers)
        documents.raise_for_status()
        print(f"[documents] {len(documents.json()['items'])} documents")

        rag_questions = [
            "新闻推荐系统为什么需要推荐透明度？",
            "Markdown 和 PDF 文档应该如何切分？",
            "资料中有没有提到 2028 年某个虚构法规的处罚金额是多少？",
            "RAG 问答模块应该如何评估回答质量？",
        ]
        for question in rag_questions:
            response = client.post("/me/rag/query", headers=headers, json={"question": question, "top_k": 4})
            response.raise_for_status()
            payload = response.json()
            print("\n[rag]", question)
            print("answer:", payload["answer"][:220].replace("\n", " "))
            print("citations:", len(payload["citations"]), "confidence:", payload["confidence"])
            print("evaluation:", payload["evaluation"])

        analysis = client.post("/me/articles/N1006/grounded-analysis", headers=headers)
        analysis.raise_for_status()
        print("\n[article-analysis] N1006")
        print("answer:", analysis.json()["answer"][:220].replace("\n", " "))
        print("citations:", len(analysis.json()["citations"]))

        agent = client.post(
            "/me/agent/chat",
            headers=headers,
            json={"query": "结合我的资料库，推荐并解释几篇 AI 监管相关的新闻", "top_k": 3},
        )
        agent.raise_for_status()
        payload = agent.json()
        print("\n[agent-chat]", payload["intent"])
        print("answer:", payload["answer"])
        print("trace:", " -> ".join(step["agent"] for step in payload["workflow_trace"]))


def content_type_for(path: Path) -> str:
    if path.suffix.lower() in {".md", ".markdown"}:
        return "text/markdown"
    if path.suffix.lower() == ".txt":
        return "text/plain"
    if path.suffix.lower() == ".pdf":
        return "application/pdf"
    return "application/octet-stream"


if __name__ == "__main__":
    main()
