"""Use case for opening the selected workspace in an allowlisted editor."""

from __future__ import annotations

from localmind.application.ports import ApplicationLauncher
from localmind.domain.applications import ApplicationLaunchError


class LaunchWorkspaceInVSCode:
    def __init__(self, launcher: ApplicationLauncher) -> None:
        self._launcher = launcher

    def execute(self, workspace: str) -> None:
        if not workspace.strip():
            raise ApplicationLaunchError("Choose a workspace before opening VS Code.")
        self._launcher.open_in_vscode(workspace)

