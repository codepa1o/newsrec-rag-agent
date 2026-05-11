from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from app.core.text import top_keywords
from app.models import Article, Behavior, Feedback, UserProfile

if TYPE_CHECKING:
    from app.services.database import Database


class ProfileService:
    def __init__(
        self,
        articles: dict[str, Article],
        behaviors: list[Behavior],
        feedback: list[Feedback] | None = None,
        database: "Database | None" = None,
    ) -> None:
        self.articles = articles
        self.behaviors = behaviors
        self.feedback = feedback or []
        self.database = database

    def build_profile(self, user_id: str) -> UserProfile:
        clicked_news = self._clicked_news(user_id)
        category_counts: Counter[str] = Counter()
        clicked_texts: list[str] = []

        for news_id in clicked_news:
            article = self.articles.get(news_id)
            if not article:
                continue
            category_counts[article.category] += 1
            clicked_texts.append(article.text)

        blocked_categories = [
            item.category
            for item in self.feedback
            if item.user_id == user_id and item.feedback_type == "block_category" and item.category
        ]

        liked_news = [item.news_id for item in self.feedback if item.user_id == user_id and item.feedback_type == "like"]
        for news_id in liked_news:
            article = self.articles.get(news_id)
            if article:
                category_counts[article.category] += 2
                clicked_texts.append(article.text)

        if self.database:
            for item in self.database.list_favorites(user_id, limit=50):
                article = self.articles.get(item["news_id"])
                if article:
                    category_counts[article.category] += 2
                    clicked_texts.append(article.text)

            for item in self.database.list_history(user_id, limit=50):
                article = self.articles.get(item["news_id"])
                if article:
                    category_counts[article.category] += 1
                    clicked_texts.append(article.text)
                    if article.news_id not in clicked_news:
                        clicked_news.append(article.news_id)

        return UserProfile(
            user_id=user_id,
            preferred_categories=[category for category, _ in category_counts.most_common(5)],
            keywords=top_keywords(clicked_texts, limit=12),
            recent_clicked_news=clicked_news[-20:],
            blocked_categories=sorted(set(blocked_categories)),
        )

    def _clicked_news(self, user_id: str) -> list[str]:
        clicked: list[str] = []
        for behavior in self.behaviors:
            if behavior.user_id != user_id:
                continue
            clicked.extend(news_id for news_id in behavior.history if news_id)
            clicked.extend(impression.news_id for impression in behavior.impressions if impression.clicked)
        return list(dict.fromkeys(clicked))
