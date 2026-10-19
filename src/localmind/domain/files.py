"""File discovery value objects and errors."""

from __future__ import annotations

from dataclasses import dataclass


class WorkspaceError(ValueError):
    """Raised when the selected workspace cannot be scanned."""


class FileRevealError(RuntimeError):
    """Raised when a workspace file cannot safely be revealed."""


@dataclass(frozen=True, slots=True)
class FileEntry:
    name: str
    relative_path: str
    extension: str
    is_pdf: bool


@dataclass(frozen=True, slots=True)
class ScanReport:
    files: tuple[FileEntry, ...]
    entries_seen: int
    truncated: bool
    cancelled: bool
    unreadable_directories: int
    duration_seconds: float

    @property
    def partial(self) -> bool:
        return self.truncated or self.unreadable_directories > 0

