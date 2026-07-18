from __future__ import annotations

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gim.core.profile import ColumnProfile, build_column_profiles


class ProfilePanel(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.setMaximumHeight(270)
        self._profiles: list[ColumnProfile] = []
        self._visible_profiles: list[ColumnProfile] = []
        self._kind_filter = "all"
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 10)
        root.setSpacing(7)

        header = QHBoxLayout()
        title = QLabel("Profile")
        title.setObjectName("SectionTitle")
        self.dataset_label = QLabel("No dataset selected")
        self.dataset_label.setObjectName("Muted")
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.dataset_label)
        root.addLayout(header)

        controls = QHBoxLayout()
        self.filter_group = QButtonGroup(self)
        self.filter_group.setExclusive(True)
        for label, key in [("All", "all"), ("Numeric", "numeric"), ("Text", "text"), ("Dates", "date")]:
            button = QPushButton(label)
            button.setCheckable(True)
            button.setProperty("profileFilter", True)
            button.clicked.connect(lambda checked=False, value=key: self._set_filter(value))
            self.filter_group.addButton(button)
            controls.addWidget(button)
            if key == "all":
                button.setChecked(True)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search columns")
        self.search.textChanged.connect(self._refresh_rows)
        controls.addWidget(self.search, 1)
        root.addLayout(controls)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Column", "Type", "Missing", "Unique", "Mean / Top"])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._show_selected_details)
        root.addWidget(self.table, 1)

        self.details = QLabel("Select a history node to inspect dataframe summary statistics.")
        self.details.setObjectName("Muted")
        self.details.setWordWrap(True)
        self.details.setMinimumHeight(34)
        root.addWidget(self.details)

    def set_dataframe(self, alias: str, dataframe: pd.DataFrame) -> None:
        self.dataset_label.setText(f"{alias} - {len(dataframe):,} rows x {len(dataframe.columns):,} cols")
        self._profiles = build_column_profiles(dataframe)
        self._refresh_rows()

    def clear_profile(self) -> None:
        self.dataset_label.setText("No dataset selected")
        self._profiles = []
        self._visible_profiles = []
        self.table.setRowCount(0)
        self.details.setText("Select a history node to inspect dataframe summary statistics.")

    def _set_filter(self, value: str) -> None:
        self._kind_filter = value
        self._refresh_rows()

    def _refresh_rows(self) -> None:
        query = self.search.text().strip().lower()
        self._visible_profiles = [
            profile
            for profile in self._profiles
            if (
                self._kind_filter == "all"
                or profile.kind == self._kind_filter
                or (self._kind_filter == "text" and profile.kind == "boolean")
            )
            and (not query or query in profile.name.lower())
        ]
        self.table.setRowCount(len(self._visible_profiles))
        for row, profile in enumerate(self._visible_profiles):
            values = [
                profile.name,
                profile.dtype,
                f"{profile.missing:,} ({profile.missing_pct:.1f}%)",
                "-" if profile.unique is None else f"{profile.unique:,}",
                profile.headline,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(profile.details)
                if column in {2, 3}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, column, item)
        if self._visible_profiles:
            self.table.selectRow(0)
            self._show_selected_details()
        else:
            self.details.setText("No matching columns.")

    def _show_selected_details(self) -> None:
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return
        row = rows[0].row()
        if 0 <= row < len(self._visible_profiles):
            profile = self._visible_profiles[row]
            self.details.setText(f"{profile.name}: {profile.details}")
