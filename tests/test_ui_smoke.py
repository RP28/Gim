from __future__ import annotations

import pandas as pd


def test_public_run_accepts_multiple_dataframes(qapp) -> None:
    import gim

    controller = gim.run(
        ("first", pd.DataFrame({"x": [1, 2], "y": [3, 4]})),
        ("second", pd.DataFrame({"id": [1, 2]})),
        start_event_loop=False,
    )
    assert controller.main_window is not None
    assert len(controller.main_window.workspace.sources) == 2
    controller.main_window.mark_dirty(False)
    controller.main_window.close()


def test_history_view_requests_merge_on_shift_selection(qapp) -> None:
    from gim.core.workspace import Workspace
    from gim.ui.history_view import HistoryGraphView

    workspace = Workspace()
    first = workspace.add_source(pd.DataFrame({"id": [1]}), "first")
    second = workspace.add_source(pd.DataFrame({"id": [1]}), "second")
    view = HistoryGraphView()
    view.set_workspace(workspace)
    pairs: list[tuple[str, str]] = []
    view.mergePairSelected.connect(lambda left, right: pairs.append((left, right)))
    view.select_node(first.id)
    view.select_node(second.id, additive=True)
    assert view.selected_node_ids() == [first.id, second.id]
    assert pairs == [(first.id, second.id)]


def test_main_window_context_updates(qapp) -> None:
    from PySide6.QtWidgets import QPushButton

    from gim.core.workspace import Workspace
    from gim.ui.main_window import MainWindow

    workspace = Workspace()
    node = workspace.add_source(pd.DataFrame({"x": [1, 2], "y": [3, 4]}), "data")
    window = MainWindow(workspace)
    window.select_node(node.id)
    assert window.plot_panel.node_id == node.id
    assert window.plot_panel.x_column.findText("x") >= 0
    assert window.profile_panel.table.rowCount() == 2
    assert window.command_console.column_tokens.count() == 2
    assert "data" in window.node_summary.text()
    button_texts = [button.text() for button in window.findChildren(QPushButton)]
    assert "Transform" not in button_texts
    assert "Duplicate branch" not in button_texts
    window.mark_dirty(False)
    window.close()


def test_main_window_opens_merge_from_shift_selection(qapp) -> None:
    from gim.core.workspace import Workspace
    from gim.ui.main_window import MainWindow

    workspace = Workspace()
    first = workspace.add_source(pd.DataFrame({"id": [1]}), "first")
    second = workspace.add_source(pd.DataFrame({"id": [1]}), "second")
    window = MainWindow(workspace)
    pairs: list[tuple[str, str]] = []
    window.open_merge_dialog = lambda left, right: pairs.append((left, right))  # type: ignore[method-assign]

    window.history.select_node(first.id)
    window.history.select_node(second.id, additive=True)

    assert window.history.selected_node_ids() == [first.id, second.id]
    assert pairs == [(first.id, second.id)]
    window.mark_dirty(False)
    window.close()


def test_merge_dialog_keeps_long_fields_readable(qapp) -> None:
    from gim.ui.dialogs import MergeDialog

    long_name = "product_sub_category"
    long_column = "product_subcategory_extremely_long_identifier"
    dialog = MergeDialog(long_name, "product", [long_column], [long_column])

    assert dialog.minimumWidth() >= 720
    assert dialog.left_key.minimumWidth() >= 360
    assert dialog.right_key.minimumWidth() >= 360
    assert dialog.left_key.view().minimumWidth() >= dialog.left_key.minimumWidth()
    dialog.close()


def test_command_console_runs_transform_and_duplicate(qapp) -> None:
    from gim.core.workspace import Workspace
    from gim.ui.main_window import MainWindow

    workspace = Workspace()
    source = workspace.add_source(pd.DataFrame({"x": [1, 2], "y": [3, 4]}), "data")
    window = MainWindow(workspace)
    window.select_node(source.id)

    window.run_console_command("drop @y")
    dropped = workspace.require_node(workspace.selected_node_id)
    assert list(workspace.materialize(dropped.id).columns) == ["x"]
    assert "Dropped columns" in window.command_console.output.toPlainText()

    window.run_console_command("duplicate as Stats branch")
    duplicated = workspace.require_node(workspace.selected_node_id)
    assert duplicated.alias == "Stats branch"
    assert "Duplicated branch" in window.command_console.output.toPlainText()
    window.mark_dirty(False)
    window.close()


def test_command_console_runs_multiline_batch(qapp) -> None:
    from gim.core.workspace import Workspace
    from gim.ui.main_window import MainWindow

    workspace = Workspace()
    source = workspace.add_source(pd.DataFrame({"x": [1, 2], "y": [3, 4]}), "data")
    window = MainWindow(workspace)
    window.select_node(source.id)

    window.run_console_command("drop @y\nupdate @x = @x + 10")
    frame = workspace.materialize(workspace.selected_node_id)

    assert list(frame.columns) == ["x"]
    assert list(frame["x"]) == [11, 12]
    assert "Dropped columns" in window.command_console.output.toPlainText()
    assert "Updated column" in window.command_console.output.toPlainText()
    assert len(workspace.nodes) == 3
    window.mark_dirty(False)
    window.close()


def test_command_console_cheatsheet_button_is_available(qapp) -> None:
    from PySide6.QtWidgets import QPushButton

    from gim.ui.command_console import CommandConsole

    console = CommandConsole()

    button_texts = [button.text() for button in console.findChildren(QPushButton)]
    assert "Show language cheatsheet" in button_texts


def test_plot_panel_bins_slider_and_spin_stay_synchronised(qapp) -> None:
    from gim.ui.plot_panel import PlotPanel

    panel = PlotPanel()
    panel.bins_slider.setValue(37)
    assert panel.bins_spin.value() == 37
    panel.bins_spin.setValue(42)
    assert panel.bins_slider.value() == 42


def test_profile_panel_double_click_opens_column_detail(qapp, monkeypatch) -> None:
    import gim.ui.profile_panel as profile_module

    opened: list[str] = []

    class FakeDialog:
        def __init__(self, detail, parent=None) -> None:
            opened.append(detail.name)

        def exec(self) -> int:
            return 0

    monkeypatch.setattr(profile_module, "ColumnDetailDialog", FakeDialog)

    panel = profile_module.ProfilePanel()
    panel.set_dataframe("data", pd.DataFrame({"x": [1, 2], "city": ["Sydney", "Melbourne"]}))
    panel._open_detail_dialog(panel.table.item(0, 0))

    assert opened == ["x"]
