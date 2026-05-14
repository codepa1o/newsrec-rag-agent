from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Any, Literal

from app.models import Article, Behavior, Recommendation, UserProfile
from app.services.database import Database
from app.services.evaluator import hit_rate_at_k, mrr_at_k, ndcg_at_k
from app.services.ltr_service import LearningToRankService
from app.services.profile import ProfileService
from app.services.recommender import NewsRecommender
from app.services.vector_store import SearchHit


StrategyName = Literal["hot", "category", "vector", "feedback", "agentic_rag", "ltr_rerank", "hybrid_ltr_rag"]

STRATEGY_LABELS: dict[str, str] = {
    "hot": "热门推荐 baseline",
    "category": "类别偏好推荐",
    "vector": "向量语义推荐",
    "feedback": "反馈增强推荐",
    "agentic_rag": "Agentic RAG 推荐",
    "ltr_rerank": "LTR 学习排序推荐",
    "hybrid_ltr_rag": "Hybrid LTR + RAG 推荐",
}


@dataclass
class StrategyEvaluation:
    strategy: str
    hit_rate: float
    mrr: float
    ndcg: float
    auc: float
    catalog_coverage: float
    category_coverage: float
    diversity: float
    novelty: float
    calibration: float
    users: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "label": STRATEGY_LABELS.get(self.strategy, self.strategy),
            "hit_rate": round(self.hit_rate, 4),
            "mrr": round(self.mrr, 4),
            "ndcg": round(self.ndcg, 4),
            "auc": round(self.auc, 4),
            "catalog_coverage": round(self.catalog_coverage, 4),
            "category_coverage": round(self.category_coverage, 4),
            "diversity": round(self.diversity, 4),
            "novelty": round(self.novelty, 4),
            "calibration": round(self.calibration, 4),
            "users": self.users,
        }


class RecommendationExperimentService:
    def __init__(
        self,
        articles: dict[str, Article],
        behaviors: list[Behavior],
        database: Database,
        profile_service: ProfileService,
        recommender: NewsRecommender,
        ltr_service: LearningToRankService,
        max_eval_users: int = 80,
    ) -> None:
        self.articles = articles
        self.behaviors = behaviors
        self.database = database
        self.profile_service = profile_service
        self.recommender = recommender
        self.ltr_service = ltr_service
        self.max_eval_users = max_eval_users

    def strategy_names(self) -> list[str]:
        return ["hot", "category", "vector", "feedback", "agentic_rag", "ltr_rerank", "hybrid_ltr_rag"]

    def compare(self, user_id: str, top_k: int = 20, query: str | None = None) -> dict[str, Any]:
        strategies = self.strategy_names()
        items = {
            strategy: [item.to_dict() for item in self.recommend_by_strategy(strategy, user_id, top_k, query=query)]
            for strategy in strategies
        }
        return {
            "user_id": user_id,
            "top_k": top_k,
            "strategies": [{"name": name, "label": STRATEGY_LABELS[name], "items": items[name]} for name in strategies],
            "category_distribution": {name: category_distribution(items[name]) for name in strategies},
            "research_metrics": {name: list_metrics(items[name], self.articles) for name in strategies},
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
        elif strategy == "ltr_rerank":
            return self.ltr_service.recommend(user_id, top_k=top_k)
        elif strategy == "hybrid_ltr_rag":
            return self.ltr_service.recommend(user_id, top_k=top_k, hybrid_rag=True)
        else:
            return self.recommender.recommend(user_id, top_k=top_k)

        hits = [hit for hit in self.recommender._deduplicate(hits) if hit.article.category not in profile.blocked_categories]
        reranked = self.recommender.reranker.rerank(hits, profile)
        diversified = self.recommender._diversity_filter(reranked, top_k)
        return [self.recommender._to_recommendation(hit, profile) for hit in diversified]

    def evaluate_strategies(self, k_values: list[int] | None = None) -> dict[str, Any]:
        k_values = k_values or [5, 10, 20]
        strategies = self.strategy_names()
        results: dict[str, list[dict[str, Any]]] = {strategy: [] for strategy in strategies}
        for k in k_values:
            for strategy in strategies:
                results[strategy].append(self._evaluate_strategy(strategy, k).to_dict() | {"k": k})

        best_by_k = {}
        for k in k_values:
            candidates = [rows for rows in results.values() for rows in rows if rows["k"] == k]
            best_by_k[str(k)] = max(candidates, key=lambda row: (row["ndcg"], row["mrr"], row["hit_rate"]), default={})

        experiment_id = self.database.record_experiment(
            name="multi_strategy_evaluation",
            strategy="all",
            parameters={"k_values": k_values, "strategies": strategies},
            metrics={"results": results, "best_by_k": best_by_k},
            sample_count=sum(rows[0]["users"] for rows in results.values() if rows),
        )
        return {"experiment_id": experiment_id, "k_values": k_values, "results": results, "best_by_k": best_by_k}

    def ablation(self, user_id: str, top_k: int = 20) -> dict[str, Any]:
        full = self.ltr_service.recommend(user_id, top_k=top_k, hybrid_rag=True)
        variants = [
            {"name": "full_hybrid_ltr_rag", "label": "完整 Hybrid LTR + RAG 推荐", "items": [item.to_dict() for item in full]},
            {"name": "no_semantic", "label": "去掉语义相似度", "items": [item.to_dict() for item in self._hot_recommendations(user_id, top_k)]},
            {"name": "no_diversity", "label": "去掉多样性过滤", "items": [item.to_dict() for item in self._without_diversity(user_id, top_k)]},
            {"name": "no_feedback", "label": "去掉反馈增强", "items": [item.to_dict() for item in self.recommend_by_strategy("vector", user_id, top_k)]},
            {"name": "no_rag", "label": "去掉本地资料库 RAG 特征", "items": [item.to_dict() for item in self.ltr_service.recommend(user_id, top_k)]},
        ]
        result = {
            "user_id": user_id,
            "top_k": top_k,
            "variants": [variant | {"metrics": list_metrics(variant["items"], self.articles)} for variant in variants],
        }
        self.database.record_experiment(
            name="ablation",
            strategy="hybrid_ltr_rag",
            parameters={"user_id": user_id, "top_k": top_k},
            metrics=result,
            sample_count=len(full),
        )
        return result

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
        totals = {
            "hit_rate": 0.0,
            "mrr": 0.0,
            "ndcg": 0.0,
            "auc": 0.0,
            "catalog_coverage": 0.0,
            "category_coverage": 0.0,
            "diversity": 0.0,
            "novelty": 0.0,
            "calibration": 0.0,
        }
        users = 0
        for behavior in self.behaviors:
            relevant = {impression.news_id for impression in behavior.impressions if impression.clicked}
            if not relevant:
                continue
            recommended_items = self.recommend_by_strategy(strategy, behavior.user_id, top_k=k)
            recommended = [item.news_id for item in recommended_items]
            totals["hit_rate"] += hit_rate_at_k(recommended, relevant, k)
            totals["mrr"] += mrr_at_k(recommended, relevant, k)
            totals["ndcg"] += ndcg_at_k(recommended, relevant, k)
            totals["auc"] += auc_from_ranking(recommended, relevant)
            metrics = list_metrics([item.to_dict() for item in recommended_items], self.articles)
            for key in ["catalog_coverage", "category_coverage", "diversity", "novelty"]:
                totals[key] += metrics[key]
            totals["calibration"] += calibration_score(
                self.profile_service.build_profile(behavior.user_id).preferred_categories,
                recommended,
                self.articles,
            )
            users += 1
            if users >= self.max_eval_users:
                break
        if users == 0:
            return StrategyEvaluation(strategy, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0)
        return StrategyEvaluation(
            strategy=strategy,
            hit_rate=totals["hit_rate"] / users,
            mrr=totals["mrr"] / users,
            ndcg=totals["ndcg"] / users,
            auc=totals["auc"] / users,
            catalog_coverage=totals["catalog_coverage"] / users,
            category_coverage=totals["category_coverage"] / users,
            diversity=totals["diversity"] / users,
            novelty=totals["novelty"] / users,
            calibration=totals["calibration"] / users,
            users=users,
        )

    def _hot_recommendations(self, user_id: str, top_k: int) -> list[Recommendation]:
        profile = self.profile_service.build_profile(user_id)
        return [self.recommender._to_recommendation(hit, profile) for hit in self._hot_hits(top_k, set(profile.recent_clicked_news))]

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
        reranked = self.ltr_service.rerank_hits(user_id, self.recommender._deduplicate(hits), hybrid_rag=True)
        return [self.ltr_service._to_ltr_recommendation(hit, profile, hybrid_rag=True) for hit in reranked[:top_k]]


def category_distribution(items: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(item.get("category", "unknown") for item in items))


def list_metrics(items: list[dict[str, Any]], articles: dict[str, Article]) -> dict[str, float]:
    if not items:
        return {"catalog_coverage": 0.0, "category_coverage": 0.0, "diversity": 0.0, "novelty": 0.0}
    ids = [item["news_id"] for item in items if item.get("news_id") in articles]
    categories = [articles[news_id].category for news_id in ids]
    all_categories = {article.category for article in articles.values()}
    return {
        "catalog_coverage": round(len(set(ids)) / max(len(articles), 1), 4),
        "category_coverage": round(len(set(categories)) / max(len(all_categories), 1), 4),
        "diversity": round(intra_list_diversity(categories), 4),
        "novelty": round(sum(novelty(articles[news_id]) for news_id in ids) / max(len(ids), 1), 4),
    }


def intra_list_diversity(categories: list[str]) -> float:
    if len(categories) <= 1:
        return 0.0
    total_pairs = len(categories) * (len(categories) - 1) / 2
    different_pairs = 0
    for left_index, left in enumerate(categories):
        for right in categories[left_index + 1 :]:
            if left != right:
                different_pairs += 1
    return different_pairs / total_pairs


def novelty(article: Article) -> float:
    return 1.0 / math.log2(max(article.popularity, 1) + 2)


def calibration_score(preferred_categories: list[str], recommended_ids: list[str], articles: dict[str, Article]) -> float:
    if not preferred_categories or not recommended_ids:
        return 0.0
    preferred = Counter(preferred_categories)
    recommended = Counter(articles[news_id].category for news_id in recommended_ids if news_id in articles)
    categories = set(preferred) | set(recommended)
    total_preferred = sum(preferred.values()) or 1
    total_recommended = sum(recommended.values()) or 1
    distance = sum(abs(preferred[category] / total_preferred - recommended[category] / total_recommended) for category in categories)
    return max(0.0, 1.0 - distance / 2)


def auc_from_ranking(recommended_ids: list[str], relevant_ids: set[str]) -> float:
    positives = [index for index, news_id in enumerate(recommended_ids) if news_id in relevant_ids]
    negatives = [index for index, news_id in enumerate(recommended_ids) if news_id not in relevant_ids]
    if not positives or not negatives:
        return 0.5
    wins = 0.0
    for positive in positives:
        for negative in negatives:
            if positive < negative:
                wins += 1.0
            elif positive == negative:
                wins += 0.5
    return wins / (len(positives) * len(negatives))
