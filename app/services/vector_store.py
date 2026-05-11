from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models import Article
from app.services.embedding import EmbeddingProvider, cosine_similarity


@dataclass
class SearchHit:
    article: Article
    score: float


@dataclass
class LocalVectorStore:
    embedding_provider: EmbeddingProvider
    vectors: dict[str, list[float]] = field(default_factory=dict)
    articles: dict[str, Article] = field(default_factory=dict)

    def upsert(self, articles: dict[str, Article]) -> None:
        for article in articles.values():
            self.articles[article.news_id] = article
            self.vectors[article.news_id] = self.embedding_provider.embed(article.text)

    def search(
        self,
        query: str,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
        exclude_ids: set[str] | None = None,
    ) -> list[SearchHit]:
        query_vector = self.embedding_provider.embed(query)
        filters = filters or {}
        exclude_ids = exclude_ids or set()
        hits: list[SearchHit] = []

        for news_id, vector in self.vectors.items():
            if news_id in exclude_ids:
                continue
            article = self.articles[news_id]
            if not _matches_filters(article, filters):
                continue
            hits.append(SearchHit(article=article, score=cosine_similarity(query_vector, vector)))

        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:top_k]


class ChromaVectorStore:
    """Thin optional Chroma adapter; LocalVectorStore remains the no-key fallback."""

    def __init__(self, persist_dir: str, embedding_provider: EmbeddingProvider, collection_name: str = "mind_news") -> None:
        try:
            import chromadb
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("Install chromadb to use ChromaVectorStore.") from exc

        self.embedding_provider = embedding_provider
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(collection_name)
        self.articles: dict[str, Article] = {}

    def upsert(self, articles: dict[str, Article]) -> None:
        self.articles.update(articles)
        self.collection.upsert(
            ids=[article.news_id for article in articles.values()],
            documents=[article.text for article in articles.values()],
            embeddings=[self.embedding_provider.embed(article.text) for article in articles.values()],
            metadatas=[
                {
                    "category": article.category,
                    "subcategory": article.subcategory,
                    "title": article.title,
                    "abstract": article.abstract,
                    "popularity": article.popularity,
                }
                for article in articles.values()
            ],
        )

    def search(
        self,
        query: str,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
        exclude_ids: set[str] | None = None,
    ) -> list[SearchHit]:
        where = filters or None
        result = self.collection.query(
            query_embeddings=[self.embedding_provider.embed(query)],
            n_results=max(top_k + len(exclude_ids or set()), top_k),
            where=where,
        )
        hits: list[SearchHit] = []
        ids = result.get("ids", [[]])[0]
        distances = result.get("distances", [[]])[0]
        exclude_ids = exclude_ids or set()
        for news_id, distance in zip(ids, distances):
            if news_id in exclude_ids or news_id not in self.articles:
                continue
            hits.append(SearchHit(article=self.articles[news_id], score=1.0 - float(distance)))
            if len(hits) >= top_k:
                break
        return hits


def _matches_filters(article: Article, filters: dict[str, Any]) -> bool:
    for key, expected in filters.items():
        actual = getattr(article, key, None)
        if isinstance(expected, (list, tuple, set)):
            if actual not in expected:
                return False
        elif actual != expected:
            return False
    return True
