from fastapi.testclient import TestClient

from app.main import app
from app.services.document_service import parse_markdown, split_text


client = TestClient(app)


def auth_headers() -> dict[str, str]:
    login_response = client.post("/auth/login", json={"username": "U100", "password": "demo123456"})
    assert login_response.status_code == 200
    token = login_response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_markdown_parser_keeps_heading_path():
    pages = parse_markdown("# AI 治理\n\n推荐系统需要透明度。\n\n## 合规\n\n需要引用来源。")

    assert pages
    assert any("AI 治理" in page.heading_path for page in pages)


def test_split_text_handles_long_paragraph():
    chunks = split_text("A" * 2400, chunk_size=800, overlap=100)

    assert len(chunks) >= 3
    assert all(len(chunk) <= 800 for chunk in chunks)


def test_document_upload_rag_query_article_analysis_and_agent_chat():
    headers = auth_headers()
    content = (
        "# AI 监管资料\n\n"
        "AI 新闻推荐系统需要关注透明度、可解释性和用户反馈闭环。\n\n"
        "在合规场景中，推荐理由应引用可靠资料，避免生成没有依据的结论。"
    ).encode("utf-8")

    upload_response = client.post(
        "/me/documents/upload",
        headers=headers,
        files={"file": ("ai_policy.md", content, "text/markdown")},
    )
    assert upload_response.status_code == 200
    document_id = upload_response.json()["document_id"]
    assert upload_response.json()["status"] == "ready"

    list_response = client.get("/me/documents", headers=headers)
    detail_response = client.get(f"/me/documents/{document_id}", headers=headers)
    rag_response = client.post(
        "/me/rag/query",
        json={"question": "AI 新闻推荐系统为什么需要可解释性？", "top_k": 3},
        headers=headers,
    )
    analysis_response = client.post("/me/articles/N1006/grounded-analysis", headers=headers)
    agent_response = client.post(
        "/me/agent/chat",
        json={"query": "结合资料解释 AI 推荐系统合规", "top_k": 3},
        headers=headers,
    )

    assert list_response.status_code == 200
    assert any(item["document_id"] == document_id for item in list_response.json()["items"])
    assert detail_response.status_code == 200
    assert detail_response.json()["chunks"]
    assert rag_response.status_code == 200
    assert rag_response.json()["answer"]
    assert rag_response.json()["citations"]
    assert {"faithfulness", "answer_relevance", "citation_coverage"} <= set(rag_response.json()["evaluation"])
    assert analysis_response.status_code == 200
    assert "citations" in analysis_response.json()
    assert agent_response.status_code == 200
    assert agent_response.json()["workflow_trace"]

    delete_response = client.delete(f"/me/documents/{document_id}", headers=headers)
    assert delete_response.status_code == 200
