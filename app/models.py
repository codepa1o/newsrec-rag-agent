from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


FeedbackType = Literal["like", "dislike", "block_category"]


@dataclass(frozen=True)
class Article:
    news_id: str
    category: str
    subcategory: str
    title: str
    abstract: str = ""
    url: str = ""
    title_entities: str = ""
    abstract_entities: str = ""
    publish_time: str = ""
    popularity: int = 0

    @property
    def text(self) -> str:
        return " ".join(part for part in [self.title, self.abstract, self.category, self.subcategory] if part)

    def to_dict(self) -> dict[str, Any]:
        return {
            "news_id": self.news_id,
            "category": self.category,
            "subcategory": self.subcategory,
            "title": self.title,
            "abstract": self.abstract,
            "url": self.url,
            "title_entities": self.title_entities,
            "abstract_entities": self.abstract_entities,
            "publish_time": self.publish_time,
            "popularity": self.popularity,
        }


@dataclass(frozen=True)
class Impression:
    news_id: str
    clicked: bool


@dataclass(frozen=True)
class Behavior:
    impression_id: str
    user_id: str
    time: str
    history: tuple[str, ...] = ()
    impressions: tuple[Impression, ...] = ()


@dataclass
class UserProfile:
    user_id: str
    preferred_categories: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    recent_clicked_news: list[str] = field(default_factory=list)
    blocked_categories: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "preferred_categories": self.preferred_categories,
            "keywords": self.keywords,
            "recent_clicked_news": self.recent_clicked_news,
            "blocked_categories": self.blocked_categories,
        }


@dataclass
class Recommendation:
    news_id: str
    title: str
    category: str
    abstract: str
    score: float
    reason: str
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "news_id": self.news_id,
            "title": self.title,
            "category": self.category,
            "abstract": self.abstract,
            "score": round(self.score, 4),
            "reason": self.reason,
            "evidence": self.evidence,
        }


@dataclass
class Feedback:
    user_id: str
    news_id: str
    feedback_type: FeedbackType
    category: str | None = None
