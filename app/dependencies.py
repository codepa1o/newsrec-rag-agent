from __future__ import annotations

from functools import lru_cache

from app.config import Settings, get_settings
from app.agent.research_workflow import MultiAgentResearchWorkflow
from app.models import Feedback
from app.services.database import Database
from app.services.document_service import DocumentService
from app.services.embedding import DashScopeEmbeddingProvider, HashingEmbeddingProvider
from app.services.evaluator import Evaluator
from app.services.experiment_service import RecommendationExperimentService
from app.services.article_service import ArticleService
from app.services.llm_service import LLMService
from app.services.ltr_service import LearningToRankService
from app.services.news_intelligence import NewsIntelligenceService
from app.services.profile import ProfileService
from app.services.rag_service import RAGService
from app.services.recommender import NewsRecommender
from app.services.store import NewsDataStore


class ServiceContainer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.database = Database(settings.database_path)
        self.store = NewsDataStore(settings, database=self.database)
        self.embedding_provider = self._build_embedding_provider()
        self.profile_service = ProfileService(
            self.store.articles,
            self.store.behaviors,
            self.store.feedback,
            database=self.database,
        )
        self.recommender = NewsRecommender(
            articles=self.store.articles,
            profile_service=self.profile_service,
            embedding_provider=self.embedding_provider,
            retrieval_top_k=settings.retrieval_top_k,
        )
        self.llm_service = LLMService(settings=self.settings, database=self.database)
        self.document_service = DocumentService(
            settings=self.settings,
            database=self.database,
            embedding_provider=self.embedding_provider,
        )
        self.rag_service = RAGService(
            database=self.database,
            document_service=self.document_service,
            llm_service=self.llm_service,
        )
        self.article_service = ArticleService(
            articles=self.store.articles,
            database=self.database,
            recommender=self.recommender,
            llm_service=self.llm_service,
            rag_service=self.rag_service,
        )
        self.evaluator = Evaluator(self.recommender, self.store.behaviors)
        self.ltr_service = LearningToRankService(
            articles=self.store.articles,
            behaviors=self.store.behaviors,
            database=self.database,
            profile_service=self.profile_service,
            recommender=self.recommender,
            model_path=settings.ltr_model_path,
            max_train_users=settings.max_eval_users * 5,
        )
        self.experiment_service = RecommendationExperimentService(
            articles=self.store.articles,
            behaviors=self.store.behaviors,
            database=self.database,
            profile_service=self.profile_service,
            recommender=self.recommender,
            ltr_service=self.ltr_service,
            max_eval_users=settings.max_eval_users,
        )
        self.news_intelligence = NewsIntelligenceService(
            articles=self.store.articles,
            database=self.database,
            profile_service=self.profile_service,
            recommender=self.recommender,
            llm_service=self.llm_service,
        )
        self.research_workflow = MultiAgentResearchWorkflow(self)

    def record_feedback(self, feedback: Feedback) -> None:
        self.store.add_feedback(feedback)
        self.recommender.apply_feedback(feedback)

    def _build_embedding_provider(self):
        if self.settings.use_dashscope:
            return DashScopeEmbeddingProvider(
                api_key=self.settings.dashscope_api_key,
                model=self.settings.embedding_model,
                dimensions=self.settings.embedding_dimensions,
            )
        return HashingEmbeddingProvider()


@lru_cache(maxsize=1)
def get_container() -> ServiceContainer:
    return ServiceContainer(get_settings())
