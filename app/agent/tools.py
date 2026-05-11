from __future__ import annotations

from app.dependencies import get_container
from app.models import Feedback

try:
    from langchain_core.tools import tool
except ImportError:  # pragma: no cover - optional dependency
    def tool(func):
        return func


@tool
def get_user_profile(user_id: str) -> dict:
    """获取用户的新闻兴趣画像。"""
    return get_container().recommender.get_profile(user_id)


@tool
def search_news(query: str, top_k: int = 5, category: str | None = None) -> list[dict]:
    """按查询词搜索新闻，可选择按类别过滤。"""
    filters = {"category": category} if category else None
    return [item.to_dict() for item in get_container().recommender.search(query, top_k=top_k, filters=filters)]


@tool
def recommend_news(user_id: str, top_k: int = 10) -> list[dict]:
    """为指定用户生成个性化新闻推荐。"""
    return [item.to_dict() for item in get_container().recommender.recommend(user_id, top_k=top_k)]


@tool
def explain_recommendation(user_id: str, news_id: str) -> dict:
    """解释为什么向用户推荐某篇新闻。"""
    return get_container().recommender.explain(user_id, news_id).to_dict()


@tool
def record_feedback(user_id: str, news_id: str, feedback_type: str) -> dict:
    """记录用户反馈：喜欢、不感兴趣或屏蔽类别。"""
    container = get_container()
    article = container.store.articles[news_id]
    feedback = Feedback(user_id=user_id, news_id=news_id, feedback_type=feedback_type, category=article.category)
    container.record_feedback(feedback)
    return {"status": "recorded", "user_id": user_id, "news_id": news_id, "feedback_type": feedback_type}


@tool
def evaluate_recommender(split_name: str = "sample", k: int = 10) -> dict:
    """在已加载的行为数据上运行离线推荐指标。"""
    result = get_container().evaluator.evaluate(k=k)
    payload = result.to_dict()
    payload["split_name"] = split_name
    payload["k"] = k
    return payload
