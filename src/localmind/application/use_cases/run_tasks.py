"""Bounded sequential tools with explicit scope and live result references."""

import re
from dataclasses import replace
from pathlib import Path

from localmind.application.ports import FileActions
from localmind.application.task_registry import TaskRegistry
from localmind.domain.assistant import AssistantError, TaskCancelled
from localmind.domain.tasks import TaskBatchResult, TaskResult

KNOWN_FOLDERS = {name.casefold(): name for name in ("Downloads", "Documents", "Pictures", "Desktop", "Movies", "Music")}


class RunTasks:
    def __init__(self, registry: TaskRegistry, file_actions: FileActions, *, home: Path | None = None) -> None:
        self.registry = registry
        self._file_actions = file_actions
        self._home = home or Path.home()

    def execute(self, requests, workspace, context, event, progress) -> TaskBatchResult:
        if not 1 <= len(requests) <= 6:
            raise AssistantError("Please ask for between one and six supported steps.")
        results = []
        current = dict(context)
        for request in requests:
            if event.is_set():
                if results:
                    results.append(TaskResult(request.task_id, False, "Remaining steps cancelled. No unapproved changes were made.", error_code="cancelled"))
                    break
                raise TaskCancelled("Task cancelled. No unapproved changes were made.")
            parameters = dict(request.parameters)
            hint = parameters.get("scope", "")
            if hint and hint not in KNOWN_FOLDERS:
                raise AssistantError("That folder is not an authorized named scope. Choose it as the workspace first.")
            scope = str(self._home / KNOWN_FOLDERS[hint]) if hint in KNOWN_FOLDERS else current.get("scope") or workspace
            if request.task_id.startswith(("F", "P")) and not request.task_id.startswith("FM") or request.task_id == "A03":
                explicit = re.search(r'["“]((?:/|[A-Za-z]:[\\/])[^"”]+)["”]|(?<!\w)((?:/|[A-Za-z]:[\\/])[^\s,!?]+)', parameters.get("text", ""))
                if explicit:
                    candidate = Path(explicit.group(1) or explicit.group(2)).expanduser()
                    base = Path(scope).resolve() if scope else None
                    if base is None or not candidate.resolve().is_relative_to(base):
                        raise AssistantError("That path is outside the authorized folder. Choose it as the workspace first.")
                    try:
                        relative = candidate.relative_to(base)
                    except ValueError:
                        if candidate.resolve() != base:
                            raise AssistantError("Choose this folder directly as the workspace to avoid path aliases.") from None
                        relative = Path(".")
                    cursor = base
                    for part in relative.parts:
                        cursor = cursor / part
                        if cursor.is_symlink():
                            raise AssistantError("Symbolic-link folders are not allowed.")
                    scope = str(candidate.resolve())
            if request.task_id.startswith("S") or request.task_id in {"A01", "A04"}:
                scope = scope or ""
            elif not scope:
                raise AssistantError("Choose a workspace folder first, or name a supported user folder such as Downloads.")
            if current.get("scope") and scope != current["scope"]:
                current = {}  # A filename reference never carries over to a different folder.
            # Only live, verified references are used. History text cannot authorize tools.
            if request.task_id.startswith("C") and request.task_id != "C15" or request.task_id == "A02":
                parameters["target"] = self._target(parameters, current)
            if request.task_id in {"FM02", "FM03", "FM04"}:
                source = parameters.get("source", "")
                if source.casefold() in {"this file", "that file", "it", "this pdf", "this image", "that document"}:
                    parameters["source"] = self._target({"text": source}, current)
            definition = self.registry.definition(request.task_id)
            progress(f"Running {definition.name if definition else 'requested task'} locally…")
            try:
                result = self.registry.execute(replace(request, parameters=parameters), scope, event, progress)
            except TaskCancelled:
                if not results:
                    raise
                result = TaskResult(request.task_id, False, "Remaining steps cancelled. No unapproved changes were made.", error_code="cancelled")
            except (AssistantError, OSError, ValueError) as exc:
                result = TaskResult(request.task_id, False, str(exc), error_code="task_failed")
            results.append(result)
            if result.data.get("scope"):
                current = dict(result.data)
            if not result.success or result.plan is not None:
                break  # Approval is a hard workflow boundary; later actions never auto-resume.
        return TaskBatchResult(tuple(results))

    @staticmethod
    def _target(parameters, context):
        explicit = parameters.get("target", "")
        if explicit:
            return explicit
        text = parameters.get("text", "")
        quoted = re.search(r'["“]([^"”]+)["”]', text)
        if quoted:
            return quoted.group(1)
        filename = re.search(r"(?:[\w.-]+/)*[\w.-]+\.[a-zA-Z0-9]{1,10}\b", text)
        if filename:
            return filename.group(0)
        if "readme" in text.casefold():
            return context.get("readme") or "README.md"
        if context.get("target"):
            return context["target"]
        files = context.get("files", [])
        if len(files) == 1:
            return files[0]["path"]
        return ""

    def apply(self, plan, approved_id, event, progress):
        return self._file_actions.apply(plan, approved_id, event, progress)
