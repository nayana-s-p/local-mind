"""Immutable, reviewable file operations and execution results."""

from dataclasses import dataclass

from localmind.domain.assistant import AssistantError, OrganizationStrategy


class OrganizationError(AssistantError):
    pass


@dataclass(frozen=True, slots=True)
class FileIdentity:
    device: int
    inode: int
    size: int
    modified_ns: int


@dataclass(frozen=True, slots=True)
class PhotoMove:
    source: str
    destination: str
    identity: FileIdentity


@dataclass(frozen=True, slots=True)
class PhotoPlan:
    id: str
    workspace: str
    strategy: OrganizationStrategy
    moves: tuple[PhotoMove, ...]
    fallback_dates: int
    skipped: int
    entries_checked: int


@dataclass(frozen=True, slots=True)
class OrganizationResult:
    operation_id: str
    completed: int
    total: int
    cancelled: bool = False
    error: str = ""
