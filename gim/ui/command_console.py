from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QTextCursor
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from .widgets import ColumnTokenList, show_language_cheatsheet


class TerminalEditor(QPlainTextEdit):
    commandSubmitted = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._prompt_position = 0
        self.document().setMaximumBlockCount(240)
        self.setPlainText("Ready.\n> ")
        self._prompt_position = len(self.toPlainText())
        self._move_to_end()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.insertPlainText("\n")
                return
            command = self.current_command()
            if command:
                self.insertPlainText("\n")
                self.commandSubmitted.emit(command)
            elif not self.toPlainText().endswith("\n> "):
                self.insertPlainText("\n> ")
                self._prompt_position = len(self.toPlainText())
            return
        if event.key() in {Qt.Key.Key_Backspace, Qt.Key.Key_Left} and self.textCursor().position() <= self._prompt_position:
            return
        if self.textCursor().position() < self._prompt_position:
            self._move_to_end()
        super().keyPressEvent(event)

    def current_command(self) -> str:
        return self.toPlainText()[self._prompt_position :].strip()

    def append_output(self, text: str) -> None:
        if not self.toPlainText().endswith("\n"):
            self.insertPlainText("\n")
        self.insertPlainText(f"{text}\n> ")
        self._prompt_position = len(self.toPlainText())
        self._move_to_end()

    def insert_token(self, token: str) -> None:
        if self.textCursor().position() < self._prompt_position:
            self._move_to_end()
        self.insertPlainText(token)

    def set_command_enabled(self, enabled: bool) -> None:
        self.setReadOnly(not enabled)

    def _move_to_end(self) -> None:
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor)


class CommandConsole(QFrame):
    commandSubmitted = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.setMinimumHeight(190)
        self.setMaximumHeight(260)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 10)
        root.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("Command console")
        title.setObjectName("SectionTitle")
        self.context_label = QLabel("Select a history node")
        self.context_label.setObjectName("Muted")
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.context_label)
        cheat = QPushButton("Show language cheatsheet")
        cheat.clicked.connect(lambda: show_language_cheatsheet(self))
        header.addWidget(cheat)
        root.addLayout(header)

        body = QHBoxLayout()
        self.column_tokens = ColumnTokenList()
        self.terminal = TerminalEditor()
        self.terminal.setPlaceholderText(
            "drop @temporary\n"
            "update @PriceUpdatedDate = date(@PriceUpdatedDate)\n"
            "duplicate as Scenario A"
        )
        self.terminal.setToolTip("Enter runs the command. Shift+Enter inserts a new line.")
        self.column_tokens.tokenRequested.connect(self.terminal.insert_token)
        self.terminal.commandSubmitted.connect(self.commandSubmitted)
        self.terminal.set_command_enabled(False)
        body.addWidget(self.column_tokens, 1)
        body.addWidget(self.terminal, 5)
        root.addLayout(body, 1)

    def set_context(self, label: str, columns: list[str]) -> None:
        self.context_label.setText(label)
        self.column_tokens.set_columns(columns)
        self.terminal.set_command_enabled(True)

    def clear_context(self) -> None:
        self.context_label.setText("Select a history node")
        self.column_tokens.set_columns([])
        self.terminal.set_command_enabled(False)

    def append_output(self, text: str) -> None:
        self.terminal.append_output(text)
