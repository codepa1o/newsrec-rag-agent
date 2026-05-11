from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def auth_headers() -> dict[str, str]:
    login_response = client.post("/auth/login", json={"username": "U100", "password": "demo123456"})
    assert login_response.status_code == 200
    token = login_response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["message"] == "服务正常"


def test_login_and_me_recommend_flow():
    headers = auth_headers()

    profile_response = client.get("/me/profile", headers=headers)
    recommend_response = client.get("/me/recommend?top_k=3", headers=headers)

    assert profile_response.status_code == 200
    assert profile_response.json()["user_id"] == "U100"
    assert recommend_response.status_code == 200
    assert recommend_response.json()["items"]


def test_article_detail_history_favorite_and_ai_fallback_flow():
    headers = auth_headers()

    detail_response = client.get("/me/articles/N1006", headers=headers)
    view_response = client.post("/me/articles/N1006/view", headers=headers)
    favorite_response = client.post("/me/articles/N1006/favorite", json={"favorite": True}, headers=headers)
    favorites_response = client.get("/me/favorites", headers=headers)
    history_response = client.get("/me/history", headers=headers)
    summary_response = client.post("/me/articles/N1006/summary", headers=headers)
    ask_response = client.post(
        "/me/articles/N1006/ask",
        json={"question": "这篇新闻和推荐系统有什么关系？"},
        headers=headers,
    )

    assert detail_response.status_code == 200
    assert detail_response.json()["article"]["news_id"] == "N1006"
    assert view_response.status_code == 200
    assert favorite_response.status_code == 200
    assert favorite_response.json()["favorite"] is True
    assert any(item["news_id"] == "N1006" for item in favorites_response.json()["items"])
    assert any(item["news_id"] == "N1006" for item in history_response.json()["items"])
    assert summary_response.status_code == 200
    assert summary_response.json()["one_sentence"]
    assert ask_response.status_code == 200
    assert ask_response.json()["answer"]

    client.post("/me/articles/N1006/favorite", json={"favorite": False}, headers=headers)


def test_agent_recommend_endpoint():
    headers = auth_headers()

    response = client.post("/me/agent/recommend", json={"query": "AI 推荐系统", "top_k": 2}, headers=headers)

    assert response.status_code == 200
    assert response.json()["query"] == "AI 推荐系统"
    assert response.json()["items"]


def test_article_detail_404():
    headers = auth_headers()

    response = client.get("/me/articles/UNKNOWN", headers=headers)

    assert response.status_code == 404


def test_recommend_endpoint_shape():
    response = client.get("/recommend/U100?top_k=3")

    assert response.status_code == 200
    payload = response.json()
    assert payload["user_id"] == "U100"
    assert payload["items"]
    assert {"news_id", "title", "category", "abstract", "score", "reason", "evidence"} <= set(payload["items"][0])


def test_feedback_endpoint_records_feedback():
    response = client.post("/feedback", json={"user_id": "U100", "news_id": "N1006", "feedback_type": "like"})

    assert response.status_code == 200
    assert response.json()["status"] == "recorded"
