from __future__ import annotations

import json
import re
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from gim.config.theme import WINDOW_HEIGHT, WINDOW_WIDTH
from gim.core.importers import CsvReadError, ImportedFrame, read_csv_robust
from gim.core.models import ArtifactKind, SavedArtifact
from gim.core.persistence import save_workspace
from gim.core.plotting import PlotRequest, build_correlation_figure
from gim.core.stats import run_statistical_test
from gim.core.workspace import Workspace

from .command_console import CommandConsole
from .dialogs import (
    AliasDialog,
    ArtifactNameDialog,
    CorrelationDialog,
    CsvOptionsDialog,
    MergeDialog,
    StatsDialog,
)
from .history_view import HistoryGraphView
from .plot_panel import PlotPanel
from .profile_panel import ProfilePanel


class MainWindow(QMainWindow):
    def __init__(self, workspace: Workspace | None = None) -> None:
        super().__init__()
        self.workspace = workspace or Workspace()
        self.workspace_path: Path | None = None
        self._dirty = False
        self._merge_dialog_open = False
        self.setWindowTitle("GIM · Untitled workspace")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        toolbar = QFrame()
        toolbar.setObjectName("Card")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(10, 8, 10, 8)
        self.add_csv_button = QPushButton("＋ Add CSV")
        self.save_button = QPushButton("Save .gim")
        self.save_button.setObjectName("accentButton")
        self.node_summary = QLabel("No dataset selected")
        self.node_summary.setObjectName("Muted")
        toolbar_layout.addWidget(self.add_csv_button)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.node_summary)
        toolbar_layout.addWidget(self.save_button)
        root.addWidget(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        tabs = QTabWidget()
        history_tab = QWidget()
        history_layout = QVBoxLayout(history_tab)
        history_layout.setContentsMargins(6, 6, 6, 6)
        self.history = HistoryGraphView()
        history_layout.addWidget(self.history, 1)
        self.profile_panel = ProfilePanel()
        history_layout.addWidget(self.profile_panel)
        tabs.addTab(history_tab, "History")

        saved_tab = QWidget()
        saved_layout = QVBoxLayout(saved_tab)
        saved_layout.setContentsMargins(6, 6, 6, 6)
        self.saved_list = QListWidget()
        saved_layout.addWidget(self.saved_list, 1)
        tabs.addTab(saved_tab, "Saved")
        left_layout.addWidget(tabs)

        self.plot_panel = PlotPanel()
        splitter.addWidget(left)
        splitter.addWidget(self.plot_panel)
        splitter.setSizes([470, 960])
        root.addWidget(splitter, 1)
        self.command_console = CommandConsole()
        root.addWidget(self.command_console)
        self.setCentralWidget(central)

        self.add_csv_button.clicked.connect(self.prompt_add_csv)
        self.save_button.clicked.connect(self.save_workspace_dialog)
        self.history.nodeSelected.connect(self.select_history_node)
        self.history.mergePairSelected.connect(self.open_merge_dialog)
        self.plot_panel.savePlotRequested.connect(self.save_plot)
        self.plot_panel.statsRequested.connect(self.run_stats)
        self.plot_panel.correlationRequested.connect(self.run_correlation)
        self.command_console.commandSubmitted.connect(self.run_console_command)
        self.saved_list.itemDoubleClicked.connect(self.open_artifact_item)

    def mark_dirty(self, dirty: bool = True) -> None:
        self._dirty = dirty
        name = self.workspace_path.name if self.workspace_path else self.workspace.name
        self.setWindowTitle(f"GIM · {name}{' *' if dirty else ''}")

    def refresh(self, animate_node_id: str | None = None) -> None:
        self.history.set_workspace(self.workspace, animate_node_id=animate_node_id)
        self.saved_list.clear()
        for artifact in sorted(self.workspace.artifacts.values(), key=lambda item: item.created_at, reverse=True):
            node = self.workspace.nodes.get(artifact.node_id)
            prefix = {ArtifactKind.PLOT: "Plot", ArtifactKind.STAT: "Test", ArtifactKind.CORRELATION: "Corr"}[artifact.kind]
            item = QListWidgetItem(f"{prefix} · {artifact.title}\n{node.alias if node else 'Missing node'}")
            item.setData(Qt.ItemDataRole.UserRole, artifact.id)
            self.saved_list.addItem(item)
        selected = self.workspace.selected_node_id
        if selected and selected in self.workspace.nodes:
            self.select_node(selected)
        else:
            self.node_summary.setText("No dataset selected")
            self.profile_panel.clear_profile()
            self.command_console.clear_context()

    def prompt_add_csv(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Import CSV files", "", "CSV files (*.csv *.txt);;All files (*)")
        for path in paths:
            self._import_path(path)

    def _import_path(self, path: str) -> None:
        try:
            dataframe, options = read_csv_robust(path)
            alias_dialog = AliasDialog(Path(path).stem, self)
            if alias_dialog.exec() != AliasDialog.DialogCode.Accepted:
                return
            alias = alias_dialog.alias or Path(path).stem
        except CsvReadError:
            options_dialog = CsvOptionsDialog(path, self)
            if options_dialog.exec() != CsvOptionsDialog.DialogCode.Accepted:
                return
            alias, encoding, delimiter = options_dialog.values()
            try:
                dataframe, options = read_csv_robust(path, encoding=encoding, delimiter=delimiter)
            except Exception as exc:
                QMessageBox.critical(self, "CSV import failed", str(exc))
                return
        node = self.workspace.add_source(dataframe, alias, source_path=path, read_options=options)
        self.mark_dirty()
        self.refresh(animate_node_id=node.id)

    def add_imported_frames(self, frames: list[ImportedFrame]) -> None:
        last_id: str | None = None
        for frame in frames:
            node = self.workspace.add_source(
                frame.dataframe,
                frame.alias,
                source_path=frame.source_path,
                read_options=frame.read_options,
            )
            last_id = node.id
        if frames:
            self.mark_dirty()
            self.refresh(animate_node_id=last_id)

    def select_node(self, node_id: str) -> None:
        self._activate_node(node_id, sync_history=True)

    def select_history_node(self, node_id: str) -> None:
        self._activate_node(node_id, sync_history=False)

    def _activate_node(self, node_id: str, *, sync_history: bool) -> None:
        if node_id not in self.workspace.nodes:
            return
        self.workspace.selected_node_id = node_id
        node = self.workspace.nodes[node_id]
        frame = self.workspace.materialize(node_id)
        self.node_summary.setText(f"{node.alias} · {len(frame):,} × {len(frame.columns):,}")
        self.plot_panel.set_context(self.workspace, node_id)
        self.profile_panel.set_dataframe(node.alias, frame)
        self.command_console.set_context(f"{node.alias} - {len(frame):,} rows x {len(frame.columns):,} cols", [str(column) for column in frame.columns])
        if sync_history:
            self.history.select_node(node_id, emit=False)

    def run_console_command(self, command: str) -> None:
        node_id = self.workspace.selected_node_id
        if not node_id:
            self.command_console.append_output("No dataset selected.")
            return
        statements = self._command_statements(command)
        if not statements:
            return
        current_id = node_id
        last_node_id: str | None = None
        try:
            for statement in statements:
                if self._is_duplicate_statement(statement):
                    source_ref, alias = self._duplicate_parts(statement)
                    parent_id = self._resolve_duplicate_source(source_ref, current_id)
                    node = self.workspace.duplicate(parent_id, alias)
                    action = "Duplicated branch"
                else:
                    node = self.workspace.apply_transform(current_id, statement)
                    action = self._command_status(statement)
                current_id = node.id
                last_node_id = node.id
                frame = self.workspace.materialize(node.id)
                self.command_console.append_output(f"{action}: {node.alias} - {len(frame):,} rows x {len(frame.columns):,} cols")
        except Exception as exc:
            self.command_console.append_output(f"Error: {exc}")
            return
        self.mark_dirty()
        self.refresh(animate_node_id=last_node_id)

    @staticmethod
    def _command_statements(command: str) -> list[str]:
        return [
            line.strip()
            for line in command.replace("|", "\n").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

    @staticmethod
    def _is_duplicate_statement(statement: str) -> bool:
        return statement.lower().split(maxsplit=1)[0] == "duplicate"

    def _duplicate_parts(self, statement: str) -> tuple[str | None, str | None]:
        match = re.fullmatch(r"duplicate(?:\s+from\s+(.+?))?(?:\s+as\s+(.+))?", statement, flags=re.I)
        if not match:
            raise ValueError("duplicate syntax: duplicate [from branch-or-node] [as New branch name]")
        source_ref = self._unquote(match.group(1) or "")
        alias = self._unquote(match.group(2) or "")
        return source_ref or None, alias or None

    @staticmethod
    def _unquote(value: str) -> str:
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            return value[1:-1].strip()
        return value

    def _resolve_duplicate_source(self, source_ref: str | None, fallback_id: str) -> str:
        if not source_ref:
            return fallback_id
        lookup = source_ref.casefold()
        id_matches = [node_id for node_id in self.workspace.nodes if node_id == source_ref or node_id.startswith(source_ref)]
        if len(id_matches) == 1:
            return id_matches[0]
        if len(id_matches) > 1:
            raise ValueError(f"Ambiguous node id prefix: {source_ref}")
        latest_nodes = self.workspace.latest_nodes_by_branch().values()
        alias_matches = [node.id for node in latest_nodes if node.alias.casefold() == lookup]
        if len(alias_matches) == 1:
            return alias_matches[0]
        if len(alias_matches) > 1:
            raise ValueError(f"Ambiguous branch alias: {source_ref}")
        raise ValueError(f"Unknown branch or node: {source_ref}")

    @staticmethod
    def _command_status(statement: str) -> str:
        verb = statement.split(maxsplit=1)[0].lower()
        return {
            "where": "Filtered rows",
            "keep": "Kept columns",
            "drop": "Dropped columns",
            "dedupe": "Removed duplicates",
            "rename": "Renamed column",
            "derive": "Derived column",
            "update": "Updated column",
            "sort": "Sorted rows",
            "head": "Selected head rows",
            "tail": "Selected tail rows",
            "sample": "Sampled rows",
            "fill": "Filled values",
            "cast": "Cast column",
        }.get(verb, "Transformed dataset")

    def open_merge_dialog(self, left_id: str, right_id: str) -> None:
        if self._merge_dialog_open or left_id == right_id:
            return
        self._merge_dialog_open = True
        try:
            left_node = self.workspace.require_node(left_id)
            right_node = self.workspace.require_node(right_id)
            left = self.workspace.materialize(left_id)
            right = self.workspace.materialize(right_id)
            dialog = MergeDialog(
                left_node.alias,
                right_node.alias,
                [str(column) for column in left.columns],
                [str(column) for column in right.columns],
                self,
            )
            if dialog.exec() != MergeDialog.DialogCode.Accepted:
                return
            try:
                node = self.workspace.merge(left_id, right_id, **dialog.values())
            except Exception as exc:
                QMessageBox.warning(self, "Merge failed", str(exc))
                return
            self.mark_dirty()
            self.refresh(animate_node_id=node.id)
        finally:
            self._merge_dialog_open = False

    def save_workspace_dialog(self) -> None:
        initial = str(self.workspace_path or Path.home() / "workspace.gim")
        path, _ = QFileDialog.getSaveFileName(self, "Save GIM workspace", initial, "GIM workspace (*.gim)")
        if not path:
            return
        try:
            self.workspace_path = save_workspace(self.workspace, path)
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return
        self.workspace.name = self.workspace_path.stem
        self.mark_dirty(False)

    def save_plot(self, request: PlotRequest, local_code: str, suggested_title: str) -> None:
        node_id = self.workspace.selected_node_id
        if not node_id:
            return
        dialog = ArtifactNameDialog(suggested_title, self)
        if dialog.exec() != ArtifactNameDialog.DialogCode.Accepted:
            return
        self.workspace.add_artifact(
            kind=ArtifactKind.PLOT,
            node_id=node_id,
            title=dialog.title,
            config=request.to_dict(),
            local_code=local_code,
        )
        self.mark_dirty()
        self.refresh()

    def run_stats(self) -> None:
        node_id = self.workspace.selected_node_id
        if not node_id:
            return
        frame = self.workspace.materialize(node_id)
        dialog = StatsDialog([str(column) for column in frame.columns], self)
        if dialog.exec() != StatsDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        try:
            result = run_statistical_test(frame, **values)
        except Exception as exc:
            QMessageBox.warning(self, "Statistical test failed", str(exc))
            return
        details = json.dumps(result.details, indent=2, ensure_ascii=False)
        choice = QMessageBox.question(
            self,
            result.test,
            f"Statistic: {result.statistic:.6g}\nP-value: {result.p_value:.6g}\n\n{result.interpretation}\n\n{details}\n\nSave this test?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Close,
            QMessageBox.StandardButton.Save,
        )
        if choice == QMessageBox.StandardButton.Save:
            self.workspace.add_artifact(
                kind=ArtifactKind.STAT,
                node_id=node_id,
                title=result.test,
                config=values,
                local_code="",
                result=result.to_dict(),
            )
            self.mark_dirty()
            self.refresh()

    def run_correlation(self) -> None:
        node_id = self.workspace.selected_node_id
        if not node_id:
            return
        frame = self.workspace.materialize(node_id)
        dialog = CorrelationDialog([str(column) for column in frame.columns], self)
        if dialog.exec() != CorrelationDialog.DialogCode.Accepted:
            return
        columns = dialog.selected_columns()
        method = dialog.method.currentText()
        try:
            figure = build_correlation_figure(frame, columns, method)
            self.plot_panel.plot_host.set_html(
                figure.to_html(full_html=True, include_plotlyjs=True, config={"responsive": True, "displaylogo": False})
            )
        except Exception as exc:
            QMessageBox.warning(self, "Correlation failed", str(exc))
            return
        choice = QMessageBox.question(
            self,
            "Correlation map",
            "Save this correlation map to the selected history node?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Close,
            QMessageBox.StandardButton.Save,
        )
        if choice == QMessageBox.StandardButton.Save:
            self.workspace.add_artifact(
                kind=ArtifactKind.CORRELATION,
                node_id=node_id,
                title=f"{method.title()} correlation",
                config={"columns": columns, "method": method},
            )
            self.mark_dirty()
            self.refresh()

    def open_artifact_item(self, item: QListWidgetItem) -> None:
        artifact_id = item.data(Qt.ItemDataRole.UserRole)
        artifact = self.workspace.artifacts.get(artifact_id)
        if not artifact:
            return
        self.select_node(artifact.node_id)
        if artifact.kind == ArtifactKind.PLOT:
            self.plot_panel.render_saved(PlotRequest.from_dict(artifact.config), artifact.local_code)
        elif artifact.kind == ArtifactKind.CORRELATION:
            frame = self.workspace.materialize(artifact.node_id)
            try:
                figure = build_correlation_figure(frame, artifact.config["columns"], artifact.config.get("method", "pearson"))
                self.plot_panel.plot_host.set_html(
                    figure.to_html(full_html=True, include_plotlyjs=True, config={"responsive": True, "displaylogo": False})
                )
            except Exception as exc:
                QMessageBox.warning(self, "Could not reopen correlation", str(exc))
        else:
            result = artifact.result or {}
            QMessageBox.information(
                self,
                artifact.title,
                f"Statistic: {result.get('statistic', '—')}\nP-value: {result.get('p_value', '—')}\n\n{result.get('interpretation', '')}",
            )

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if not self._dirty:
            event.accept()
            return
        choice = QMessageBox.question(
            self,
            "Unsaved workspace",
            "Close without saving the current workspace?",
            QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if choice == QMessageBox.StandardButton.Discard:
            event.accept()
        else:
            event.ignore()
