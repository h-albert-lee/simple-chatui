"""SQLite-backed conversation storage for the chat UI."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Dict, Iterable, List, Optional
from uuid import uuid4

from .config import settings

_DB_PATH = settings.database_path
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);
"""


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
    """Ensure that the SQLite schema exists."""

    with _connect() as conn:
        conn.executescript(_SCHEMA)


def create_conversation(title: str = "새로운 대화") -> str:
    """Create a new conversation and return its identifier."""

    conversation_id = str(uuid4())
    now = datetime.now(UTC).isoformat()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO conversations(id, title, created_at) VALUES (?, ?, ?)",
            (conversation_id, title, now),
        )
    return conversation_id


def update_conversation_title(conversation_id: str, title: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE conversations SET title = ? WHERE id = ?",
            (title, conversation_id),
        )


def append_message(conversation_id: str, role: str, content: str) -> None:
    now = datetime.now(UTC).isoformat()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO messages(conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (conversation_id, role, content, now),
        )


def list_conversations(limit: Optional[int] = None) -> List[Dict[str, str]]:
    query = "SELECT id, title, created_at FROM conversations ORDER BY created_at DESC, id DESC"
    if limit:
        query += " LIMIT ?"
        params: tuple[int, ...] = (limit,)
    else:
        params = tuple()

    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()

    return [dict(row) for row in rows]


def get_conversation(conversation_id: str) -> Optional[Dict[str, object]]:
    with _connect() as conn:
        convo_row = conn.execute(
            "SELECT id, title, created_at FROM conversations WHERE id = ?",
            (conversation_id,),
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


def delete_conversation(conversation_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
