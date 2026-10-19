"""Use an available system UI font, including on Qt's offscreen platform."""

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication


def configure_application_font(app: QApplication) -> None:
    available = set(QFontDatabase.families())
    font = app.font()
    if font.family() not in available:
        for family in ("SF Pro Text", "Helvetica Neue", "Segoe UI", "Noto Sans", "DejaVu Sans", "Arial"):
            if family in available:
                font.setFamily(family)
                app.setFont(font)
                break
