"""Preview and explicitly authorize immutable photo organization plans."""

import threading
from collections.abc import Callable

from localmind.application.ports import PhotoOrganizer
from localmind.domain.assistant import OrganizationStrategy
from localmind.domain.organization import (
    OrganizationError,
    OrganizationResult,
    PhotoPlan,
)


class OrganizePhotos:
    def __init__(self, organizer: PhotoOrganizer) -> None:
        self._organizer = organizer

    def preview(
        self, workspace: str, strategy: OrganizationStrategy,
        cancel_event: threading.Event, progress: Callable[[str], None],
    ) -> PhotoPlan:
        if strategy not in {"month", "year", "type"}:
            raise OrganizationError("Choose month, year, or file type as the grouping method.")
        return self._organizer.preview(workspace, strategy, cancel_event, progress)

    def apply(
        self, plan: PhotoPlan, approved_plan_id: str,
        cancel_event: threading.Event, progress: Callable[[str], None],
    ) -> OrganizationResult:
        if not approved_plan_id or approved_plan_id != plan.id:
            raise OrganizationError("Review and approve this exact preview before moving files.")
        return self._organizer.execute(plan, cancel_event, progress)

    def undo(
        self, workspace: str, cancel_event: threading.Event, progress: Callable[[str], None],
    ) -> OrganizationResult:
        return self._organizer.undo(workspace, cancel_event, progress)
