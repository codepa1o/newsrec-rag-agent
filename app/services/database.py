from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models import Feedback


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class UserRecord:
    user_id: str
    username: str
    display_name: str
    created_at: str

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "display_name": self.display_name,
            "created_at": self.created_at,
        }


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
        self._seed_demo_users()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def create_user(self, username: str, password: str, display_name: str | None = None) -> UserRecord:
        username = normalize_username(username)
        validate_password(password)
        display_name = (display_name or username).strip() or username
        salt = secrets.token_hex(16)
        password_hash = hash_password(password, salt)
        created_at = utc_now()

        try:
            with self.connect() as connection:
                connection.execute(
                    """
                    INSERT INTO users (user_id, username, display_name, password_hash, password_salt, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (username, username, display_name, password_hash, salt, created_at),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("用户名已存在") from exc

        return UserRecord(user_id=username, username=username, display_name=display_name, created_at=created_at)

    def authenticate(self, username: str, password: str) -> tuple[UserRecord, str] | None:
        username = normalize_username(username)
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            if row is None:
                return None
            expected = hash_password(password, row["password_salt"])
            if not secrets.compare_digest(expected, row["password_hash"]):
                return None
            token = secrets.token_urlsafe(32)
            connection.execute(
                "INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)",
                (token, row["user_id"], utc_now()),
            )
            connection.execute("UPDATE users SET last_login_at = ? WHERE user_id = ?", (utc_now(), row["user_id"]))
            return row_to_user(row), token

    def get_user_by_token(self, token: str) -> UserRecord | None:
        if not token:
            return None
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT users.* FROM sessions
                JOIN users ON users.user_id = sessions.user_id
                WHERE sessions.token = ?
                """,
                (token,),
            ).fetchone()
            return row_to_user(row) if row else None

    def revoke_token(self, token: str) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM sessions WHERE token = ?", (token,))

    def add_feedback(self, feedback: Feedback) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO feedback_events (user_id, news_id, feedback_type, category, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (feedback.user_id, feedback.news_id, feedback.feedback_type, feedback.category, utc_now()),
            )

    def load_feedback(self) -> list[Feedback]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT user_id, news_id, feedback_type, category FROM feedback_events ORDER BY id"
            ).fetchall()
        return [
            Feedback(
                user_id=row["user_id"],
                news_id=row["news_id"],
                feedback_type=row["feedback_type"],
                category=row["category"],
            )
            for row in rows
        ]

    def record_view(self, user_id: str, news_id: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO article_views (user_id, news_id, created_at) VALUES (?, ?, ?)",
                (user_id, news_id, utc_now()),
            )

    def list_history(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT news_id, MAX(created_at) AS viewed_at, COUNT(*) AS view_count
                FROM article_views
                WHERE user_id = ?
                GROUP BY news_id
                ORDER BY viewed_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def set_favorite(self, user_id: str, news_id: str, favorite: bool) -> bool:
        with self.connect() as connection:
            if favorite:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO favorites (user_id, news_id, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (user_id, news_id, utc_now()),
                )
            else:
                connection.execute("DELETE FROM favorites WHERE user_id = ? AND news_id = ?", (user_id, news_id))
        return favorite

    def toggle_favorite(self, user_id: str, news_id: str) -> bool:
        current = self.is_favorite(user_id, news_id)
        return self.set_favorite(user_id, news_id, favorite=not current)

    def is_favorite(self, user_id: str, news_id: str) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM favorites WHERE user_id = ? AND news_id = ?",
                (user_id, news_id),
            ).fetchone()
        return row is not None

    def list_favorites(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT news_id, created_at AS favorited_at
                FROM favorites
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_cached_ai(self, task: str, cache_key: str) -> str | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT response FROM ai_cache WHERE task = ? AND cache_key = ?",
                (task, cache_key),
            ).fetchone()
        return row["response"] if row else None

    def set_cached_ai(self, task: str, cache_key: str, response: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO ai_cache (task, cache_key, response, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(task, cache_key) DO UPDATE SET response = excluded.response, created_at = excluded.created_at
                """,
                (task, cache_key, response, utc_now()),
            )

    def record_agent_run(self, user_id: str, query: str, response: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO agent_runs (user_id, query, response_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, query, json.dumps(response, ensure_ascii=False), utc_now()),
            )

    def list_agent_runs(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT query, response_json, created_at
                FROM agent_runs
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_or_replace_document(
        self,
        user_id: str,
        filename: str,
        file_type: str,
        file_path: str,
        content_hash: str,
    ) -> str:
        document_id = hashlib.sha256(f"{user_id}:{content_hash}".encode("utf-8")).hexdigest()[:16]
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT document_id FROM documents WHERE user_id = ? AND content_hash = ?",
                (user_id, content_hash),
            ).fetchone()
            if existing:
                document_id = existing["document_id"]
                connection.execute("DELETE FROM document_chunks WHERE document_id = ?", (document_id,))
                connection.execute(
                    """
                    UPDATE documents
                    SET filename = ?, file_type = ?, file_path = ?, status = ?, error_message = '',
                        chunk_count = 0, updated_at = ?
                    WHERE document_id = ?
                    """,
                    (filename, file_type, file_path, "processing", utc_now(), document_id),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO documents (
                        document_id, user_id, filename, file_type, file_path, content_hash,
                        status, error_message, chunk_count, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, '', 0, ?, ?)
                    """,
                    (
                        document_id,
                        user_id,
                        filename,
                        file_type,
                        file_path,
                        content_hash,
                        "processing",
                        utc_now(),
                        utc_now(),
                    ),
                )
        return document_id

    def update_document_status(
        self,
        document_id: str,
        status: str,
        chunk_count: int = 0,
        error_message: str = "",
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE documents
                SET status = ?, chunk_count = ?, error_message = ?, updated_at = ?
                WHERE document_id = ?
                """,
                (status, chunk_count, error_message, utc_now(), document_id),
            )

    def add_document_chunks(self, chunks: list[dict[str, Any]]) -> None:
        if not chunks:
            return
        with self.connect() as connection:
            connection.executemany(
                """
                INSERT INTO document_chunks (
                    chunk_id, document_id, user_id, chunk_index, text, page, heading_path,
                    source, token_count, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        chunk["chunk_id"],
                        chunk["document_id"],
                        chunk["user_id"],
                        chunk["chunk_index"],
                        chunk["text"],
                        chunk.get("page"),
                        chunk.get("heading_path", ""),
                        chunk.get("source", ""),
                        chunk.get("token_count", 0),
                        utc_now(),
                    )
                    for chunk in chunks
                ],
            )

    def list_documents(self, user_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT document_id, filename, file_type, status, error_message, chunk_count,
                       created_at, updated_at
                FROM documents
                WHERE user_id = ?
                ORDER BY updated_at DESC
                """,
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_document(self, user_id: str, document_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT document_id, user_id, filename, file_type, file_path, content_hash, status,
                       error_message, chunk_count, created_at, updated_at
                FROM documents
                WHERE user_id = ? AND document_id = ?
                """,
                (user_id, document_id),
            ).fetchone()
        return dict(row) if row else None

    def delete_document(self, user_id: str, document_id: str) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT file_path FROM documents WHERE user_id = ? AND document_id = ?",
                (user_id, document_id),
            ).fetchone()
            if not row:
                return False
            connection.execute("DELETE FROM document_chunks WHERE user_id = ? AND document_id = ?", (user_id, document_id))
            connection.execute("DELETE FROM documents WHERE user_id = ? AND document_id = ?", (user_id, document_id))
        return True

    def list_document_chunks(self, user_id: str | None = None, document_id: str | None = None) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if user_id is not None:
            clauses.append("user_id = ?")
            params.append(user_id)
        if document_id is not None:
            clauses.append("document_id = ?")
            params.append(document_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT chunk_id, document_id, user_id, chunk_index, text, page,
                       heading_path, source, token_count, created_at
                FROM document_chunks
                {where}
                ORDER BY document_id, chunk_index
                """,
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def record_rag_query(
        self,
        user_id: str,
        question: str,
        answer: str,
        confidence: float,
        workflow_trace: list[dict[str, Any]],
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO rag_queries (user_id, question, answer, confidence, workflow_trace_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, question, answer, confidence, json.dumps(workflow_trace, ensure_ascii=False), utc_now()),
            )
            return int(cursor.lastrowid)

    def record_rag_citations(self, query_id: int, citations: list[dict[str, Any]]) -> None:
        if not citations:
            return
        with self.connect() as connection:
            connection.executemany(
                """
                INSERT INTO rag_citations (
                    query_id, chunk_id, document_id, filename, page, heading_path, snippet, score
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        query_id,
                        citation["chunk_id"],
                        citation["document_id"],
                        citation["filename"],
                        citation.get("page"),
                        citation.get("heading_path", ""),
                        citation.get("snippet", ""),
                        citation.get("score", 0.0),
                    )
                    for citation in citations
                ],
            )

    def record_answer_evaluation(self, query_id: int, evaluation: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO answer_evaluations (
                    query_id, faithfulness, answer_relevance, citation_coverage, notes, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    query_id,
                    evaluation.get("faithfulness", 0.0),
                    evaluation.get("answer_relevance", 0.0),
                    evaluation.get("citation_coverage", 0.0),
                    evaluation.get("notes", ""),
                    utc_now(),
                ),
            )

    def record_experiment(
        self,
        name: str,
        strategy: str,
        parameters: dict[str, Any],
        metrics: dict[str, Any],
        sample_count: int = 0,
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO experiments (name, strategy, parameters_json, metrics_json, sample_count, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    strategy,
                    json.dumps(parameters, ensure_ascii=False),
                    json.dumps(metrics, ensure_ascii=False),
                    sample_count,
                    utc_now(),
                ),
            )
            return int(cursor.lastrowid)

    def list_experiments(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, name, strategy, parameters_json, metrics_json, sample_count, created_at
                FROM experiments
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [experiment_row_to_dict(row) for row in rows]

    def get_experiment(self, experiment_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT id, name, strategy, parameters_json, metrics_json, sample_count, created_at
                FROM experiments
                WHERE id = ?
                """,
                (experiment_id,),
            ).fetchone()
        return experiment_row_to_dict(row) if row else None

    def _init_schema(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT UNIQUE,
                    username TEXT UNIQUE NOT NULL,
                    display_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    password_salt TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_login_at TEXT
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                );

                CREATE TABLE IF NOT EXISTS feedback_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    news_id TEXT NOT NULL,
                    feedback_type TEXT NOT NULL,
                    category TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS article_views (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    news_id TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS favorites (
                    user_id TEXT NOT NULL,
                    news_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, news_id)
                );

                CREATE TABLE IF NOT EXISTS ai_cache (
                    task TEXT NOT NULL,
                    cache_key TEXT NOT NULL,
                    response TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (task, cache_key)
                );

                CREATE TABLE IF NOT EXISTS agent_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    query TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error_message TEXT NOT NULL DEFAULT '',
                    chunk_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents(user_id);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_user_hash ON documents(user_id, content_hash);

                CREATE TABLE IF NOT EXISTS document_chunks (
                    chunk_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    page INTEGER,
                    heading_path TEXT,
                    source TEXT,
                    token_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (document_id) REFERENCES documents(document_id)
                );

                CREATE INDEX IF NOT EXISTS idx_document_chunks_user_id ON document_chunks(user_id);
                CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id ON document_chunks(document_id);

                CREATE TABLE IF NOT EXISTS rag_queries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    workflow_trace_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS rag_citations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_id INTEGER NOT NULL,
                    chunk_id TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    page INTEGER,
                    heading_path TEXT,
                    snippet TEXT,
                    score REAL NOT NULL DEFAULT 0,
                    FOREIGN KEY (query_id) REFERENCES rag_queries(id)
                );

                CREATE TABLE IF NOT EXISTS answer_evaluations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_id INTEGER NOT NULL,
                    faithfulness REAL NOT NULL,
                    answer_relevance REAL NOT NULL,
                    citation_coverage REAL NOT NULL,
                    notes TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (query_id) REFERENCES rag_queries(id)
                );

                CREATE TABLE IF NOT EXISTS experiments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    parameters_json TEXT NOT NULL,
                    metrics_json TEXT NOT NULL,
                    sample_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                """
            )

    def _seed_demo_users(self) -> None:
        for username, display_name in [("U100", "演示用户 U100"), ("U200", "演示用户 U200")]:
            try:
                self.create_user(username=username, password="demo123456", display_name=display_name)
            except ValueError:
                with self.connect() as connection:
                    connection.execute(
                        "UPDATE users SET user_id = ?, display_name = ? WHERE username = ?",
                        (username, display_name, username),
                    )


def normalize_username(username: str) -> str:
    username = username.strip()
    if len(username) < 3:
        raise ValueError("用户名至少需要 3 个字符")
    if len(username) > 32:
        raise ValueError("用户名不能超过 32 个字符")
    return username


def validate_password(password: str) -> None:
    if len(password) < 8:
        raise ValueError("密码至少需要 8 个字符")


def hash_password(password: str, salt: str) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return digest.hex()


def row_to_user(row: sqlite3.Row) -> UserRecord:
    return UserRecord(
        user_id=row["user_id"],
        username=row["username"],
        display_name=row["display_name"],
        created_at=row["created_at"],
    )


def experiment_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "strategy": row["strategy"],
        "parameters": json.loads(row["parameters_json"] or "{}"),
        "metrics": json.loads(row["metrics_json"] or "{}"),
        "sample_count": row["sample_count"],
        "created_at": row["created_at"],
    }
