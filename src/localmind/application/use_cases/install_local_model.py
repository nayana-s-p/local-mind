"""Use case for explicitly downloading the verified LocalMind model pack."""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

from localmind.application.ports import LocalModelInstaller


class InstallLocalModel:
    def __init__(self, installer: LocalModelInstaller) -> None:
        self._installer = installer

    @property
    def install_path(self) -> Path:
        return self._installer.install_path

    @property
    def total_size(self) -> int:
        return self._installer.total_size

    def is_installed(self) -> bool:
        return self._installer.is_installed()

    def execute(
        self,
        progress: Callable[[int, int], None],
        cancel_event: threading.Event,
    ) -> Path:
        return self._installer.install(progress, cancel_event)
