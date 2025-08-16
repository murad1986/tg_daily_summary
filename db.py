from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Generator, List, Optional


DATABASE_PATH = os.environ.get("SQLITE_DB_PATH", os.path.abspath("chat_logs.db"))


def _ensure_parent_dir_exists(path: str) -> None:
    parent = os.path.dirname(path)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    _ensure_parent_dir_exists(DATABASE_PATH)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def initialize_database() -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        
        # Создаём таблицу messages без message_thread_id если её нет
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                user_name TEXT,
                message_text TEXT NOT NULL,
                timestamp DATETIME NOT NULL
            );
            """
        )
        
        # Проверяем, есть ли колонка message_thread_id
        cur.execute("PRAGMA table_info(messages);")
        columns = [row[1] for row in cur.fetchall()]
        
        if 'message_thread_id' not in columns:
            # Добавляем колонку message_thread_id если её нет
            cur.execute("ALTER TABLE messages ADD COLUMN message_thread_id INTEGER;")
            print("Добавлена колонка message_thread_id в таблицу messages")
        
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_messages_chat_time
            ON messages(chat_id, timestamp);
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_messages_chat_thread_time
            ON messages(chat_id, message_thread_id, timestamp);
            """
        )
        conn.commit()


@dataclass
class ChatMessage:
    id: int
    chat_id: int
    message_thread_id: Optional[int]
    user_name: Optional[str]
    message_text: str
    timestamp: datetime


def add_message(chat_id: int, user_name: Optional[str], message_text: str, timestamp: datetime, message_thread_id: Optional[int] = None) -> None:
    iso_time = timestamp.astimezone(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO messages (chat_id, message_thread_id, user_name, message_text, timestamp) VALUES (?, ?, ?, ?, ?)",
            (chat_id, message_thread_id, user_name, message_text, iso_time),
        )
        conn.commit()


def get_messages_for_chat_since(chat_id: int, since_time: datetime, message_thread_id: Optional[int] = None) -> List[ChatMessage]:
    since_iso = since_time.astimezone(timezone.utc).isoformat()
    with get_connection() as conn:
        if message_thread_id is not None:
            rows = conn.execute(
                "SELECT id, chat_id, message_thread_id, user_name, message_text, timestamp FROM messages WHERE chat_id = ? AND message_thread_id = ? AND timestamp >= ? ORDER BY timestamp ASC",
                (chat_id, message_thread_id, since_iso),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, chat_id, message_thread_id, user_name, message_text, timestamp FROM messages WHERE chat_id = ? AND timestamp >= ? ORDER BY timestamp ASC",
                (chat_id, since_iso),
            ).fetchall()
    messages: List[ChatMessage] = []
    for r in rows:
        ts = _parse_ts(r["timestamp"])  # type: ignore[index]
        messages.append(
            ChatMessage(
                id=int(r["id"]),  # type: ignore[index]
                chat_id=int(r["chat_id"]),  # type: ignore[index]
                message_thread_id=(int(r["message_thread_id"]) if r["message_thread_id"] is not None else None),  # type: ignore[index]
                user_name=(r["user_name"] if r["user_name"] is not None else None),  # type: ignore[index]
                message_text=str(r["message_text"]),  # type: ignore[index]
                timestamp=ts,
            )
        )
    return messages


def get_active_chat_ids_since(since_time: datetime) -> List[int]:
    since_iso = since_time.astimezone(timezone.utc).isoformat()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT chat_id FROM messages WHERE timestamp >= ? ORDER BY chat_id",
            (since_iso,),
        ).fetchall()
    return [int(r[0]) for r in rows]


def get_active_thread_ids_for_chat_since(chat_id: int, since_time: datetime) -> List[Optional[int]]:
    """Получить список активных тем (thread_id) в чате за период."""
    since_iso = since_time.astimezone(timezone.utc).isoformat()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT message_thread_id FROM messages WHERE chat_id = ? AND timestamp >= ? ORDER BY message_thread_id",
            (chat_id, since_iso),
        ).fetchall()
    return [int(r[0]) if r[0] is not None else None for r in rows]


def delete_messages_older_than(days: int) -> int:
    threshold = datetime.now(timezone.utc) - timedelta(days=days)
    threshold_iso = threshold.isoformat()
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM messages WHERE timestamp < ?", (threshold_iso,))
        conn.commit()
        return cur.rowcount


def _parse_ts(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
