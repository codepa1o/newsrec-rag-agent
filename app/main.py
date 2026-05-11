from __future__ import annotations

from typing import Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from app.dependencies import ServiceContainer, get_container
from app.models import Feedback
from app.services.database import UserRecord


security = HTTPBearer(auto_error=False)


class FeedbackRequest(BaseModel):
    user_id: str = ""
    news_id: str
    feedback_type: Literal["like", "dislike", "block_category"]
    category: str | None = None


class EvaluateRequest(BaseModel):
    k: int = Field(default=10, ge=1, le=50)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=8)
    display_name: str | None = Field(default=None, max_length=40)


class LoginRequest(BaseModel):
    username: str
    password: str


app = FastAPI(
    title="智能新闻推荐 RAG Agent",
    description="基于 FastAPI、LangGraph、LangChain、ChromaDB 和 DashScope 预留能力的智能新闻推荐系统。",
    version="0.1.0",
)


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    container: ServiceContainer = Depends(get_container),
) -> UserRecord:
    if credentials is None:
        raise HTTPException(status_code=401, detail="请先登录")
    user = container.database.get_user_by_token(credentials.credentials)
    if user is None:
        raise HTTPException(status_code=401, detail="登录状态已失效，请重新登录")
    return user


@app.get("/health")
def health(container: ServiceContainer = Depends(get_container)) -> dict:
    return {
        "status": "ok",
        "message": "服务正常",
        "articles": len(container.store.articles),
        "behaviors": len(container.store.behaviors),
        "use_dashscope": container.settings.use_dashscope,
    }


@app.post("/auth/register")
def register(payload: RegisterRequest, container: ServiceContainer = Depends(get_container)) -> dict:
    try:
        user = container.database.create_user(
            username=payload.username,
            password=payload.password,
            display_name=payload.display_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"message": "注册成功", "user": user.to_dict()}


@app.post("/auth/login")
def login(payload: LoginRequest, container: ServiceContainer = Depends(get_container)) -> dict:
    result = container.database.authenticate(payload.username, payload.password)
    if result is None:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    user, token = result
    return {"message": "登录成功", "token": token, "user": user.to_dict()}


@app.post("/auth/logout")
def logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    container: ServiceContainer = Depends(get_container),
) -> dict:
    if credentials:
        container.database.revoke_token(credentials.credentials)
    return {"message": "已退出登录"}


@app.get("/me")
def me(user: UserRecord = Depends(current_user)) -> dict:
    return {"user": user.to_dict()}


@app.get("/me/profile")
def get_my_profile(user: UserRecord = Depends(current_user), container: ServiceContainer = Depends(get_container)) -> dict:
    return container.recommender.get_profile(user.user_id)


@app.get("/me/recommend")
def recommend_for_me(
    top_k: int = 10,
    user: UserRecord = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> dict:
    recommendations = container.recommender.recommend(user_id=user.user_id, top_k=top_k)
    return {
        "user_id": user.user_id,
        "top_k": top_k,
        "items": [item.to_dict() for item in recommendations],
    }


@app.get("/users/{user_id}/profile")
def get_user_profile(user_id: str, container: ServiceContainer = Depends(get_container)) -> dict:
    return container.recommender.get_profile(user_id)


@app.get("/recommend/{user_id}")
def recommend(user_id: str, top_k: int = 10, container: ServiceContainer = Depends(get_container)) -> dict:
    recommendations = container.recommender.recommend(user_id=user_id, top_k=top_k)
    return {
        "user_id": user_id,
        "top_k": top_k,
        "items": [item.to_dict() for item in recommendations],
    }


@app.get("/articles/{news_id}")
def get_article(news_id: str, container: ServiceContainer = Depends(get_container)) -> dict:
    article = container.store.articles.get(news_id)
    if not article:
        raise HTTPException(status_code=404, detail=f"未找到新闻：{news_id}")
    return article.to_dict()


@app.post("/feedback")
def record_feedback(payload: FeedbackRequest, container: ServiceContainer = Depends(get_container)) -> dict:
    if not payload.user_id:
        raise HTTPException(status_code=400, detail="缺少用户 ID")
    article = container.store.articles.get(payload.news_id)
    if not article:
        raise HTTPException(status_code=404, detail=f"未找到新闻：{payload.news_id}")
    feedback = Feedback(
        user_id=payload.user_id,
        news_id=payload.news_id,
        feedback_type=payload.feedback_type,
        category=payload.category or article.category,
    )
    container.record_feedback(feedback)
    return {"status": "recorded", "message": "反馈已记录", "feedback": feedback.__dict__}


@app.post("/me/feedback")
def record_my_feedback(
    payload: FeedbackRequest,
    user: UserRecord = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> dict:
    article = container.store.articles.get(payload.news_id)
    if not article:
        raise HTTPException(status_code=404, detail=f"未找到新闻：{payload.news_id}")
    feedback = Feedback(
        user_id=user.user_id,
        news_id=payload.news_id,
        feedback_type=payload.feedback_type,
        category=payload.category or article.category,
    )
    container.record_feedback(feedback)
    return {"status": "recorded", "message": "反馈已记录", "feedback": feedback.__dict__}


@app.post("/evaluate")
def evaluate(payload: EvaluateRequest | None = None, container: ServiceContainer = Depends(get_container)) -> dict:
    k = payload.k if payload else 10
    result = container.evaluator.evaluate(k=k)
    return {"k": k, **result.to_dict()}
