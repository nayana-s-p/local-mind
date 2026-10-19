"""Version-one task, factual result, and immutable file preview contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from localmind.domain.organization import FileIdentity


class RiskLevel(StrEnum):
    READ_ONLY = "read_only"
    LOW = "low"
    WRITE = "write"


@dataclass(frozen=True, slots=True)
class TaskDefinition:
    task_id: str
    name: str
    description: str
    risk: RiskLevel
    requires_confirmation: bool
    parameters: tuple[str, ...]
    handler: str


@dataclass(frozen=True, slots=True)
class TaskRequest:
    task_id: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FileChange:
    source: str
    destination: str
    identity: FileIdentity | None = None
    kind: str = "move"
    content: str = ""


@dataclass(frozen=True, slots=True)
class FilePlan:
    id: str
    workspace: str
    moves: tuple[FileChange, ...]
    strategy: str = "files"
    skipped: int = 0
    root_identity: tuple[int, int] | None = None


@dataclass(frozen=True, slots=True)
class TaskResult:
    task_id: str
    success: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    suggestions: tuple[str, ...] = ()
    plan: FilePlan | None = None


@dataclass(frozen=True, slots=True)
class TaskBatchResult:
    results: tuple[TaskResult, ...]
