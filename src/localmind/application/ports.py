"""Interfaces implemented by infrastructure adapters."""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from localmind.domain.assistant import IntentPrediction, OrganizationStrategy
from localmind.domain.files import ScanReport
from localmind.domain.history import ConversationSummary, HistorySnapshot, MessageRole
from localmind.domain.organization import OrganizationResult, PhotoPlan
from localmind.domain.tasks import FilePlan, TaskRequest, TaskResult


class WorkspaceFileScanner(Protocol):
    def scan(
        self,
        workspace: str,
        *,
        query: str,
        pdf_only: bool,
        cancel_event: threading.Event,
    ) -> ScanReport: ...


class ApplicationLauncher(Protocol):
    def open_in_vscode(self, workspace: str) -> None: ...


class FileRevealer(Protocol):
    def reveal(self, workspace: str, relative_path: str) -> None: ...


class LocalModelInstaller(Protocol):
    @property
    def install_path(self) -> Path: ...

    @property
    def total_size(self) -> int: ...

    def is_installed(self) -> bool: ...

    def install(
        self,
        progress: Callable[[int, int], None],
        cancel_event: threading.Event,
    ) -> Path: ...


class IntentClassifier(Protocol):
    def classify(self, text: str, cancel_event: threading.Event) -> IntentPrediction: ...


class PhotoOrganizer(Protocol):
    def preview(
        self, workspace: str, strategy: OrganizationStrategy,
        cancel_event: threading.Event, progress: Callable[[str], None],
    ) -> PhotoPlan: ...

    def execute(
        self, plan: PhotoPlan, cancel_event: threading.Event,
        progress: Callable[[str], None],
    ) -> OrganizationResult: ...

    def undo(
        self, workspace: str, cancel_event: threading.Event,
        progress: Callable[[str], None],
    ) -> OrganizationResult: ...


class ConversationRepository(Protocol):
    def initialize(self, welcome: str) -> HistorySnapshot: ...
    def open_conversation(self, conversation_id: str) -> HistorySnapshot: ...
    def new_conversation(self, welcome: str) -> HistorySnapshot: ...
    def append_message(
        self, conversation_id: str, role: MessageRole, text: str,
    ) -> tuple[ConversationSummary, ...]: ...
    def save_context(self, conversation_id: str, context: dict[str, str]) -> None: ...
    def save_plan(self, conversation_id: str, plan: PhotoPlan | FilePlan) -> None: ...
    def record_approval(self, conversation_id: str, plan_id: str, approved: bool, source: str) -> None: ...
    def record_event(
        self, conversation_id: str, plan_id: str | None, kind: str, outcome: str, summary: str,
    ) -> None: ...
    def clear(self, welcome: str) -> HistorySnapshot: ...
    def set_retention(self, conversation_id: str, days: int) -> HistorySnapshot: ...


class FileActions(Protocol):
    def preview(self, request: TaskRequest, scope: str, event: threading.Event,
                progress: Callable[[str], None]) -> TaskResult: ...

    def apply(self, plan: FilePlan, approved_id: str, event: threading.Event,
              progress: Callable[[str], None]) -> TaskResult: ...


