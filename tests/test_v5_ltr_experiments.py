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


def test_ltr_training_status_recommendation_and_explain():
    headers = auth_headers()

    status_before = client.get("/models/ltr/status")
    train = client.post("/models/ltr/train", json={"max_users": 20, "epochs": 20, "learning_rate": 0.05})
    status_after = client.get("/models/ltr/status")
    recommendation = client.post("/recommend/ltr", json={"user_id": "U100", "top_k": 5, "hybrid_rag": True})
    first_item = recommendation.json()["items"][0]
    explanation = client.get(f"/me/recommend/explain/{first_item['news_id']}", headers=headers)

    assert status_before.status_code == 200
    assert train.status_code == 200
    assert train.json()["trained"] is True
    assert train.json()["sample_count"] >= 0
    assert status_after.json()["loaded"] is True
    assert recommendation.status_code == 200
    assert recommendation.json()["strategy"] == "hybrid_ltr_rag"
    assert recommendation.json()["items"]
    assert explanation.status_code == 200
    assert explanation.json()["contributions"]
    assert "category_match" in explanation.json()["features"]


def test_strategy_evaluation_has_v5_metrics_and_experiment_record():
    response = client.post("/evaluate/strategies", json={"k_values": [5]})
    experiments = client.get("/experiments")

    assert response.status_code == 200
    payload = response.json()
    assert payload["experiment_id"] > 0
    assert "ltr_rerank" in payload["results"]
    row = payload["results"]["ltr_rerank"][0]
    assert {"auc", "catalog_coverage", "category_coverage", "diversity", "novelty", "calibration"} <= set(row)
    assert experiments.status_code == 200
    assert experiments.json()["items"]


def test_ablation_returns_variants_and_records_experiment():
    response = client.post("/evaluate/ablation", json={"user_id": "U100", "top_k": 5})

    assert response.status_code == 200
    variants = response.json()["variants"]
    names = {variant["name"] for variant in variants}
    assert {"full_hybrid_ltr_rag", "no_semantic", "no_diversity", "no_feedback", "no_rag"} <= names
    assert all(variant["items"] for variant in variants)
    assert all("metrics" in variant for variant in variants)
