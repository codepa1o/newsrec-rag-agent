import os
from pathlib import Path

os.environ.setdefault("MIND_NEWS_PATH", str(Path("missing-news.tsv")))
os.environ.setdefault("MIND_BEHAVIORS_PATH", str(Path("missing-behaviors.tsv")))
os.environ.setdefault("MAX_EVAL_USERS", "8")

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def auth_headers() -> dict[str, str]:
    response = client.post("/auth/login", json={"username": "U100", "password": "demo123456"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_metrics_overview_and_strategy_compare():
    overview = client.get("/metrics/overview")
    compare = client.post("/recommend/compare", json={"user_id": "U100", "top_k": 5, "query": "AI"})

    assert overview.status_code == 200
    assert overview.json()["articles"] > 0
    assert compare.status_code == 200
    strategies = compare.json()["strategies"]
    assert len(strategies) >= 5
    assert all(strategy["items"] for strategy in strategies)


def test_strategy_evaluation_interest_drift_and_cluster():
    headers = auth_headers()

    evaluation = client.post("/evaluate/strategies", json={"k_values": [5, 10]})
    drift = client.get("/me/interest-drift", headers=headers)
    cluster = client.get("/articles/N1006/event-cluster?top_k=3")
    viewpoints = client.get("/articles/N1006/viewpoints?top_k=3")

    assert evaluation.status_code == 200
    assert "agentic_rag" in evaluation.json()["results"]
    assert drift.status_code == 200
    assert "summary" in drift.json()
    assert cluster.status_code == 200
    assert cluster.json()["items"]
    assert viewpoints.status_code == 200
    assert "viewpoints" in viewpoints.json()


def test_hybrid_rag_daily_briefing_and_agent_trace():
    headers = auth_headers()
    content = (
        "# 推荐透明度\n\n"
        "新闻推荐系统需要展示推荐依据、引用来源和用户反馈闭环，以降低幻觉风险。"
    ).encode("utf-8")
    upload = client.post(
        "/me/documents/upload",
        headers=headers,
        files={"file": ("resume_v4_rag.md", content, "text/markdown")},
    )
    assert upload.status_code == 200
    document_id = upload.json()["document_id"]

    rag = client.post(
        "/me/rag/hybrid-query",
        headers=headers,
        json={"question": "推荐透明度为什么重要？", "top_k": 3},
    )
    briefing = client.post("/me/daily-briefing", headers=headers, json={"top_k": 3})
    trace = client.post(
        "/me/agent/trace",
        headers=headers,
        json={"query": "结合资料解释推荐透明度", "top_k": 3},
    )

    assert rag.status_code == 200
    assert rag.json()["retrieval_mode"] == "hybrid"
    assert "verification" in rag.json()
    assert briefing.status_code == 200
    assert briefing.json()["items"]
    assert trace.status_code == 200
    agents = {step["agent"] for step in trace.json()["workflow_trace"]}
    assert {"PlannerAgent", "RouterAgent", "CitationVerifierAgent"} <= agents

    delete = client.delete(f"/me/documents/{document_id}", headers=headers)
    assert delete.status_code == 200
