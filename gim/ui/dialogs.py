from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from gim.core.stats import TEST_NAMES

from .widgets import ColumnTokenList, DslEditor, show_language_cheatsheet


def _configure_form_layout(layout: QFormLayout) -> None:
    layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    layout.setFormAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
    layout.setHorizontalSpacing(18)
    layout.setVerticalSpacing(14)


def _expand_field(widget: QWidget, minimum_width: int = 280) -> None:
    widget.setMinimumWidth(minimum_width)
    widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)


def _configure_combo(combo: QComboBox, items: list[str], *, minimum_width: int = 280) -> None:
    combo.addItems(items)
    combo.setMinimumContentsLength(min(36, max((len(item) for item in items), default=12)))
    combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    combo.view().setMinimumWidth(min(560, max(minimum_width, max((len(item) for item in items), default=12) * 9 + 48)))
    _expand_field(combo, minimum_width)


class AliasDialog(QDialog):
    def __init__(self, default_alias: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Dataset alias")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Name this dataset in the history tree."))
        self.alias_edit = QLineEdit(default_alias)
        _expand_field(self.alias_edit)
        self.alias_edit.selectAll()
        layout.addWidget(self.alias_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def alias(self) -> str:
        return self.alias_edit.text().strip()


class CsvOptionsDialog(QDialog):
    def __init__(self, path: str | Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("CSV import options")
        self.setMinimumWidth(460)
        layout = QFormLayout(self)
        _configure_form_layout(layout)
        self.alias_edit = QLineEdit(Path(path).stem)
        _expand_field(self.alias_edit)
        self.encoding = QComboBox()
        _configure_combo(self.encoding, ["utf-8-sig", "utf-8", "cp1252", "latin-1"])
        self.delimiter = QComboBox()
        self.delimiter.addItem("Auto detect", None)
        self.delimiter.addItem("Comma (,)", ",")
        self.delimiter.addItem("Semicolon (;)", ";")
        self.delimiter.addItem("Tab", "\t")
        self.delimiter.addItem("Pipe (|)", "|")
        _expand_field(self.delimiter)
        layout.addRow("Alias", self.alias_edit)
        layout.addRow("Encoding", self.encoding)
        layout.addRow("Delimiter", self.delimiter)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def values(self) -> tuple[str, str, str | None]:
        return self.alias_edit.text().strip(), self.encoding.currentText(), self.delimiter.currentData()


class TransformDialog(QDialog):
    def __init__(self, columns: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Transform dataset")
        self.resize(820, 520)
        root = QVBoxLayout(self)
        body = QHBoxLayout()
        self.columns = ColumnTokenList()
        self.columns.set_columns(columns)
        self.editor = DslEditor()
        self.editor.setPlaceholderText(
            "Examples:\n"
            "drop @temporary\n"
            "where @age >= 18\n"
            "derive margin = @revenue - @cost\n"
            "dedupe @customer, @{Order Date}"
        )
        self.columns.tokenRequested.connect(self.editor.insert_token)
        body.addWidget(self.columns, 1)
        body.addWidget(self.editor, 4)
        root.addLayout(body)
        cheat = QPushButton("Show language cheatsheet")
        cheat.clicked.connect(lambda: show_language_cheatsheet(self))
        root.addWidget(cheat, alignment=Qt.AlignmentFlag.AlignLeft)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Cancel)
        apply_button = buttons.button(QDialogButtonBox.StandardButton.Apply)
        apply_button.setObjectName("accentButton")
        apply_button.clicked.connect(self._validate)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _validate(self) -> None:
        if not self.editor.toPlainText().strip():
            QMessageBox.warning(self, "No transformation", "Enter at least one transformation statement.")
            return
        self.accept()

    @property
    def code(self) -> str:
        return self.editor.toPlainText()


class DuplicateDialog(QDialog):
    def __init__(self, default_alias: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Duplicate branch")
        self.setMinimumWidth(460)
        layout = QFormLayout(self)
        _configure_form_layout(layout)
        self.alias_edit = QLineEdit(default_alias)
        _expand_field(self.alias_edit)
        layout.addRow("New branch alias", self.alias_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    @property
    def alias(self) -> str:
        return self.alias_edit.text().strip()


class MergeDialog(QDialog):
    def __init__(
        self,
        left_alias: str,
        right_alias: str,
        left_columns: list[str],
        right_columns: list[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Merge selected datasets")
        self.setMinimumSize(720, 300)
        self.resize(760, 320)
        layout = QFormLayout(self)
        _configure_form_layout(layout)
        self.join_type = QComboBox()
        _configure_combo(self.join_type, ["inner", "left", "right"], minimum_width=320)
        self.left_key = QComboBox()
        _configure_combo(self.left_key, left_columns, minimum_width=360)
        self.right_key = QComboBox()
        _configure_combo(self.right_key, right_columns, minimum_width=360)
        common = next((column for column in left_columns if column in right_columns), None)
        if common:
            self.left_key.setCurrentText(common)
            self.right_key.setCurrentText(common)
        self.alias_edit = QLineEdit(f"{left_alias} + {right_alias}")
        _expand_field(self.alias_edit, 360)
        self.left_key.setToolTip(left_alias)
        self.right_key.setToolTip(right_alias)
        layout.addRow("Join type", self.join_type)
        layout.addRow("Left key", self.left_key)
        layout.addRow("Right key", self.right_key)
        layout.addRow("Result alias", self.alias_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setObjectName("accentButton")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def values(self) -> dict[str, str]:
        return {
            "how": self.join_type.currentText(),
            "left_on": self.left_key.currentText(),
            "right_on": self.right_key.currentText(),
            "alias": self.alias_edit.text().strip(),
        }


class CorrelationDialog(QDialog):
    def __init__(self, columns: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Correlation map")
        self.resize(460, 520)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        _configure_form_layout(form)
        self.method = QComboBox()
        _configure_combo(self.method, ["pearson", "spearman", "kendall"])
        form.addRow("Method", self.method)
        layout.addLayout(form)
        layout.addWidget(QLabel("Select at least two columns"))
        self.columns = QListWidget()
        for column in columns:
            item = QListWidgetItem(column)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.columns.addItem(item)
        layout.addWidget(self.columns)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate(self) -> None:
        if len(self.selected_columns()) < 2:
            QMessageBox.warning(self, "Select columns", "Choose at least two columns.")
            return
        self.accept()

    def selected_columns(self) -> list[str]:
        return [
            self.columns.item(index).text()
            for index in range(self.columns.count())
            if self.columns.item(index).checkState() == Qt.CheckState.Checked
        ]


class StatsDialog(QDialog):
    def __init__(self, columns: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Statistical test")
        self.resize(760, 560)
        root = QVBoxLayout(self)
        form = QFormLayout()
        _configure_form_layout(form)
        self.test = QComboBox()
        _configure_combo(self.test, TEST_NAMES, minimum_width=360)
        self.column_a = QComboBox()
        self.column_b = QComboBox()
        _configure_combo(self.column_a, columns, minimum_width=360)
        _configure_combo(self.column_b, columns, minimum_width=360)
        self.alpha = QDoubleSpinBox()
        self.alpha.setRange(0.001, 0.2)
        self.alpha.setDecimals(3)
        self.alpha.setSingleStep(0.005)
        self.alpha.setValue(0.05)
        form.addRow("Test", self.test)
        form.addRow("Value / first column", self.column_a)
        form.addRow("Group / second column", self.column_b)
        form.addRow("Significance α", self.alpha)
        root.addLayout(form)
        root.addWidget(QLabel("Optional local operations before testing"))
        body = QHBoxLayout()
        self.column_tokens = ColumnTokenList()
        self.column_tokens.set_columns(columns)
        self.editor = DslEditor()
        self.editor.setPlaceholderText("where @region == \"NSW\"\ndrop @temporary")
        self.column_tokens.tokenRequested.connect(self.editor.insert_token)
        body.addWidget(self.column_tokens, 1)
        body.addWidget(self.editor, 3)
        root.addLayout(body)
        cheat = QPushButton("Show language cheatsheet")
        cheat.clicked.connect(lambda: show_language_cheatsheet(self))
        root.addWidget(cheat, alignment=Qt.AlignmentFlag.AlignLeft)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setObjectName("accentButton")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def values(self) -> dict[str, Any]:
        return {
            "test": self.test.currentText(),
            "column_a": self.column_a.currentText(),
            "column_b": self.column_b.currentText(),
            "alpha": self.alpha.value(),
            "local_code": self.editor.toPlainText(),
        }


class ArtifactNameDialog(QDialog):
    def __init__(self, default_title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Save result")
        layout = QFormLayout(self)
        _configure_form_layout(layout)
        self.title_edit = QLineEdit(default_title)
        _expand_field(self.title_edit)
        self.title_edit.selectAll()
        layout.addRow("Title", self.title_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    @property
    def title(self) -> str:
        return self.title_edit.text().strip()
