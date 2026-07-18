from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QTextCursor
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from .widgets import ColumnTokenList, show_language_cheatsheet


class CommandInput(QPlainTextEdit):
    commandSubmitted = Signal(str)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.insertPlainText("\n")
                return
            command = self.toPlainText().strip()
            if command:
                self.commandSubmitted.emit(command)
                self.clear()
            return
        super().keyPressEvent(event)


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
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.document().setMaximumBlockCount(200)
        self.output.setPlainText("Ready.")
        self.input = CommandInput()
        self.input.setPlaceholderText(
            "drop @temporary\n"
            "update @PriceUpdatedDate = date(@PriceUpdatedDate)\n"
            "duplicate as Scenario A"
        )
        self.input.setToolTip("Enter runs the command. Shift+Enter inserts a new line.")
        self.column_tokens.tokenRequested.connect(self.input.insertPlainText)
        self.input.commandSubmitted.connect(self.commandSubmitted)
        body.addWidget(self.column_tokens, 1)
        body.addWidget(self.output, 2)
        body.addWidget(self.input, 3)
        root.addLayout(body, 1)

    def set_context(self, label: str, columns: list[str]) -> None:
        self.context_label.setText(label)
        self.column_tokens.set_columns(columns)
        self.input.setEnabled(True)

    def clear_context(self) -> None:
        self.context_label.setText("Select a history node")
        self.column_tokens.set_columns([])
        self.input.setEnabled(False)

    def append_output(self, text: str) -> None:
        current = self.output.toPlainText()
        self.output.setPlainText(f"{current}\n{text}" if current else text)
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.output.setTextCursor(cursor)
