from __future__ import annotations

import math
from dataclasses import dataclass

from app.models import Behavior
from app.services.recommender import NewsRecommender


@dataclass
class EvaluationResult:
    hit_rate: float
    mrr: float
    ndcg: float
    users: int

    def to_dict(self) -> dict:
        return {
            "hit_rate": round(self.hit_rate, 4),
            "mrr": round(self.mrr, 4),
            "ndcg": round(self.ndcg, 4),
            "users": self.users,
        }


def hit_rate_at_k(recommended_ids: list[str], relevant_ids: set[str], k: int) -> float:
    return 1.0 if relevant_ids.intersection(recommended_ids[:k]) else 0.0


def mrr_at_k(recommended_ids: list[str], relevant_ids: set[str], k: int) -> float:
    for rank, news_id in enumerate(recommended_ids[:k], start=1):
        if news_id in relevant_ids:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(recommended_ids: list[str], relevant_ids: set[str], k: int) -> float:
    dcg = 0.0
    for rank, news_id in enumerate(recommended_ids[:k], start=1):
        if news_id in relevant_ids:
            dcg += 1.0 / math.log2(rank + 1)
    ideal_hits = min(len(relevant_ids), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / idcg if idcg else 0.0


class Evaluator:
    def __init__(self, recommender: NewsRecommender, behaviors: list[Behavior]) -> None:
        self.recommender = recommender
        self.behaviors = behaviors

    def evaluate(self, k: int = 10) -> EvaluationResult:
        totals = {"hit_rate": 0.0, "mrr": 0.0, "ndcg": 0.0}
        users = 0
        for behavior in self.behaviors:
            relevant = {impression.news_id for impression in behavior.impressions if impression.clicked}
            if not relevant:
                continue
            recommended = [item.news_id for item in self.recommender.recommend(behavior.user_id, top_k=k)]
            totals["hit_rate"] += hit_rate_at_k(recommended, relevant, k)
            totals["mrr"] += mrr_at_k(recommended, relevant, k)
            totals["ndcg"] += ndcg_at_k(recommended, relevant, k)
            users += 1

        if users == 0:
            return EvaluationResult(hit_rate=0.0, mrr=0.0, ndcg=0.0, users=0)
        return EvaluationResult(
            hit_rate=totals["hit_rate"] / users,
            mrr=totals["mrr"] / users,
            ndcg=totals["ndcg"] / users,
            users=users,
        )
