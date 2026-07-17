from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Any, ClassVar

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy.stats import gaussian_kde

from gim.config.theme import PALETTE


class PlotBuildError(ValueError):
    pass


@dataclass(slots=True)
class PlotRequest:
    family: str = "Distribution"
    mode: str = "Histogram + KDE"
    x: str | None = None
    y: str | None = None
    hue: str | None = None
    bins: int = 20
    flip: bool = False
    title: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "PlotRequest":
        accepted = {field.name for field in cls.__dataclass_fields__.values()}
        return cls(**{key: item for key, item in value.items() if key in accepted})


class PlotBuilder(ABC):
    family: ClassVar[str]
    modes: ClassVar[tuple[str, ...]]

    @abstractmethod
    def build(self, dataframe: pd.DataFrame, request: PlotRequest) -> go.Figure:
        raise NotImplementedError

    @staticmethod
    def require_column(dataframe: pd.DataFrame, column: str | None, role: str) -> str:
        if not column:
            raise PlotBuildError(f"Select a column for {role}")
        if column not in dataframe.columns:
            raise PlotBuildError(f"Unknown {role} column: {column}")
        return column

    @staticmethod
    def numeric(dataframe: pd.DataFrame, column: str) -> pd.Series:
        values = pd.to_numeric(dataframe[column], errors="coerce").dropna()
        if values.empty:
            raise PlotBuildError(f"{column} does not contain numeric values")
        return values


_BUILDERS: dict[str, PlotBuilder] = {}


def register_builder(cls: type[PlotBuilder]) -> type[PlotBuilder]:
    instance = cls()
    if instance.family in _BUILDERS:
        raise ValueError(f"Duplicate plot family: {instance.family}")
    _BUILDERS[instance.family] = instance
    return cls


def plot_families() -> tuple[str, ...]:
    return tuple(_BUILDERS)


def modes_for(family: str) -> tuple[str, ...]:
    try:
        return _BUILDERS[family].modes
    except KeyError as exc:
        raise PlotBuildError(f"Unknown plot family: {family}") from exc


def build_figure(dataframe: pd.DataFrame, request: PlotRequest) -> go.Figure:
    try:
        builder = _BUILDERS[request.family]
    except KeyError as exc:
        raise PlotBuildError(f"Unknown plot family: {request.family}") from exc
    figure = builder.build(dataframe, request)
    figure.update_layout(
        template="plotly_dark",
        paper_bgcolor=PALETTE.background,
        plot_bgcolor=PALETTE.surface,
        font={"color": PALETTE.text, "family": "Arial, Helvetica, sans-serif"},
        margin={"l": 55, "r": 30, "t": 60, "b": 55},
        hoverlabel={"bgcolor": PALETTE.surface_alt, "font_color": PALETTE.text},
        title=request.title or f"{request.family} · {request.mode}",
        legend_title_text=request.hue or "",
    )
    figure.update_xaxes(gridcolor="#2A313B", zerolinecolor="#39424D")
    figure.update_yaxes(gridcolor="#2A313B", zerolinecolor="#39424D")
    return figure


@register_builder
class DistributionBuilder(PlotBuilder):
    family = "Distribution"
    modes = ("Histogram", "KDE", "Histogram + KDE")

    def build(self, dataframe: pd.DataFrame, request: PlotRequest) -> go.Figure:
        column = self.require_column(dataframe, request.x, "X")
        bins: int | str = "auto" if int(request.bins) <= 0 else max(1, min(int(request.bins), 500))
        hue = request.hue if request.hue in dataframe.columns else None
        figure = go.Figure()
        groups = [("All", dataframe)] if not hue else list(dataframe.groupby(hue, dropna=False, observed=True))

        for group_name, group in groups:
            values = pd.to_numeric(group[column], errors="coerce").dropna().to_numpy()
            if values.size == 0:
                continue
            label = str(group_name)
            if request.mode in {"Histogram", "Histogram + KDE"}:
                counts, edges = np.histogram(values, bins=bins)
                centers = (edges[:-1] + edges[1:]) / 2
                percentages = counts / counts.sum() * 100 if counts.sum() else np.zeros_like(counts, dtype=float)
                custom = np.column_stack([counts, percentages, edges[:-1], edges[1:]])
                histogram_args: dict[str, Any] = {
                    "name": f"{label} · histogram" if hue else "Histogram",
                    "customdata": custom,
                    "opacity": 0.72,
                }
                if request.flip:
                    histogram_args.update(
                        {
                            "x": counts,
                            "y": centers,
                            "orientation": "h",
                            "hovertemplate": (
                                f"{column}: %{{customdata[2]:.4g}}–%{{customdata[3]:.4g}}<br>"
                                "Count: %{customdata[0]:,.0f}<br>Share: %{customdata[1]:.2f}%<extra>%{fullData.name}</extra>"
                            ),
                        }
                    )
                else:
                    histogram_args.update(
                        {
                            "x": centers,
                            "y": counts,
                            "hovertemplate": (
                                f"{column}: %{{customdata[2]:.4g}}–%{{customdata[3]:.4g}}<br>"
                                "Count: %{customdata[0]:,.0f}<br>Share: %{customdata[1]:.2f}%<extra>%{fullData.name}</extra>"
                            ),
                        }
                    )
                figure.add_trace(go.Bar(**histogram_args))
            if request.mode in {"KDE", "Histogram + KDE"} and values.size >= 2 and np.nanstd(values) > 0:
                grid = np.linspace(float(np.nanmin(values)), float(np.nanmax(values)), 240)
                density = gaussian_kde(values)(grid)
                if request.flip:
                    trace = go.Scatter(
                        x=density,
                        y=grid,
                        mode="lines",
                        name=f"{label} · KDE" if hue else "KDE",
                        hovertemplate=f"{column}: %{{y:.4g}}<br>Density: %{{x:.5g}}<extra>%{{fullData.name}}</extra>",
                    )
                    if request.mode == "Histogram + KDE":
                        trace.update(xaxis="x2")
                else:
                    trace = go.Scatter(
                        x=grid,
                        y=density,
                        mode="lines",
                        name=f"{label} · KDE" if hue else "KDE",
                        hovertemplate=f"{column}: %{{x:.4g}}<br>Density: %{{y:.5g}}<extra>%{{fullData.name}}</extra>",
                    )
                    if request.mode == "Histogram + KDE":
                        trace.update(yaxis="y2")
                figure.add_trace(trace)
        if not figure.data:
            raise PlotBuildError(f"{column} has no numeric data to plot")

        figure.update_layout(barmode="overlay")
        if request.flip:
            figure.update_yaxes(title_text=column)
            figure.update_xaxes(title_text="Count" if request.mode != "KDE" else "Density")
            if request.mode == "Histogram + KDE":
                figure.update_layout(
                    xaxis2={
                        "title": "Density",
                        "overlaying": "x",
                        "side": "top",
                        "showgrid": False,
                        "zeroline": False,
                    }
                )
        else:
            figure.update_xaxes(title_text=column)
            figure.update_yaxes(title_text="Count" if request.mode != "KDE" else "Density")
            if request.mode == "Histogram + KDE":
                figure.update_layout(
                    yaxis2={
                        "title": "Density",
                        "overlaying": "y",
                        "side": "right",
                        "showgrid": False,
                        "zeroline": False,
                    }
                )
        return figure


@register_builder
class RangeBuilder(PlotBuilder):
    family = "Range & shape"
    modes = ("Box", "Violin")

    def build(self, dataframe: pd.DataFrame, request: PlotRequest) -> go.Figure:
        value_column = request.y or request.x
        value_column = self.require_column(dataframe, value_column, "value")
        category_column = request.x if request.y else request.hue
        if category_column == value_column:
            category_column = None
        if category_column and category_column not in dataframe.columns:
            category_column = None
        groups = [("All", dataframe)] if not category_column else list(dataframe.groupby(category_column, dropna=False, observed=True))
        figure = go.Figure()
        for group_name, group in groups:
            values = pd.to_numeric(group[value_column], errors="coerce").dropna()
            if values.empty:
                continue
            q1, median, q3 = values.quantile([0.25, 0.5, 0.75]).tolist()
            iqr = q3 - q1
            summary = (
                f"Q1: {q1:.6g}<br>Median: {median:.6g}<br>Q3: {q3:.6g}<br>"
                f"IQR: {iqr:.6g}<br>Count: {len(values):,}"
            )
            label = str(group_name)
            common = {
                "name": label,
                "customdata": np.repeat(summary, len(values)),
                "hovertemplate": f"{value_column}: %{{y:.6g}}<br>%{{customdata}}<extra>{label}</extra>",
            }
            if request.mode == "Box":
                trace = go.Box(y=values, boxpoints="outliers", boxmean=True, **common)
            else:
                trace = go.Violin(y=values, box_visible=True, meanline_visible=True, points="outliers", **common)
            figure.add_trace(trace)
        if not figure.data:
            raise PlotBuildError(f"{value_column} has no numeric data to plot")
        figure.update_yaxes(title_text=value_column)
        if request.flip:
            for trace in figure.data:
                trace.x, trace.y = trace.y, None
                trace.orientation = "h"
                trace.hovertemplate = trace.hovertemplate.replace("%{y", "%{x")
            figure.update_xaxes(title_text=value_column)
            figure.update_yaxes(title_text=category_column or "")
        return figure


@register_builder
class ScatterBuilder(PlotBuilder):
    family = "Scatter"
    modes = ("Points",)

    def build(self, dataframe: pd.DataFrame, request: PlotRequest) -> go.Figure:
        x = self.require_column(dataframe, request.x, "X")
        y = self.require_column(dataframe, request.y, "Y")
        if request.flip:
            x, y = y, x
        hue = request.hue if request.hue in dataframe.columns else None
        figure = go.Figure()
        groups = [("All", dataframe)] if not hue else list(dataframe.groupby(hue, dropna=False, observed=True))
        for group_name, group in groups:
            figure.add_trace(
                go.Scattergl(
                    x=group[x],
                    y=group[y],
                    mode="markers",
                    name=str(group_name),
                    marker={"size": 7, "opacity": 0.72},
                    customdata=np.arange(len(group)),
                    hovertemplate=f"{x}: %{{x}}<br>{y}: %{{y}}<br>Row: %{{customdata}}<extra>%{{fullData.name}}</extra>",
                )
            )
        figure.update_xaxes(title_text=x)
        figure.update_yaxes(title_text=y)
        return figure


@register_builder
class PieBuilder(PlotBuilder):
    family = "Pie"
    modes = ("Share",)

    def build(self, dataframe: pd.DataFrame, request: PlotRequest) -> go.Figure:
        names = self.require_column(dataframe, request.x, "category")
        if request.y:
            values_column = self.require_column(dataframe, request.y, "value")
            aggregated = dataframe.groupby(names, dropna=False, observed=True)[values_column].sum(min_count=1).reset_index()
            labels = aggregated[names].astype(str)
            values = pd.to_numeric(aggregated[values_column], errors="coerce").fillna(0)
        else:
            counts = dataframe[names].astype("string").fillna("<missing>").value_counts(dropna=False)
            labels, values = counts.index.astype(str), counts.values
        return go.Figure(
            go.Pie(
                labels=labels,
                values=values,
                hole=0.32,
                hovertemplate="%{label}<br>Value: %{value:,.4g}<br>Share: %{percent}<extra></extra>",
            )
        )


@register_builder
class LineBuilder(PlotBuilder):
    family = "Line"
    modes = ("Line", "Line + markers")

    def build(self, dataframe: pd.DataFrame, request: PlotRequest) -> go.Figure:
        x = self.require_column(dataframe, request.x, "X")
        y = self.require_column(dataframe, request.y, "Y")
        if request.flip:
            x, y = y, x
        hue = request.hue if request.hue in dataframe.columns else None
        figure = go.Figure()
        groups = [("All", dataframe)] if not hue else list(dataframe.groupby(hue, dropna=False, observed=True))
        mode = "lines+markers" if request.mode == "Line + markers" else "lines"
        for group_name, group in groups:
            ordered = group.sort_values(x, kind="mergesort")
            figure.add_trace(
                go.Scatter(
                    x=ordered[x],
                    y=ordered[y],
                    mode=mode,
                    name=str(group_name),
                    hovertemplate=f"{x}: %{{x}}<br>{y}: %{{y}}<extra>%{{fullData.name}}</extra>",
                )
            )
        figure.update_xaxes(title_text=x)
        figure.update_yaxes(title_text=y)
        return figure


@register_builder
class FrequencyBuilder(PlotBuilder):
    family = "Frequency"
    modes = ("Count", "Percentage")

    def build(self, dataframe: pd.DataFrame, request: PlotRequest) -> go.Figure:
        column = self.require_column(dataframe, request.x, "category")
        counts = dataframe[column].astype("string").fillna("<missing>").value_counts(dropna=False)
        labels = counts.index.astype(str)
        values = counts.to_numpy(dtype=float)
        percentages = values / values.sum() * 100 if values.sum() else values
        plotted = percentages if request.mode == "Percentage" else values
        custom = np.column_stack([values, percentages])
        if request.flip:
            trace = go.Bar(
                x=plotted,
                y=labels,
                orientation="h",
                customdata=custom,
                hovertemplate="%{y}<br>Count: %{customdata[0]:,.0f}<br>Share: %{customdata[1]:.2f}%<extra></extra>",
            )
            figure = go.Figure(trace)
            figure.update_xaxes(title_text=request.mode)
            figure.update_yaxes(title_text=column, autorange="reversed")
        else:
            trace = go.Bar(
                x=labels,
                y=plotted,
                customdata=custom,
                hovertemplate="%{x}<br>Count: %{customdata[0]:,.0f}<br>Share: %{customdata[1]:.2f}%<extra></extra>",
            )
            figure = go.Figure(trace)
            figure.update_xaxes(title_text=column)
            figure.update_yaxes(title_text=request.mode)
        return figure


def build_correlation_figure(dataframe: pd.DataFrame, columns: list[str], method: str = "pearson") -> go.Figure:
    if method not in {"pearson", "spearman", "kendall"}:
        raise PlotBuildError(f"Unsupported correlation method: {method}")
    selected = [column for column in columns if column in dataframe.columns]
    if len(selected) < 2:
        raise PlotBuildError("Choose at least two columns")
    numeric = dataframe[selected].apply(pd.to_numeric, errors="coerce")
    valid = [column for column in numeric.columns if numeric[column].notna().sum() >= 2]
    if len(valid) < 2:
        raise PlotBuildError("At least two selected columns must contain numeric data")
    correlation = numeric[valid].corr(method=method)
    text = correlation.map(lambda value: "" if pd.isna(value) else f"{value:.2f}")
    figure = go.Figure(
        go.Heatmap(
            z=correlation.values,
            x=correlation.columns,
            y=correlation.index,
            zmin=-1,
            zmax=1,
            colorscale="RdBu",
            reversescale=True,
            text=text.values,
            texttemplate="%{text}",
            hovertemplate="%{y} × %{x}<br>Correlation: %{z:.4f}<extra></extra>",
        )
    )
    figure.update_layout(
        template="plotly_dark",
        title=f"{method.title()} correlation",
        paper_bgcolor=PALETTE.background,
        plot_bgcolor=PALETTE.surface,
        font={"color": PALETTE.text},
        margin={"l": 75, "r": 30, "t": 60, "b": 75},
    )
    return figure
