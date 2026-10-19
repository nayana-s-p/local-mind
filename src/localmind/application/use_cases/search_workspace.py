"""Use case for bounded filename search in a user-selected workspace."""

from __future__ import annotations

import threading

from localmind.application.ports import WorkspaceFileScanner
from localmind.domain.files import ScanReport, WorkspaceError


class SearchWorkspaceFiles:
    def __init__(self, scanner: WorkspaceFileScanner) -> None:
        self._scanner = scanner

    def execute(
        self,
        workspace: str,
        *,
        query: str = "",
        pdf_only: bool = False,
        cancel_event: threading.Event,
    ) -> ScanReport:
        if not workspace.strip():
            raise WorkspaceError("Choose a workspace before scanning.")
        return self._scanner.scan(
            workspace,
            query=query,
            pdf_only=pdf_only,
            cancel_event=cancel_event,
        )

