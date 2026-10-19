"""Typed assistant decisions; no model, Qt, or filesystem dependencies."""

from dataclasses import dataclass
from typing import Literal

from localmind.domain.tasks import TaskRequest

Capability = Literal["organize_photos", "list_files", "search_files", "find_pdfs", "open_vscode", "task_pipeline", "unknown"]
OrganizationStrategy = Literal["month", "year", "type"]


class AssistantError(RuntimeError):
    pass


class TaskCancelled(AssistantError):
    pass


@dataclass(frozen=True, slots=True)
class IntentPrediction:
    intent: str
    similarity: float
    margin: float
    model_version: str


@dataclass(frozen=True, slots=True)
class AssistantDecision:
    capability: Capability = "unknown"
    message: str = ""
    query: str = ""
    strategy: OrganizationStrategy | None = None
    needs_strategy: bool = False
    model_version: str = ""
    tasks: tuple[TaskRequest, ...] = ()
