from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency during lightweight tests
    load_dotenv = None


if load_dotenv:
    load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "dev")
    data_dir: Path = Path(os.getenv("DATA_DIR", "data"))
    database_path: Path = Path(os.getenv("DATABASE_PATH", "data/newsrec.db"))
    upload_dir: Path = Path(os.getenv("UPLOAD_DIR", "data/uploads"))
    model_dir: Path = Path(os.getenv("MODEL_DIR", "data/models"))
    ltr_model_path: Path = Path(os.getenv("LTR_MODEL_PATH", "data/models/ltr_model.json"))
    mind_news_path: Path = Path(os.getenv("MIND_NEWS_PATH", "data/sample/news.tsv"))
    mind_behaviors_path: Path = Path(os.getenv("MIND_BEHAVIORS_PATH", "data/sample/behaviors.tsv"))
    chroma_persist_dir: Path = Path(os.getenv("CHROMA_PERSIST_DIR", "data/chroma"))
    dashscope_api_key: str = os.getenv("DASHSCOPE_API_KEY", "")
    dashscope_base_url: str = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    llm_model: str = os.getenv("LLM_MODEL", "qwen-plus")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-v4")
    embedding_dimensions: int = int(os.getenv("EMBEDDING_DIMENSIONS", "1024"))
    rerank_model: str = os.getenv("RERANK_MODEL", "qwen3-rerank")
    recommend_top_k: int = int(os.getenv("RECOMMEND_TOP_K", "20"))
    retrieval_top_k: int = int(os.getenv("RETRIEVAL_TOP_K", "80"))
    use_chroma: bool = os.getenv("USE_CHROMA", "false").lower() == "true"
    use_dashscope: bool = os.getenv("USE_DASHSCOPE", "false").lower() == "true"
    ai_cache_enabled: bool = os.getenv("AI_CACHE_ENABLED", "true").lower() == "true"
    ai_timeout_seconds: int = int(os.getenv("AI_TIMEOUT_SECONDS", "30"))
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "20"))
    max_eval_users: int = int(os.getenv("MAX_EVAL_USERS", "80"))


def get_settings() -> Settings:
    return Settings()
