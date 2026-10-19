"""The installed capability catalog. Entries always map to an injected handler."""

from collections.abc import Callable

from localmind.domain.assistant import AssistantError
from localmind.domain.tasks import RiskLevel, TaskDefinition, TaskRequest, TaskResult

_GROUPS = {
    "folder": {
        "F01": "Folder overview", "F02": "File and directory counts", "F03": "Logical folder size",
        "F04": "File type breakdown", "F05": "Largest files", "F06": "Recently modified files",
        "F07": "Empty directories", "F11": "Subfolder space usage", "F13": "Folder summary",
        "F14": "Find files by extension", "F15": "Scan exclusions and inaccessible entries",
        "C15": "Find matching filenames",
    },
    "project": {
        "P01": "Project languages", "P02": "Framework evidence", "P03": "Project structure",
        "P04": "README facts and excerpt", "P05": "Declared entry points", "P06": "Declared dependencies",
        "P07": "Test framework evidence", "P15": "Project overview",
    },
    "preview": {
        "C01": "Text preview", "C02": "Markdown preview", "C03": "JSON inspection",
        "C04": "CSV columns and sample", "C09": "Word and line counts",
        "C10": "Text encoding", "C13": "Markdown headings", "C14": "File metadata",
    },
    "files": {
        "FM01": "Create directory", "FM02": "Rename file", "FM03": "Move file",
        "FM04": "Copy file", "FM05": "Organize by type", "FM13": "Create text file",
        "FM15": "Preview organization changes",
    },
    "desktop": {"A01": "Open known installed app", "A02": "Open safe local file", "A03": "Open folder", "A04": "Open HTTP website"},
    "system": {
        "S01": "CPU usage", "S02": "Memory usage", "S03": "Disk usage", "S04": "System information",
        "S05": "Operating system", "S06": "Top memory processes", "S08": "Battery status",
        "S11": "System uptime", "S12": "Refresh system metrics",
    },
}


def definitions() -> tuple[TaskDefinition, ...]:
    return tuple(
        TaskDefinition(key, name, name, RiskLevel.WRITE if group == "files" else RiskLevel.LOW if group == "desktop" else RiskLevel.READ_ONLY,
                       group == "files", ("scope", "text", "target", "extension", "query", "source", "destination", "content", "limit", "browser"), group)
        for group, entries in _GROUPS.items() for key, name in entries.items()
    )


class TaskRegistry:
    def __init__(self, handlers: dict[str, Callable[..., TaskResult]]) -> None:
        self._tasks = {item.task_id: item for item in definitions() if item.handler in handlers}
        self._handlers = dict(handlers)

    @property
    def tasks(self) -> tuple[TaskDefinition, ...]:
        return tuple(self._tasks.values())

    def definition(self, task_id: str) -> TaskDefinition | None:
        return self._tasks.get(task_id)

    def execute(self, request: TaskRequest, scope: str, event, progress) -> TaskResult:
        definition = self._tasks.get(request.task_id)
        if definition is None:
            raise AssistantError("That task has no installed handler.")
        if set(request.parameters) - set(definition.parameters):
            raise AssistantError("The task contains unsupported parameters.")
        if any(not isinstance(value, str) or len(value) > 4096 for value in request.parameters.values()):
            raise AssistantError("Task parameters must be bounded text.")
        # Write handlers can only return previews. Commit has a separate exact-plan gate.
        result = self._handlers[definition.handler](request, scope, event, progress)
        if definition.requires_confirmation and result.success and result.plan is None:
            raise AssistantError("The file tool did not produce an approval preview.")
        return result
