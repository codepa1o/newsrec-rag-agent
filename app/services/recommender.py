from __future__ import annotations

from app.models import Article, Feedback, Recommendation
from app.services.embedding import EmbeddingProvider
from app.services.explainer import ExplanationService
from app.services.profile import ProfileService
from app.services.reranker import HeuristicReranker
from app.services.vector_store import LocalVectorStore, SearchHit


class NewsRecommender:
    def __init__(
        self,
        articles: dict[str, Article],
        profile_service: ProfileService,
        embedding_provider: EmbeddingProvider,
        retrieval_top_k: int = 40,
    ) -> None:
        self.articles = articles
        self.profile_service = profile_service
        self.vector_store = LocalVectorStore(embedding_provider=embedding_provider)
        self.vector_store.upsert(articles)
        self.reranker = HeuristicReranker()
        self.explainer = ExplanationService()
        self.retrieval_top_k = retrieval_top_k

    def recommend(self, user_id: str, top_k: int = 10) -> list[Recommendation]:
        profile = self.profile_service.build_profile(user_id)
        query = self._profile_query(profile)
        exclude_ids = set(profile.recent_clicked_news)
        hits = self.vector_store.search(query, top_k=self.retrieval_top_k, exclude_ids=exclude_ids)
        hits.extend(self._category_recall(profile, exclude_ids))
        hits.extend(self._hot_recall(profile, exclude_ids))
        hits = self._deduplicate(hits)
        hits = [hit for hit in hits if hit.article.category not in profile.blocked_categories]
        reranked = self.reranker.rerank(hits, profile)
        diversified = self._diversity_filter(reranked, top_k)
        return [self._to_recommendation(hit, profile) for hit in diversified]

    def get_profile(self, user_id: str) -> dict:
        return self.profile_service.build_profile(user_id).to_dict()

    def search(self, query: str, top_k: int = 10, filters: dict | None = None) -> list[Recommendation]:
        hits = self.vector_store.search(query, top_k=top_k, filters=filters)
        empty_profile = self.profile_service.build_profile("__anonymous__")
        return [self._to_recommendation(hit, empty_profile) for hit in hits]

    def explain(self, user_id: str, news_id: str) -> Recommendation:
        profile = self.profile_service.build_profile(user_id)
        article = self.articles[news_id]
        return self._to_recommendation(SearchHit(article=article, score=1.0), profile)

    def apply_feedback(self, feedback: Feedback) -> None:
        self.profile_service.feedback.append(feedback)

    def _profile_query(self, profile) -> str:
        if profile.keywords or profile.preferred_categories:
            return " ".join(profile.preferred_categories + profile.keywords)
        return "最新 个性化 新闻 科技 财经 健康 体育 国际"

    def _category_recall(self, profile, exclude_ids: set[str]) -> list[SearchHit]:
        hits: list[SearchHit] = []
        for article in self.articles.values():
            if article.news_id in exclude_ids:
                continue
            if article.category in profile.preferred_categories:
                hits.append(SearchHit(article=article, score=0.55))
        return hits

    def _hot_recall(self, profile, exclude_ids: set[str]) -> list[SearchHit]:
        candidates = [
            article
            for article in self.articles.values()
            if article.news_id not in exclude_ids and article.category not in profile.blocked_categories
        ]
        candidates.sort(key=lambda article: article.popularity, reverse=True)
        return [SearchHit(article=article, score=0.35) for article in candidates[:10]]

    def _deduplicate(self, hits: list[SearchHit]) -> list[SearchHit]:
        best: dict[str, SearchHit] = {}
        for hit in hits:
            current = best.get(hit.article.news_id)
            if current is None or hit.score > current.score:
                best[hit.article.news_id] = hit
        return list(best.values())

    def _diversity_filter(self, hits: list[SearchHit], top_k: int) -> list[SearchHit]:
        selected: list[SearchHit] = []
        category_counts: dict[str, int] = {}
        for hit in hits:
            count = category_counts.get(hit.article.category, 0)
            if count >= 3 and len(selected) < top_k - 1:
                continue
            selected.append(hit)
            category_counts[hit.article.category] = count + 1
            if len(selected) >= top_k:
                break
        return selected

    def _to_recommendation(self, hit: SearchHit, profile) -> Recommendation:
        reason, evidence = self.explainer.explain(hit.article, profile, hit.score)
        return Recommendation(
            news_id=hit.article.news_id,
            title=hit.article.title,
            category=hit.article.category,
            abstract=hit.article.abstract,
            score=hit.score,
            reason=reason,
            evidence=evidence,
        )
