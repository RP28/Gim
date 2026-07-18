from __future__ import annotations

import os
import tempfile
from pathlib import Path

from PySide6.QtCore import QUrl, Signal
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QListWidget, QListWidgetItem, QPlainTextEdit, QTextBrowser, QVBoxLayout, QWidget

from gim.core.dsl import CHEATSHEET


class ColumnTokenList(QListWidget):
    tokenRequested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(150)
        self.setToolTip("Double-click a column to insert its safe token")
        self.itemDoubleClicked.connect(self._emit_token)

    def set_columns(self, columns: list[str]) -> None:
        self.clear()
        for column in columns:
            item = QListWidgetItem(column)
            item.setToolTip(self.token_for(column))
            self.addItem(item)

    @staticmethod
    def token_for(column: str) -> str:
        return f"@{column}" if column.replace("_", "a").isalnum() and not column[0].isdigit() else f"@{{{column}}}"

    def _emit_token(self, item: QListWidgetItem) -> None:
        self.tokenRequested.emit(self.token_for(item.text()))


class DslEditor(QPlainTextEdit):
    def insert_token(self, token: str) -> None:
        cursor = self.textCursor()
        cursor.insertText(token)
        self.setTextCursor(cursor)
        self.setFocus()


def show_language_cheatsheet(parent: QWidget | None = None) -> None:
    dialog = QDialog(parent)
    dialog.setWindowTitle("Local data language")
    dialog.resize(720, 620)
    layout = QVBoxLayout(dialog)
    text = QPlainTextEdit(CHEATSHEET)
    text.setReadOnly(True)
    layout.addWidget(text)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.rejected.connect(dialog.reject)
    buttons.clicked.connect(dialog.accept)
    layout.addWidget(buttons)
    dialog.exec()


class PlotHost(QWidget):
    """A test-friendly wrapper around Qt WebEngine."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._html = ""
        self._web = None
        self._temporary_directory: tempfile.TemporaryDirectory[str] | None = None
        self._is_webengine = False
        test_mode = os.getenv("GIM_TEST_MODE") == "1"
        if not test_mode:
            try:
                from PySide6.QtWebEngineWidgets import QWebEngineView

                self._web = QWebEngineView(self)
                self._is_webengine = True
                self._temporary_directory = tempfile.TemporaryDirectory(prefix="gim_plot_")
            except Exception:
                self._web = None
        if self._web is None:
            self._web = QTextBrowser(self)
        layout.addWidget(self._web)

    def set_html(self, html: str) -> None:
        self._html = html
        if self._is_webengine and self._temporary_directory is not None:
            # Large Plotly documents are more reliable when loaded from a local file.
            path = Path(self._temporary_directory.name) / "plot.html"
            path.write_text(html, encoding="utf-8")
            self._web.load(QUrl.fromLocalFile(str(path)))
        elif hasattr(self._web, "setHtml"):
            self._web.setHtml(html)

    def html(self) -> str:
        return self._html
