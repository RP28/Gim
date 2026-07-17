from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from gim.config.theme import build_stylesheet
from gim.core.importers import normalise_sources
from gim.core.persistence import load_workspace
from gim.core.workspace import Workspace
from gim.ui.main_window import MainWindow
from gim.ui.welcome import WelcomeWindow

_ACTIVE_CONTROLLERS: list["ApplicationController"] = []


class ApplicationController:
    def __init__(self, application: QApplication) -> None:
        self.application = application
        self.welcome: WelcomeWindow | None = None
        self.main_window: MainWindow | None = None

    def launch(self, sources: tuple[Any, ...]) -> None:
        if sources:
            imported = normalise_sources(*sources)
            self.open_workspace(Workspace(), imported_frames=imported)
            return
        self.welcome = WelcomeWindow()
        self.welcome.createRequested.connect(self.create_workspace)
        self.welcome.resumeRequested.connect(self.resume_workspace)
        self.welcome.show()

    def create_workspace(self) -> None:
        self.open_workspace(Workspace())
        QTimer.singleShot(100, self.main_window.prompt_add_csv if self.main_window else lambda: None)

    def resume_workspace(self) -> None:
        parent = self.welcome
        path, _ = QFileDialog.getOpenFileName(parent, "Open GIM workspace", "", "GIM workspace (*.gim)")
        if not path:
            return
        try:
            workspace = load_workspace(path)
        except Exception as exc:
            QMessageBox.critical(parent, "Could not open workspace", str(exc))
            return
        self.open_workspace(workspace)
        if self.main_window:
            self.main_window.workspace_path = Path(path)
            self.main_window.mark_dirty(False)

    def open_workspace(self, workspace: Workspace, imported_frames=None) -> None:  # type: ignore[no-untyped-def]
        self.main_window = MainWindow(workspace)
        if imported_frames:
            self.main_window.add_imported_frames(imported_frames)
        self.main_window.show()
        if self.welcome:
            self.welcome.close()
            self.welcome = None


def run(*sources: Any, start_event_loop: bool = True) -> ApplicationController | int:
    """Launch GIM.

    Parameters
    ----------
    *sources:
        Zero or more CSV paths, pandas DataFrames, ``(alias, object)`` tuples,
        mappings of aliases to objects, iterables, or dataframe-interchange
        objects. With no sources, GIM opens the create/resume screen.
    start_event_loop:
        Set to ``False`` for embedding or GUI tests. The returned controller
        keeps the windows alive.
    """

    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    application = QApplication.instance()
    owns_application = application is None
    if application is None:
        application = QApplication(sys.argv)
    application.setApplicationName("GIM")
    application.setOrganizationName("GIM")
    application.setStyleSheet(build_stylesheet())

    controller = ApplicationController(application)
    _ACTIVE_CONTROLLERS.append(controller)
    controller.launch(tuple(sources))

    if start_event_loop and owns_application:
        return application.exec()
    return controller
