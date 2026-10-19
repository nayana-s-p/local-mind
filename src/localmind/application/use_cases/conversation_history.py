"""Bounded conversation use case; persistence is never execution authority."""

from localmind.application.ports import ConversationRepository
from localmind.domain.history import HistoryError, HistorySnapshot

WELCOME = (
    "What would you like help with? I can inspect folders, projects and text files, show system metrics, "
    "open supported apps and prepare file-change previews. Try: “Analyze my Downloads, show the biggest files, "
    "and help me organize the PDFs.” File changes wait for your approval."
)
RETENTION_DAYS = (7, 30, 90, 365)


class ConversationHistory:
    def __init__(self, repository: ConversationRepository) -> None:
        self.repository = repository

    def start(self) -> HistorySnapshot:
        return self.repository.initialize(WELCOME)

    def new(self) -> HistorySnapshot:
        return self.repository.new_conversation(WELCOME)

    def clear(self) -> HistorySnapshot:
        return self.repository.clear(WELCOME)

    def change_retention(self, conversation_id: str, days: int) -> HistorySnapshot:
        if days not in RETENTION_DAYS:
            raise HistoryError("Choose 7, 30, 90, or 365 days of local history.")
        return self.repository.set_retention(conversation_id, days)
