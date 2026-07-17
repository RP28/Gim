from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from gim.config.theme import WINDOW_HEIGHT, WINDOW_WIDTH


class WelcomeWindow(QWidget):
    createRequested = Signal()
    resumeRequested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("GIM · Graphical Insight Mapper")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        root = QVBoxLayout(self)
        root.setContentsMargins(120, 90, 120, 90)
        root.addStretch()

        card = QFrame()
        card.setObjectName("Card")
        card.setMaximumWidth(760)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(48, 44, 48, 44)
        card_layout.setSpacing(18)

        title = QLabel("GIM")
        title.setObjectName("Title")
        subtitle = QLabel("A history-first workspace for interactive data analysis")
        subtitle.setObjectName("Muted")
        subtitle.setWordWrap(True)
        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)

        button_row = QHBoxLayout()
        create = QPushButton("Create new workspace")
        create.setObjectName("accentButton")
        resume = QPushButton("Resume .gim workspace")
        create.setMinimumHeight(48)
        resume.setMinimumHeight(48)
        create.clicked.connect(self.createRequested)
        resume.clicked.connect(self.resumeRequested)
        button_row.addWidget(create)
        button_row.addWidget(resume)
        card_layout.addLayout(button_row)

        note = QLabel("New workspaces begin by importing one or more CSV files. Existing workspaces replay their saved history from original data.")
        note.setObjectName("Muted")
        note.setWordWrap(True)
        card_layout.addWidget(note)

        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(card)
        row.addStretch()
        root.addLayout(row)
        root.addStretch()
