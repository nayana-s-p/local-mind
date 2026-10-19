"""Bounded, read-only filesystem adapter for filename discovery."""

from __future__ import annotations

import os
import stat
import threading
import time
from pathlib import Path

from localmind.domain.files import FileEntry, ScanReport, WorkspaceError

MAX_RESULTS = 100
MAX_ENTRIES = 10_000
MAX_DEPTH = 12
MAX_SECONDS = 4.0


def _is_inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


class FilesystemScanner:
    """Read names and directory metadata; never opens file contents.

    Paths are canonicalized and symlink entries are skipped. Standard-library
    path checks are not a substitute for handle-based, race-resistant OS
    confinement; the caller must treat this as a bounded prototype adapter.
    """

    def scan(
        self,
        workspace: str,
        *,
        query: str = "",
        pdf_only: bool = False,
        cancel_event: threading.Event,
    ) -> ScanReport:
        selected = Path(workspace).expanduser()
        try:
            root = selected.resolve(strict=True)
            root_stat = root.stat()
        except OSError as exc:
            raise WorkspaceError("The selected workspace is unavailable.") from exc
        if not root.is_dir():
            raise WorkspaceError("Choose an existing folder as the workspace.")

        needle = query.strip().casefold()
        started = time.monotonic()
        stop_at = started + MAX_SECONDS
        directories: list[tuple[Path, int]] = [(root, 0)]
        matches: list[FileEntry] = []
        entries_seen = 0
        unreadable = 0
        truncated = False
        cancelled = False

        while directories:
            if cancel_event.is_set():
                cancelled = True
                break
            if time.monotonic() >= stop_at:
                truncated = True
                break

            directory, depth = directories.pop()
            try:
                # Recheck queued folders before traversing. This is still a
                # path-based check and cannot eliminate every TOCTOU race.
                directory_stat = os.lstat(directory)
                if stat.S_ISLNK(directory_stat.st_mode) or not stat.S_ISDIR(directory_stat.st_mode):
                    continue
                resolved_directory = directory.resolve(strict=True)
                if not _is_inside(resolved_directory, root):
                    truncated = True
                    continue
                if directory_stat.st_dev != root_stat.st_dev:
                    truncated = True
                    continue
                with os.scandir(directory) as iterator:
                    for entry in iterator:
                        if cancel_event.is_set():
                            cancelled = True
                            break
                        if time.monotonic() >= stop_at:
                            truncated = True
                            break
                        if entries_seen >= MAX_ENTRIES:
                            truncated = True
                            break
                        entries_seen += 1
                        try:
                            if entry.is_symlink():
                                continue
                            if entry.is_dir(follow_symlinks=False):
                                if depth < MAX_DEPTH:
                                    candidate = Path(entry.path)
                                    resolved = candidate.resolve(strict=True)
                                    if _is_inside(resolved, root):
                                        child_stat = entry.stat(follow_symlinks=False)
                                        if child_stat.st_dev == root_stat.st_dev:
                                            directories.append((candidate, depth + 1))
                                        else:
                                            truncated = True
                                    else:
                                        truncated = True
                                else:
                                    truncated = True
                                continue
                            if not entry.is_file(follow_symlinks=False):
                                continue
                            name = entry.name
                            extension = Path(name).suffix.lower()
                            is_pdf = extension == ".pdf"
                            if pdf_only and not is_pdf:
                                continue
                            if needle and needle not in name.casefold():
                                continue
                            file_path = Path(entry.path)
                            resolved_file = file_path.resolve(strict=True)
                            if not _is_inside(resolved_file, root):
                                continue
                            if len(matches) >= MAX_RESULTS:
                                truncated = True
                                break
                            matches.append(
                                FileEntry(
                                    name=name,
                                    relative_path=file_path.relative_to(root).as_posix(),
                                    extension=extension,
                                    is_pdf=is_pdf,
                                )
                            )
                        except (OSError, ValueError):
                            # Skip entries that disappear or change during the
                            # read-only scan; no content access is attempted.
                            continue
                if truncated or cancelled:
                    break
            except OSError:
                unreadable += 1

        matches.sort(key=lambda item: (item.relative_path.casefold(), item.relative_path))
        return ScanReport(
            files=tuple(matches),
            entries_seen=entries_seen,
            truncated=truncated,
            cancelled=cancelled,
            unreadable_directories=unreadable,
            duration_seconds=max(0.0, time.monotonic() - started),
        )

