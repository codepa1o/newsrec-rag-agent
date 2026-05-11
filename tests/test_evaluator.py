from app.services.evaluator import hit_rate_at_k, mrr_at_k, ndcg_at_k


def test_ranking_metrics():
    recommended = ["N1", "N2", "N3"]
    relevant = {"N2"}

    assert hit_rate_at_k(recommended, relevant, 3) == 1.0
    assert mrr_at_k(recommended, relevant, 3) == 0.5
    assert ndcg_at_k(recommended, relevant, 3) > 0
