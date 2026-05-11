from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Protocol

from app.core.text import tokenize


class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> list[float]:
        ...


@dataclass
class HashingEmbeddingProvider:
    dimensions: int = 128

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in tokenize(text):
            digest = hashlib.md5(token.encode("utf-8")).hexdigest()
            index = int(digest[:8], 16) % self.dimensions
            sign = 1.0 if int(digest[8:10], 16) % 2 == 0 else -1.0
            vector[index] += sign
        return normalize(vector)


@dataclass
class DashScopeEmbeddingProvider:
    api_key: str
    model: str = "text-embedding-v4"
    dimensions: int = 1024

    def embed(self, text: str) -> list[float]:
        if not self.api_key:
            raise RuntimeError("DASHSCOPE_API_KEY is required for DashScope embeddings.")
        try:
            import dashscope
        except ImportError as exc:  # pragma: no cover - optional online provider
            raise RuntimeError("Install dashscope to use DashScope embeddings.") from exc

        dashscope.api_key = self.api_key
        response = dashscope.TextEmbedding.call(
            model=self.model,
            input=text,
            dimension=self.dimensions,
        )
        if response.status_code != 200:
            raise RuntimeError(f"DashScope embedding failed: {response.message}")
        embedding = response.output["embeddings"][0]["embedding"]
        return normalize([float(value) for value in embedding])


def normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    size = min(len(left), len(right))
    return sum(left[index] * right[index] for index in range(size))
