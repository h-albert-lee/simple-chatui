"""SQLite-backed conversation storage for the chat UI."""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Dict, Iterable, List, Optional
from uuid import uuid4

from .config import settings

_DB_PATH = settings.database_path
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_DEFAULT_TITLE = "새로운 대화"
_PASSWORD_ITERATIONS = 100_000
_LEGACY_USER_ID = "00000000-0000-0000-0000-000000000000"
_LEGACY_USERNAME = "_legacy_user"


class UserAlreadyExistsError(ValueError):
    """Raised when attempting to create a user with a duplicate username."""


@contextmanager
def _connect() -> Iterable[sqlite3.Connection]:
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def initialize_database() -> None:
    """Ensure that the SQLite schema exists and is migrated to the latest version."""

    with _connect() as conn:
        _ensure_user_table(conn)
        _ensure_session_table(conn)
        _ensure_conversation_table(conn)
        _ensure_message_table(conn)
        _ensure_legacy_user(conn)


def _ensure_user_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            password_salt TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )


def _ensure_session_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """
    )


def _ensure_conversation_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """
    )

    columns = {row["name"] for row in conn.execute("PRAGMA table_info(conversations)").fetchall()}
    if "user_id" not in columns:
        conn.execute("ALTER TABLE conversations ADD COLUMN user_id TEXT")
    if "title" not in columns:
        conn.execute("ALTER TABLE conversations ADD COLUMN title TEXT")
    if "created_at" not in columns:
        conn.execute("ALTER TABLE conversations ADD COLUMN created_at TEXT")

    now_iso = datetime.now(UTC).isoformat()
    conn.execute(
        "UPDATE conversations SET user_id = COALESCE(user_id, ?)",
        (_LEGACY_USER_ID,),
    )
    conn.execute(
        "UPDATE conversations SET title = ? WHERE title IS NULL OR title = ''",
        (_DEFAULT_TITLE,),
    )
    conn.execute(
        "UPDATE conversations SET created_at = COALESCE(created_at, ?)",
        (now_iso,),
    )


def _ensure_message_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        );
        """
    )


def _ensure_legacy_user(conn: sqlite3.Connection) -> None:
    now = datetime.now(UTC).isoformat()
    row = conn.execute(
        "SELECT id FROM users WHERE id = ?",
        (_LEGACY_USER_ID,),
    ).fetchone()
    if not row:
        salt = secrets.token_hex(16)
        password_hash = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
        conn.execute(
            "INSERT OR IGNORE INTO users(id, username, password_hash, password_salt, created_at) VALUES (?, ?, ?, ?, ?)",
            (_LEGACY_USER_ID, _LEGACY_USERNAME, password_hash, salt, now),
        )


def _hash_password(password: str, *, salt: Optional[str] = None) -> tuple[str, str]:
    if salt is None:
        salt_bytes = secrets.token_bytes(16)
        salt_hex = salt_bytes.hex()
    else:
        salt_hex = salt
        salt_bytes = bytes.fromhex(salt)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt_bytes,
        _PASSWORD_ITERATIONS,
    ).hex()
    return password_hash, salt_hex


def create_user(username: str, password: str) -> str:
    username = username.strip()
    if not username:
        raise ValueError("Username cannot be empty")
    if not password:
        raise ValueError("Password cannot be empty")

    user_id = str(uuid4())
    now = datetime.now(UTC).isoformat()
    password_hash, salt_hex = _hash_password(password)

    with _connect() as conn:
        try:
            conn.execute(
                "INSERT INTO users(id, username, password_hash, password_salt, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, username, password_hash, salt_hex, now),
            )
        except sqlite3.IntegrityError as exc:  # duplicate username
            raise UserAlreadyExistsError(f"Username '{username}' is already taken") from exc

    return user_id


def authenticate_user(username: str, password: str) -> Optional[Dict[str, str]]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, username, password_hash, password_salt FROM users WHERE username = ?",
            (username,),
        ).fetchone()

    if not row:
        return None

    if not row["password_salt"]:
        return None

    computed_hash, _ = _hash_password(password, salt=row["password_salt"])
    if computed_hash != row["password_hash"]:
        return None

    return {"id": row["id"], "username": row["username"]}


def issue_token(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = datetime.now(UTC)
    expires_at = now + timedelta(hours=settings.AUTH_TOKEN_TTL_HOURS)

    with _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO sessions(token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (
                token_hash,
                user_id,
                now.isoformat(),
                expires_at.isoformat(),
            ),
        )

    return token


def get_user_by_token(token: str) -> Optional[Dict[str, str]]:
    if not token:
        return None

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now_iso = datetime.now(UTC).isoformat()

    with _connect() as conn:
        row = conn.execute(
            """
            SELECT u.id, u.username, s.expires_at
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.token_hash = ?
            """,
            (token_hash,),
        ).fetchone()

        if not row:
            return None

        if row["expires_at"] <= now_iso:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
            return None

    return {"id": row["id"], "username": row["username"]}


def revoke_token(token: str) -> None:
    if not token:
        return
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    with _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))


def create_conversation(user_id: str, title: str = _DEFAULT_TITLE) -> str:
    """Create a new conversation and return its identifier."""

    conversation_id = str(uuid4())
    now = datetime.now(UTC).isoformat()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO conversations(id, user_id, title, created_at) VALUES (?, ?, ?, ?)",
            (conversation_id, user_id, title, now),
        )
    return conversation_id


def update_conversation_title(user_id: str, conversation_id: str, title: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE conversations SET title = ? WHERE id = ? AND user_id = ?",
            (title, conversation_id, user_id),
        )


def append_message(user_id: str, conversation_id: str, role: str, content: str) -> None:
    now = datetime.now(UTC).isoformat()
    with _connect() as conn:
        convo = conn.execute(
            "SELECT 1 FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        ).fetchone()
        if not convo:
            raise ValueError("Conversation not found or access denied")
        conn.execute(
            "INSERT INTO messages(conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (conversation_id, role, content, now),
        )


def list_conversations(user_id: str, limit: Optional[int] = None) -> List[Dict[str, str]]:
    query = (
        "SELECT id, title, created_at FROM conversations WHERE user_id = ? "
        "ORDER BY created_at DESC, id DESC"
    )
    params: tuple[object, ...]
    if limit:
        query += " LIMIT ?"
        params = (user_id, limit)
    else:
        params = (user_id,)

    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()

    return [dict(row) for row in rows]


def get_conversation(user_id: str, conversation_id: str) -> Optional[Dict[str, object]]:
    with _connect() as conn:
        convo_row = conn.execute(
            "SELECT id, title, created_at FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        ).fetchone()
        if not convo_row:
            return None
        message_rows = conn.execute(
            "SELECT role, content, created_at FROM messages WHERE conversation_id = ? ORDER BY id",
            (conversation_id,),
        ).fetchall()

    conversation = dict(convo_row)
    conversation["messages"] = [dict(row) for row in message_rows]
    return conversation


def delete_conversation(user_id: str, conversation_id: str) -> None:
    with _connect() as conn:
        conn.execute(
            "DELETE FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        )
