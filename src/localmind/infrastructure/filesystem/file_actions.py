"""Preview-only general file actions and separately authorized exclusive commits."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from filelock import FileLock, Timeout

from localmind.domain.assistant import AssistantError, TaskCancelled
from localmind.domain.tasks import FileChange, FilePlan, TaskRequest, TaskResult
from localmind.infrastructure.filesystem.inspection import inventory
from localmind.infrastructure.filesystem.photo_organizer import (
    checked_path,
    identity,
    workspace_root,
)

OUTPUT = "Organized Files"


def available_destination(root: Path, relative: str, reserved: set[str], existing_names: dict[str, set[str]]) -> str:
    path = checked_path(root, relative)
    parent_key = str(path.parent)
    if parent_key not in existing_names:
        existing_names[parent_key] = {item.name.casefold() for item in path.parent.iterdir()} if path.parent.exists() else set()
    names = existing_names[parent_key]
    name = path.name
    index = 1
    while name.casefold() in names or str(path.with_name(name).relative_to(root)).casefold() in reserved:
        index += 1
        name = f"{path.stem} ({index}){path.suffix}"
    result = path.with_name(name).relative_to(root).as_posix()
    reserved.add(result.casefold())
    return result


class ScopedFileActions:
    def __init__(self, journal_directory: Path) -> None:
        self._directory = journal_directory

    def preview(self, request: TaskRequest, scope, event, progress) -> TaskResult:
        root = workspace_root(scope)
        task = request.task_id
        changes = []
        skipped = 0
        started = time.monotonic()
        if task in {"FM05", "FM15"}:
            _, files, _, _, exclusions, partial = inventory(str(root), event, progress)
            if partial:
                raise AssistantError("The folder exceeds scan limits. Choose a smaller folder before organizing.")
            reserved: set[str] = set()
            existing_names: dict[str, set[str]] = {}
            extension = request.parameters.get("extension", "").casefold()
            for item in sorted(files, key=lambda item: item["path"]):
                if event.is_set():
                    raise TaskCancelled("Preview cancelled. No user files changed.")
                if time.monotonic() - started > 30:
                    raise AssistantError("The organization preview exceeded 30 seconds. Choose a smaller folder.")
                source = item["path"]
                if Path(source).parts[0].casefold() in {OUTPUT.casefold(), "organized photos"}:
                    continue
                if extension and extension != item["extension"]:
                    continue
                if len(changes) >= 5000:
                    raise AssistantError("More than 5,000 changes would be needed. Choose a smaller folder.")
                destination = available_destination(root, f"{OUTPUT}/{item['extension'].upper().strip('()')}/{Path(source).name}", reserved, existing_names)
                changes.append(FileChange(source, destination, identity(checked_path(root, source))))
                if len(changes) % 100 == 0:
                    progress(f"Prepared {len(changes):,} file changes for review…")
            skipped = len(exclusions)
        else:
            destination = request.parameters.get("destination", "").strip()
            if not destination:
                raise AssistantError("Please provide a destination name, for example: Create a folder named Reports.")
            if destination.casefold() in {"documents", "downloads", "pictures", "desktop", "music", "movies"} and task in {"FM03", "FM04"}:
                raise AssistantError("Moving between workspaces isn't supported yet. Give a destination relative to the selected folder; I won't reinterpret your system Documents or Pictures folder.")
            path = checked_path(root, destination)
            if os.path.lexists(path) or path.parent.exists() and path.name.casefold() in {item.name.casefold() for item in path.parent.iterdir()}:
                raise AssistantError("That destination already exists. Choose a new name; nothing will be overwritten.")
            if task in {"FM01", "FM13"}:
                content = request.parameters.get("content", "")
                if task == "FM13" and path.suffix.casefold() not in {".txt", ".md", ".json", ".csv"}:
                    raise AssistantError("New files must use .txt, .md, .json or .csv. Executable creation is unavailable.")
                if task == "FM13" and not content and path.name.casefold() == "readme.md":
                    content = f"# {root.name}\n\n"
                changes.append(FileChange("(new folder)" if task == "FM01" else "(new file)", destination, kind="mkdir" if task == "FM01" else "create", content=content))
            else:
                source = request.parameters.get("source", "")
                source_path = checked_path(root, source)
                if not source_path.is_file():
                    raise AssistantError("Select one existing regular file to move, copy or rename.")
                kind = "copy" if task == "FM04" else "move"
                source_identity = identity(source_path)
                if kind == "copy" and source_identity.size > 2 * 1024**3:
                    raise AssistantError("Copies are limited to 2 GiB per file. Use your file manager for larger files.")
                changes.append(FileChange(source, destination, source_identity, kind))
        if event.is_set():
            raise TaskCancelled("Preview cancelled. No user files changed.")
        root_info = root.stat()
        plan = FilePlan(str(uuid4()), str(root), tuple(changes), skipped=skipped,
                        root_identity=(root_info.st_dev, root_info.st_ino))
        contents = ""
        if any(change.kind == "create" for change in changes):
            contents = "\nExact new-file content:\n" + changes[0].content + "\n(End of content.)"
        message = f"Prepared {len(changes):,} changes in {root}. No user files changed. Review the full preview and approve this exact plan. {skipped} excluded entries.{contents}"
        return TaskResult(task, True, message, {"scope": str(root), "change_count": len(changes)}, plan=plan)

    def apply(self, plan: FilePlan, approved_id: str, event, progress) -> TaskResult:
        if not approved_id or plan.id != approved_id:
            raise AssistantError("Approval must match this exact preview.")
        root = workspace_root(plan.workspace)
        self._directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        info = root.stat()
        if plan.root_identity != (info.st_dev, info.st_ino):
            raise AssistantError("The workspace changed since this preview. Prepare a new preview.")
        key = hashlib.sha256(f"{info.st_dev}:{info.st_ino}".encode()).hexdigest()
        try:
            with FileLock(str(self._directory / f"files-{key}.lock"), timeout=0):
                return self._commit(plan, root, event, progress)
        except Timeout as exc:
            raise AssistantError("Another general file operation is using this folder.") from exc

    def _commit(self, plan, root, event, progress):
        if len(plan.moves) > 5000:
            raise AssistantError("This plan exceeds the supported batch size.")
        for change in plan.moves:
            if event.is_set():
                raise TaskCancelled("Approved operation cancelled before file changes began.")
            self._validate(root, change)
        completed = 0
        error = ""
        outcomes = []
        deadline = time.monotonic() + 120
        with sqlite3.connect(self._directory / "file-operations.sqlite3") as db:
            if db.execute("PRAGMA user_version").fetchone()[0] > 1:
                raise AssistantError("The file operation journal belongs to a newer app version.")
            db.execute("PRAGMA synchronous=FULL")
            db.execute("CREATE TABLE IF NOT EXISTS operations (id TEXT PRIMARY KEY, created REAL, root TEXT, plan TEXT, state TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS outcomes (operation TEXT, position INTEGER, state TEXT, detail TEXT, PRIMARY KEY(operation,position))")
            db.execute("PRAGMA user_version=1")
            db.execute("INSERT INTO operations VALUES (?, ?, ?, ?, 'applying')", (plan.id, time.time(), str(root), json.dumps(asdict(plan))))
            db.commit()
            for index, change in enumerate(plan.moves):
                if event.is_set():
                    break
                if time.monotonic() > deadline:
                    error = "The two-minute operation limit was reached. Completed changes are recorded."
                    break
                db.execute("INSERT INTO outcomes VALUES (?, ?, 'started', '')", (plan.id, index))
                db.commit()
                try:
                    source, destination = self._validate(root, change)
                    # Parents are contained within the displayed scope; reject symlink components again.
                    relative_parent = Path(change.destination).parent
                    if str(relative_parent) != ".":
                        checked_path(root, relative_parent.as_posix()).mkdir(parents=True, exist_ok=True)
                    destination = checked_path(root, change.destination)
                    if change.kind == "mkdir":
                        destination.mkdir()
                    elif change.kind == "create":
                        with destination.open("x", encoding="utf-8") as stream:
                            stream.write(change.content)
                    elif change.kind == "move":
                        os.link(source, destination, follow_symlinks=False)
                        if identity(destination) != change.identity or identity(source) != change.identity:
                            raise AssistantError("A file changed during the move. Both paths were preserved for review.")
                        source.unlink()
                    else:
                        descriptor = os.open(source, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
                        with os.fdopen(descriptor, "rb") as incoming, destination.open("xb") as outgoing:
                            copied_identity = destination.stat()
                            while chunk := incoming.read(1024 * 1024):
                                if event.is_set() or time.monotonic() > deadline:
                                    break
                                outgoing.write(chunk)
                        if event.is_set() or time.monotonic() > deadline or identity(source) != change.identity:
                            current = destination.lstat()
                            if (current.st_dev, current.st_ino) == (copied_identity.st_dev, copied_identity.st_ino):
                                destination.unlink()
                            raise AssistantError("Copy stopped before completion; its incomplete destination was removed.")
                    completed += 1
                    outcomes.append({"source": change.source, "destination": change.destination, "kind": change.kind, "state": "completed"})
                    db.execute("UPDATE outcomes SET state='completed' WHERE operation=? AND position=?", (plan.id, index))
                    db.commit()
                    progress(f"Completed {completed:,} of {len(plan.moves):,} approved changes…")
                except (OSError, AssistantError) as exc:
                    error = str(exc)
                    db.execute("UPDATE outcomes SET state='failed', detail=? WHERE operation=? AND position=?", (error, plan.id, index))
                    db.commit()
                    break
            state = "failed" if error else "cancelled" if event.is_set() else "completed"
            db.execute("UPDATE operations SET state=? WHERE id=?", (state, plan.id))
            db.commit()
        message = f"{completed:,} of {len(plan.moves):,} approved changes completed. Status: {state}."
        if error:
            message += " " + error
        message += "\nGeneral file changes have no automatic undo. The operation journal records completed and interrupted steps."
        return TaskResult("file_commit", not error and not event.is_set(), message, {"scope": str(root), "completed": completed, "total": len(plan.moves), "state": state, "operation_id": plan.id, "outcomes": outcomes[:100]}, error_code=state if state != "completed" else None)

    @staticmethod
    def _validate(root, change):
        if change.kind not in {"move", "copy", "mkdir", "create"}:
            raise AssistantError("Unsupported file operation.")
        destination = checked_path(root, change.destination)
        if os.path.lexists(destination):
            raise AssistantError("A destination appeared after the preview. Prepare a new preview; nothing was replaced.")
        if destination.parent.exists() and destination.name.casefold() in {item.name.casefold() for item in destination.parent.iterdir()}:
            raise AssistantError("A destination name appeared after the preview. Nothing was replaced.")
        source = None
        if change.kind in {"move", "copy"}:
            source = checked_path(root, change.source)
            try:
                if identity(source) != change.identity:
                    raise AssistantError("A source changed after the preview. Prepare a new preview.")
                if change.identity.device != root.stat().st_dev:
                    raise AssistantError("Cross-volume operations are unavailable.")
            except OSError as exc:
                raise AssistantError("A source disappeared after the preview.") from exc
        return source, destination
