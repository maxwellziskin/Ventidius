"""Store and retrieve raw Gmail messages in the database."""

import logging
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from .models import RawMessage

logger = logging.getLogger(__name__)


def upsert_raw_message(conn: sqlite3.Connection, msg: RawMessage) -> Optional[int]:
    """Insert raw message; return row id, or None if already exists."""
    existing = conn.execute(
        "SELECT id, parse_status FROM raw_messages WHERE gmail_message_id = ?",
        (msg.gmail_message_id,),
    ).fetchone()

    if existing:
        logger.debug("Message %s already in DB (status=%s)", msg.gmail_message_id, existing["parse_status"])
        return None  # Signal: already stored

    cursor = conn.execute(
        """
        INSERT INTO raw_messages
            (gmail_message_id, gmail_thread_id, sender, subject, snippet,
             received_at, raw_html, raw_text, parse_status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', datetime('now'))
        """,
        (
            msg.gmail_message_id,
            msg.gmail_thread_id,
            msg.sender,
            msg.subject,
            msg.snippet,
            msg.received_at,
            msg.raw_html,
            msg.raw_text,
        ),
    )
    row_id = cursor.lastrowid
    logger.debug("Stored new raw message id=%d gmail_id=%s", row_id, msg.gmail_message_id)
    return row_id


def mark_parse_success(conn: sqlite3.Connection, raw_message_id: int) -> None:
    conn.execute(
        """
        UPDATE raw_messages
        SET parse_status = 'success', processed_at = datetime('now'), parse_error = NULL
        WHERE id = ?
        """,
        (raw_message_id,),
    )


def mark_parse_failed(conn: sqlite3.Connection, raw_message_id: int, error: str) -> None:
    conn.execute(
        """
        UPDATE raw_messages
        SET parse_status = 'failed', processed_at = datetime('now'), parse_error = ?
        WHERE id = ?
        """,
        (error[:2000], raw_message_id),
    )


def mark_parse_partial(conn: sqlite3.Connection, raw_message_id: int, note: str) -> None:
    conn.execute(
        """
        UPDATE raw_messages
        SET parse_status = 'partial', processed_at = datetime('now'), parse_error = ?
        WHERE id = ?
        """,
        (note[:2000], raw_message_id),
    )


def get_pending_messages(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM raw_messages WHERE parse_status = 'pending' ORDER BY received_at ASC"
    ).fetchall()


def get_failed_messages(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM raw_messages WHERE parse_status IN ('failed', 'partial') ORDER BY received_at ASC"
    ).fetchall()


def get_message_by_id(conn: sqlite3.Connection, row_id: int) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM raw_messages WHERE id = ?", (row_id,)).fetchone()


def get_message_by_gmail_id(conn: sqlite3.Connection, gmail_id: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM raw_messages WHERE gmail_message_id = ?", (gmail_id,)
    ).fetchone()


def reset_message_for_reparse(conn: sqlite3.Connection, row_id: int) -> None:
    conn.execute(
        "UPDATE raw_messages SET parse_status = 'pending', parse_error = NULL, processed_at = NULL WHERE id = ?",
        (row_id,),
    )
