"""Use case for revealing a discovered file in the system file manager."""

from __future__ import annotations

from localmind.application.ports import FileRevealer
from localmind.domain.files import FileRevealError


class RevealWorkspaceFile:
    def __init__(self, revealer: FileRevealer) -> None:
        self._revealer = revealer

    def execute(self, workspace: str, relative_path: str) -> None:
        if not workspace.strip():
            raise FileRevealError("Choose a workspace before revealing a file.")
        if not relative_path.strip():
            raise FileRevealError("Select a file from the results first.")
        self._revealer.reveal(workspace, relative_path)
