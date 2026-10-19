"""Versioned, Qt-free conversation and audit storage boundaries."""

from dataclasses import dataclass
from typing import Literal

MessageRole = Literal["user", "assistant"]


class HistoryError(RuntimeError):
    """Storage could not safely complete; existing data is never reset."""


@dataclass(frozen=True, slots=True)
class StoredMessage:
    id: str
    role: MessageRole
    text: str
    created_at: float


@dataclass(frozen=True, slots=True)
class ConversationSummary:
    id: str
    title: str
    created_at: float
    updated_at: float
    message_count: int


@dataclass(frozen=True, slots=True)
class HistorySnapshot:
    conversation_id: str
    messages: tuple[StoredMessage, ...]
    context: dict[str, str]
    conversations: tuple[ConversationSummary, ...]
    retention_days: int
