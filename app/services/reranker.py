from __future__ import annotations

from dataclasses import dataclass

from app.models import Article, UserProfile
from app.services.vector_store import SearchHit


@dataclass
class HeuristicReranker:
    category_weight: float = 0.18
    popularity_weight: float = 0.08
    keyword_weight: float = 0.12

    def rerank(self, hits: list[SearchHit], profile: UserProfile) -> list[SearchHit]:
        scored: list[SearchHit] = []
        max_popularity = max((hit.article.popularity for hit in hits), default=1) or 1
        for hit in hits:
            article = hit.article
            score = hit.score
            if article.category in profile.preferred_categories:
                score += self.category_weight
            score += (article.popularity / max_popularity) * self.popularity_weight
            score += self._keyword_overlap(article, profile) * self.keyword_weight
            scored.append(SearchHit(article=article, score=score))
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored

    def _keyword_overlap(self, article: Article, profile: UserProfile) -> float:
        if not profile.keywords:
            return 0.0
        text = article.text.lower()
        matches = sum(1 for keyword in profile.keywords if keyword.lower() in text)
        return matches / max(len(profile.keywords), 1)


class DashScopeReranker:
    """Optional online reranker. Falls back to heuristic in the recommender if unavailable."""

    def __init__(self, api_key: str, model: str = "qwen3-rerank") -> None:
        self.api_key = api_key
        self.model = model

    def rerank(self, query: str, hits: list[SearchHit]) -> list[SearchHit]:
        if not self.api_key:
            raise RuntimeError("DASHSCOPE_API_KEY is required for DashScope reranking.")
        try:
            import dashscope
        except ImportError as exc:  # pragma: no cover - optional online provider
            raise RuntimeError("Install dashscope to use DashScope reranking.") from exc

        dashscope.api_key = self.api_key
        documents = [hit.article.text for hit in hits]
        response = dashscope.TextReRank.call(model=self.model, query=query, documents=documents, top_n=len(documents))
        if response.status_code != 200:
            raise RuntimeError(f"DashScope rerank failed: {response.message}")

        reranked: list[SearchHit] = []
        for item in response.output["results"]:
            index = int(item["index"])
            reranked.append(SearchHit(article=hits[index].article, score=float(item["relevance_score"])))
        return reranked
