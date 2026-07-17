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
    from gim.core.workspace import Workspace
    from gim.ui.main_window import MainWindow

    workspace = Workspace()
    node = workspace.add_source(pd.DataFrame({"x": [1, 2], "y": [3, 4]}), "data")
    window = MainWindow(workspace)
    window.select_node(node.id)
    assert window.plot_panel.node_id == node.id
    assert window.plot_panel.x_column.findText("x") >= 0
    assert "data" in window.node_summary.text()
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


def test_transform_dialog_apply_button_accepts(qapp) -> None:
    from PySide6.QtWidgets import QDialogButtonBox

    from gim.ui.dialogs import TransformDialog

    dialog = TransformDialog(["product_id"])
    dialog.editor.setPlainText("drop @product_id")

    buttons = dialog.findChild(QDialogButtonBox)
    assert buttons is not None
    buttons.button(QDialogButtonBox.StandardButton.Apply).click()

    assert dialog.result() == TransformDialog.DialogCode.Accepted


def test_local_operation_cheatsheet_buttons_are_available(qapp) -> None:
    from PySide6.QtWidgets import QPushButton

    from gim.ui.dialogs import StatsDialog, TransformDialog
    from gim.ui.plot_panel import PlotPanel

    dialogs = [TransformDialog(["x"]), StatsDialog(["x", "y"])]
    panel = PlotPanel()

    for widget in [*dialogs, panel]:
        button_texts = [button.text() for button in widget.findChildren(QPushButton)]
        assert "Show language cheatsheet" in button_texts


def test_plot_panel_bins_slider_and_spin_stay_synchronised(qapp) -> None:
    from gim.ui.plot_panel import PlotPanel

    panel = PlotPanel()
    panel.bins_slider.setValue(37)
    assert panel.bins_spin.value() == 37
    panel.bins_spin.setValue(42)
    assert panel.bins_slider.value() == 42
