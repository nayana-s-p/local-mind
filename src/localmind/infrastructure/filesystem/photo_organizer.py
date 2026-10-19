"""Previewed, scoped photo moves with a durable write-ahead undo journal."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import stat
import threading
import time
import warnings
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime
from pathlib import Path, PurePosixPath
from uuid import uuid4

from localmind.domain.assistant import OrganizationStrategy, TaskCancelled
from localmind.domain.organization import (
    FileIdentity,
    OrganizationError,
    OrganizationResult,
    PhotoMove,
    PhotoPlan,
)

IMAGE_EXTENSIONS = frozenset({
    ".jpg", ".jpeg", ".jpe", ".png", ".webp", ".tif", ".tiff", ".gif",
    ".bmp", ".heic", ".heif", ".avif", ".dng",
})
OUTPUT_FOLDER = "Organized Photos"
MAX_ENTRIES = 150_000
MAX_PHOTOS = 50_000
MAX_DEPTH = 32
MAX_PREVIEW_SECONDS = 120


def identity(path: Path) -> FileIdentity:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise OrganizationError("An image changed into a link or non-file. Prepare a new preview.")
    return FileIdentity(info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)


def workspace_root(workspace: str) -> Path:
    if not workspace:
        raise OrganizationError("Choose the folder containing the images first.")
    try:
        root = Path(workspace).expanduser().resolve(strict=True)
        if not root.is_dir():
            raise OSError("Not a directory")
        return root
    except (OSError, ValueError) as exc:
        raise OrganizationError("The selected folder is unavailable. Choose an existing local folder.") from exc


def checked_path(root: Path, relative: str) -> Path:
    parts = PurePosixPath(relative).parts
    if not parts or PurePosixPath(relative).is_absolute() or any(p in {"..", "."} or "\\" in p or ":" in p for p in parts):
        raise OrganizationError("An operation contains an invalid relative path.")
    candidate = root.joinpath(*parts)
    current = root
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise OrganizationError("A folder or image is a symbolic link. Nothing outside the selected folder is allowed.")
        if current != candidate and current.exists() and not current.is_dir():
            raise OrganizationError("An output folder path is occupied by a file. Nothing was replaced.")
    try:
        candidate.resolve().relative_to(root)
    except (ValueError, OSError) as exc:
        raise OrganizationError("An image path no longer belongs to the selected folder.") from exc
    return candidate


class FilesystemPhotoOrganizer:
    def __init__(self, journal_directory: Path) -> None:
        self._journal_directory = journal_directory

    def preview(
        self, workspace: str, strategy: OrganizationStrategy,
        cancel_event: threading.Event, progress: Callable[[str], None],
    ) -> PhotoPlan:
        root = workspace_root(workspace)
        root_device = root.stat().st_dev
        started = time.monotonic()
        files: list[tuple[str, FileIdentity]] = []
        directories = [(root, 0)]
        entries = skipped = 0
        while directories:
            self._check_preview(cancel_event, started)
            directory, depth = directories.pop()
            try:
                relative_directory = directory.relative_to(root).as_posix()
                if directory != root:
                    checked_path(root, relative_directory)
                with os.scandir(directory) as iterator:
                    for entry in iterator:
                        self._check_preview(cancel_event, started)
                        entries += 1
                        if entries > MAX_ENTRIES:
                            raise OrganizationError("This folder has more than 150,000 entries. Choose a smaller photo folder.")
                        if entry.is_symlink():
                            skipped += 1
                            continue
                        try:
                            if entry.is_dir(follow_symlinks=False):
                                if directory == root and entry.name.casefold() == OUTPUT_FOLDER.casefold():
                                    continue
                                if depth >= MAX_DEPTH:
                                    raise OrganizationError("This folder is nested too deeply. Choose a smaller photo folder.")
                                if entry.stat(follow_symlinks=False).st_dev != root_device:
                                    skipped += 1
                                    continue
                                directories.append((Path(entry.path), depth + 1))
                            elif entry.is_file(follow_symlinks=False) and Path(entry.name).suffix.lower() in IMAGE_EXTENSIONS:
                                path = Path(entry.path)
                                relative = path.relative_to(root).as_posix()
                                checked_path(root, relative)
                                info = identity(path)
                                if info.device != root_device:
                                    skipped += 1
                                    continue
                                files.append((relative, info))
                                if len(files) > MAX_PHOTOS:
                                    raise OrganizationError("There are more than 50,000 images. Select a smaller folder and organize it in batches.")
                        except OSError:
                            skipped += 1
                        if entries % 200 == 0:
                            progress(f"Looking through your folder · {entries:,} entries · {len(files):,} images")
            except OSError:
                skipped += 1
        moves = []
        fallback_dates = 0
        reserved: set[str] = set()
        existing_names: dict[str, set[str]] = {}
        for position, (relative, original_identity) in enumerate(sorted(files)):
            self._check_preview(cancel_event, started)
            path = checked_path(root, relative)
            if strategy == "type":
                extension = path.suffix.lstrip(".").upper()
                group = "JPEG" if extension in {"JPG", "JPE", "JPEG"} else extension
            else:
                taken = self._date_taken(path)
                if taken is None:
                    taken = datetime.fromtimestamp(original_identity.modified_ns / 1e9)
                    fallback_dates += 1
                group = taken.strftime("%Y/%m" if strategy == "month" else "%Y")
            folder = f"{OUTPUT_FOLDER}/{group}"
            parent = checked_path(root, folder)
            if folder not in existing_names:
                try:
                    existing_names[folder] = {item.name.casefold() for item in parent.iterdir()} if parent.exists() else set()
                except OSError as exc:
                    raise OrganizationError("An output folder cannot be read. Check its permissions before trying again.") from exc
            name = path.name
            counter = 1
            while f"{folder}/{name}".casefold() in reserved or name.casefold() in existing_names[folder]:
                counter += 1
                name = f"{path.stem} ({counter}){path.suffix}"
            destination = f"{folder}/{name}"
            checked_path(root, destination)
            reserved.add(destination.casefold())
            moves.append(PhotoMove(relative, destination, original_identity))
            if position % 100 == 0:
                progress(f"Preparing your preview · {position + 1:,} of {len(files):,} images")
        return PhotoPlan(str(uuid4()), str(root), strategy, tuple(moves), fallback_dates, skipped, entries)

    @staticmethod
    def _check_preview(cancel_event: threading.Event, started: float) -> None:
        if cancel_event.is_set():
            raise TaskCancelled("Preview cancelled. No files were changed.")
        if time.monotonic() - started > MAX_PREVIEW_SECONDS:
            raise OrganizationError("The preview took longer than two minutes. Choose a smaller folder; no images were moved.")

    @staticmethod
    def _date_taken(path: Path) -> datetime | None:
        from PIL import Image
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(path) as image:
                    exif = image.getexif()
                    original = exif.get_ifd(34665) if 34665 in exif else {}
                    for value in (original.get(36867), original.get(36868), exif.get(36867), exif.get(306)):
                        if value:
                            try:
                                return datetime.strptime(str(value)[:19], "%Y:%m:%d %H:%M:%S")
                            except (ValueError, TypeError):
                                continue
        except (OSError, ValueError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            pass
        return None

    def _connect(self) -> sqlite3.Connection:
        self._journal_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        db = sqlite3.connect(self._journal_directory / "photo-operations.sqlite3")
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA foreign_keys=ON")
        if db.execute("PRAGMA user_version").fetchone()[0] > 1:
            db.close()
            raise OrganizationError("The undo journal was created by a newer app version.")
        db.executescript("""
            CREATE TABLE IF NOT EXISTS operations (
                id TEXT PRIMARY KEY, root TEXT NOT NULL, state TEXT NOT NULL, created REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS moves (
                operation TEXT NOT NULL REFERENCES operations(id), position INTEGER NOT NULL,
                source TEXT NOT NULL, destination TEXT NOT NULL, identity TEXT NOT NULL,
                state TEXT NOT NULL, PRIMARY KEY (operation, position)
            );
            CREATE TABLE IF NOT EXISTS directories (
                operation TEXT NOT NULL REFERENCES operations(id), path TEXT NOT NULL,
                PRIMARY KEY (operation, path)
            );
            PRAGMA user_version=1;
        """)
        return db

    @contextmanager
    def _locked_journal(self, root: Path):
        from filelock import FileLock, Timeout
        self._journal_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        root_info = root.stat()
        # Path aliases (/var vs /private/var on macOS, or case variants)
        # must serialize against the same directory, not just the same string.
        key = hashlib.sha256(f"{root_info.st_dev}:{root_info.st_ino}".encode()).hexdigest()
        try:
            with FileLock(str(self._journal_directory / f"{key}.lock"), timeout=0):
                db = self._connect()
                try:
                    yield db
                finally:
                    db.close()
        except Timeout as exc:
            raise OrganizationError("Another photo operation is using this folder. Wait for it to finish.") from exc

    @staticmethod
    def _validate_source(root: Path, move: PhotoMove) -> None:
        try:
            if identity(checked_path(root, move.source)) != move.identity:
                raise OrganizationError("An image changed since the preview. Prepare a new preview before organizing.")
        except OSError as exc:
            raise OrganizationError("An image is no longer available. Prepare a new preview.") from exc

    @staticmethod
    def _make_parents(root: Path, relative: str, db: sqlite3.Connection, operation_id: str) -> None:
        for parent in reversed(PurePosixPath(relative).parents):
            if str(parent) == ".":
                continue
            path = checked_path(root, str(parent))
            if not path.exists():
                path.mkdir()
                db.execute("INSERT OR IGNORE INTO directories VALUES (?, ?)", (operation_id, str(parent)))
                db.commit()
            elif not path.is_dir():
                raise OrganizationError("An output path is occupied by a file. Nothing was replaced.")

    @staticmethod
    def _move_without_replacing(source: Path, destination: Path, expected: FileIdentity) -> None:
        # A hard link followed by unlink is a same-filesystem move with exclusive
        # destination creation. Unlike POSIX rename(), it cannot replace a file.
        if identity(source) != expected:
            raise OrganizationError("An image changed while the operation was running.")
        os.link(source, destination, follow_symlinks=False)
        if identity(destination) != expected or identity(source) != expected:
            raise OrganizationError("An image changed during the move. Use Undo to recover this operation.")
        source.unlink()

    def execute(
        self, plan: PhotoPlan, cancel_event: threading.Event, progress: Callable[[str], None],
    ) -> OrganizationResult:
        root = workspace_root(plan.workspace)
        total = len(plan.moves)
        if not total:
            return OrganizationResult(plan.id, 0, 0)
        with self._locked_journal(root) as db:
            unresolved = db.execute(
                "SELECT 1 FROM operations WHERE root=? AND state IN ('applying','partial','undoing') LIMIT 1",
                (str(root),),
            ).fetchone()
            if unresolved:
                raise OrganizationError("Undo the previous interrupted photo operation before starting another.")
            destinations: set[str] = set()
            for move in plan.moves:
                if cancel_event.is_set():
                    raise TaskCancelled("Organization cancelled before any images were moved.")
                self._validate_source(root, move)
                if not move.destination.startswith(OUTPUT_FOLDER + "/"):
                    raise OrganizationError("The destination is outside the approved photo output folder.")
                destination = checked_path(root, move.destination)
                key = move.destination.casefold()
                if os.path.lexists(destination) or key in destinations:
                    raise OrganizationError("A destination changed since the preview. Prepare a new preview; nothing was replaced.")
                destinations.add(key)
            db.execute("INSERT INTO operations VALUES (?, ?, 'applying', ?)", (plan.id, str(root), time.time()))
            db.executemany(
                "INSERT INTO moves VALUES (?, ?, ?, ?, ?, 'pending')",
                [(plan.id, i, move.source, move.destination, json.dumps(asdict(move.identity))) for i, move in enumerate(plan.moves)],
            )
            db.commit()
            completed = 0
            error = ""
            try:
                for i, move in enumerate(plan.moves):
                    if cancel_event.is_set():
                        break
                    self._validate_source(root, move)
                    self._make_parents(root, move.destination, db, plan.id)
                    source = checked_path(root, move.source)
                    destination = checked_path(root, move.destination)
                    db.execute("UPDATE moves SET state='moving' WHERE operation=? AND position=?", (plan.id, i))
                    db.commit()  # Durable intent before either filesystem change.
                    self._move_without_replacing(source, destination, move.identity)
                    db.execute("UPDATE moves SET state='moved' WHERE operation=? AND position=?", (plan.id, i))
                    db.commit()
                    completed += 1
                    if completed % 20 == 0 or completed == total:
                        progress(f"Organizing images · {completed:,} of {total:,} moved")
            except (OSError, OrganizationError) as exc:
                error = str(exc) if isinstance(exc, OrganizationError) else (
                    "A move could not finish. Check permissions and that this disk supports hard links. "
                    "Use Undo to restore the completed moves."
                )
            state = "completed" if completed == total else "partial"
            db.execute("UPDATE operations SET state=? WHERE id=?", (state, plan.id))
            db.commit()
            return OrganizationResult(plan.id, completed, total, cancel_event.is_set() and completed < total, error)

    def undo(
        self, workspace: str, cancel_event: threading.Event, progress: Callable[[str], None],
    ) -> OrganizationResult:
        root = workspace_root(workspace)
        with self._locked_journal(root) as db:
            record = db.execute(
                "SELECT id FROM operations WHERE root=? AND state != 'undone' ORDER BY created DESC LIMIT 1",
                (str(root),),
            ).fetchone()
            if record is None:
                raise OrganizationError("There is no photo organization to undo in this folder.")
            operation_id = record[0]
            rows = db.execute(
                "SELECT position, source, destination, identity FROM moves "
                "WHERE operation=? AND state IN ('moving','moved','undoing') ORDER BY position DESC",
                (operation_id,),
            ).fetchall()
            db.execute("UPDATE operations SET state='undoing' WHERE id=?", (operation_id,))
            db.commit()
            completed = 0
            error = ""
            try:
                for position, original, organized, saved_identity in rows:
                    if cancel_event.is_set():
                        break
                    source = checked_path(root, original)
                    destination = checked_path(root, organized)
                    expected = FileIdentity(**json.loads(saved_identity))
                    db.execute("UPDATE moves SET state='undoing' WHERE operation=? AND position=?", (operation_id, position))
                    db.commit()
                    if destination.exists():
                        if identity(destination) != expected:
                            raise OrganizationError("Undo paused: an organized image has been edited or replaced. It was left untouched.")
                        if os.path.lexists(source):
                            if identity(source) != expected:
                                raise OrganizationError("Undo paused: an original filename is occupied. Nothing was replaced.")
                            # Recover a crash between exclusive link and unlink.
                            destination.unlink()
                        else:
                            self._make_parents(root, original, db, operation_id)
                            self._move_without_replacing(destination, source, expected)
                    elif not source.exists() or identity(source) != expected:
                        raise OrganizationError("Undo paused: an image is missing or changed. Restore it before retrying.")
                    db.execute("UPDATE moves SET state='undone' WHERE operation=? AND position=?", (operation_id, position))
                    db.commit()
                    completed += 1
                    if completed % 20 == 0 or completed == len(rows):
                        progress(f"Restoring original folders · {completed:,} of {len(rows):,} images")
            except (OSError, OrganizationError) as exc:
                error = str(exc) if isinstance(exc, OrganizationError) else "Undo paused because a file or folder could not be accessed. Check permissions and retry."
            finished = completed == len(rows)
            if finished:
                for (relative,) in sorted(
                    db.execute("SELECT path FROM directories WHERE operation=?", (operation_id,)).fetchall(),
                    key=lambda item: len(PurePosixPath(item[0]).parts), reverse=True,
                ):
                    try:
                        checked_path(root, relative).rmdir()  # Empty directories created by this operation only.
                    except (OSError, OrganizationError):
                        pass
                db.execute("UPDATE operations SET state='undone' WHERE id=?", (operation_id,))
                db.commit()
            return OrganizationResult(operation_id, completed, len(rows), cancel_event.is_set() and not finished, error)
