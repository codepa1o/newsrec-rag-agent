from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.core.text import top_keywords
from app.models import Article
from app.services.database import Database
from app.services.llm_service import LLMService
from app.services.profile import ProfileService
from app.services.recommender import NewsRecommender


@dataclass
class NewsIntelligenceService:
    articles: dict[str, Article]
    database: Database
    profile_service: ProfileService
    recommender: NewsRecommender
    llm_service: LLMService

    def metrics_overview(self) -> dict[str, Any]:
        documents = self.database.list_document_chunks()
        categories = Counter(article.category for article in self.articles.values())
        with self.database.connect() as connection:
            users = connection.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
            feedback = connection.execute("SELECT COUNT(*) AS count FROM feedback_events").fetchone()["count"]
            views = connection.execute("SELECT COUNT(*) AS count FROM article_views").fetchone()["count"]
            favorites = connection.execute("SELECT COUNT(*) AS count FROM favorites").fetchone()["count"]
            rag_queries = connection.execute("SELECT COUNT(*) AS count FROM rag_queries").fetchone()["count"]
            documents_count = connection.execute("SELECT COUNT(*) AS count FROM documents").fetchone()["count"]
        return {
            "articles": len(self.articles),
            "users": users,
            "behaviors_tracked": views,
            "feedback_events": feedback,
            "favorites": favorites,
            "documents": documents_count,
            "document_chunks": len(documents),
            "rag_queries": rag_queries,
            "top_categories": categories.most_common(10),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def interest_drift(self, user_id: str) -> dict[str, Any]:
        profile = self.profile_service.build_profile(user_id)
        long_texts: list[str] = []
        recent_texts: list[str] = []
        history = self.database.list_history(user_id, limit=50)

        for behavior in self.profile_service.behaviors:
            if behavior.user_id != user_id:
                continue
            for news_id in behavior.history:
                article = self.articles.get(news_id)
                if article:
                    long_texts.append(article.text)

        for item in history[:20]:
            article = self.articles.get(item["news_id"])
            if article:
                recent_texts.append(article.text)

        long_keywords = top_keywords(long_texts, limit=12)
        recent_keywords = top_keywords(recent_texts, limit=12)
        shared = sorted(set(long_keywords) & set(recent_keywords))
        emerging = [keyword for keyword in recent_keywords if keyword not in long_keywords]
        fading = [keyword for keyword in long_keywords if keyword not in recent_keywords]
        return {
            "user_id": user_id,
            "preferred_categories": profile.preferred_categories,
            "long_term_keywords": long_keywords,
            "recent_keywords": recent_keywords,
            "shared_keywords": shared,
            "emerging_keywords": emerging,
            "fading_keywords": fading,
            "summary": build_drift_summary(long_keywords, recent_keywords, emerging, fading),
        }

    def event_cluster(self, news_id: str, top_k: int = 8) -> dict[str, Any]:
        article = self.articles.get(news_id)
        if not article:
            raise KeyError(news_id)
        query = f"{article.title} {article.abstract}"
        related = self.recommender.search(query, top_k=top_k + 5, filters={"category": article.category})
        items = [item.to_dict() for item in related if item.news_id != news_id][:top_k]
        keywords = top_keywords([article.title, article.abstract] + [item["title"] for item in items], limit=10)
        return {
            "article": article.to_dict(),
            "event_keywords": keywords,
            "items": items,
            "summary": f"该事件聚类围绕 {', '.join(keywords[:5]) or article.category} 展开，包含 {len(items)} 篇同类相关新闻。",
        }

    def daily_briefing(self, user_id: str, top_k: int = 8) -> dict[str, Any]:
        recommendations = [item.to_dict() for item in self.recommender.recommend(user_id, top_k=top_k)]
        profile = self.profile_service.build_profile(user_id)
        briefing = self._generate_briefing_text(profile.to_dict(), recommendations)
        return {
            "user_id": user_id,
            "title": "今日个性化新闻简报",
            "briefing": briefing,
            "items": recommendations,
            "profile_keywords": profile.keywords[:10],
        }

    def compare_viewpoints(self, news_id: str, top_k: int = 5) -> dict[str, Any]:
        cluster = self.event_cluster(news_id, top_k=top_k)
        items = cluster["items"]
        categories = Counter(item["category"] for item in items)
        viewpoints = [
            {
                "news_id": item["news_id"],
                "title": item["title"],
                "angle": infer_angle(item),
                "category": item["category"],
            }
            for item in items
        ]
        return {
            "article": cluster["article"],
            "viewpoints": viewpoints,
            "category_distribution": dict(categories),
            "summary": f"共找到 {len(viewpoints)} 篇同事件相关新闻，可从 {', '.join(categories.keys()) or '相同类别'} 等角度比较报道差异。",
        }

    def _generate_briefing_text(self, profile: dict[str, Any], recommendations: list[dict[str, Any]]) -> str:
        prompt = (
            "请生成一份中文个性化新闻日报，包含今日重点、推荐理由和阅读建议。"
            f"\n用户画像：{json.dumps(profile, ensure_ascii=False)}"
            f"\n推荐新闻：{json.dumps(recommendations[:5], ensure_ascii=False)}"
        )
        answer = self.llm_service._chat(prompt)
        if answer:
            return answer
        lines = ["今天为你挑选了以下新闻："]
        for index, item in enumerate(recommendations[:5], start=1):
            lines.append(f"{index}. {item['title']}：{item.get('reason') or '与近期兴趣相关'}")
        lines.append("建议优先阅读分数较高且类别不同的新闻，以兼顾兴趣和信息多样性。")
        return "\n".join(lines)


def build_drift_summary(
    long_keywords: list[str],
    recent_keywords: list[str],
    emerging: list[str],
    fading: list[str],
) -> str:
    if not long_keywords and not recent_keywords:
        return "该用户历史行为较少，暂时无法判断兴趣漂移。"
    if emerging:
        return f"近期兴趣出现新主题：{', '.join(emerging[:5])}；建议提高这些主题的探索权重。"
    return "近期兴趣与长期兴趣较稳定，可以继续沿用当前画像，同时保留少量探索推荐。"


def infer_angle(item: dict[str, Any]) -> str:
    text = f"{item.get('title', '')} {item.get('abstract', '')}".lower()
    if any(token in text for token in ("policy", "regulation", "law", "监管", "政策")):
        return "政策与监管角度"
    if any(token in text for token in ("market", "stock", "price", "finance", "市场")):
        return "市场与商业角度"
    if any(token in text for token in ("health", "study", "research", "研究")):
        return "研究与数据角度"
    if any(token in text for token in ("ai", "tech", "technology", "model", "系统")):
        return "技术发展角度"
    return "综合新闻角度"
