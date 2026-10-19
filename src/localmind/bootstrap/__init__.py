"""Application composition root. Infrastructure is assembled only here."""

from pathlib import Path

from localmind.application.ports import IntentClassifier
from localmind.application.task_registry import TaskRegistry
from localmind.application.use_cases.conversation_history import ConversationHistory
from localmind.application.use_cases.install_local_model import InstallLocalModel
from localmind.application.use_cases.interpret_request import InterpretAssistantRequest
from localmind.application.use_cases.launch_workspace import LaunchWorkspaceInVSCode
from localmind.application.use_cases.organize_photos import OrganizePhotos
from localmind.application.use_cases.reveal_workspace_file import RevealWorkspaceFile
from localmind.application.use_cases.run_tasks import RunTasks
from localmind.application.use_cases.search_workspace import SearchWorkspaceFiles
from localmind.infrastructure.filesystem.file_actions import ScopedFileActions
from localmind.infrastructure.filesystem.inspection import LocalInspection
from localmind.infrastructure.filesystem.photo_organizer import FilesystemPhotoOrganizer
from localmind.infrastructure.filesystem.scanner import FilesystemScanner
from localmind.infrastructure.models.installer import PinnedHuggingFaceModelInstaller
from localmind.infrastructure.models.intent_classifier import OnnxIntentClassifier
from localmind.infrastructure.persistence.history import SQLiteConversationRepository
from localmind.infrastructure.platform.catalog_desktop import CatalogDesktop
from localmind.infrastructure.platform.file_revealer import DesktopFileRevealer
from localmind.infrastructure.platform.launcher import DesktopApplicationLauncher
from localmind.infrastructure.platform.system_metrics import SystemMetrics
from localmind.presentation.assistant_viewmodel import AssistantViewModel
from localmind.presentation.history_viewmodel import HistoryViewModel
from localmind.presentation.viewmodels import DashboardViewModel


def create_view_models(
    data_directory: Path | None = None, *, classifier: IntentClassifier | None = None,
    journal_directory: Path | None = None, history_path: Path | None = None,
) -> tuple[DashboardViewModel, AssistantViewModel]:
    model_installer = PinnedHuggingFaceModelInstaller(data_directory)
    app_data = model_installer.install_path.parent.parent
    view_model = DashboardViewModel(
        SearchWorkspaceFiles(FilesystemScanner()),
        LaunchWorkspaceInVSCode(DesktopApplicationLauncher()),
        RevealWorkspaceFile(DesktopFileRevealer()),
        InstallLocalModel(model_installer),
    )
    # Explicit overrides keep integration tests out of the user's application DB.
    history = HistoryViewModel(ConversationHistory(SQLiteConversationRepository(history_path or app_data / "history.sqlite3")))
    inspection = LocalInspection()
    file_actions = ScopedFileActions(journal_directory or app_data / "actions")
    tasks = RunTasks(TaskRegistry({
        "folder": inspection.folder, "project": inspection.project, "preview": inspection.preview,
        "files": file_actions.preview, "desktop": CatalogDesktop().execute, "system": SystemMetrics().execute,
    }), file_actions)
    assistant = AssistantViewModel(
        InterpretAssistantRequest(classifier or OnnxIntentClassifier(model_installer)),
        OrganizePhotos(FilesystemPhotoOrganizer(journal_directory or app_data / "actions")),
        history,
        tasks,
    )
    view_model.assistantRequest.connect(assistant.submit)
    view_model.workspaceChanged.connect(lambda: assistant.setWorkspace(view_model.workspace))
    assistant.busyChanged.connect(lambda: view_model.setAssistantBusy(assistant.busy or history.switching))
    history.switchingChanged.connect(lambda: view_model.setAssistantBusy(assistant.busy or history.switching))
    view_model.busyChanged.connect(lambda: history.setActionBusy(view_model.busy))
    view_model.busyChanged.connect(lambda: assistant.setExternalBusy(view_model._busy))
    assistant.scanCancelRequested.connect(view_model.cancelScan)
    assistant.scanRequested.connect(view_model.runAssistantScan)
    assistant.launchRequested.connect(view_model.openWorkspaceInVSCode)
    assistant.filesystemChanged.connect(view_model.invalidateFileResults)
    assistant.activityEvent.connect(view_model._record_activity_entry)
    view_model.toolFinished.connect(assistant.receiveToolResult)
    view_model.fileResults.connect(assistant.receiveFileResults)
    history.sessionLoaded.connect(assistant.restoreConversation)
    history.initialize()
    return view_model, assistant
