"""Ordered asynchronous persistence and functional history controls."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import uuid4

from PySide6.QtCore import Property, QObject, QRunnable, QThreadPool, Signal, Slot
from PySide6.QtWidgets import QMessageBox

from localmind.application.use_cases.conversation_history import ConversationHistory
from localmind.domain.history import HistoryError, HistorySnapshot
from localmind.domain.organization import PhotoPlan
from localmind.domain.tasks import FilePlan


class PersistenceSignals(QObject):
    finished = Signal(str, object)


class PersistenceWorker(QRunnable):
    def __init__(self, request_id: str, operation: Callable) -> None:
        super().__init__()
        self.request_id = request_id
        self.operation = operation
        self.signals = PersistenceSignals()

    def run(self) -> None:
        try:
            result = self.operation()
            self.signals.finished.emit(self.request_id, {"result": result})
        except HistoryError as exc:
            self.signals.finished.emit(self.request_id, {"error": str(exc)})
        except Exception:  # noqa: BLE001 - the worker boundary must report unexpected failures
            self.signals.finished.emit(self.request_id, {
                "error": "History could not be saved. Existing records and the separate photo undo journal were not reset."
            })


class HistoryViewModel(QObject):
    changed = Signal()
    switchingChanged = Signal()
    sessionLoaded = Signal(object)
    sessionOpened = Signal()

    def __init__(self, service: ConversationHistory) -> None:
        super().__init__()
        self._service = service
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self._workers: dict[str, tuple[PersistenceWorker, bool, bool]] = {}
        self._conversations: list[dict] = []
        self._conversation_id = ""
        self._ready = False
        self._switching = False
        self._action_busy = False
        self._error = ""
        self._retention_days = 30

    @Property("QVariantList", notify=changed)
    def conversations(self):
        return self._conversations

    @Property(str, notify=changed)
    def conversationId(self):
        return self._conversation_id

    @Property(bool, notify=changed)
    def ready(self):
        return self._ready

    @Property(bool, notify=switchingChanged)
    def switching(self):
        return self._switching

    @Property(bool, notify=changed)
    def pending(self):
        return bool(self._workers)

    @Property(str, notify=changed)
    def error(self):
        return self._error

    @Property(int, notify=changed)
    def retentionDays(self):
        return self._retention_days

    def setActionBusy(self, busy: bool) -> None:
        self._action_busy = busy

    def initialize(self) -> None:
        self._enqueue(self._service.start, switching=True)

    def _enqueue(self, operation: Callable, *, switching: bool = False, navigate: bool = False) -> None:
        request_id = str(uuid4())
        worker = PersistenceWorker(request_id, operation)
        worker.signals.finished.connect(self._on_finished)
        self._workers[request_id] = (worker, switching, navigate)
        if switching:
            self._switching = True
            self.switchingChanged.emit()
        self.changed.emit()
        self._pool.start(worker)

    @Slot(str, object)
    def _on_finished(self, request_id: str, payload: dict) -> None:
        record = self._workers.pop(request_id, None)
        if record is None:
            return
        if record[1]:
            self._switching = False
            self.switchingChanged.emit()
        if "error" in payload:
            self._error = payload["error"]
            self.changed.emit()
            return
        result = payload["result"]
        self._error = ""
        if isinstance(result, HistorySnapshot):
            self._conversation_id = result.conversation_id
            self._retention_days = result.retention_days
            self._ready = True
            self._set_conversations(result.conversations)
            self.sessionLoaded.emit(result)
            if record[2]:
                self.sessionOpened.emit()
        elif isinstance(result, tuple):
            self._set_conversations(result)
        self.changed.emit()

    def _set_conversations(self, conversations) -> None:
        self._conversations = [
            {
                "id": item.id, "title": item.title, "messageCount": item.message_count,
                "updated": datetime.fromtimestamp(item.updated_at).astimezone().strftime("%Y-%m-%d %H:%M"),
            }
            for item in conversations
        ]

    def append(self, role: str, text: str) -> None:
        if not self._ready or self._switching:
            return
        conversation_id = self._conversation_id
        self._enqueue(lambda: self._service.repository.append_message(conversation_id, role, text))

    def saveContext(self, context: dict[str, str]) -> None:
        if self._ready and not self._switching:
            conversation_id = self._conversation_id
            snapshot = dict(context)
            self._enqueue(lambda: self._service.repository.save_context(conversation_id, snapshot))

    def savePlan(self, plan: PhotoPlan | FilePlan) -> None:
        if self._ready:
            conversation_id = self._conversation_id
            self._enqueue(lambda: self._service.repository.save_plan(conversation_id, plan))

    def recordApproval(self, plan_id: str, approved: bool, source: str) -> None:
        if self._ready:
            conversation_id = self._conversation_id
            self._enqueue(lambda: self._service.repository.record_approval(conversation_id, plan_id, approved, source))

    def recordEvent(self, kind: str, outcome: str, summary: str, plan_id: str | None = None) -> None:
        if self._ready:
            conversation_id = self._conversation_id
            self._enqueue(lambda: self._service.repository.record_event(conversation_id, plan_id, kind, outcome, summary))

    @Slot(str)
    def openConversation(self, conversation_id: str) -> None:
        if self._action_busy or self._switching:
            return
        self._enqueue(lambda: self._service.repository.open_conversation(conversation_id), switching=True, navigate=True)

    @Slot()
    def newConversation(self) -> None:
        if self._action_busy or self._switching:
            return
        self._enqueue(self._service.new, switching=True, navigate=True)

    @Slot()
    def clearHistory(self) -> None:
        if self._action_busy or self._switching:
            return
        answer = QMessageBox.question(
            None, "Clear local conversation history?",
            "Permanently remove local conversations, messages, context references, and conversation audit records?\n\n"
            "Photo undo records and downloaded models will be kept.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self._enqueue(self._service.clear, switching=True)

    @Slot(int)
    def setRetentionDays(self, days: int) -> None:
        if self._action_busy or self._switching or not self._ready:
            return
        if days < self._retention_days:
            answer = QMessageBox.question(
                None, "Reduce history retention?",
                f"Keep at most {days} days of local conversation history? Older history will be permanently removed.\n\n"
                "The independent photo undo journal will be kept.",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                self.changed.emit()
                return
        conversation_id = self._conversation_id
        self._enqueue(lambda: self._service.change_retention(conversation_id, days), switching=True)

    @Slot()
    def shutdown(self) -> None:
        self._pool.waitForDone()
