"""Dashboard state and worker-thread orchestration."""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import datetime
from platform import python_version, system

from PySide6.QtCore import Property, QObject, QRunnable, QThreadPool, Signal, Slot
from PySide6.QtWidgets import QFileDialog, QMessageBox

from localmind.application.use_cases.install_local_model import InstallLocalModel
from localmind.application.use_cases.launch_workspace import LaunchWorkspaceInVSCode
from localmind.application.use_cases.reveal_workspace_file import RevealWorkspaceFile
from localmind.application.use_cases.search_workspace import SearchWorkspaceFiles
from localmind.domain.applications import ApplicationLaunchError
from localmind.domain.files import (
    FileRevealError,
    ScanReport,
    WorkspaceError,
)
from localmind.domain.models import ModelInstallCancelled, ModelInstallError


class ScanSignals(QObject):
    finished = Signal(int, object)


class ScanWorker(QRunnable):
    def __init__(
        self,
        task_id: int,
        workspace: str,
        query: str,
        pdf_only: bool,
        cancel_event: threading.Event,
        search_workspace: SearchWorkspaceFiles,
    ) -> None:
        super().__init__()
        self.task_id = task_id
        self.workspace = workspace
        self.query = query
        self.pdf_only = pdf_only
        self.cancel_event = cancel_event
        self.search_workspace = search_workspace
        self.signals = ScanSignals()

    def run(self) -> None:
        try:
            report = self.search_workspace.execute(
                self.workspace,
                query=self.query,
                pdf_only=self.pdf_only,
                cancel_event=self.cancel_event,
            )
            self.signals.finished.emit(self.task_id, {"report": report})
        except WorkspaceError as exc:
            self.signals.finished.emit(self.task_id, {"error": str(exc)})
        except Exception:  # noqa: BLE001 - worker failures must reach the UI
            # Do not expose exception details or paths in the user-facing UI.
            self.signals.finished.emit(
                self.task_id,
                {"error": "The scan stopped because of an unexpected local error."},
            )


class ModelInstallSignals(QObject):
    progress = Signal(int, int)
    finished = Signal()
    failed = Signal(str)
    cancelled = Signal()


class ModelInstallWorker(QRunnable):
    def __init__(self, installer: InstallLocalModel, cancel_event: threading.Event) -> None:
        super().__init__()
        self.installer = installer
        self.cancel_event = cancel_event
        self.signals = ModelInstallSignals()

    def run(self) -> None:
        try:
            self.installer.execute(self.signals.progress.emit, self.cancel_event)
            self.signals.finished.emit()
        except ModelInstallCancelled:
            self.signals.cancelled.emit()
        except ModelInstallError as exc:
            if self.cancel_event.is_set():
                self.signals.cancelled.emit()
            else:
                self.signals.failed.emit(str(exc))
        except Exception:  # noqa: BLE001 - worker failures must reach the UI
            self.signals.failed.emit("Model setup stopped because of an unexpected local error.")


class LocalWorkSignals(QObject):
    finished = Signal(object)


class LocalWork(QRunnable):
    """Small existing OS/verification operations also stay off the GUI thread."""

    def __init__(self, task: Callable) -> None:
        super().__init__()
        self.task = task
        self.signals = LocalWorkSignals()

    def run(self) -> None:
        try:
            self.signals.finished.emit({"result": self.task()})
        except (ApplicationLaunchError, FileRevealError, OSError) as exc:
            self.signals.finished.emit({"error": str(exc)})
        except Exception:  # noqa: BLE001 - worker failures must reach the UI
            self.signals.finished.emit({"error": "The local operation could not finish."})


class DashboardViewModel(QObject):
    assistantRequest = Signal(str)
    toolFinished = Signal(str)
    fileResults = Signal(str, object)
    workspaceChanged = Signal()
    busyChanged = Signal()
    statusChanged = Signal()
    resultsChanged = Signal()
    activityChanged = Signal()
    scannedCountChanged = Signal()
    resultCountChanged = Signal()
    partialChanged = Signal()
    errorChanged = Signal()
    modelInstalledChanged = Signal()
    modelDownloadingChanged = Signal()
    modelProgressChanged = Signal()
    modelStatusChanged = Signal()
    modelErrorChanged = Signal()
    modelCheckingChanged = Signal()

    def __init__(
        self,
        search_workspace: SearchWorkspaceFiles,
        launch_workspace: LaunchWorkspaceInVSCode,
        reveal_workspace_file: RevealWorkspaceFile,
        install_local_model: InstallLocalModel,
    ) -> None:
        super().__init__()
        self._workspace = ""
        self._busy = False
        self._assistant_busy = False
        self._status = "Choose a workspace to begin"
        self._results: list[dict[str, str | bool]] = []
        self._activity: list[dict[str, str]] = []
        self._scanned_count = 0
        self._result_count = 0
        self._partial = False
        self._error = ""
        self._task_id = 0
        self._pending_title = "File scan"
        self._cancel_event: threading.Event | None = None
        self._workers: dict[int, ScanWorker] = {}
        self._thread_pool = QThreadPool(self)
        self._thread_pool.setMaxThreadCount(1)
        self._search_workspace = search_workspace
        self._launch_workspace = launch_workspace
        self._reveal_workspace_file = reveal_workspace_file
        self._install_local_model = install_local_model
        self._model_installed = False
        self._model_checking = True
        self._model_downloading = False
        self._model_progress = 100 if self._model_installed else 0
        self._model_status = "Checking installed model files…"
        self._model_error = ""
        self._model_cancel_event: threading.Event | None = None
        self._model_worker: ModelInstallWorker | None = None
        self._setup_thread_pool = QThreadPool(self)
        self._setup_thread_pool.setMaxThreadCount(1)
        self._model_check = LocalWork(install_local_model.is_installed)
        self._model_check.signals.finished.connect(self._on_model_checked)
        self._setup_thread_pool.start(self._model_check)
        self._desktop_pool = QThreadPool(self)
        self._desktop_pool.setMaxThreadCount(1)
        self._desktop_worker: LocalWork | None = None
        self._desktop_title = ""
        self._desktop_success = ""

    @Slot(object)
    def _on_model_checked(self, payload: dict) -> None:
        self._model_checking = False
        self._model_installed = bool(payload.get("result", False))
        self._model_progress = 100 if self._model_installed else 0
        self._model_status = "Downloaded and verified" if self._model_installed else "Not installed"
        self._model_error = payload.get("error", "")
        self.modelCheckingChanged.emit()
        self.modelInstalledChanged.emit()
        self.modelProgressChanged.emit()
        self.modelStatusChanged.emit()
        self.modelErrorChanged.emit()

    @Property(str, notify=workspaceChanged)
    def workspace(self) -> str:
        return self._workspace

    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._busy or self._assistant_busy

    def setAssistantBusy(self, value: bool) -> None:
        self._assistant_busy = value
        self.busyChanged.emit()

    @Property(str, notify=statusChanged)
    def status(self) -> str:
        return self._status

    @Property("QVariantList", notify=resultsChanged)
    def results(self) -> list[dict[str, str | bool]]:
        return self._results

    @Property("QVariantList", notify=activityChanged)
    def activity(self) -> list[dict[str, str]]:
        return self._activity

    @Property(int, notify=scannedCountChanged)
    def scannedCount(self) -> int:
        return self._scanned_count

    @Property(int, notify=resultCountChanged)
    def resultCount(self) -> int:
        return self._result_count

    @Property(bool, notify=partialChanged)
    def partial(self) -> bool:
        return self._partial

    @Property(str, notify=errorChanged)
    def error(self) -> str:
        return self._error

    @Property(bool, notify=modelInstalledChanged)
    def modelInstalled(self) -> bool:
        return self._model_installed

    @Property(bool, notify=modelCheckingChanged)
    def modelChecking(self) -> bool:
        return self._model_checking

    @Property(bool, notify=modelDownloadingChanged)
    def modelDownloading(self) -> bool:
        return self._model_downloading

    @Property(int, notify=modelProgressChanged)
    def modelProgress(self) -> int:
        return self._model_progress

    @Property(str, notify=modelStatusChanged)
    def modelStatus(self) -> str:
        return self._model_status

    @Property(str, notify=modelErrorChanged)
    def modelError(self) -> str:
        return self._model_error

    @Property(str, constant=True)
    def modelPath(self) -> str:
        return str(self._install_local_model.install_path)

    @Property(int, constant=True)
    def modelDownloadSize(self) -> int:
        return self._install_local_model.total_size

    @Property(str, constant=True)
    def runtimeLabel(self) -> str:
        return f"Python {python_version()} · {system()}"

    @Slot()
    def chooseWorkspace(self) -> None:
        if self.busy:
            return
        selected = QFileDialog.getExistingDirectory(
            None,
            "Choose a local workspace",
            self._workspace or "",
        )
        if not selected:
            return
        self._workspace = selected
        self._error = ""
        self._results = []
        self._result_count = 0
        self._scanned_count = 0
        self._partial = False
        self._status = "Workspace selected · ready for your request"
        self.workspaceChanged.emit()
        self.errorChanged.emit()
        self.statusChanged.emit()
        self.resultsChanged.emit()
        self.resultCountChanged.emit()
        self.scannedCountChanged.emit()
        self.partialChanged.emit()

    @Slot()
    def downloadModel(self) -> None:
        if self._model_downloading or self._model_checking:
            return
        self._model_error = ""
        self._model_progress = 0
        self._model_downloading = True
        self._model_status = "Preparing secure download…"
        self._model_cancel_event = threading.Event()
        worker = ModelInstallWorker(self._install_local_model, self._model_cancel_event)
        worker.signals.progress.connect(self._on_model_progress)
        worker.signals.finished.connect(self._on_model_installed)
        worker.signals.failed.connect(self._on_model_install_failed)
        worker.signals.cancelled.connect(self._on_model_install_cancelled)
        self._model_worker = worker
        self.modelErrorChanged.emit()
        self.modelProgressChanged.emit()
        self.modelDownloadingChanged.emit()
        self.modelStatusChanged.emit()
        self._setup_thread_pool.start(worker)

    @Slot()
    def cancelModelDownload(self) -> None:
        if self._model_cancel_event is None or not self._model_downloading:
            return
        self._model_cancel_event.set()
        self._model_status = "Stopping download…"
        self.modelStatusChanged.emit()

    @Slot(int, int)
    def _on_model_progress(self, downloaded: int, total: int) -> None:
        self._model_progress = int(downloaded * 100 / total) if total else 0
        downloaded_mb = downloaded / 1_000_000
        total_mb = total / 1_000_000
        self._model_status = f"Downloading · {downloaded_mb:.1f} of {total_mb:.1f} MB"
        self.modelProgressChanged.emit()
        self.modelStatusChanged.emit()

    @Slot()
    def _on_model_installed(self) -> None:
        self._model_cancel_event = None
        self._model_worker = None
        self._model_downloading = False
        self._model_installed = True
        self._model_progress = 100
        self._model_error = ""
        self._model_status = "Downloaded and verified · saved on this device"
        self.modelInstalledChanged.emit()
        self.modelDownloadingChanged.emit()
        self.modelProgressChanged.emit()
        self.modelStatusChanged.emit()
        self.modelErrorChanged.emit()
        self._record_activity_entry("Install local model", "Model files downloaded and verified", "Complete")

    @Slot(str)
    def _on_model_install_failed(self, message: str) -> None:
        self._finish_model_download()
        self._model_status = "Setup failed"
        self._model_error = message
        self.modelStatusChanged.emit()
        self.modelErrorChanged.emit()

    @Slot()
    def _on_model_install_cancelled(self) -> None:
        self._finish_model_download()
        self._model_status = "Download cancelled · incomplete files removed"
        self.modelStatusChanged.emit()

    def _finish_model_download(self) -> None:
        self._model_cancel_event = None
        self._model_worker = None
        self._model_downloading = False
        self.modelDownloadingChanged.emit()

    @Slot(str)
    def searchFiles(self, query: str) -> None:
        query = query.strip()
        if not query:
            self._set_error("Enter a filename or part of a filename to search.")
            return
        self._start_scan(query=query, pdf_only=False, title="Filename search")

    @Slot(str)
    def submitCommand(self, text: str) -> None:
        self.assistantRequest.emit(text)

    @Slot(str, bool)
    def runAssistantScan(self, query: str, pdf_only: bool) -> None:
        self._start_scan(query=query, pdf_only=pdf_only, title="Find PDFs" if pdf_only else "Filename search" if query else "List files")

    @Slot()
    def openWorkspaceInVSCode(self) -> None:
        self._confirm_and_open_vscode()

    def _confirm_and_open_vscode(self) -> None:
        if not self._workspace:
            self._status = "Workspace required"
            self.statusChanged.emit()
            self._set_error("Choose the project folder first, then ask to open it in VS Code.")
            return
        answer = QMessageBox.question(
            None,
            "Open workspace in VS Code?",
            f"Launch VS Code with this selected workspace?\n\n{self._workspace}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            self._status = "Launch declined"
            self.statusChanged.emit()
            self._record_activity_entry("Open VS Code", "Launch was declined", "Declined")
            self.toolFinished.emit("VS Code launch declined.")
            return
        workspace = self._workspace
        self._start_desktop("Open VS Code", "VS Code launch request sent for the selected folder.",
                            lambda: self._launch_workspace.execute(workspace))

    def _start_desktop(self, title: str, success: str, task: Callable) -> None:
        if self.busy:
            return
        self._busy = True
        self._desktop_title = title
        self._desktop_success = success
        self._status = title + "…"
        worker = LocalWork(task)
        worker.signals.finished.connect(self._on_desktop_finished)
        self._desktop_worker = worker
        self.busyChanged.emit()
        self.statusChanged.emit()
        self._desktop_pool.start(worker)

    @Slot(object)
    def _on_desktop_finished(self, payload: dict) -> None:
        self._desktop_worker = None
        self._busy = False
        self._error = payload.get("error", "")
        self._status = self._error or self._desktop_success
        self._record_activity_entry(self._desktop_title, self._status, "Failed" if self._error else "Requested")
        self.busyChanged.emit()
        self.statusChanged.emit()
        self.errorChanged.emit()
        self.toolFinished.emit(self._status)

    @Slot()
    def listFiles(self) -> None:
        self._start_scan(query="", pdf_only=False, title="List files")

    @Slot(str)
    def findPdfs(self, query: str = "") -> None:
        self._start_scan(query=query.strip(), pdf_only=True, title="Find PDFs")

    @Slot(str)
    def revealFile(self, relative_path: str) -> None:
        if self.busy:
            return
        displayed_paths = {str(result.get("relativePath", "")) for result in self._results}
        if relative_path not in displayed_paths:
            self._set_error("Select a file from the current search results.")
            return
        workspace = self._workspace
        self._start_desktop("Show in folder", "Reveal request sent to the file manager.",
                            lambda: self._reveal_workspace_file.execute(workspace, relative_path))

    @Slot()
    def cancelScan(self) -> None:
        if self._cancel_event is None or not self._busy:
            return
        self._cancel_event.set()
        self._status = "Stopping scan…"
        self.statusChanged.emit()

    def _start_scan(self, *, query: str, pdf_only: bool, title: str) -> None:
        if self.busy:
            return
        if not self._workspace:
            self._set_error("Choose a workspace before scanning.")
            return

        self._task_id += 1
        task_id = self._task_id
        cancel_event = threading.Event()
        worker = ScanWorker(
            task_id,
            self._workspace,
            query,
            pdf_only,
            cancel_event,
            self._search_workspace,
        )
        worker.signals.finished.connect(self._on_scan_finished)
        self._workers[task_id] = worker
        self._cancel_event = cancel_event
        self._pending_title = title
        self._busy = True
        self._error = ""
        self._status = "Scanning selected workspace…"
        self._results = []
        self._result_count = 0
        self._scanned_count = 0
        self._partial = False
        self.busyChanged.emit()
        self.statusChanged.emit()
        self.errorChanged.emit()
        self.resultsChanged.emit()
        self.resultCountChanged.emit()
        self.scannedCountChanged.emit()
        self.partialChanged.emit()
        self._thread_pool.start(worker)

    @Slot(int, object)
    def _on_scan_finished(self, task_id: int, payload: object) -> None:
        self._workers.pop(task_id, None)
        if task_id != self._task_id:
            return
        self._cancel_event = None
        self._busy = False
        self.busyChanged.emit()

        if not isinstance(payload, dict):
            self._set_error("The scan returned an invalid result.")
            return
        if "error" in payload:
            self._status = "Scan stopped"
            self._set_error(str(payload["error"]))
            self.statusChanged.emit()
            self.toolFinished.emit(str(payload["error"]))
            return
        report = payload.get("report")
        if not isinstance(report, ScanReport):
            self._status = "Scan stopped"
            self._set_error("The scan returned an invalid result.")
            self.statusChanged.emit()
            return

        self._results = [
            {
                "name": file.name,
                "relativePath": file.relative_path,
                "extension": file.extension or "File",
                "isPdf": file.is_pdf,
            }
            for file in report.files
        ]
        self._result_count = len(report.files)
        self._scanned_count = report.entries_seen
        self._partial = report.partial
        self._status = self._completion_text(report)
        self._error = ""
        self.resultsChanged.emit()
        self.resultCountChanged.emit()
        self.scannedCountChanged.emit()
        self.partialChanged.emit()
        self.statusChanged.emit()
        self.errorChanged.emit()
        self._record_activity(self._pending_title, report)
        self.fileResults.emit(self._workspace, report)
        self.toolFinished.emit(self._status)

    @Slot()
    def invalidateFileResults(self) -> None:
        self._results = []
        self._result_count = 0
        self._scanned_count = 0
        self._partial = False
        self.resultsChanged.emit()
        self.resultCountChanged.emit()
        self.scannedCountChanged.emit()
        self.partialChanged.emit()

    @Slot()
    def shutdown(self) -> None:
        if self._cancel_event:
            self._cancel_event.set()
        if self._model_cancel_event:
            self._model_cancel_event.set()
        self._thread_pool.waitForDone()
        self._setup_thread_pool.waitForDone()
        self._desktop_pool.waitForDone()

    def _completion_text(self, report: ScanReport) -> str:
        if report.cancelled:
            summary = f"Scan cancelled · {len(report.files)} result(s)"
        elif report.partial:
            summary = f"Scan incomplete · {len(report.files)} result(s)"
        else:
            summary = f"Scan complete · {len(report.files)} result(s)"
        if report.unreadable_directories:
            summary += f" · {report.unreadable_directories} folder(s) skipped"
        return summary

    def _record_activity(self, title: str, report: ScanReport) -> None:
        if report.cancelled:
            outcome = "Cancelled"
        elif report.partial:
            outcome = "Partial"
        else:
            outcome = "Complete"
        self._record_activity_entry(
            title,
            f"{len(report.files)} result(s) · {report.entries_seen} entries checked",
            outcome,
        )

    def _record_activity_entry(self, title: str, detail: str, outcome: str) -> None:
        row = {
            "title": title,
            "detail": detail,
            "time": datetime.now().astimezone().strftime("%H:%M"),
            "outcome": outcome,
        }
        self._activity = [row, *self._activity[:4]]
        self.activityChanged.emit()

    def _set_error(self, message: str) -> None:
        self._error = message
        self.errorChanged.emit()

