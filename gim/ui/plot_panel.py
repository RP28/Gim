from __future__ import annotations

from typing import Any

import pandas as pd
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from gim.core.dsl import LocalTransformEngine
from gim.core.plotting import PlotRequest, build_figure, modes_for, plot_families
from gim.core.workspace import Workspace

from .widgets import ColumnTokenList, DslEditor, PlotHost, show_language_cheatsheet


def _fit_combo(combo: QComboBox, items: list[str], *, minimum_width: int = 140) -> None:
    combo.setMinimumWidth(minimum_width)
    combo.setMinimumContentsLength(min(28, max((len(item) for item in items), default=12)))
    combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    combo.view().setMinimumWidth(min(560, max(minimum_width, max((len(item) for item in items), default=12) * 9 + 48)))


class PlotPanel(QWidget):
    savePlotRequested = Signal(object, str, str)  # PlotRequest, local code, suggested title
    statsRequested = Signal()
    correlationRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.workspace: Workspace | None = None
        self.node_id: str | None = None
        self.last_request: PlotRequest | None = None
        self.last_local_code = ""
        self._building = False
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        self.title_label = QLabel("Plot workspace")
        self.title_label.setObjectName("Title")
        self.data_label = QLabel("Select a history node")
        self.data_label.setObjectName("Muted")
        title_box.addWidget(self.title_label)
        title_box.addWidget(self.data_label)
        header.addLayout(title_box)
        header.addStretch()
        self.stats_button = QPushButton("Statistical tests")
        self.corr_button = QPushButton("Correlation map")
        header.addWidget(self.stats_button)
        header.addWidget(self.corr_button)
        root.addLayout(header)

        controls_card = QFrame()
        controls_card.setObjectName("Card")
        controls = QVBoxLayout(controls_card)
        selector_row = QHBoxLayout()
        self.family = QComboBox()
        families = plot_families()
        self.family.addItems(families)
        _fit_combo(self.family, families)
        self.mode = QComboBox()
        self.x_column = QComboBox()
        self.y_column = QComboBox()
        self.hue_column = QComboBox()
        for combo in [self.mode, self.x_column, self.y_column, self.hue_column]:
            _fit_combo(combo, [], minimum_width=150)
        self.flip_button = QPushButton("⇄ Flip")
        self.render_button = QPushButton("Render plot")
        self.render_button.setObjectName("accentButton")
        for label, widget, stretch in [
            ("Plot", self.family, 2),
            ("Style", self.mode, 2),
            ("X / category", self.x_column, 2),
            ("Y / value", self.y_column, 2),
            ("Hue", self.hue_column, 2),
        ]:
            box = QVBoxLayout()
            caption = QLabel(label)
            caption.setObjectName("Muted")
            box.addWidget(caption)
            box.addWidget(widget)
            selector_row.addLayout(box, stretch)
        selector_row.addWidget(self.flip_button)
        selector_row.addWidget(self.render_button)
        controls.addLayout(selector_row)

        self.dynamic_row = QHBoxLayout()
        self.bins_label = QLabel("Bins")
        self.auto_bins = QCheckBox("Auto")
        self.auto_bins.setChecked(True)
        self.bins_slider = QSlider(Qt.Orientation.Horizontal)
        self.bins_slider.setRange(1, 200)
        self.bins_slider.setValue(20)
        self.bins_spin = QSpinBox()
        self.bins_spin.setRange(1, 500)
        self.bins_spin.setValue(20)
        self.dynamic_row.addWidget(self.bins_label)
        self.dynamic_row.addWidget(self.auto_bins)
        self.dynamic_row.addWidget(self.bins_slider, 1)
        self.dynamic_row.addWidget(self.bins_spin)
        self.dynamic_row.addStretch()
        controls.addLayout(self.dynamic_row)
        root.addWidget(controls_card)

        splitter = QSplitter(Qt.Orientation.Vertical)
        self.plot_host = PlotHost()
        self.plot_host.setMinimumHeight(390)
        splitter.addWidget(self.plot_host)

        local_card = QFrame()
        local_card.setObjectName("Card")
        local_layout = QVBoxLayout(local_card)
        local_header = QHBoxLayout()
        local_title = QLabel("Plot-local data steps")
        local_title.setObjectName("SectionTitle")
        local_header.addWidget(local_title)
        local_header.addStretch()
        cheat = QPushButton("Show language cheatsheet")
        cheat.clicked.connect(lambda: show_language_cheatsheet(self))
        local_header.addWidget(cheat)
        self.save_button = QPushButton("Save plot")
        local_header.addWidget(self.save_button)
        local_layout.addLayout(local_header)
        local_body = QHBoxLayout()
        self.column_tokens = ColumnTokenList()
        self.local_editor = DslEditor()
        self.local_editor.setPlaceholderText(
            "where @region == \"NSW\"\n"
            "derive margin = @revenue - @cost\n"
            "drop @temporary"
        )
        self.column_tokens.tokenRequested.connect(self.local_editor.insert_token)
        local_body.addWidget(self.column_tokens, 1)
        local_body.addWidget(self.local_editor, 4)
        local_layout.addLayout(local_body)
        splitter.addWidget(local_card)
        splitter.setSizes([560, 230])
        root.addWidget(splitter, 1)

        self.family.currentTextChanged.connect(self._family_changed)
        self.mode.currentTextChanged.connect(self._dynamic_controls)
        self.bins_slider.valueChanged.connect(self.bins_spin.setValue)
        self.bins_spin.valueChanged.connect(self._sync_bins)
        self.auto_bins.toggled.connect(self._auto_bins_changed)
        self.render_button.clicked.connect(self.render)
        self.flip_button.clicked.connect(self._flip)
        self.save_button.clicked.connect(self._save)
        self.stats_button.clicked.connect(self.statsRequested)
        self.corr_button.clicked.connect(self.correlationRequested)
        self._family_changed(self.family.currentText())
        self._auto_bins_changed(self.auto_bins.isChecked())
        self._show_placeholder()

    def _show_placeholder(self) -> None:
        self.plot_host.set_html(
            """<!doctype html><html><body style='margin:0;background:#0B0D10;color:#9AA4B2;
            font-family:Arial,Helvetica,sans-serif;display:flex;height:100vh;align-items:center;justify-content:center'>
            <div style='text-align:center'><div style='font-size:30px;color:#F2F4F7'>Blank plot</div>
            </div></body></html>"""
        )

    def set_context(self, workspace: Workspace, node_id: str) -> None:
        self.workspace = workspace
        self.node_id = node_id
        node = workspace.require_node(node_id)
        frame = workspace.materialize(node_id)
        columns = [str(column) for column in frame.columns]
        self.data_label.setText(f"{node.alias} · {len(frame):,} rows × {len(frame.columns):,} columns")
        current = {
            "x": self.x_column.currentText(),
            "y": self.y_column.currentText(),
            "hue": self.hue_column.currentText(),
        }
        self._set_combo_columns(self.x_column, columns, allow_empty=True, preferred=current["x"])
        self._set_combo_columns(self.y_column, columns, allow_empty=True, preferred=current["y"])
        self._set_combo_columns(self.hue_column, columns, allow_empty=True, preferred=current["hue"])
        self.column_tokens.set_columns(columns)

    @staticmethod
    def _set_combo_columns(combo: QComboBox, columns: list[str], *, allow_empty: bool, preferred: str) -> None:
        combo.blockSignals(True)
        combo.clear()
        if allow_empty:
            combo.addItem("", None)
        combo.addItems(columns)
        combo.setMinimumContentsLength(min(28, max((len(column) for column in columns), default=12)))
        combo.view().setMinimumWidth(min(620, max(180, max((len(column) for column in columns), default=12) * 9 + 48)))
        if preferred in columns:
            combo.setCurrentText(preferred)
        combo.blockSignals(False)

    def _family_changed(self, family: str) -> None:
        self.mode.blockSignals(True)
        self.mode.clear()
        modes = modes_for(family)
        self.mode.addItems(modes)
        self.mode.setMinimumContentsLength(min(28, max((len(mode) for mode in modes), default=12)))
        self.mode.view().setMinimumWidth(min(420, max(180, max((len(mode) for mode in modes), default=12) * 9 + 48)))
        self.mode.blockSignals(False)
        self._dynamic_controls()

    def _dynamic_controls(self) -> None:
        show_bins = self.family.currentText() == "Distribution" and self.mode.currentText() in {"Histogram", "Histogram + KDE"}
        self.bins_label.setVisible(show_bins)
        self.auto_bins.setVisible(show_bins)
        self.bins_slider.setVisible(show_bins)
        self.bins_spin.setVisible(show_bins)
        family = self.family.currentText()
        self.flip_button.setEnabled(family != "Pie")
        needs_y = family in {"Scatter", "Line"}
        optional_y = family in {"Range & shape", "Pie"}
        self.y_column.setEnabled(needs_y or optional_y)
        self.hue_column.setEnabled(family in {"Distribution", "Range & shape", "Scatter", "Line"})

    def _auto_bins_changed(self, automatic: bool) -> None:
        self.bins_slider.setEnabled(not automatic)
        self.bins_spin.setEnabled(not automatic)

    def _sync_bins(self, value: int) -> None:
        if value <= self.bins_slider.maximum():
            self.bins_slider.blockSignals(True)
            self.bins_slider.setValue(value)
            self.bins_slider.blockSignals(False)

    def _flip(self) -> None:
        family = self.family.currentText()
        if family in {"Scatter", "Line"}:
            x, y = self.x_column.currentText(), self.y_column.currentText()
            self.x_column.setCurrentText(y)
            self.y_column.setCurrentText(x)
        else:
            self.flip_button.setProperty("activeFlip", not bool(self.flip_button.property("activeFlip")))
            self.flip_button.setText("⇄ Flipped" if self.flip_button.property("activeFlip") else "⇄ Flip")
        self.render()

    def request(self) -> PlotRequest:
        return PlotRequest(
            family=self.family.currentText(),
            mode=self.mode.currentText(),
            x=self.x_column.currentText() or None,
            y=self.y_column.currentText() or None,
            hue=self.hue_column.currentText() or None,
            bins=0 if self.auto_bins.isChecked() else self.bins_spin.value(),
            flip=bool(self.flip_button.property("activeFlip")),
        )

    def prepared_dataframe(self) -> pd.DataFrame:
        if not self.workspace or not self.node_id:
            raise ValueError("Select a history node first")
        frame = self.workspace.materialize(self.node_id)
        code = self.local_editor.toPlainText().strip()
        return LocalTransformEngine().apply(frame, code) if code else frame

    def render(self) -> None:
        if self._building:
            return
        try:
            self._building = True
            dataframe = self.prepared_dataframe()
            request = self.request()
            figure = build_figure(dataframe, request)
            html = figure.to_html(
                full_html=True,
                include_plotlyjs=True,
                config={"responsive": True, "displaylogo": False, "scrollZoom": True},
            )
            self.plot_host.set_html(html)
            self.last_request = request
            self.last_local_code = self.local_editor.toPlainText()
        except Exception as exc:
            QMessageBox.warning(self, "Could not build plot", str(exc))
        finally:
            self._building = False

    def render_saved(self, request: PlotRequest, local_code: str) -> None:
        self.family.setCurrentText(request.family)
        self.mode.setCurrentText(request.mode)
        self.x_column.setCurrentText(request.x or "")
        self.y_column.setCurrentText(request.y or "")
        self.hue_column.setCurrentText(request.hue or "")
        self.auto_bins.setChecked(request.bins <= 0)
        if request.bins > 0:
            self.bins_spin.setValue(request.bins)
        self.flip_button.setProperty("activeFlip", request.flip)
        self.flip_button.setText("⇄ Flipped" if request.flip else "⇄ Flip")
        self.local_editor.setPlainText(local_code)
        self.render()

    def _save(self) -> None:
        if not self.node_id:
            QMessageBox.information(self, "No dataset", "Select a history node first.")
            return
        if self.last_request is None:
            self.render()
        if self.last_request is None:
            return
        suggested = f"{self.last_request.family} · {self.last_request.mode}"
        self.savePlotRequested.emit(self.last_request, self.local_editor.toPlainText(), suggested)
