from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models import Article, Feedback
from app.services.database import Database
from app.services.llm_service import LLMService
from app.services.rag_service import RAGService
from app.services.recommender import NewsRecommender


@dataclass
class ArticleService:
    articles: dict[str, Article]
    database: Database
    recommender: NewsRecommender
    llm_service: LLMService
    rag_service: RAGService | None = None

    def detail_for_user(self, user_id: str, news_id: str) -> dict[str, Any]:
        article = self._get_article(news_id)
        profile = self.recommender.profile_service.build_profile(user_id)
        recommendation = self.recommender.explain(user_id, news_id)
        ai_explanation = self.llm_service.explain_recommendation(article, profile, recommendation.reason)
        return {
            "article": article.to_dict(),
            "favorite": self.database.is_favorite(user_id, news_id),
            "reason": ai_explanation["explanation"],
            "rule_reason": recommendation.reason,
            "evidence": recommendation.evidence,
            "related": [item.to_dict() for item in self.related_articles(user_id, article)],
            "event_cluster": self._event_cluster(article),
            "has_original_url": bool(article.url),
        }

    def related_articles(self, user_id: str, article: Article, limit: int = 4):
        results = self.recommender.search(
            query=f"{article.category} {article.subcategory} {article.title}",
            top_k=limit + 3,
            filters={"category": article.category},
        )
        return [item for item in results if item.news_id != article.news_id][:limit]

    def record_view(self, user_id: str, news_id: str) -> dict[str, str]:
        self._get_article(news_id)
        self.database.record_view(user_id, news_id)
        return {"message": "浏览记录已保存", "news_id": news_id}

    def set_favorite(self, user_id: str, news_id: str, favorite: bool | None = None) -> dict[str, Any]:
        self._get_article(news_id)
        current = self.database.toggle_favorite(user_id, news_id) if favorite is None else self.database.set_favorite(user_id, news_id, favorite)
        if current:
            article = self.articles[news_id]
            self.recommender.apply_feedback(
                Feedback(user_id=user_id, news_id=news_id, feedback_type="like", category=article.category)
            )
        return {"news_id": news_id, "favorite": current}

    def favorites_for_user(self, user_id: str) -> list[dict[str, Any]]:
        rows = self.database.list_favorites(user_id)
        return [self._article_with_meta(row["news_id"], {"favorited_at": row["favorited_at"]}) for row in rows if row["news_id"] in self.articles]

    def history_for_user(self, user_id: str) -> list[dict[str, Any]]:
        rows = self.database.list_history(user_id)
        return [
            self._article_with_meta(row["news_id"], {"viewed_at": row["viewed_at"], "view_count": row["view_count"]})
            for row in rows
            if row["news_id"] in self.articles
        ]

    def summarize(self, news_id: str) -> dict[str, Any]:
        return self.llm_service.summarize_article(self._get_article(news_id))

    def ask(self, news_id: str, question: str) -> dict[str, str]:
        if not question.strip():
            return {"answer": "请输入一个和新闻内容相关的问题。"}
        return self.llm_service.answer_article_question(self._get_article(news_id), question.strip())

    def grounded_analysis(self, user_id: str, news_id: str) -> dict[str, Any]:
        if self.rag_service is None:
            return {
                "answer": "本地资料库服务尚未启用。",
                "citations": [],
                "confidence": 0.0,
                "missing_evidence": True,
            }
        return self.rag_service.analyze_article(user_id, self._get_article(news_id))

    def _event_cluster(self, article: Article) -> list[dict[str, Any]]:
        related = self.recommender.search(article.title, top_k=6, filters={"category": article.category})
        return [item.to_dict() for item in related if item.news_id != article.news_id][:5]

    def _article_with_meta(self, news_id: str, meta: dict[str, Any]) -> dict[str, Any]:
        payload = self.articles[news_id].to_dict()
        payload.update(meta)
        return payload

    def _get_article(self, news_id: str) -> Article:
        article = self.articles.get(news_id)
        if not article:
            raise KeyError(news_id)
        return article
