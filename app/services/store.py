from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from collections import Counter

from app.config import Settings
from app.core.mind import load_behaviors, load_news
from app.core.sample_data import sample_articles, sample_behaviors
from app.models import Article, Behavior, Feedback
from app.services.database import Database


class NewsDataStore:
    def __init__(self, settings: Settings, database: Database | None = None) -> None:
        self.settings = settings
        self.database = database
        self.articles = self._load_articles()
        self.behaviors = self._load_behaviors()
        self._apply_behavior_popularity()
        self.feedback = self._load_feedback()

    def add_feedback(self, feedback: Feedback) -> None:
        self.feedback.append(feedback)
        if self.database:
            self.database.add_feedback(feedback)
        else:
            self._save_feedback()

    def _load_articles(self) -> dict[str, Article]:
        if self.settings.mind_news_path.exists():
            articles = load_news(self.settings.mind_news_path)
            for news_id, article in sample_articles().items():
                articles.setdefault(news_id, article)
            return articles
        return sample_articles()

    def _load_behaviors(self) -> list[Behavior]:
        if self.settings.mind_behaviors_path.exists():
            return load_behaviors(self.settings.mind_behaviors_path)
        return sample_behaviors()

    def _load_feedback(self) -> list[Feedback]:
        if self.database:
            database_feedback = self.database.load_feedback()
            if database_feedback:
                return database_feedback

        path = self._feedback_path()
        if not path.exists():
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [Feedback(**item) for item in raw]

    def _save_feedback(self) -> None:
        path = self._feedback_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            {
                "user_id": item.user_id,
                "news_id": item.news_id,
                "feedback_type": item.feedback_type,
                "category": item.category,
            }
            for item in self.feedback
        ]
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _feedback_path(self) -> Path:
        return self.settings.data_dir / "feedback.json"

    def _apply_behavior_popularity(self) -> None:
        counts: Counter[str] = Counter()
        for behavior in self.behaviors:
            counts.update(news_id for news_id in behavior.history if news_id)
            for impression in behavior.impressions:
                counts[impression.news_id] += 3 if impression.clicked else 1
        for news_id, popularity in counts.items():
            article = self.articles.get(news_id)
            if article:
                self.articles[news_id] = replace(article, popularity=popularity)
