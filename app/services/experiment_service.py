from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Literal

from app.models import Article, Behavior, Recommendation, UserProfile
from app.services.evaluator import hit_rate_at_k, mrr_at_k, ndcg_at_k
from app.services.profile import ProfileService
from app.services.recommender import NewsRecommender
from app.services.vector_store import SearchHit


StrategyName = Literal["hot", "category", "vector", "feedback", "agentic_rag"]

STRATEGY_LABELS: dict[str, str] = {
    "hot": "热门推荐 baseline",
    "category": "类别偏好推荐",
    "vector": "向量语义推荐",
    "feedback": "反馈增强推荐",
    "agentic_rag": "Agentic RAG 推荐",
}


@dataclass
class StrategyEvaluation:
    strategy: str
    hit_rate: float
    mrr: float
    ndcg: float
    users: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "label": STRATEGY_LABELS.get(self.strategy, self.strategy),
            "hit_rate": round(self.hit_rate, 4),
            "mrr": round(self.mrr, 4),
            "ndcg": round(self.ndcg, 4),
            "users": self.users,
        }


class RecommendationExperimentService:
    def __init__(
        self,
        articles: dict[str, Article],
        behaviors: list[Behavior],
        profile_service: ProfileService,
        recommender: NewsRecommender,
        max_eval_users: int = 80,
    ) -> None:
        self.articles = articles
        self.behaviors = behaviors
        self.profile_service = profile_service
        self.recommender = recommender
        self.max_eval_users = max_eval_users

    def compare(self, user_id: str, top_k: int = 20, query: str | None = None) -> dict[str, Any]:
        strategies: list[str] = ["hot", "category", "vector", "feedback", "agentic_rag"]
        items = {
            strategy: [item.to_dict() for item in self.recommend_by_strategy(strategy, user_id, top_k, query=query)]
            for strategy in strategies
        }
        return {
            "user_id": user_id,
            "top_k": top_k,
            "strategies": [{"name": name, "label": STRATEGY_LABELS[name], "items": items[name]} for name in strategies],
            "category_distribution": {name: category_distribution(items[name]) for name in strategies},
        }

    def recommend_by_strategy(
        self,
        strategy: str,
        user_id: str,
        top_k: int = 20,
        query: str | None = None,
    ) -> list[Recommendation]:
        profile = self.profile_service.build_profile(user_id)
        exclude_ids = set(profile.recent_clicked_news)

        if strategy == "hot":
            hits = self._hot_hits(top_k * 3, exclude_ids)
        elif strategy == "category":
            hits = self._category_hits(profile, top_k * 4, exclude_ids)
        elif strategy == "vector":
            search_query = query or self.recommender._profile_query(profile)
            hits = self.recommender.vector_store.search(search_query, top_k=top_k * 3, exclude_ids=exclude_ids)
        elif strategy == "feedback":
            hits = self._feedback_hits(profile, top_k * 4, exclude_ids)
        else:
            return self.recommender.recommend(user_id, top_k=top_k)

        hits = [hit for hit in self.recommender._deduplicate(hits) if hit.article.category not in profile.blocked_categories]
        reranked = self.recommender.reranker.rerank(hits, profile)
        diversified = self.recommender._diversity_filter(reranked, top_k)
        return [self.recommender._to_recommendation(hit, profile) for hit in diversified]

    def evaluate_strategies(self, k_values: list[int] | None = None) -> dict[str, Any]:
        k_values = k_values or [5, 10, 20]
        strategies = ["hot", "category", "vector", "feedback", "agentic_rag"]
        results: dict[str, list[dict[str, Any]]] = {strategy: [] for strategy in strategies}
        for k in k_values:
            for strategy in strategies:
                results[strategy].append(self._evaluate_strategy(strategy, k).to_dict() | {"k": k})

        best_by_k = {}
        for k in k_values:
            candidates = [rows for rows in results.values() for rows in rows if rows["k"] == k]
            best_by_k[str(k)] = max(candidates, key=lambda row: (row["ndcg"], row["mrr"], row["hit_rate"]), default={})
        return {"k_values": k_values, "results": results, "best_by_k": best_by_k}

    def ablation(self, user_id: str, top_k: int = 20) -> dict[str, Any]:
        full = self.recommender.recommend(user_id, top_k=top_k)
        no_diversity = self._without_diversity(user_id, top_k)
        no_feedback = self.recommend_by_strategy("vector", user_id, top_k=top_k)
        no_rag = self.recommend_by_strategy("feedback", user_id, top_k=top_k)
        return {
            "user_id": user_id,
            "top_k": top_k,
            "variants": [
                {"name": "full_agentic_rag", "label": "完整 Agentic RAG 推荐", "items": [item.to_dict() for item in full]},
                {"name": "no_diversity", "label": "去掉多样性过滤", "items": [item.to_dict() for item in no_diversity]},
                {"name": "no_feedback", "label": "去掉反馈增强", "items": [item.to_dict() for item in no_feedback]},
                {"name": "no_rag", "label": "去掉本地资料库主题", "items": [item.to_dict() for item in no_rag]},
            ],
        }

    def cold_start(self, interest_tags: list[str], top_k: int = 20) -> dict[str, Any]:
        query = " ".join(tag for tag in interest_tags if tag.strip()) or "breaking news technology finance health sports"
        hits = self.recommender.vector_store.search(query, top_k=top_k * 3)
        hot = self._hot_hits(top_k)
        merged = self.recommender._deduplicate(hits + hot)
        pseudo_profile = UserProfile(user_id="cold_start", preferred_categories=interest_tags[:5], keywords=interest_tags[:12])
        reranked = self.recommender.reranker.rerank(merged, pseudo_profile)
        diversified = self.recommender._diversity_filter(reranked, top_k)
        return {
            "interest_tags": interest_tags,
            "top_k": top_k,
            "items": [self.recommender._to_recommendation(hit, pseudo_profile).to_dict() for hit in diversified],
        }

    def _evaluate_strategy(self, strategy: str, k: int) -> StrategyEvaluation:
        totals = {"hit_rate": 0.0, "mrr": 0.0, "ndcg": 0.0}
        users = 0
        for behavior in self.behaviors:
            relevant = {impression.news_id for impression in behavior.impressions if impression.clicked}
            if not relevant:
                continue
            recommended = [item.news_id for item in self.recommend_by_strategy(strategy, behavior.user_id, top_k=k)]
            totals["hit_rate"] += hit_rate_at_k(recommended, relevant, k)
            totals["mrr"] += mrr_at_k(recommended, relevant, k)
            totals["ndcg"] += ndcg_at_k(recommended, relevant, k)
            users += 1
            if users >= self.max_eval_users:
                break
        if users == 0:
            return StrategyEvaluation(strategy, 0.0, 0.0, 0.0, 0)
        return StrategyEvaluation(
            strategy=strategy,
            hit_rate=totals["hit_rate"] / users,
            mrr=totals["mrr"] / users,
            ndcg=totals["ndcg"] / users,
            users=users,
        )

    def _hot_hits(self, limit: int, exclude_ids: set[str] | None = None) -> list[SearchHit]:
        exclude_ids = exclude_ids or set()
        candidates = [article for article in self.articles.values() if article.news_id not in exclude_ids]
        candidates.sort(key=lambda article: article.popularity, reverse=True)
        return [SearchHit(article=article, score=0.3 + min(article.popularity, 100) / 100.0) for article in candidates[:limit]]

    def _category_hits(self, profile, limit: int, exclude_ids: set[str]) -> list[SearchHit]:
        if not profile.preferred_categories:
            return self._hot_hits(limit, exclude_ids)
        hits: list[SearchHit] = []
        category_rank = {category: index for index, category in enumerate(profile.preferred_categories)}
        for article in self.articles.values():
            if article.news_id in exclude_ids or article.category not in category_rank:
                continue
            score = 0.75 - category_rank[article.category] * 0.05 + min(article.popularity, 50) / 500
            hits.append(SearchHit(article=article, score=score))
        hits.sort(key=lambda hit: hit.score, reverse=True)
        if not hits:
            return self._hot_hits(limit, exclude_ids)
        return hits[:limit]

    def _feedback_hits(self, profile, limit: int, exclude_ids: set[str]) -> list[SearchHit]:
        query = " ".join(profile.preferred_categories + profile.keywords)
        hits = self.recommender.vector_store.search(query or "news", top_k=limit * 2, exclude_ids=exclude_ids)
        hits.extend(self._category_hits(profile, limit, exclude_ids))
        return self.recommender._deduplicate(hits)[:limit]

    def _without_diversity(self, user_id: str, top_k: int) -> list[Recommendation]:
        profile = self.profile_service.build_profile(user_id)
        query = self.recommender._profile_query(profile)
        exclude_ids = set(profile.recent_clicked_news)
        hits = self.recommender.vector_store.search(query, top_k=self.recommender.retrieval_top_k, exclude_ids=exclude_ids)
        hits.extend(self._category_hits(profile, top_k * 3, exclude_ids))
        hits.extend(self._hot_hits(top_k, exclude_ids))
        reranked = self.recommender.reranker.rerank(self.recommender._deduplicate(hits), profile)
        return [self.recommender._to_recommendation(hit, profile) for hit in reranked[:top_k]]


def category_distribution(items: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(item.get("category", "unknown") for item in items))
