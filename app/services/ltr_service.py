from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.text import tokenize
from app.models import Article, Behavior, Recommendation, UserProfile
from app.services.database import Database
from app.services.embedding import cosine_similarity
from app.services.profile import ProfileService
from app.services.recommender import NewsRecommender
from app.services.vector_store import SearchHit


FEATURE_NAMES = [
    "category_match",
    "keyword_overlap",
    "semantic_similarity",
    "popularity",
    "freshness",
    "recent_interest",
    "feedback_weight",
    "document_topic_match",
]


@dataclass
class TrainingSample:
    user_id: str
    news_id: str
    label: int
    features: list[float]


@dataclass
class LinearLTRModel:
    weights: list[float]
    bias: float

    def predict_proba(self, features: list[float]) -> float:
        logit = self.bias + sum(weight * value for weight, value in zip(self.weights, features))
        if logit >= 0:
            z = math.exp(-logit)
            return 1.0 / (1.0 + z)
        z = math.exp(logit)
        return z / (1.0 + z)

    def to_dict(self) -> dict[str, Any]:
        return {"weights": self.weights, "bias": self.bias, "feature_names": FEATURE_NAMES}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "LinearLTRModel":
        return cls(weights=[float(value) for value in payload["weights"]], bias=float(payload.get("bias", 0.0)))


class LearningToRankService:
    def __init__(
        self,
        articles: dict[str, Article],
        behaviors: list[Behavior],
        database: Database,
        profile_service: ProfileService,
        recommender: NewsRecommender,
        model_path: Path,
        max_train_users: int = 400,
    ) -> None:
        self.articles = articles
        self.behaviors = behaviors
        self.database = database
        self.profile_service = profile_service
        self.recommender = recommender
        self.model_path = model_path
        self.max_train_users = max_train_users
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        self.model: LinearLTRModel | None = self._load_model()
        self.metadata: dict[str, Any] = self._load_metadata()

    def train(self, max_users: int | None = None, epochs: int = 90, learning_rate: float = 0.08) -> dict[str, Any]:
        samples = self.build_training_samples(max_users=max_users or self.max_train_users)
        if not samples:
            self.model = self._default_model()
            self.metadata = {
                "trained": True,
                "status": "fallback",
                "sample_count": 0,
                "positive_count": 0,
                "negative_count": 0,
                "trained_at": utc_now(),
                "message": "训练样本不足，已启用默认权重模型。",
            }
            self._save_model()
            return self.status()

        weights = [0.0] * len(FEATURE_NAMES)
        bias = 0.0
        for _ in range(max(epochs, 1)):
            for sample in samples:
                score = bias + sum(weight * value for weight, value in zip(weights, sample.features))
                prediction = sigmoid(score)
                error = float(sample.label) - prediction
                for index, value in enumerate(sample.features):
                    weights[index] += learning_rate * error * value
                bias += learning_rate * error

        self.model = LinearLTRModel(weights=weights, bias=bias)
        positives = sum(sample.label for sample in samples)
        self.metadata = {
            "trained": True,
            "status": "trained",
            "model_type": "pure_python_logistic_ltr",
            "sample_count": len(samples),
            "positive_count": positives,
            "negative_count": len(samples) - positives,
            "feature_names": FEATURE_NAMES,
            "trained_at": utc_now(),
            "model_path": str(self.model_path),
        }
        self._save_model()
        return self.status()

    def status(self) -> dict[str, Any]:
        loaded = self.model is not None
        return {
            "trained": bool(self.metadata.get("trained") or loaded),
            "loaded": loaded,
            "model_path": str(self.model_path),
            "feature_names": FEATURE_NAMES,
            **self.metadata,
        }

    def recommend(self, user_id: str, top_k: int = 20, hybrid_rag: bool = False) -> list[Recommendation]:
        profile = self.profile_service.build_profile(user_id)
        exclude_ids = set(profile.recent_clicked_news)
        query = self.recommender._profile_query(profile)
        hits = self.recommender.vector_store.search(query, top_k=max(top_k * 6, 30), exclude_ids=exclude_ids)
        hits.extend(self.recommender._category_recall(profile, exclude_ids))
        hits.extend(self.recommender._hot_recall(profile, exclude_ids))
        hits = [hit for hit in self.recommender._deduplicate(hits) if hit.article.category not in profile.blocked_categories]
        reranked = self.rerank_hits(user_id, hits, hybrid_rag=hybrid_rag)
        diversified = self.recommender._diversity_filter(reranked, top_k)
        return [self._to_ltr_recommendation(hit, profile, hybrid_rag=hybrid_rag) for hit in diversified]

    def rerank_hits(self, user_id: str, hits: list[SearchHit], hybrid_rag: bool = False) -> list[SearchHit]:
        model = self.model or self._default_model()
        scored: list[SearchHit] = []
        for hit in hits:
            features = self.extract_features(user_id, hit.article, base_score=hit.score, hybrid_rag=hybrid_rag)
            score = model.predict_proba(features)
            scored.append(SearchHit(article=hit.article, score=score))
        scored.sort(key=lambda hit: hit.score, reverse=True)
        return scored

    def explain(self, user_id: str, news_id: str, hybrid_rag: bool = True) -> dict[str, Any]:
        article = self.articles.get(news_id)
        if not article:
            raise KeyError(news_id)
        model = self.model or self._default_model()
        features = self.extract_features(user_id, article, hybrid_rag=hybrid_rag)
        contributions = [
            {
                "feature": name,
                "value": round(value, 4),
                "weight": round(weight, 4),
                "contribution": round(value * weight, 4),
            }
            for name, value, weight in zip(FEATURE_NAMES, features, model.weights)
        ]
        contributions.sort(key=lambda item: abs(item["contribution"]), reverse=True)
        score = model.predict_proba(features)
        return {
            "user_id": user_id,
            "news_id": news_id,
            "title": article.title,
            "score": round(score, 4),
            "model_status": self.status(),
            "features": dict(zip(FEATURE_NAMES, [round(value, 4) for value in features])),
            "contributions": contributions,
            "summary": build_explanation_summary(contributions, score),
        }

    def build_training_samples(self, max_users: int = 400) -> list[TrainingSample]:
        samples: list[TrainingSample] = []
        users = 0
        for behavior in self.behaviors:
            impressions = [item for item in behavior.impressions if item.news_id in self.articles]
            if not impressions:
                continue
            users += 1
            for impression in impressions:
                article = self.articles[impression.news_id]
                samples.append(
                    TrainingSample(
                        user_id=behavior.user_id,
                        news_id=impression.news_id,
                        label=1 if impression.clicked else 0,
                        features=self.extract_features(
                            behavior.user_id,
                            article,
                            profile=self.profile_service.build_profile(behavior.user_id),
                        ),
                    )
                )
            if users >= max_users:
                break
        return balance_samples(samples)

    def extract_features(
        self,
        user_id: str,
        article: Article,
        base_score: float | None = None,
        profile: UserProfile | None = None,
        hybrid_rag: bool = False,
    ) -> list[float]:
        profile = profile or self.profile_service.build_profile(user_id)
        article_tokens = set(tokenize(article.text))
        profile_tokens = set(tokenize(" ".join(profile.keywords + profile.preferred_categories)))
        category_match = 1.0 if article.category in profile.preferred_categories else 0.0
        keyword_overlap = jaccard(article_tokens, profile_tokens)
        semantic_similarity = base_score if base_score is not None else cosine_similarity(
            self.recommender.vector_store.embedding_provider.embed(self.recommender._profile_query(profile)),
            self.recommender.vector_store.embedding_provider.embed(article.text),
        )
        popularity = min(max(article.popularity, 0), 100) / 100.0
        freshness = estimate_freshness(article.publish_time)
        recent_interest = 1.0 if article.news_id in profile.recent_clicked_news[-5:] else 0.0
        feedback_weight = self._feedback_weight(user_id, article)
        document_topic_match = self._document_topic_match(user_id, article) if hybrid_rag else 0.0
        return [
            clamp(category_match),
            clamp(keyword_overlap),
            clamp(semantic_similarity),
            clamp(popularity),
            clamp(freshness),
            clamp(recent_interest),
            clamp(feedback_weight),
            clamp(document_topic_match),
        ]

    def _feedback_weight(self, user_id: str, article: Article) -> float:
        value = 0.0
        for feedback in self.profile_service.feedback:
            if feedback.user_id != user_id:
                continue
            if feedback.news_id == article.news_id and feedback.feedback_type == "like":
                value += 0.6
            if feedback.category == article.category and feedback.feedback_type == "like":
                value += 0.2
            if feedback.category == article.category and feedback.feedback_type == "block_category":
                value -= 0.8
        if self.database.is_favorite(user_id, article.news_id):
            value += 0.6
        return (value + 1.0) / 2.0

    def _document_topic_match(self, user_id: str, article: Article) -> float:
        chunks = self.database.list_document_chunks(user_id=user_id)
        if not chunks:
            return 0.0
        article_tokens = set(tokenize(article.text))
        best = 0.0
        for chunk in chunks[:80]:
            best = max(best, jaccard(article_tokens, set(tokenize(chunk["text"][:600]))))
        return best

    def _to_ltr_recommendation(self, hit: SearchHit, profile: UserProfile, hybrid_rag: bool = False) -> Recommendation:
        article = hit.article
        explanation = self.explain(profile.user_id, article.news_id, hybrid_rag=hybrid_rag)
        top_features = [item["feature"] for item in explanation["contributions"][:3] if item["contribution"] > 0]
        reason = "LTR 学习排序模型预测该新闻点击概率较高"
        if top_features:
            reason += "，主要贡献特征：" + "、".join(top_features)
        return Recommendation(
            news_id=article.news_id,
            title=article.title,
            category=article.category,
            abstract=article.abstract,
            score=hit.score,
            reason=reason,
            evidence=[f"{item['feature']}={item['value']}" for item in explanation["contributions"][:3]],
        )

    def _load_model(self) -> LinearLTRModel | None:
        if not self.model_path.exists():
            return None
        try:
            payload = json.loads(self.model_path.read_text(encoding="utf-8"))
            return LinearLTRModel.from_dict(payload["model"])
        except (OSError, KeyError, ValueError, TypeError, json.JSONDecodeError):
            return None

    def _load_metadata(self) -> dict[str, Any]:
        if not self.model_path.exists():
            return {"trained": False, "status": "not_trained"}
        try:
            payload = json.loads(self.model_path.read_text(encoding="utf-8"))
            return payload.get("metadata", {})
        except (OSError, json.JSONDecodeError):
            return {"trained": False, "status": "load_failed", "message": "模型文件损坏，已回退到默认权重。"}

    def _save_model(self) -> None:
        if self.model is None:
            return
        payload = {"model": self.model.to_dict(), "metadata": self.metadata}
        self.model_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _default_model(self) -> LinearLTRModel:
        return LinearLTRModel(weights=[0.9, 1.1, 1.2, 0.45, 0.25, 0.35, 0.75, 0.65], bias=-0.55)


def balance_samples(samples: list[TrainingSample]) -> list[TrainingSample]:
    positives = [sample for sample in samples if sample.label == 1]
    negatives = [sample for sample in samples if sample.label == 0]
    if not positives or not negatives:
        return samples
    negatives = negatives[: max(len(positives) * 4, 20)]
    return positives + negatives


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def estimate_freshness(publish_time: str) -> float:
    if not publish_time:
        return 0.5
    digits = "".join(char for char in publish_time if char.isdigit())
    if len(digits) >= 8:
        try:
            year = int(digits[:4])
            month = int(digits[4:6])
            day = int(digits[6:8])
            published = datetime(year, month, day, tzinfo=timezone.utc)
            age_days = max((datetime.now(timezone.utc) - published).days, 0)
            return math.exp(-age_days / 90)
        except ValueError:
            return 0.5
    return 0.5


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_explanation_summary(contributions: list[dict[str, Any]], score: float) -> str:
    positive = [item for item in contributions if item["contribution"] > 0]
    if not positive:
        return f"模型预测点击概率为 {score:.2f}，当前主要依赖默认排序信号。"
    top = "、".join(item["feature"] for item in positive[:3])
    return f"模型预测点击概率为 {score:.2f}，排序主要受 {top} 影响。"


def category_distribution_from_ids(article_ids: list[str], articles: dict[str, Article]) -> Counter[str]:
    return Counter(articles[news_id].category for news_id in article_ids if news_id in articles)
