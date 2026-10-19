"""Versioned SQLite conversation storage. All callers use a serialized worker."""

from __future__ import annotations

import json
import re
import sqlite3
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from localmind.domain.history import (
    ConversationSummary,
    HistoryError,
    HistorySnapshot,
    MessageRole,
    StoredMessage,
)
from localmind.domain.organization import PhotoPlan
from localmind.domain.tasks import FilePlan

SCHEMA_VERSION = 1
MAX_CONVERSATIONS = 100
MAX_MESSAGES = 1000
CONTEXT_KEYS = frozenset({"workspace", "last_tool", "last_plan_id"})


def redact(text: str) -> str:
    """Mask recognizable credentials, not arbitrary secrets in free-form prose."""
    text = re.sub(r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----", "[REDACTED PRIVATE KEY]", text, flags=re.DOTALL)
    text = re.sub(r"\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16})\b", "[REDACTED TOKEN]", text)
    text = re.sub(
        r"""(?i)(\b(?:password|passwd|api[_ -]?key|secret|access[_ -]?token|authorization)\b\s*[:=]\s*)(?:"[^"]*"|'[^']*'|[^\s,;]+)""",
        r"\1[REDACTED]", text,
    )
    text = re.sub(r"(?i)(\bbearer\s+)[A-Za-z0-9._~+/-]{8,}", r"\1[REDACTED]", text)
    return text


SCHEMA = """
BEGIN IMMEDIATE;
CREATE TABLE conversations (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL
);
CREATE TABLE messages (
    id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK(role IN ('user','assistant')), text TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE INDEX messages_conversation_time ON messages(conversation_id, created_at);
CREATE INDEX conversations_updated ON conversations(updated_at);
CREATE TABLE contexts (
    conversation_id TEXT PRIMARY KEY REFERENCES conversations(id) ON DELETE CASCADE,
    payload TEXT NOT NULL, updated_at REAL NOT NULL
);
CREATE TABLE action_plans (
    id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    payload TEXT NOT NULL, state TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE INDEX plans_conversation_time ON action_plans(conversation_id, created_at);
CREATE TABLE approvals (
    id TEXT PRIMARY KEY, plan_id TEXT NOT NULL REFERENCES action_plans(id) ON DELETE CASCADE,
    approved INTEGER NOT NULL CHECK(approved IN (0,1)), source TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TABLE execution_events (
    id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    plan_id TEXT REFERENCES action_plans(id) ON DELETE SET NULL,
    kind TEXT NOT NULL, outcome TEXT NOT NULL, summary TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE INDEX events_conversation_time ON execution_events(conversation_id, created_at);
CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
INSERT INTO settings VALUES ('retention_days','30');
PRAGMA user_version=1;
COMMIT;
"""


class SQLiteConversationRepository:
    def __init__(self, path: Path, clock: Callable[[], float] = time.time) -> None:
        self.path = path
        self._clock = clock

    @contextmanager
    def _connection(self, *, migrate: bool = False) -> Iterator[sqlite3.Connection]:
        db = None
        try:
            self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            if self.path.is_symlink():
                raise HistoryError("The history database is a symbolic link. Choose a regular application storage location.")
            db = sqlite3.connect(self.path, timeout=3)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                raise HistoryError("History was created by a newer LocalMind version. It was left unchanged.")
            if version == 0 and migrate:
                tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                if tables:
                    raise HistoryError("The history database has an unknown schema. It was left unchanged.")
                db.execute("PRAGMA journal_mode=WAL")
                db.execute("PRAGMA synchronous=FULL")
                db.executescript(SCHEMA)
            elif version != SCHEMA_VERSION:
                raise HistoryError("History is not initialized. Restart LocalMind to retry storage setup.")
            yield db
            db.commit()
        except HistoryError:
            if db is not None:
                db.rollback()
            raise
        except (sqlite3.Error, OSError, ValueError, TypeError) as exc:
            if db is not None:
                db.rollback()
            raise HistoryError("Local history could not be read or saved. Check app storage permissions and disk space; existing data was not reset.") from exc
        finally:
            if db is not None:
                db.close()

    def _summaries(self, db: sqlite3.Connection) -> tuple[ConversationSummary, ...]:
        rows = db.execute(
            "SELECT c.*, (SELECT COUNT(*) FROM messages m WHERE m.conversation_id=c.id) AS message_count "
            "FROM conversations c ORDER BY updated_at DESC, rowid DESC LIMIT ?", (MAX_CONVERSATIONS,),
        ).fetchall()
        return tuple(ConversationSummary(row["id"], row["title"], row["created_at"], row["updated_at"], row["message_count"]) for row in rows)

    def _snapshot(self, db: sqlite3.Connection, conversation_id: str) -> HistorySnapshot:
        if not db.execute("SELECT 1 FROM conversations WHERE id=?", (conversation_id,)).fetchone():
            raise HistoryError("That conversation is no longer available.")
        rows = db.execute(
            "SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at DESC, rowid DESC LIMIT 100",
            (conversation_id,),
        ).fetchall()
        messages = tuple(StoredMessage(row["id"], row["role"], row["text"], row["created_at"]) for row in reversed(rows))
        context_row = db.execute("SELECT payload FROM contexts WHERE conversation_id=?", (conversation_id,)).fetchone()
        context = json.loads(context_row[0]) if context_row else {}
        if not isinstance(context, dict) or any(key not in CONTEXT_KEYS or not isinstance(value, str) for key, value in context.items()):
            raise HistoryError("Stored conversation context is invalid. It was not restored.")
        days = int(db.execute("SELECT value FROM settings WHERE key='retention_days'").fetchone()[0])
        return HistorySnapshot(conversation_id, messages, context, self._summaries(db), days)

    def _new(self, db: sqlite3.Connection, welcome: str) -> str:
        conversation_id, now = str(uuid4()), self._clock()
        db.execute("INSERT INTO conversations VALUES (?, 'New conversation', ?, ?)", (conversation_id, now, now))
        self._append(db, conversation_id, "assistant", welcome)
        self._set_active(db, conversation_id)
        return conversation_id

    @staticmethod
    def _set_active(db: sqlite3.Connection, conversation_id: str) -> None:
        db.execute(
            "INSERT INTO settings VALUES ('active_conversation', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (conversation_id,),
        )

    def _prune(self, db: sqlite3.Connection) -> None:
        days = int(db.execute("SELECT value FROM settings WHERE key='retention_days'").fetchone()[0])
        if days not in {7, 30, 90, 365}:
            raise HistoryError("Stored retention policy is invalid. History was left unchanged.")
        cutoff = self._clock() - days * 86400
        db.execute("DELETE FROM messages WHERE created_at < ?", (cutoff,))
        db.execute("DELETE FROM execution_events WHERE created_at < ?", (cutoff,))
        db.execute("DELETE FROM action_plans WHERE created_at < ?", (cutoff,))
        db.execute("DELETE FROM contexts WHERE updated_at < ?", (cutoff,))
        db.execute("DELETE FROM conversations WHERE updated_at < ?", (cutoff,))
        db.execute(
            "DELETE FROM conversations WHERE id IN "
            "(SELECT id FROM conversations ORDER BY updated_at DESC, rowid DESC LIMIT -1 OFFSET ?)",
            (MAX_CONVERSATIONS,),
        )

    def initialize(self, welcome: str) -> HistorySnapshot:
        with self._connection(migrate=True) as db:
            self._prune(db)
            # Historical plans never carry authorization across process starts.
            db.execute("UPDATE action_plans SET state='expired' WHERE state IN ('awaiting_approval','approved')")
            row = db.execute(
                "SELECT id FROM conversations WHERE id=(SELECT value FROM settings WHERE key='active_conversation')"
            ).fetchone()
            if row is None:
                row = db.execute("SELECT id FROM conversations ORDER BY updated_at DESC, rowid DESC LIMIT 1").fetchone()
            conversation_id = row[0] if row else self._new(db, welcome)
            self._set_active(db, conversation_id)
            return self._snapshot(db, conversation_id)

    def open_conversation(self, conversation_id: str) -> HistorySnapshot:
        with self._connection() as db:
            snapshot = self._snapshot(db, conversation_id)
            self._set_active(db, conversation_id)
            return snapshot

    def new_conversation(self, welcome: str) -> HistorySnapshot:
        with self._connection() as db:
            conversation_id = self._new(db, welcome)
            self._prune(db)
            return self._snapshot(db, conversation_id)

    def _append(self, db: sqlite3.Connection, conversation_id: str, role: MessageRole, text: str) -> None:
        if role not in {"user", "assistant"}:
            raise HistoryError("Unsupported conversation role.")
        body, now = redact(text)[:8000], self._clock()
        db.execute("INSERT INTO messages VALUES (?, ?, ?, ?, ?)", (str(uuid4()), conversation_id, role, body, now))
        if role == "user":
            title = " ".join(body.split())[:64]
            db.execute("UPDATE conversations SET title=? WHERE id=? AND title='New conversation'", (title or "Conversation", conversation_id))
        db.execute("UPDATE conversations SET updated_at=? WHERE id=?", (now, conversation_id))
        db.execute(
            "DELETE FROM messages WHERE id IN (SELECT id FROM messages WHERE conversation_id=? "
            "ORDER BY created_at DESC, rowid DESC LIMIT -1 OFFSET ?)", (conversation_id, MAX_MESSAGES),
        )

    def append_message(self, conversation_id: str, role: MessageRole, text: str) -> tuple[ConversationSummary, ...]:
        with self._connection() as db:
            self._append(db, conversation_id, role, text)
            self._prune(db)
            return self._summaries(db)

    def save_context(self, conversation_id: str, context: dict[str, str]) -> None:
        if any(key not in CONTEXT_KEYS or not isinstance(value, str) or len(value) > 4096 for key, value in context.items()):
            raise HistoryError("Only bounded structured context references can be saved.")
        payload = json.dumps({key: redact(value) for key, value in context.items()})
        with self._connection() as db:
            db.execute(
                "INSERT INTO contexts VALUES (?, ?, ?) ON CONFLICT(conversation_id) "
                "DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at",
                (conversation_id, payload, self._clock()),
            )

    def save_plan(self, conversation_id: str, plan: PhotoPlan | FilePlan) -> None:
        if len(plan.moves) > 50_000:
            raise HistoryError("The plan exceeds the supported history size.")
        def sanitized(value):
            if isinstance(value, str):
                return redact(value)
            if isinstance(value, dict):
                return {key: sanitized(item) for key, item in value.items()}
            if isinstance(value, (list, tuple)):
                return [sanitized(item) for item in value]
            return value
        payload = json.dumps(sanitized(asdict(plan)), ensure_ascii=False)
        with self._connection() as db:
            db.execute("INSERT INTO action_plans VALUES (?, ?, ?, 'awaiting_approval', ?)", (plan.id, conversation_id, payload, self._clock()))

    def record_approval(self, conversation_id: str, plan_id: str, approved: bool, source: str) -> None:
        if source not in {"button", "chat", "discard"}:
            raise HistoryError("Approval must identify an explicit user control.")
        with self._connection() as db:
            if not db.execute("SELECT 1 FROM action_plans WHERE id=? AND conversation_id=?", (plan_id, conversation_id)).fetchone():
                raise HistoryError("The approved plan is not part of this conversation.")
            db.execute("INSERT INTO approvals VALUES (?, ?, ?, ?, ?)", (str(uuid4()), plan_id, int(approved), source, self._clock()))
            db.execute("UPDATE action_plans SET state=? WHERE id=?", ("approved" if approved else "denied", plan_id))

    def record_event(self, conversation_id: str, plan_id: str | None, kind: str, outcome: str, summary: str) -> None:
        with self._connection() as db:
            if plan_id and not db.execute("SELECT 1 FROM action_plans WHERE id=? AND conversation_id=?", (plan_id, conversation_id)).fetchone():
                plan_id = None  # Undo can refer to a plan whose chat was cleared.
            db.execute(
                "INSERT INTO execution_events VALUES (?, ?, ?, ?, ?, ?, ?)",
                (str(uuid4()), conversation_id, plan_id, kind[:100], outcome[:100], redact(summary)[:4000], self._clock()),
            )
            if plan_id:
                db.execute("UPDATE action_plans SET state=? WHERE id=?", (outcome[:100], plan_id))

    def clear(self, welcome: str) -> HistorySnapshot:
        with self._connection() as db:
            db.execute("DELETE FROM conversations")
            conversation_id = self._new(db, welcome)
            return self._snapshot(db, conversation_id)

    def set_retention(self, conversation_id: str, days: int) -> HistorySnapshot:
        if days not in {7, 30, 90, 365}:
            raise HistoryError("Choose a supported history retention period.")
        with self._connection() as db:
            db.execute("UPDATE settings SET value=? WHERE key='retention_days'", (str(days),))
            self._prune(db)
            if not db.execute("SELECT 1 FROM conversations WHERE id=?", (conversation_id,)).fetchone():
                row = db.execute("SELECT id FROM conversations ORDER BY updated_at DESC LIMIT 1").fetchone()
                conversation_id = row[0] if row else self._new(db, "History retention updated. Choose a workspace to continue.")
            self._set_active(db, conversation_id)
            return self._snapshot(db, conversation_id)
