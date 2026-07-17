from __future__ import annotations

import pandas as pd
import pytest

from gim.core.plotting import PlotBuildError, PlotRequest, build_correlation_figure, build_figure


@pytest.fixture
def frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "x": [1, 2, 3, 4, 5, 6],
            "y": [2, 4, 3, 8, 7, 9],
            "group": ["A", "A", "A", "B", "B", "B"],
            "date": pd.date_range("2025-01-01", periods=6),
        }
    )


@pytest.mark.parametrize(
    ("family", "mode", "x", "y"),
    [
        ("Distribution", "Histogram", "x", None),
        ("Distribution", "KDE", "x", None),
        ("Distribution", "Histogram + KDE", "x", None),
        ("Range & shape", "Box", "group", "y"),
        ("Range & shape", "Violin", "group", "y"),
        ("Scatter", "Points", "x", "y"),
        ("Pie", "Share", "group", None),
        ("Line", "Line + markers", "date", "y"),
        ("Frequency", "Percentage", "group", None),
    ],
)
def test_requested_plot_families(frame, family, mode, x, y) -> None:
    figure = build_figure(frame, PlotRequest(family=family, mode=mode, x=x, y=y, hue="group" if family in {"Distribution", "Scatter", "Line"} else None))
    assert len(figure.data) >= 1
    assert figure.layout.template is not None



def test_distribution_auto_bins_and_flip(frame) -> None:
    figure = build_figure(frame, PlotRequest(family="Distribution", mode="Histogram + KDE", x="x", bins=0, flip=True))
    assert figure.data[0].orientation == "h"
    assert figure.layout.xaxis2.overlaying == "x"


def test_frequency_flip_becomes_horizontal_bar(frame) -> None:
    figure = build_figure(frame, PlotRequest(family="Frequency", mode="Count", x="group", flip=True))
    assert figure.data[0].orientation == "h"



def test_range_flip_becomes_horizontal(frame) -> None:
    figure = build_figure(frame, PlotRequest(family="Range & shape", mode="Box", x="group", y="y", flip=True))
    assert all(trace.orientation == "h" for trace in figure.data)


def test_scatter_flip_swaps_axis_titles(frame) -> None:
    figure = build_figure(frame, PlotRequest(family="Scatter", mode="Points", x="x", y="y", flip=True))
    assert figure.layout.xaxis.title.text == "y"
    assert figure.layout.yaxis.title.text == "x"


def test_histogram_hover_contains_count_and_share(frame) -> None:
    figure = build_figure(frame, PlotRequest(family="Distribution", mode="Histogram", x="x", bins=3))
    template = figure.data[0].hovertemplate
    assert "Count" in template and "Share" in template


def test_correlation_heatmap(frame) -> None:
    figure = build_correlation_figure(frame, ["x", "y"], "spearman")
    assert figure.data[0].type == "heatmap"


def test_missing_column_error(frame) -> None:
    with pytest.raises(PlotBuildError, match="Select"):
        build_figure(frame, PlotRequest(family="Scatter", mode="Points", x="x"))
