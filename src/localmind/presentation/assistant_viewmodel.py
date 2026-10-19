"""Conversation, clarification, approval, and asynchronous assistant tasks."""

from __future__ import annotations

import re
import threading
from collections import Counter
from collections.abc import Callable
from typing import TYPE_CHECKING

from PySide6.QtCore import (
    Property,
    QAbstractListModel,
    QModelIndex,
    QObject,
    QRunnable,
    Qt,
    QThreadPool,
    Signal,
    Slot,
)
from PySide6.QtWidgets import QMessageBox

from localmind.application.use_cases.conversation_history import WELCOME
from localmind.application.use_cases.interpret_request import (
    InterpretAssistantRequest,
    organization_strategy,
)
from localmind.application.use_cases.organize_photos import OrganizePhotos
from localmind.application.use_cases.run_tasks import RunTasks
from localmind.domain.assistant import AssistantDecision, AssistantError, TaskCancelled
from localmind.domain.files import ScanReport
from localmind.domain.history import HistorySnapshot
from localmind.domain.organization import OrganizationResult, PhotoPlan
from localmind.domain.tasks import FilePlan, TaskBatchResult, TaskRequest, TaskResult

if TYPE_CHECKING:
    from localmind.presentation.history_viewmodel import HistoryViewModel


class PhotoPlanModel(QAbstractListModel):
    """Expose every proposed move lazily rather than copying 50,000 rows to QML."""

    SOURCE = Qt.UserRole + 1
    DESTINATION = Qt.UserRole + 2
    KIND = Qt.UserRole + 3

    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self._plan: PhotoPlan | FilePlan | None = None

    def roleNames(self):
        return {self.SOURCE: b"sourcePath", self.DESTINATION: b"destinationPath", self.KIND: b"operationKind"}

    def rowCount(self, parent=None):
        if parent is None:
            parent = QModelIndex()
        return 0 if parent.isValid() or self._plan is None else len(self._plan.moves)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or self._plan is None or not 0 <= index.row() < len(self._plan.moves):
            return None
        move = self._plan.moves[index.row()]
        if role == self.SOURCE:
            return move.source
        if role == self.DESTINATION:
            return move.destination
        if role == self.KIND:
            return move.kind if isinstance(self._plan, FilePlan) else "move"
        return None

    def set_plan(self, plan: PhotoPlan | FilePlan | None) -> None:
        self.beginResetModel()
        self._plan = plan
        self.endResetModel()


class AssistantSignals(QObject):
    progress = Signal(str)
    finished = Signal(object)


class AssistantWorker(QRunnable):
    def __init__(self, task: Callable, cancel_event: threading.Event) -> None:
        super().__init__()
        self.task = task
        self.cancel_event = cancel_event
        self.signals = AssistantSignals()

    def run(self) -> None:
        try:
            result = self.task(self.cancel_event, self.signals.progress.emit)
            if self.cancel_event.is_set() and not isinstance(result, (OrganizationResult, TaskBatchResult, TaskResult)):
                raise TaskCancelled("Task cancelled. No file changes were approved.")
            self.signals.finished.emit({"result": result})
        except TaskCancelled as exc:
            self.signals.finished.emit({"cancelled": str(exc)})
        except AssistantError as exc:
            self.signals.finished.emit({"error": str(exc)})
        except Exception:  # noqa: BLE001 - unexpected worker failures must reach the UI
            self.signals.finished.emit({
                "error": "The local task could not finish. No further actions were attempted. "
                         "If file changes were interrupted, review the affected paths. "
                         "Only photo organization has automatic Undo."
            })


class AssistantViewModel(QObject):
    messagesChanged = Signal()
    busyChanged = Signal()
    statusChanged = Signal()
    planChanged = Signal()
    questionChanged = Signal()
    engineChanged = Signal()
    resultsChanged = Signal()
    scanCancelRequested = Signal()
    scanRequested = Signal(str, bool)
    launchRequested = Signal()
    filesystemChanged = Signal()
    activityEvent = Signal(str, str, str)

    def __init__(
        self, interpreter: InterpretAssistantRequest, organizer: OrganizePhotos,
        history: HistoryViewModel | None = None,
        tasks: RunTasks | None = None,
    ) -> None:
        super().__init__()
        self._interpreter = interpreter
        self._organizer = organizer
        self._history = history
        self._tasks = tasks
        self._context: dict = {}
        self._cards: list[dict] = []
        self._suggestions: list[str] = []
        self._recent: list[str] = []
        self._last_error = ""
        self._pending_tasks: tuple[TaskRequest, ...] = ()
        self._external_busy = False
        self._active_plan_id: str | None = None
        self._workspace = ""
        self._messages = [{
            "role": "assistant",
            "text": WELCOME,
        }]
        self._busy = False
        self._status = "Ready"
        self._engine = "Local tools · semantic model used when needed"
        self._question = ""
        self._deferred_decision: AssistantDecision | None = None
        self._plan: PhotoPlan | FilePlan | None = None
        self._plan_model = PhotoPlanModel(self)
        self._cancel_event: threading.Event | None = None
        self._worker: AssistantWorker | None = None
        self._operation = ""
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)

    @Property(QObject, constant=True)
    def history(self):
        return self._history

    @Slot(object)
    def restoreConversation(self, snapshot: HistorySnapshot) -> None:
        # Stored context and plans are data, never replayed approval or access.
        self._clear_plan(record_discard=False)
        self._set_question("")
        self._deferred_decision = None
        self._context = {}
        self._cards = []
        self._suggestions = []
        self._recent = []
        self._last_error = ""
        self._pending_tasks = ()
        self.resultsChanged.emit()
        self._messages = [{"role": item.role, "text": item.text} for item in snapshot.messages]
        self.messagesChanged.emit()

    @Property("QVariantList", notify=messagesChanged)
    def messages(self):
        return self._messages

    @Property("QVariantList", notify=resultsChanged)
    def resultCards(self):
        return self._cards

    @Property("QStringList", notify=resultsChanged)
    def suggestions(self):
        return self._suggestions

    @Property(int, constant=True)
    def registeredTaskCount(self):
        return len(self._tasks.registry.tasks) if self._tasks else 0

    def setExternalBusy(self, value: bool) -> None:
        self._external_busy = value

    @Property(bool, notify=busyChanged)
    def busy(self):
        return self._busy

    @Property(str, notify=statusChanged)
    def status(self):
        return self._status

    @Property(str, notify=engineChanged)
    def engine(self):
        return self._engine

    @Property(bool, notify=planChanged)
    def hasPlan(self):
        return self._plan is not None

    @Property(QObject, constant=True)
    def planModel(self):
        return self._plan_model

    @Property(int, notify=planChanged)
    def planCount(self):
        return len(self._plan.moves) if self._plan else 0

    @Property(str, notify=planChanged)
    def planScope(self):
        return self._plan.workspace if self._plan else ""

    @Property(str, notify=planChanged)
    def planSummary(self):
        if not self._plan:
            return ""
        if isinstance(self._plan, FilePlan):
            kinds = ", ".join(f"{count} {kind}" for kind, count in Counter(item.kind for item in self._plan.moves).items())
            return (f"Proposed operations: {kinds}. Changes would be applied only inside this folder. "
                    f"{self._plan.skipped:,} excluded entries. Existing files will never be replaced. "
                    "General file operations have no automatic undo. New file content is shown in the conversation.")
        grouping = {"month": "year and month", "year": "year", "type": "file format"}[self._plan.strategy]
        return (f"{len(self._plan.moves):,} images → Organized Photos, grouped by {grouping}. "
                f"{self._plan.fallback_dates:,} file-date fallbacks; {self._plan.skipped:,} inaccessible or linked entries skipped. "
                "Only images in this preview will move. Names are preserved except to avoid collisions.")

    @Property(bool, notify=questionChanged)
    def choosingStrategy(self):
        return self._question == "strategy"

    def _say(self, text: str, role: str = "assistant", *, persist: bool = True) -> None:
        self._messages = [*self._messages[-99:], {"role": role, "text": text}]
        self.messagesChanged.emit()
        if self._history and persist:
            self._history.append(role, text)

    def _set_question(self, value: str) -> None:
        self._question = value
        self.questionChanged.emit()

    def setWorkspace(self, workspace: str) -> None:
        if self._workspace != workspace:
            self._workspace = workspace
            self._context = {}
            self._cards = []
            self._suggestions = []
            self._pending_tasks = ()
            self.resultsChanged.emit()
            self._clear_plan()
            if self._history:
                self._history.saveContext({"workspace": workspace})
        if self._deferred_decision is not None and workspace:
            decision = self._deferred_decision
            self._deferred_decision = None
            self._dispatch(decision)

    @Slot(str)
    def submit(self, text: str) -> None:
        text = text.strip()
        if not text or self._history and self._history.switching:
            return
        if len(text) > 2000:
            self._say("Please keep your request under 2,000 characters.")
            return
        self._say(text, "user")
        lower = " ".join(text.casefold().strip(" .!?").split())
        lower = re.sub(r"[,;](?=\s)", "", lower)
        cancelling = lower in {"cancel", "stop", "no", "no thanks", "never mind", "nevermind", "forget it", "cancel that operation", "stop that", "cancel the scan"} or bool(re.fullmatch(
            r"(?:(?:please|can you|could you) )?(?:cancel|stop)(?: (?:that|this|the|current|my|last|it|operation|task|scan|organization|please|safely))*", lower))
        if self._busy or self._external_busy:
            if cancelling:
                self.cancel()
                self.scanCancelRequested.emit()
                self._say("Stopping the current task safely. Completed operations remain recorded.")
            elif re.search(r"\b(status|finished|progress|doing|working)\b", lower):
                self._say(self._status if self._busy else "A workspace scan is still running.")
            else:
                self._say("A task is running. You can ask for its status or say “cancel that operation”.")
            return
        if cancelling:
            self._clear_plan()
            self._set_question("")
            self._deferred_decision = None
            self._pending_tasks = ()
            self._say("Cancelled. No unapproved changes were made.")
            return
        if lower in {"status", "has the scan finished", "is it done", "are you finished", "task status"}:
            self._say("No task is running. " + (self._recent[-1] if self._recent else "No tools have completed in this live conversation yet."))
            return
        if lower in {"which folder did you mean", "which folder", "what folder are you using"}:
            self._say(self._context.get("scope") or self._workspace or "No folder is selected. Choose a workspace or explicitly name Downloads.")
            return
        if self._plan and re.search(r"what will change|show (?:me )?(?:the )?(?:preview|plan)|before (?:you )?organiz", lower):
            self._say(self.planSummary + "\nFolder: " + self.planScope + "\nThe complete change list is in the approval preview. No changes have been applied.")
            return
        approving = lower in {"yes", "yes please", "yes do it", "do it", "go ahead", "looks good", "approve", "apply", "organize them", "yes organize those files", "yes organize them", "yes apply this plan"} or bool(re.fullmatch(
            r"(?:yes(?: please)? )?(?:approve|apply|organize|move|create|rename|copy)(?: (?:this|that|the|those|these|current|reviewed|shown|approved|proposed|plan|changes|files|them|it|folder|file|preview|now|please))*", lower))
        if self._plan and approving:
            self._approve_plan("chat")
            return
        if lower in {"start a new conversation", "new conversation", "reset conversation"}:
            if self._history:
                self._history.newConversation()
            return
        if re.search(r"what (?:did you do|happened).*earlier|recent activity", lower):
            self._say("\n".join(self._recent) or "No completed tools in this live conversation yet.")
            return
        if re.search(r"why did (?:that|it) fail|last error", lower):
            self._say(self._last_error or "No tool failure has been recorded in this live conversation.")
            return
        if re.search(r"what (?:does that mean|should i do next)|explain (?:that|the results)|give me a short summary", lower):
            self._say((self._context.get("summary", "No live result yet. Ask me to analyze a folder first.")[:2500]) +
                      ("\nNext supported actions: " + "; ".join(self._suggestions) if self._suggestions else ""),
                      persist=not self._context.get("private_content", False))
            return
        if re.search(r"how many files (?:did you find|were found)", lower) and "file_count" in self._context:
            self._say(f"The last scan found {self._context['file_count']:,} files in {self._context['scope']}. " +
                      ("It was partial; this is not a whole-folder total." if self._context.get("partial") else "Excluded entries were not counted."))
            return
        if self._pending_tasks:
            pending = self._pending_tasks
            self._pending_tasks = ()
            if len(text.split()) <= 6 and not re.search(r"\b(delete|open|find|organize|create|analyze|show|rename|move|copy)\b", lower):
                task = pending[-1]
                self._dispatch(AssistantDecision(capability="task_pipeline", tasks=(TaskRequest(task.task_id, {**task.parameters, "target": text.strip(' "“”')}),)))
                return
        if re.fullmatch(r"(?:please )?(?:undo(?: (?:that|it|the last organization))?|put (?:them|the photos|the images) back|restore (?:my |the )?(?:photos|images))", lower):
            self.undoLastOrganization()
            return
        strategy = organization_strategy(text)
        simple_strategy_reply = len(text.split()) <= 10 and not re.search(
            r"\b(delete|remove|don't|do not|never|without|open|find|search|rename|resize)\b", lower
        )
        if strategy and simple_strategy_reply and (self._question == "strategy" or isinstance(self._plan, PhotoPlan)):
            self._clear_plan()
            self._set_question("")
            self._dispatch(AssistantDecision(capability="organize_photos", strategy=strategy))
            return
        if self._question == "query":
            self._set_question("")
            self._dispatch(AssistantDecision(capability="search_files", query=text[:200]))
            return
        self._clear_plan()
        self._set_question("")
        self._deferred_decision = None
        self._start("interpret", "Understanding your request locally…",
                    lambda event, progress: self._interpreter.execute(text, event))

    def _dispatch(self, decision: AssistantDecision) -> None:
        if decision.model_version:
            self._engine = decision.model_version
            self.engineChanged.emit()
        if decision.capability == "unknown":
            self._say(decision.message)
            return
        if decision.capability == "task_pipeline" and self._tasks:
            needs_scope = any(not item.task_id.startswith("S") and item.task_id not in {"A01", "A04"} and not item.parameters.get("scope") for item in decision.tasks)
            if needs_scope and not self._workspace and not self._context.get("scope"):
                self._deferred_decision = decision
                self._say("Choose the folder using Choose workspace. I'll continue this request there.")
                return
            workspace, context = self._workspace, dict(self._context)
            self._pending_tasks = decision.tasks
            self._start("tasks", "Running local tools…", lambda event, progress: self._tasks.execute(decision.tasks, workspace, context, event, progress))
            return
        if (self._tasks and decision.capability in {"list_files", "search_files", "find_pdfs"}
                and self._context.get("scope") and (decision.capability != "search_files" or decision.query)):
            self._dispatch(AssistantDecision(capability="task_pipeline", tasks=(TaskRequest("F14", {
                "query": decision.query, "extension": "pdf" if decision.capability == "find_pdfs" else "",
            }),)))
            return
        if not self._workspace and not self._context.get("scope"):
            self._deferred_decision = decision
            self._say("Choose the folder you want me to work in using Choose workspace. I'll continue this request there.")
            return
        if self._history:
            self._history.saveContext({"workspace": self._workspace, "last_tool": decision.capability})
        if decision.capability == "organize_photos":
            if decision.needs_strategy or not decision.strategy:
                self._set_question("strategy")
                self._say(decision.message or "How should I group the images: by month, year, or file type?")
                return
            workspace, strategy = self._context.get("scope") or self._workspace, decision.strategy
            self._start("preview", "Inspecting images and preparing a preview…",
                        lambda event, progress: self._organizer.preview(workspace, strategy, event, progress))
        elif decision.capability == "search_files" and not decision.query:
            self._set_question("query")
            self._say(decision.message or "What filename should I look for?")
        elif decision.capability in {"search_files", "list_files", "find_pdfs"}:
            self._say(f"I'll look in the selected folder: {self._workspace}. Results will appear under Workspace files.")
            self.scanRequested.emit(decision.query, decision.capability == "find_pdfs")
        elif decision.capability == "open_vscode":
            if self._tasks:
                self._dispatch(AssistantDecision(capability="task_pipeline", tasks=(TaskRequest("A01", {"target": "vscode"}),)))
                return
            self._say(f"I can open {self._workspace} in VS Code. Please confirm the launch in the dialog.")
            self.launchRequested.emit()

    def _start(self, operation: str, status: str, task: Callable) -> None:
        self._busy = True
        self._status = status
        self._operation = operation
        self._cancel_event = threading.Event()
        worker = AssistantWorker(task, self._cancel_event)
        worker.signals.progress.connect(self._on_progress)
        worker.signals.finished.connect(self._on_finished)
        self._worker = worker
        self.busyChanged.emit()
        self.statusChanged.emit()
        self._pool.start(worker)

    @Slot(str)
    def _on_progress(self, message: str) -> None:
        self._status = message
        self.statusChanged.emit()

    @Slot(object)
    def _on_finished(self, payload: dict) -> None:
        operation = self._operation
        self._worker = None
        self._cancel_event = None
        self._busy = False
        self._status = "Ready"
        self.busyChanged.emit()
        self.statusChanged.emit()
        if "error" in payload or "cancelled" in payload:
            self._last_error = payload.get("error", "")
            self._say(payload.get("error", payload.get("cancelled")))
            self.activityEvent.emit("Assistant task", operation, "Failed" if "error" in payload else "Cancelled")
            if operation in {"apply", "undo", "file_apply"}:
                self.filesystemChanged.emit()
            if self._history:
                self._history.recordEvent(operation, "failed" if "error" in payload else "cancelled",
                                          payload.get("error", payload.get("cancelled")), self._active_plan_id)
            self._active_plan_id = None
            return
        result = payload["result"]
        if isinstance(result, AssistantDecision):
            self._dispatch(result)
        elif isinstance(result, TaskBatchResult):
            self._cards = []
            pending = self._pending_tasks
            for item in result.results:
                self._receive_result(item)
            if result.results and not result.results[-1].success and "Which file" in result.results[-1].message:
                self._pending_tasks = tuple(item for item in pending if item.task_id == result.results[-1].task_id)
            self.resultsChanged.emit()
        elif isinstance(result, TaskResult):
            self._receive_result(result)
            self.filesystemChanged.emit()
            self._active_plan_id = None
        elif isinstance(result, PhotoPlan):
            self._context = {"scope": result.workspace, "summary": f"Photo organization preview for {len(result.moves)} images."}
            if not result.moves:
                self._say(f"I found no images to organize in {result.workspace}. The existing Organized Photos folder is excluded. "
                          f"{result.skipped:,} inaccessible or linked entries were skipped.")
                return
            self._plan = result
            if self._history:
                self._history.savePlan(result)
                self._history.saveContext({"workspace": result.workspace, "last_tool": "organize_photos", "last_plan_id": result.id})
            self._plan_model.set_plan(result)
            self.planChanged.emit()
            self._say(f"I've prepared a plan for {len(result.moves):,} images. Review the complete move list below. "
                      "Nothing has moved yet. Approve this plan, ask for a different grouping, or cancel.")
            self.activityEvent.emit("Photo organization", f"{len(result.moves):,} images ready for review", "Awaiting approval")
        elif isinstance(result, OrganizationResult):
            verb = "restored to their original paths" if operation == "undo" else "moved into Organized Photos"
            message = f"{result.completed:,} of {result.total:,} images {verb}."
            if result.cancelled:
                message += " Stopped at your request. Completed moves remain recorded; use Undo to restore them."
            if result.error:
                message += " " + result.error
            elif operation == "apply" and result.completed:
                message += " You can undo this organization, including after restarting LocalMind."
            self._say(message)
            self.activityEvent.emit("Undo photo organization" if operation == "undo" else "Organize photos",
                                    message, "Failed" if result.error else "Cancelled" if result.cancelled else "Complete")
            self.filesystemChanged.emit()
            if self._history:
                self._history.recordEvent(operation, "failed" if result.error else "cancelled" if result.cancelled else "completed",
                                          message + f" Operation: {result.operation_id}", result.operation_id)
            self._active_plan_id = None

    def _receive_result(self, result: TaskResult) -> None:
        definition = self._tasks.registry.definition(result.task_id) if self._tasks else None
        title = definition.name if definition else "Approved file changes" if result.task_id == "file_commit" else "Local task"
        contains_content = result.task_id.startswith(("C", "P")) and result.task_id != "C15"
        self._say(result.message, persist=not contains_content)
        if contains_content and self._history:
            self._history.append("assistant", f"{result.task_id}: {'completed' if result.success else 'failed'}. File/project content is shown only in the live session and is not retained.")
        state = " · Awaiting approval" if result.plan and result.plan.moves else " · Completed" if result.success else " · Needs attention"
        self._cards = [*self._cards[-5:], {"taskId": result.task_id, "title": title + state, "detail": result.message[:240]}]
        self._suggestions = list(result.suggestions)
        self._recent = [*self._recent[-9:], title + ": " + ("Content inspection completed; extracted text is not retained." if contains_content else result.message[:220])]
        if result.success:
            # A new folder/file result replaces old references; never merge stale file targets.
            if result.data.get("scope"):
                self._context = {**(self._context if result.plan and self._context.get("scope") == result.data["scope"] else {}), **result.data, "summary": result.message, "private_content": contains_content}
            else:
                self._context = {**self._context, "summary": result.message, "private_content": contains_content}
            if not result.plan:
                self._pending_tasks = ()
        else:
            self._last_error = result.message
            if "Which file" not in result.message:
                self._pending_tasks = ()
        if result.plan is not None:
            self._pending_tasks = ()
            if result.plan.moves:
                self._plan = result.plan
                self._plan_model.set_plan(result.plan)
                if self._history:
                    self._history.savePlan(result.plan)
                self.planChanged.emit()
            else:
                self._say("No matching files need changes. No approval is needed.")
        if self._history:
            self._history.recordEvent(result.task_id, "completed" if result.success else "failed",
                                      f"{result.task_id}: content inspection {'completed' if result.success else 'failed'}." if contains_content else result.message,
                                      self._active_plan_id)
        self.activityEvent.emit(title, result.message[:150], "Awaiting approval" if result.plan and result.plan.moves else "Complete" if result.success else "Failed")
        self.resultsChanged.emit()

    @Slot()
    def approvePlan(self) -> None:
        self._approve_plan("button")

    def _approve_plan(self, source: str) -> None:
        if self._busy or self._plan is None:
            return
        plan = self._plan
        self._active_plan_id = plan.id
        if self._history:
            self._history.recordApproval(plan.id, True, source)
        self._clear_plan(record_discard=False)
        if isinstance(plan, FilePlan) and self._tasks:
            self._start("file_apply", f"Applying {len(plan.moves):,} approved changes…",
                        lambda event, progress: self._tasks.apply(plan, plan.id, event, progress))
            return
        self._start("apply", f"Organizing {len(plan.moves):,} approved images…",
                    lambda event, progress: self._organizer.apply(plan, plan.id, event, progress))

    @Slot()
    def discardPlan(self) -> None:
        if self._busy:
            return
        self._clear_plan()
        self._set_question("")
        self._say("Preview discarded. No files were moved.")

    def _clear_plan(self, *, record_discard: bool = True) -> None:
        if record_discard and self._plan is not None and self._history:
            self._history.recordApproval(self._plan.id, False, "discard")
        if record_discard and self._plan is not None:
            self._cards = [
                {**card, "title": card["title"].removesuffix(" · Awaiting approval") + " · Preview discarded",
                 "detail": "No changes were applied."}
                if card["title"].endswith(" · Awaiting approval") else card
                for card in self._cards
            ]
            self.resultsChanged.emit()
            self.activityEvent.emit("Preview discarded", "No changes were applied.", "Cancelled")
        self._plan = None
        self._plan_model.set_plan(None)
        self.planChanged.emit()

    @Slot()
    def undoLastOrganization(self) -> None:
        if self._busy:
            return
        workspace = self._context.get("scope") or self._workspace
        if not workspace:
            self._say("Choose the folder whose last photo organization you want to undo.")
            return
        answer = QMessageBox.question(
            None, "Undo last photo organization?",
            f"Restore the original paths from the most recent photo organization in:\n\n{workspace}\n\n"
            "Files that have been edited, replaced, or conflict with existing names will be left untouched.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            self._say("Undo declined. Files were left in their current folders.")
            return
        self._clear_plan()
        self._set_question("")
        self._start("undo", "Restoring original photo locations…",
                    lambda event, progress: self._organizer.undo(workspace, event, progress))

    @Slot()
    def cancel(self) -> None:
        if self._cancel_event:
            self._cancel_event.set()
            self._status = "Stopping safely…"
            self.statusChanged.emit()

    @Slot(str)
    def receiveToolResult(self, text: str) -> None:
        self._say(text)
        if self._history:
            self._history.recordEvent("file_or_launch_tool", "reported", text)

    @Slot(str, object)
    def receiveFileResults(self, scope: str, report: ScanReport) -> None:
        self._context = {"scope": scope, "files": [{"path": item.relative_path} for item in report.files],
                         "file_count": len(report.files), "partial": report.partial,
                         "summary": f"{len(report.files)} matching filenames in {scope}."}

    @Slot()
    def shutdown(self) -> None:
        if self._cancel_event:
            self._cancel_event.set()
        self._pool.waitForDone()
        if self._history:
            self._history.shutdown()
