"""Application entry point."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication

from localmind.bootstrap import create_view_models
from localmind.presentation.style import configure_application_font


def main() -> int:
    QQuickStyle.setStyle("Basic")
    app = QApplication(sys.argv)
    configure_application_font(app)
    app.setApplicationName("LocalMind")
    app.setOrganizationName("LocalMind")
    view_model, assistant = create_view_models()
    app.aboutToQuit.connect(assistant.shutdown)
    app.aboutToQuit.connect(view_model.shutdown)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("dashboard", view_model)
    engine.rootContext().setContextProperty("assistant", assistant)
    engine.rootContext().setContextProperty("history", assistant.history)
    qml_path = Path(__file__).parent / "presentation" / "qml" / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(qml_path)))
    if not engine.rootObjects():
        return 1
    exit_code = app.exec()
    # Destroy QML while its Python context objects are still alive.
    del engine
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

