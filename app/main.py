from __future__ import annotations

from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Request
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


class FavoriteRequest(BaseModel):
    favorite: bool | None = None


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)


class AgentRecommendRequest(BaseModel):
    query: str = Field(min_length=1, max_length=300)
    top_k: int = Field(default=20, ge=1, le=50)


class RAGQueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=800)
    top_k: int = Field(default=5, ge=1, le=12)
    document_id: str | None = None


class AgentChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=800)
    top_k: int = Field(default=5, ge=1, le=50)


class RecommendCompareRequest(BaseModel):
    user_id: str = "U100"
    top_k: int = Field(default=20, ge=1, le=50)
    query: str | None = None


class StrategyEvaluationRequest(BaseModel):
    k_values: list[int] = Field(default_factory=lambda: [5, 10, 20])


class ColdStartRequest(BaseModel):
    interest_tags: list[str] = Field(default_factory=list)
    top_k: int = Field(default=20, ge=1, le=50)


class DailyBriefingRequest(BaseModel):
    top_k: int = Field(default=8, ge=1, le=20)


class LTRTrainRequest(BaseModel):
    max_users: int | None = Field(default=None, ge=1, le=5000)
    epochs: int = Field(default=90, ge=1, le=500)
    learning_rate: float = Field(default=0.08, gt=0, le=1)


class LTRRecommendRequest(BaseModel):
    user_id: str = "U100"
    top_k: int = Field(default=20, ge=1, le=50)
    hybrid_rag: bool = False


class AblationRequest(BaseModel):
    user_id: str = "U100"
    top_k: int = Field(default=20, ge=1, le=50)


app = FastAPI(
    title="智能新闻推荐 RAG Agent",
    description="面向新闻推荐系统的 Agentic RAG、推荐实验、多 Agent 协作与本地资料库平台。",
    version="0.4.0",
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


def not_found(message: str) -> HTTPException:
    return HTTPException(status_code=404, detail=message)


@app.get("/health")
def health(container: ServiceContainer = Depends(get_container)) -> dict:
    return {
        "status": "ok",
        "message": "服务正常",
        "articles": len(container.store.articles),
        "behaviors": len(container.store.behaviors),
        "use_dashscope": container.settings.use_dashscope,
        "ai_cache_enabled": container.settings.ai_cache_enabled,
        "ltr": container.ltr_service.status(),
    }


@app.get("/metrics/overview")
def metrics_overview(container: ServiceContainer = Depends(get_container)) -> dict:
    return container.news_intelligence.metrics_overview()


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


@app.get("/me/profile/summary")
def get_my_profile_summary(
    user: UserRecord = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> dict:
    profile = container.profile_service.build_profile(user.user_id)
    return container.llm_service.summarize_profile(profile)


@app.get("/me/interest-drift")
def interest_drift(user: UserRecord = Depends(current_user), container: ServiceContainer = Depends(get_container)) -> dict:
    return container.news_intelligence.interest_drift(user.user_id)


@app.get("/me/recommend")
def recommend_for_me(
    top_k: int | None = None,
    user: UserRecord = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> dict:
    top_k = top_k or container.settings.recommend_top_k
    recommendations = container.recommender.recommend(user_id=user.user_id, top_k=top_k)
    return {"user_id": user.user_id, "top_k": top_k, "items": [item.to_dict() for item in recommendations]}


@app.get("/me/recommend/explain/{news_id}")
def explain_my_recommendation(
    news_id: str,
    user: UserRecord = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> dict:
    try:
        return container.ltr_service.explain(user.user_id, news_id, hybrid_rag=True)
    except KeyError as exc:
        raise not_found(f"未找到新闻：{news_id}") from exc


@app.post("/me/daily-briefing")
def daily_briefing(
    payload: DailyBriefingRequest | None = None,
    user: UserRecord = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> dict:
    top_k = payload.top_k if payload else 8
    return container.news_intelligence.daily_briefing(user.user_id, top_k=top_k)


@app.get("/me/articles/{news_id}")
def get_my_article_detail(
    news_id: str,
    user: UserRecord = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> dict:
    try:
        return container.article_service.detail_for_user(user.user_id, news_id)
    except KeyError as exc:
        raise not_found(f"未找到新闻：{news_id}") from exc


@app.post("/me/articles/{news_id}/view")
def record_article_view(
    news_id: str,
    user: UserRecord = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> dict:
    try:
        return container.article_service.record_view(user.user_id, news_id)
    except KeyError as exc:
        raise not_found(f"未找到新闻：{news_id}") from exc


@app.post("/me/articles/{news_id}/favorite")
def favorite_article(
    news_id: str,
    payload: FavoriteRequest | None = None,
    user: UserRecord = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> dict:
    try:
        return container.article_service.set_favorite(
            user.user_id,
            news_id,
            favorite=None if payload is None else payload.favorite,
        )
    except KeyError as exc:
        raise not_found(f"未找到新闻：{news_id}") from exc


@app.get("/me/favorites")
def get_my_favorites(user: UserRecord = Depends(current_user), container: ServiceContainer = Depends(get_container)) -> dict:
    return {"items": container.article_service.favorites_for_user(user.user_id)}


@app.get("/me/history")
def get_my_history(user: UserRecord = Depends(current_user), container: ServiceContainer = Depends(get_container)) -> dict:
    return {"items": container.article_service.history_for_user(user.user_id)}


@app.post("/me/articles/{news_id}/summary")
def summarize_article(
    news_id: str,
    user: UserRecord = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> dict:
    try:
        return container.article_service.summarize(news_id)
    except KeyError as exc:
        raise not_found(f"未找到新闻：{news_id}") from exc


@app.post("/me/articles/{news_id}/ask")
def ask_article(
    news_id: str,
    payload: AskRequest,
    user: UserRecord = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> dict:
    try:
        return container.article_service.ask(news_id, payload.question)
    except KeyError as exc:
        raise not_found(f"未找到新闻：{news_id}") from exc


@app.post("/me/articles/{news_id}/grounded-analysis")
def grounded_article_analysis(
    news_id: str,
    user: UserRecord = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> dict:
    try:
        return container.article_service.grounded_analysis(user.user_id, news_id)
    except KeyError as exc:
        raise not_found(f"未找到新闻：{news_id}") from exc


@app.post("/me/documents/upload")
async def upload_document(
    request: Request,
    user: UserRecord = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> dict:
    try:
        form = await request.form()
        file = form.get("file")
        if file is None or not hasattr(file, "file"):
            raise ValueError("请上传文件字段 file")
        return container.document_service.ingest_upload(user.user_id, getattr(file, "filename", None) or "document", file.file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/me/documents")
def list_documents(user: UserRecord = Depends(current_user), container: ServiceContainer = Depends(get_container)) -> dict:
    return {"items": container.document_service.list_documents(user.user_id)}


@app.get("/me/documents/{document_id}")
def get_document(
    document_id: str,
    user: UserRecord = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> dict:
    try:
        return container.document_service.get_document(user.user_id, document_id)
    except KeyError as exc:
        raise not_found(f"未找到文档：{document_id}") from exc


@app.delete("/me/documents/{document_id}")
def delete_document(
    document_id: str,
    user: UserRecord = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> dict:
    deleted = container.document_service.delete_document(user.user_id, document_id)
    if not deleted:
        raise not_found(f"未找到文档：{document_id}")
    return {"message": "文档已删除", "document_id": document_id}


@app.post("/me/documents/{document_id}/reindex")
def reindex_document(
    document_id: str,
    user: UserRecord = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> dict:
    try:
        return container.document_service.reindex_document(user.user_id, document_id)
    except KeyError as exc:
        raise not_found(f"未找到文档：{document_id}") from exc


@app.post("/me/rag/query")
def query_documents(
    payload: RAGQueryRequest,
    user: UserRecord = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> dict:
    return container.rag_service.query(user.user_id, payload.question, payload.top_k, payload.document_id)


@app.post("/me/rag/hybrid-query")
def hybrid_query_documents(
    payload: RAGQueryRequest,
    user: UserRecord = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> dict:
    return container.rag_service.hybrid_query(user.user_id, payload.question, payload.top_k, payload.document_id)


@app.post("/me/agent/recommend")
def agent_recommend(
    payload: AgentRecommendRequest,
    user: UserRecord = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> dict:
    items = [item.to_dict() for item in container.recommender.search(payload.query, top_k=payload.top_k)]
    profile = container.profile_service.build_profile(user.user_id)
    profile_summary = container.llm_service.summarize_profile(profile)["summary"]
    response = {
        "query": payload.query,
        "answer": f"已根据“{payload.query}”为你找到 {len(items)} 篇相关新闻。{profile_summary}",
        "items": items,
    }
    container.database.record_agent_run(user.user_id, payload.query, response)
    return response


@app.post("/me/agent/chat")
def agent_chat(
    payload: AgentChatRequest,
    user: UserRecord = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> dict:
    state = container.research_workflow.run(user.user_id, payload.query, top_k=payload.top_k)
    response = {
        "query": payload.query,
        "intent": state.get("intent"),
        "answer": state.get("answer", ""),
        "items": state.get("news_items", []),
        "rag": state.get("rag_result", {}),
        "evaluation": state.get("evaluation_result", {}),
        "workflow_trace": state.get("workflow_trace", []),
    }
    container.database.record_agent_run(user.user_id, payload.query, response)
    return response


@app.post("/me/agent/trace")
def agent_trace(
    payload: AgentChatRequest,
    user: UserRecord = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> dict:
    return agent_chat(payload, user, container)


@app.post("/recommend/compare")
def compare_recommendations(payload: RecommendCompareRequest, container: ServiceContainer = Depends(get_container)) -> dict:
    return container.experiment_service.compare(payload.user_id, top_k=payload.top_k, query=payload.query)


@app.post("/recommend/ltr")
def recommend_ltr(payload: LTRRecommendRequest, container: ServiceContainer = Depends(get_container)) -> dict:
    items = container.ltr_service.recommend(payload.user_id, top_k=payload.top_k, hybrid_rag=payload.hybrid_rag)
    return {
        "user_id": payload.user_id,
        "top_k": payload.top_k,
        "strategy": "hybrid_ltr_rag" if payload.hybrid_rag else "ltr_rerank",
        "model_status": container.ltr_service.status(),
        "items": [item.to_dict() for item in items],
    }


@app.post("/recommend/cold-start")
def cold_start_recommend(payload: ColdStartRequest, container: ServiceContainer = Depends(get_container)) -> dict:
    return container.experiment_service.cold_start(payload.interest_tags, top_k=payload.top_k)


@app.post("/evaluate/strategies")
def evaluate_strategies(payload: StrategyEvaluationRequest | None = None, container: ServiceContainer = Depends(get_container)) -> dict:
    k_values = payload.k_values if payload else [5, 10, 20]
    return container.experiment_service.evaluate_strategies(k_values=k_values)


@app.post("/evaluate/ablation")
def evaluate_ablation(payload: AblationRequest, container: ServiceContainer = Depends(get_container)) -> dict:
    return container.experiment_service.ablation(payload.user_id, top_k=payload.top_k)


@app.post("/models/ltr/train")
def train_ltr_model(payload: LTRTrainRequest | None = None, container: ServiceContainer = Depends(get_container)) -> dict:
    payload = payload or LTRTrainRequest()
    return container.ltr_service.train(max_users=payload.max_users, epochs=payload.epochs, learning_rate=payload.learning_rate)


@app.get("/models/ltr/status")
def ltr_model_status(container: ServiceContainer = Depends(get_container)) -> dict:
    return container.ltr_service.status()


@app.get("/experiments")
def list_experiments(limit: int = 50, container: ServiceContainer = Depends(get_container)) -> dict:
    return {"items": container.database.list_experiments(limit=limit)}


@app.get("/experiments/{experiment_id}")
def get_experiment(experiment_id: int, container: ServiceContainer = Depends(get_container)) -> dict:
    experiment = container.database.get_experiment(experiment_id)
    if not experiment:
        raise not_found(f"未找到实验：{experiment_id}")
    return experiment


@app.get("/articles/{news_id}/event-cluster")
def event_cluster(news_id: str, top_k: int = 8, container: ServiceContainer = Depends(get_container)) -> dict:
    try:
        return container.news_intelligence.event_cluster(news_id, top_k=top_k)
    except KeyError as exc:
        raise not_found(f"未找到新闻：{news_id}") from exc


@app.get("/articles/{news_id}/viewpoints")
def compare_viewpoints(news_id: str, top_k: int = 5, container: ServiceContainer = Depends(get_container)) -> dict:
    try:
        return container.news_intelligence.compare_viewpoints(news_id, top_k=top_k)
    except KeyError as exc:
        raise not_found(f"未找到新闻：{news_id}") from exc


@app.get("/users/{user_id}/profile")
def get_user_profile(user_id: str, container: ServiceContainer = Depends(get_container)) -> dict:
    return container.recommender.get_profile(user_id)


@app.get("/recommend/{user_id}")
def recommend(user_id: str, top_k: int | None = None, container: ServiceContainer = Depends(get_container)) -> dict:
    top_k = top_k or container.settings.recommend_top_k
    recommendations = container.recommender.recommend(user_id=user_id, top_k=top_k)
    return {"user_id": user_id, "top_k": top_k, "items": [item.to_dict() for item in recommendations]}


@app.get("/articles/{news_id}")
def get_article(news_id: str, container: ServiceContainer = Depends(get_container)) -> dict:
    article = container.store.articles.get(news_id)
    if not article:
        raise not_found(f"未找到新闻：{news_id}")
    return article.to_dict()


@app.post("/feedback")
def record_feedback(payload: FeedbackRequest, container: ServiceContainer = Depends(get_container)) -> dict:
    if not payload.user_id:
        raise HTTPException(status_code=400, detail="缺少用户 ID")
    article = container.store.articles.get(payload.news_id)
    if not article:
        raise not_found(f"未找到新闻：{payload.news_id}")
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
        raise not_found(f"未找到新闻：{payload.news_id}")
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
