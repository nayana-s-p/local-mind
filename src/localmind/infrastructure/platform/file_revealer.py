"""Reveal an existing workspace file in the platform file manager."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath

from localmind.domain.files import FileRevealError


class DesktopFileRevealer:
    """Open the parent folder or select the file, without invoking a shell."""

    def reveal(self, workspace: str, relative_path: str) -> None:
        try:
            root = Path(workspace).expanduser().resolve(strict=True)
            if not root.is_dir():
                raise FileRevealError("Choose an existing folder as the workspace.")

            # Reject absolute paths and traversal on either path convention.
            posix_path = PurePosixPath(relative_path)
            windows_path = PureWindowsPath(relative_path)
            if (
                posix_path.is_absolute()
                or windows_path.is_absolute()
                or windows_path.drive
                or ".." in posix_path.parts
                or ".." in windows_path.parts
            ):
                raise FileRevealError("That file is outside the selected workspace.")

            candidate = root.joinpath(*posix_path.parts)
            current = root
            for part in posix_path.parts:
                current = current / part
                if current.is_symlink():
                    raise FileRevealError("That file is no longer available in the workspace.")

            file_path = candidate.resolve(strict=True)
            file_path.relative_to(root)
            if not file_path.is_file():
                raise FileRevealError("That file is no longer available in the workspace.")
        except FileRevealError:
            raise
        except (OSError, ValueError) as exc:
            raise FileRevealError("That file is no longer available in the workspace.") from exc

        try:
            if sys.platform == "darwin":
                command = ["/usr/bin/open", "-R", str(file_path)]
            elif os.name == "nt":
                command = ["explorer.exe", f"/select,{file_path}"]
            else:
                file_manager = shutil.which("xdg-open")
                if not file_manager:
                    raise FileRevealError("No supported file manager launcher was found.")
                command = [file_manager, str(file_path.parent)]
            subprocess.Popen(
                command,
                shell=False,
                close_fds=True,
                start_new_session=(os.name != "nt"),
            )
        except FileRevealError:
            raise
        except OSError as exc:
            raise FileRevealError("The file manager could not reveal that file.") from exc
