from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
from pandas.api.types import is_bool_dtype, is_datetime64_any_dtype, is_numeric_dtype


@dataclass(frozen=True, slots=True)
class ColumnProfile:
    name: str
    position: int
    dtype: str
    kind: str
    count: int
    missing: int
    missing_pct: float
    unique: int | None
    headline: str
    details: str


@dataclass(frozen=True, slots=True)
class ColumnDetail:
    name: str
    dtype: str
    kind: str
    summary: list[tuple[str, str]]
    top_values: list[tuple[str, str, str]]
    sample_values: list[tuple[str, str]]


def _is_missing(value: Any) -> bool:
    try:
        result = pd.isna(value)
    except (TypeError, ValueError):
        return False
    try:
        return bool(result)
    except (TypeError, ValueError):
        return False


def _format_number(value: Any) -> str:
    if _is_missing(value):
        return "-"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number.is_integer() and abs(number) < 1_000_000:
        return f"{number:,.0f}"
    return f"{number:,.4g}"


def _format_value(value: Any) -> str:
    if _is_missing(value):
        return "-"
    if isinstance(value, pd.Timestamp):
        if value.hour or value.minute or value.second:
            return value.strftime("%Y-%m-%d %H:%M")
        return value.strftime("%Y-%m-%d")
    return str(value)


def _safe_unique(series: pd.Series) -> int | None:
    try:
        return int(series.nunique(dropna=True))
    except TypeError:
        return None


def _top_value(series: pd.Series) -> tuple[Any, int] | None:
    clean = series.dropna()
    if clean.empty:
        return None
    try:
        counts = clean.value_counts(dropna=True)
    except TypeError:
        counts = clean.astype("string").value_counts(dropna=True)
    if counts.empty:
        return None
    return counts.index[0], int(counts.iloc[0])


def _value_counts(series: pd.Series, limit: int) -> list[tuple[str, str, str]]:
    total = len(series)
    try:
        counts = series.value_counts(dropna=False).head(limit)
    except TypeError:
        counts = series.astype("string").fillna("<missing>").value_counts(dropna=False).head(limit)
    values: list[tuple[str, str, str]] = []
    for value, count in counts.items():
        label = "<missing>" if _is_missing(value) else _format_value(value)
        share = int(count) / total * 100 if total else 0
        values.append((label, f"{int(count):,}", f"{share:.1f}%"))
    return values


def _sample_values(series: pd.Series, limit: int) -> list[tuple[str, str]]:
    return [(str(index), _format_value(value)) for index, value in series.head(limit).items()]


def _numeric_profile(
    name: str,
    position: int,
    series: pd.Series,
    dtype: str,
    count: int,
    missing: int,
    missing_pct: float,
) -> ColumnProfile:
    values = pd.to_numeric(series, errors="coerce").dropna()
    unique = _safe_unique(series)
    if values.empty:
        headline = "-"
        details = f"count {count:,} | missing {missing:,} ({missing_pct:.1f}%) | unique {_format_number(unique)}"
    else:
        summary = values.describe()
        headline = f"mean {_format_number(summary['mean'])}"
        details = (
            f"count {int(summary['count']):,} | missing {missing:,} ({missing_pct:.1f}%) | "
            f"unique {_format_number(unique)} | mean {_format_number(summary['mean'])} | "
            f"std {_format_number(summary['std'])} | min {_format_number(summary['min'])} | "
            f"25% {_format_number(summary['25%'])} | 50% {_format_number(summary['50%'])} | "
            f"75% {_format_number(summary['75%'])} | max {_format_number(summary['max'])}"
        )
    return ColumnProfile(name, position, dtype, "numeric", count, missing, missing_pct, unique, headline, details)


def _datetime_profile(
    name: str,
    position: int,
    series: pd.Series,
    dtype: str,
    count: int,
    missing: int,
    missing_pct: float,
) -> ColumnProfile:
    values = pd.to_datetime(series, errors="coerce").dropna()
    unique = _safe_unique(series)
    if values.empty:
        headline = "-"
        details = f"count {count:,} | missing {missing:,} ({missing_pct:.1f}%) | unique {_format_number(unique)}"
    else:
        headline = f"{_format_value(values.min())} to {_format_value(values.max())}"
        details = (
            f"count {len(values):,} | missing {missing:,} ({missing_pct:.1f}%) | "
            f"unique {_format_number(unique)} | first {_format_value(values.min())} | "
            f"median {_format_value(values.quantile(0.5))} | last {_format_value(values.max())}"
        )
    return ColumnProfile(name, position, dtype, "date", count, missing, missing_pct, unique, headline, details)


def _categorical_profile(
    name: str,
    position: int,
    series: pd.Series,
    dtype: str,
    count: int,
    missing: int,
    missing_pct: float,
) -> ColumnProfile:
    unique = _safe_unique(series)
    top = _top_value(series)
    if top is None:
        headline = "-"
        details = f"count {count:,} | missing {missing:,} ({missing_pct:.1f}%) | unique {_format_number(unique)}"
    else:
        value, frequency = top
        headline = f"top {_format_value(value)}"
        details = (
            f"count {count:,} | missing {missing:,} ({missing_pct:.1f}%) | "
            f"unique {_format_number(unique)} | top {_format_value(value)} | freq {frequency:,}"
        )
    return ColumnProfile(name, position, dtype, "text", count, missing, missing_pct, unique, headline, details)


def _bool_profile(
    name: str,
    position: int,
    series: pd.Series,
    dtype: str,
    count: int,
    missing: int,
    missing_pct: float,
) -> ColumnProfile:
    unique = _safe_unique(series)
    top = _top_value(series)
    if top is None:
        headline = "-"
        details = f"count {count:,} | missing {missing:,} ({missing_pct:.1f}%) | unique {_format_number(unique)}"
    else:
        value, frequency = top
        share = frequency / count * 100 if count else 0
        headline = f"{_format_value(value)} {share:.1f}%"
        details = (
            f"count {count:,} | missing {missing:,} ({missing_pct:.1f}%) | "
            f"unique {_format_number(unique)} | most common {_format_value(value)} | freq {frequency:,} ({share:.1f}%)"
        )
    return ColumnProfile(name, position, dtype, "boolean", count, missing, missing_pct, unique, headline, details)


def build_column_profiles(dataframe: pd.DataFrame) -> list[ColumnProfile]:
    profiles: list[ColumnProfile] = []
    total = len(dataframe)
    for position, column in enumerate(dataframe.columns):
        series = dataframe.iloc[:, position]
        name = str(column)
        dtype = str(series.dtype)
        count = int(series.notna().sum())
        missing = total - count
        missing_pct = missing / total * 100 if total else 0.0
        if is_bool_dtype(series):
            profiles.append(_bool_profile(name, position, series, dtype, count, missing, missing_pct))
        elif is_datetime64_any_dtype(series):
            profiles.append(_datetime_profile(name, position, series, dtype, count, missing, missing_pct))
        elif is_numeric_dtype(series):
            profiles.append(_numeric_profile(name, position, series, dtype, count, missing, missing_pct))
        else:
            profiles.append(_categorical_profile(name, position, series, dtype, count, missing, missing_pct))
    return profiles


def build_column_detail(profile: ColumnProfile, series: pd.Series, sample_size: int = 12, top_size: int = 8) -> ColumnDetail:
    summary = [
        ("Type", profile.dtype),
        ("Kind", profile.kind.title()),
        ("Count", f"{profile.count:,}"),
        ("Missing", f"{profile.missing:,} ({profile.missing_pct:.1f}%)"),
        ("Unique", "-" if profile.unique is None else f"{profile.unique:,}"),
    ]
    if profile.kind == "numeric":
        values = pd.to_numeric(series, errors="coerce").dropna()
        if not values.empty:
            described = values.describe()
            summary.extend(
                [
                    ("Mean", _format_number(described["mean"])),
                    ("Std", _format_number(described["std"])),
                    ("Min", _format_number(described["min"])),
                    ("25%", _format_number(described["25%"])),
                    ("Median", _format_number(described["50%"])),
                    ("75%", _format_number(described["75%"])),
                    ("Max", _format_number(described["max"])),
                ]
            )
    elif profile.kind == "date":
        values = pd.to_datetime(series, errors="coerce").dropna()
        if not values.empty:
            summary.extend(
                [
                    ("First", _format_value(values.min())),
                    ("Median", _format_value(values.quantile(0.5))),
                    ("Last", _format_value(values.max())),
                ]
            )
    else:
        top = _top_value(series)
        if top is not None:
            value, frequency = top
            summary.extend([("Top", _format_value(value)), ("Top frequency", f"{frequency:,}")])
    return ColumnDetail(
        name=profile.name,
        dtype=profile.dtype,
        kind=profile.kind,
        summary=summary,
        top_values=_value_counts(series, top_size),
        sample_values=_sample_values(series, sample_size),
    )
