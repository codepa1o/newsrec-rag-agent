from __future__ import annotations

import hashlib
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

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
                """
            )

    def _seed_demo_users(self) -> None:
        for username, display_name in [("U100", "演示用户 U100"), ("U200", "演示用户 U200")]:
            try:
                self.create_user(username=username, password="demo123456", display_name=display_name)
            except ValueError:
                with self.connect() as connection:
                    connection.execute("UPDATE users SET user_id = ? WHERE username = ?", (username, username))


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
