from __future__ import annotations

from app.models import Article, UserProfile


class ExplanationService:
    def explain(self, article: Article, profile: UserProfile, score: float) -> tuple[str, list[str]]:
        signals: list[str] = []
        if article.category in profile.preferred_categories:
            signals.append(f"你近期经常阅读 {article.category} 类新闻")
        matched_keywords = [keyword for keyword in profile.keywords if keyword.lower() in article.text.lower()]
        if matched_keywords:
            signals.append(f"内容匹配关键词：{', '.join(matched_keywords[:4])}")
        if article.popularity > 0:
            signals.append(f"该新闻热度分为 {article.popularity}")

        reason = "；".join(signals[:3]) if signals else "该新闻与当前语义检索结果相关，适合作为探索推荐。"
        evidence = [article.title]
        if article.abstract:
            evidence.append(article.abstract)
        return reason, evidence
