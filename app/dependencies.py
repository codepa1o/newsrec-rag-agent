from __future__ import annotations

from functools import lru_cache

from app.config import Settings, get_settings
from app.models import Feedback
from app.services.database import Database
from app.services.embedding import DashScopeEmbeddingProvider, HashingEmbeddingProvider
from app.services.evaluator import Evaluator
from app.services.profile import ProfileService
from app.services.recommender import NewsRecommender
from app.services.store import NewsDataStore


class ServiceContainer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.database = Database(settings.database_path)
        self.store = NewsDataStore(settings, database=self.database)
        self.embedding_provider = self._build_embedding_provider()
        self.profile_service = ProfileService(self.store.articles, self.store.behaviors, self.store.feedback)
        self.recommender = NewsRecommender(
            articles=self.store.articles,
            profile_service=self.profile_service,
            embedding_provider=self.embedding_provider,
            retrieval_top_k=settings.retrieval_top_k,
        )
        self.evaluator = Evaluator(self.recommender, self.store.behaviors)

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
