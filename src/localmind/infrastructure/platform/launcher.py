"""Allowlisted VS Code launcher; arguments are passed without a shell."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from localmind.domain.applications import ApplicationLaunchError


class DesktopApplicationLauncher:
    def open_in_vscode(self, workspace: str) -> None:
        try:
            root = Path(workspace).expanduser().resolve(strict=True)
        except OSError as exc:
            raise ApplicationLaunchError("The selected workspace is unavailable.") from exc
        if not root.is_dir():
            raise ApplicationLaunchError("Choose an existing folder to open in VS Code.")

        if sys.platform == "darwin":
            command = self._mac_command(root)
        elif os.name == "nt":
            command = self._windows_command(root)
        else:
            command = self._unix_command(root)

        try:
            subprocess.Popen(command, shell=False, close_fds=True, start_new_session=(os.name != "nt"))
        except OSError as exc:
            raise ApplicationLaunchError("VS Code could not be started.") from exc

    @staticmethod
    def _mac_command(root: Path) -> list[str]:
        app_candidates = (
            Path("/Applications/Visual Studio Code.app"),
            Path.home() / "Applications/Visual Studio Code.app",
        )
        app = next((candidate for candidate in app_candidates if candidate.is_dir()), None)
        if app is not None:
            return ["/usr/bin/open", "-a", str(app), str(root)]
        code = shutil.which("code")
        if code:
            return [code, str(root)]
        raise ApplicationLaunchError("VS Code was not found. Install it or add its 'code' command to PATH.")

    @staticmethod
    def _windows_command(root: Path) -> list[str]:
        candidates: list[Path] = []
        local_app_data = os.environ.get("LOCALAPPDATA")
        program_files = os.environ.get("ProgramFiles")
        program_files_x86 = os.environ.get("ProgramFiles(x86)")
        if local_app_data:
            candidates.append(Path(local_app_data) / "Programs/Microsoft VS Code/Code.exe")
        if program_files:
            candidates.append(Path(program_files) / "Microsoft VS Code/Code.exe")
        if program_files_x86:
            candidates.append(Path(program_files_x86) / "Microsoft VS Code/Code.exe")
        executable = next((candidate for candidate in candidates if candidate.is_file()), None)
        if executable is None:
            found = shutil.which("Code.exe")
            executable = Path(found) if found else None
        if executable is None:
            raise ApplicationLaunchError("VS Code was not found on this computer.")
        return [str(executable), str(root)]

    @staticmethod
    def _unix_command(root: Path) -> list[str]:
        code = shutil.which("code") or shutil.which("code-insiders")
        if not code:
            raise ApplicationLaunchError("VS Code was not found. Install it or add its 'code' command to PATH.")
        return [code, str(root)]

