"""Known apps, safe local documents and HTTP targets; never shell commands."""

import os
import shutil
import subprocess
import sys
from urllib.parse import urlsplit

from localmind.domain.assistant import AssistantError
from localmind.domain.tasks import TaskRequest, TaskResult
from localmind.infrastructure.filesystem.photo_organizer import (
    checked_path,
    workspace_root,
)

SAFE_EXTENSIONS = {".txt", ".md", ".pdf", ".json", ".csv", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".docx"}
APPS = {
    "vscode": ("Visual Studio Code", "Code.exe", "code"),
    "safari": ("Safari", None, None), "chrome": ("Google Chrome", "chrome.exe", "google-chrome"),
    "firefox": ("Firefox", "firefox.exe", "firefox"), "calculator": ("Calculator", "calc.exe", "gnome-calculator"),
    "notepad": (None, "notepad.exe", None), "textedit": ("TextEdit", None, None),
}


class CatalogDesktop:
    def execute(self, request: TaskRequest, scope, event, progress) -> TaskResult:
        task = request.task_id
        target = request.parameters.get("target", "")
        browser = request.parameters.get("browser", "")
        if task == "A04":
            parsed = urlsplit(target)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or any(ord(char) < 32 for char in target):
                raise AssistantError("Provide a valid http:// or https:// website without credentials.")
            if browser and browser not in {"safari", "chrome", "firefox"}:
                raise AssistantError("That browser isn't in the installed launcher allowlist.")
        elif task == "A01":
            names = APPS.get(target.casefold())
            if not names:
                raise AssistantError("That application is not in the installed launcher allowlist.")
            if sys.platform == "darwin":
                app_name = names[0]
                if not app_name:
                    raise AssistantError("That app is not supported on macOS.")
                command = ["/usr/bin/open", "-a", app_name]
            else:
                executable = names[1 if os.name == "nt" else 2]
                resolved = shutil.which(executable) if executable else None
                if not resolved:
                    raise AssistantError("That application was not found on this platform.")
                command = [resolved]
            if target.casefold() == "vscode" and scope:
                command.append(str(workspace_root(scope)))
        else:
            root = workspace_root(scope)
            if task == "A03":
                target = str(root)
            else:
                if not target:
                    raise AssistantError("Which file should I open? Provide its relative filename in quotes.")
                path = checked_path(root, target)
                if not path.is_file() or path.suffix.casefold() not in SAFE_EXTENSIONS:
                    raise AssistantError("Only existing supported documents and images can be opened. Executables and scripts are blocked.")
                with path.open("rb") as stream:
                    magic = stream.read(4)
                if magic.startswith((b"MZ", b"\x7fELF", b"#!")) or magic in {b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe"}:
                    raise AssistantError("This file contains an executable signature. It cannot be opened through the document tool.")
                target = str(path)
        if event.is_set():
            raise AssistantError("Launch cancelled before starting.")
        if task != "A01":
            if browser:
                names = APPS[browser]
                if sys.platform == "darwin":
                    command = ["/usr/bin/open", "-a", names[0], target]
                else:
                    executable = names[1 if os.name == "nt" else 2]
                    resolved = shutil.which(executable) if executable else None
                    if not resolved:
                        raise AssistantError("That browser was not found on this platform.")
                    command = [resolved, target]
            elif sys.platform == "darwin":
                command = ["/usr/bin/open", target]
            elif os.name == "nt":
                os.startfile(target)
                return TaskResult(task, True, f"Handed to the desktop: {target}")
            else:
                executable = shutil.which("xdg-open")
                if not executable:
                    raise AssistantError("No desktop opener is available on this system.")
                command = [executable, target]
        try:
            process = subprocess.Popen(command, shell=False, close_fds=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if sys.platform == "darwin":
                try:
                    if process.wait(timeout=5) != 0:
                        raise AssistantError("The desktop rejected the launch. Check that the app is installed and the target exists.")
                except subprocess.TimeoutExpired:
                    return TaskResult(task, True, f"Launch submitted; desktop completion not confirmed: {target}")
        except OSError as exc:
            raise AssistantError("The desktop launcher could not start.") from exc
        return TaskResult(task, True, f"Launch handed to the desktop: {target}. Application readiness is not monitored.")
