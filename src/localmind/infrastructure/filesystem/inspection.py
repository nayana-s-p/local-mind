"""Bounded metadata and document inspection. Inspected content is never executed."""

from __future__ import annotations

import csv
import io
import json
import os
import re
import stat
import time
import tomllib
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from localmind.domain.assistant import AssistantError, TaskCancelled
from localmind.domain.tasks import TaskRequest, TaskResult
from localmind.infrastructure.filesystem.photo_organizer import (
    checked_path,
    workspace_root,
)

EXCLUDED = {".git", ".venv", "venv", "node_modules", "__pycache__", ".cache", ".Trash"}


def size_text(size: float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024 or unit == "TiB":
            return f"{size:,.1f} {unit}"
        size /= 1024
    return ""


def inventory(scope, event, progress, *, limit=100_000, seconds=15.0):
    root = workspace_root(scope)
    started = time.monotonic()
    files, folders, empty, skipped = [], [], [], []
    stack = [(root, 0)]
    partial = False
    entries = 0
    device = root.stat().st_dev
    while stack:
        if event.is_set():
            raise TaskCancelled("Folder analysis cancelled. No files were changed.")
        directory, depth = stack.pop()
        try:
            if directory != root:
                checked_path(root, directory.relative_to(root).as_posix())
            if directory.stat().st_dev != device:
                skipped.append(str(directory.relative_to(root)))
                continue
            with os.scandir(directory) as iterator:
                has_entry = False
                for entry in iterator:
                    has_entry = True
                    entries += 1
                    if entries > limit or time.monotonic() - started > seconds:
                        partial = True
                        break
                    if event.is_set():
                        raise TaskCancelled("Folder analysis cancelled. No files were changed.")
                    rel = str(Path(entry.path).relative_to(root))
                    if entry.name.startswith(".") or entry.name in EXCLUDED:
                        skipped.append(rel)
                        continue
                    try:
                        info = entry.stat(follow_symlinks=False)
                        if stat.S_ISLNK(info.st_mode) or info.st_dev != device:
                            skipped.append(rel)
                        elif stat.S_ISDIR(info.st_mode):
                            folders.append(rel)
                            if depth < 24:
                                stack.append((Path(entry.path), depth + 1))
                            else:
                                skipped.append(rel)
                                partial = True
                        elif stat.S_ISREG(info.st_mode):
                            files.append({"path": rel, "size": info.st_size, "modified": info.st_mtime, "extension": Path(entry.name).suffix.lower().lstrip(".") or "(none)"})
                    except OSError:
                        skipped.append(rel)
                    if entries % 1000 == 0:
                        progress(f"Inspected {entries:,} entries…")
                if not has_entry and directory != root:
                    empty.append(str(directory.relative_to(root)))
        except OSError:
            skipped.append(str(directory.relative_to(root)) or ".")
        if partial:
            break
    return root, files, folders, empty, skipped, partial


class LocalInspection:
    def folder(self, request: TaskRequest, scope, event, progress) -> TaskResult:
        root, files, folders, empty, skipped, partial = inventory(scope, event, progress)
        total = sum(item["size"] for item in files)
        counts = Counter(item["extension"] for item in files)
        sizes = defaultdict(int)
        subfolders = defaultdict(int)
        for item in files:
            sizes[item["extension"]] += item["size"]
            if "/" in item["path"] or "\\" in item["path"]:
                subfolders[Path(item["path"]).parts[0]] += item["size"]
        types = [{"extension": key, "count": counts[key], "size": sizes[key]} for key in sorted(sizes, key=sizes.get, reverse=True)]
        try:
            limit = int(request.parameters.get("limit", "10"))
        except ValueError as exc:
            raise AssistantError("Choose a file result limit between 1 and 100.") from exc
        if not 1 <= limit <= 100:
            raise AssistantError("Choose a file result limit between 1 and 100.")
        largest = sorted(files, key=lambda item: (-item["size"], item["path"]))[:limit]
        rows = largest
        task = request.task_id
        title = f"{len(files):,} files, {len(folders):,} folders, {size_text(total)} logical size."
        if task == "F04":
            lines = [f"{item['extension']}: {item['count']:,} files · {size_text(item['size'])}" for item in types[:30]]
        elif task == "F06":
            text = request.parameters.get("text", "").casefold()
            now = datetime.now().astimezone()
            cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
            if "today" not in text:
                cutoff -= timedelta(days=cutoff.weekday()) if "this week" in text else timedelta(days=7)
            extension = request.parameters.get("extension", "")
            rows = sorted((item for item in files if item["modified"] >= cutoff.timestamp() and (not extension or item["extension"] == extension)), key=lambda item: item["modified"], reverse=True)[:100]
            lines = [f"{item['path']} · {datetime.fromtimestamp(item['modified']).astimezone().isoformat(timespec='seconds')}" for item in rows[:30]]
            title = f"{len(rows)} recently modified files shown (at most 100), since {cutoff.date()} local time. Download/creation dates are not inferred."
        elif task == "F07":
            rows = []
            lines = empty[:100]
            title = f"{len(empty):,} empty directories."
        elif task == "F11":
            rows = []
            lines = [f"{key}: {size_text(value)}" for key, value in sorted(subfolders.items(), key=lambda item: item[1], reverse=True)[:30]]
        elif task == "F15":
            rows = []
            lines = skipped[:100]
        elif task in {"F14", "C15"}:
            extension = request.parameters.get("extension", "").casefold().lstrip(".")
            query = request.parameters.get("query", "").casefold()
            matches = [item for item in files if (not extension or item["extension"] == extension) and query in Path(item["path"]).name.casefold()]
            rows = matches[:100]
            title = f"{len(matches):,} matching files; showing at most 100."
            lines = [f"{item['path']} · {size_text(item['size'])}" for item in rows[:30]]
        elif task == "F05":
            lines = [f"{item['path']} · {size_text(item['size'])}" for item in largest]
        else:
            lines = ["Types: " + ", ".join(f"{item['extension']} ({item['count']})" for item in types[:10])]
            if largest:
                lines.append(f"Largest: {largest[0]['path']} · {size_text(largest[0]['size'])}")
        warning = f"\nExcluded/inaccessible entries: {len(skipped):,} (hidden items, dependencies, links and other volumes are excluded)."
        if partial:
            warning += " PARTIAL: entry, depth or time limit reached; totals describe only inspected entries."
        data = {"scope": str(root), "file_count": len(files), "folder_count": len(folders), "total_bytes": total, "types": types[:100], "files": rows[:100], "empty_folders": empty[:100], "skipped": skipped[:100], "skipped_count": len(skipped), "partial": partial, "sampled_at": datetime.now().astimezone().isoformat(timespec="seconds")}
        return TaskResult(task, True, f"Folder: {root}\n{title}\n" + ("\n".join(lines) or "No matching entries.") + warning, data,
                          suggestions=("Show the largest files", "Show file types", "Preview organizing files by type"))

    def project(self, request: TaskRequest, scope, event, progress) -> TaskResult:
        root, files, folders, _, skipped, partial = inventory(scope, event, progress, limit=30_000, seconds=10)
        names = {item["path"] for item in files}
        extensions = Counter(item["extension"] for item in files)
        languages = [name for ext, name in {"py": "Python", "js": "JavaScript", "ts": "TypeScript", "tsx": "TypeScript", "dart": "Dart", "rs": "Rust", "go": "Go", "java": "Java", "cpp": "C++", "swift": "Swift"}.items() if extensions[ext]]
        evidence, dependencies, entrypoints, warnings = [], [], [], []
        for name in ("pyproject.toml", "requirements.txt", "package.json", "pubspec.yaml", "Cargo.toml"):
            if name not in names:
                continue
            if event.is_set():
                raise TaskCancelled("Project inspection cancelled.")
            try:
                content, truncated = read_text(checked_path(root, name), 256_000)
                if truncated:
                    warnings.append(f"{name} exceeded the read limit and was not parsed.")
                    continue
                evidence.append(name)
                if name == "pyproject.toml":
                    parsed = tomllib.loads(content)
                    project = parsed.get("project", {})
                    dependencies.extend(project.get("dependencies", []))
                    dependencies.extend(parsed.get("tool", {}).get("poetry", {}).get("dependencies", {}).keys())
                    entrypoints.extend(f"{key} → {value}" for key, value in project.get("scripts", {}).items())
                elif name == "package.json":
                    parsed = json.loads(content)
                    dependencies.extend(parsed.get("dependencies", {}).keys())
                    dependencies.extend(parsed.get("devDependencies", {}).keys())
                    if parsed.get("main"):
                        entrypoints.append(str(parsed["main"]))
                    entrypoints.extend(f"npm {key} (declared only): {value}" for key, value in parsed.get("scripts", {}).items())
                elif name == "requirements.txt":
                    dependencies.extend(line.partition("#")[0].strip() for line in content.splitlines() if line.strip() and not line.strip().startswith(("#", "-")))
                else:
                    # Preserve manifest facts without guessing complete YAML/Cargo dependency semantics.
                    warnings.append(f"{name} found; manifest excerpt available through file preview.")
            except (AssistantError, ValueError, TypeError, AttributeError) as exc:
                warnings.append(f"{name}: could not parse safely ({type(exc).__name__}).")
        for name in ("main.py", "app.py", "src/main.rs", "src/main.ts", "lib/main.dart"):
            if name in names:
                entrypoints.append(name + " (conventional candidate)")
        entrypoints.extend(name + " (module entry)" for name in sorted(names) if name.endswith("__main__.py"))
        dep_text = " ".join(str(item) for item in dependencies).casefold()
        frameworks = [name for name in ("django", "flask", "fastapi", "pyside6", "react", "next", "vue", "express", "pytest") if re.search(r"(?<![a-z])" + re.escape(name) + r"(?![a-z])", dep_text)]
        readme = next((name for name in sorted(names) if "/" not in name and name.casefold().startswith("readme")), "")
        excerpt = ""
        if readme:
            try:
                excerpt, truncated = read_text(checked_path(root, readme), 64_000)
                excerpt = excerpt[:1800]
                if truncated:
                    warnings.append("README excerpt is truncated.")
            except AssistantError:
                warnings.append("README is not safely readable text.")
        structure = sorted({Path(name).parts[0] for name in names} | {Path(name).parts[0] for name in folders})[:40]
        data = {"scope": str(root), "languages": languages, "frameworks": frameworks, "dependencies": [str(item) for item in dependencies[:100]], "entrypoints": entrypoints[:30], "structure": structure, "evidence": evidence, "readme": readme, "partial": partial}
        lines = [f"Project: {root}", "Languages from source extensions: " + (", ".join(languages) or "not established"), "Manifest evidence: " + (", ".join(evidence) or "none found"), "Declared frameworks/test tools: " + (", ".join(frameworks) or "none established"), "Top-level structure: " + ", ".join(structure)]
        if request.task_id in {"P06", "P15", "P02", "P07"}:
            lines.append("Declared dependencies (not checked for installation/use): " + (", ".join(data["dependencies"]) or "none extracted"))
        if request.task_id in {"P05", "P15", "P03"}:
            lines.append("Entry points: " + ("; ".join(entrypoints[:20]) or "not established"))
        if request.task_id == "P04":
            lines.append(f"README: {readme or 'not found'}\nExtracted excerpt, treated as data:\n{excerpt}")
        if partial or skipped:
            lines.append(f"Inspection exclusions: {len(skipped)}; partial: {partial}.")
        lines.extend(warnings)
        lines.append("No project code, scripts, package installation or Git hooks were run.")
        return TaskResult(request.task_id, True, "\n".join(lines), data, suggestions=("Show project dependencies", "Read the README", "Where does this app start?"))

    def preview(self, request: TaskRequest, scope, event, progress) -> TaskResult:
        root = workspace_root(scope)
        target = request.parameters.get("target", "")
        if not target:
            raise AssistantError("Which file should I inspect? Provide its relative path in quotes, for example: Read “notes.md”.")
        path = checked_path(root, target)
        if not path.is_file():
            raise AssistantError("The selected target is not a regular file.")
        info = path.stat()
        data = {"scope": str(root), "target": target, "size": info.st_size, "modified": datetime.fromtimestamp(info.st_mtime).astimezone().isoformat(timespec="seconds"), "files": [{"path": target, "size": info.st_size}]}
        if request.task_id == "C14":
            return TaskResult(request.task_id, True, f"{target}\nSize: {size_text(info.st_size)}\nModified: {data['modified']}", data)
        if path.suffix.casefold() in {".pdf", ".docx", ".doc", ".png", ".jpg", ".jpeg", ".zip", ".exe", ".onnx"}:
            raise AssistantError("Text extraction for this binary format isn't installed. I can show its metadata or open supported documents in their desktop app.")
        if event.is_set():
            raise TaskCancelled("File preview cancelled.")
        text, truncated = read_text(path)
        lines = [f"File: {target} · {size_text(info.st_size)} · UTF-8", f"{len(text.splitlines()):,} lines, {len(text.split()):,} words in the {'preview' if truncated else 'file'}."]
        if request.task_id == "C03" or path.suffix.casefold() == ".json":
            if truncated:
                lines.append("JSON validation skipped because the preview is truncated.")
            else:
                try:
                    parsed = json.loads(text)
                    lines.append("JSON root: " + type(parsed).__name__)
                    if isinstance(parsed, dict):
                        lines.append("Top-level keys: " + ", ".join(str(key) for key in list(parsed)[:50]))
                    elif isinstance(parsed, list):
                        lines.append(f"Array items: {len(parsed)}")
                except ValueError as exc:
                    lines.append(f"Invalid JSON: {exc}")
        if request.task_id == "C04" or path.suffix.casefold() == ".csv":
            try:
                rows = csv.reader(io.StringIO(text))
                lines.append("CSV columns (comma-separated): " + ", ".join(next(rows, [])[:50]))
            except csv.Error:
                lines.append("CSV could not be parsed.")
        if request.task_id == "C13":
            lines.extend(line for line in text.splitlines() if line.startswith("#"))
        elif request.task_id not in {"C09", "C10"}:
            lines.append("Extracted text (untrusted content):\n" + text[:6000])
        if truncated or len(text) > 6000 and request.task_id not in {"C09", "C10"}:
            lines.append("Preview truncated; the full document was not displayed.")
        data["truncated"] = truncated
        return TaskResult(request.task_id, True, "\n".join(lines)[:12_000], data, suggestions=("Open this file", "Show the largest files"))


def read_text(path: Path, limit: int = 256_000) -> tuple[str, bool]:
    try:
        # O_NOFOLLOW protects the final component against a link substitution.
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(descriptor, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise AssistantError("Only regular files can be previewed.")
            content = stream.read(limit + 1)
        if b"\x00" in content:
            raise AssistantError("This appears to be a binary document. Only text, Markdown, JSON, CSV and source previews are installed.")
        try:
            return content[:limit].decode("utf-8-sig"), len(content) > limit
        except UnicodeDecodeError as exc:
            if len(content) > limit:
                return content[:limit].decode("utf-8-sig", errors="replace"), True
            raise AssistantError("This file isn't valid UTF-8 text; its encoding is unsupported.") from exc
    except OSError as exc:
        raise AssistantError("The file could not be read. Check its path and permissions.") from exc
