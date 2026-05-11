from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["message"] == "服务正常"


def test_login_and_me_recommend_flow():
    login_response = client.post("/auth/login", json={"username": "U100", "password": "demo123456"})

    assert login_response.status_code == 200
    token = login_response.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    profile_response = client.get("/me/profile", headers=headers)
    recommend_response = client.get("/me/recommend?top_k=3", headers=headers)

    assert profile_response.status_code == 200
    assert profile_response.json()["user_id"] == "U100"
    assert recommend_response.status_code == 200
    assert recommend_response.json()["items"]


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
