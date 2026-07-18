from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
from pandas.api.types import is_bool_dtype, is_datetime64_any_dtype, is_numeric_dtype


@dataclass(frozen=True, slots=True)
class ColumnProfile:
    name: str
    dtype: str
    kind: str
    count: int
    missing: int
    missing_pct: float
    unique: int | None
    headline: str
    details: str


def _format_number(value: Any) -> str:
    if pd.isna(value):
        return "-"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number.is_integer() and abs(number) < 1_000_000:
        return f"{number:,.0f}"
    return f"{number:,.4g}"


def _format_value(value: Any) -> str:
    if pd.isna(value):
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


def _numeric_profile(name: str, series: pd.Series, dtype: str, count: int, missing: int, missing_pct: float) -> ColumnProfile:
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
    return ColumnProfile(name, dtype, "numeric", count, missing, missing_pct, unique, headline, details)


def _datetime_profile(name: str, series: pd.Series, dtype: str, count: int, missing: int, missing_pct: float) -> ColumnProfile:
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
    return ColumnProfile(name, dtype, "date", count, missing, missing_pct, unique, headline, details)


def _categorical_profile(name: str, series: pd.Series, dtype: str, count: int, missing: int, missing_pct: float) -> ColumnProfile:
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
    return ColumnProfile(name, dtype, "text", count, missing, missing_pct, unique, headline, details)


def _bool_profile(name: str, series: pd.Series, dtype: str, count: int, missing: int, missing_pct: float) -> ColumnProfile:
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
    return ColumnProfile(name, dtype, "boolean", count, missing, missing_pct, unique, headline, details)


def build_column_profiles(dataframe: pd.DataFrame) -> list[ColumnProfile]:
    profiles: list[ColumnProfile] = []
    total = len(dataframe)
    for column in dataframe.columns:
        series = dataframe[column]
        name = str(column)
        dtype = str(series.dtype)
        count = int(series.notna().sum())
        missing = total - count
        missing_pct = missing / total * 100 if total else 0.0
        if is_bool_dtype(series):
            profiles.append(_bool_profile(name, series, dtype, count, missing, missing_pct))
        elif is_datetime64_any_dtype(series):
            profiles.append(_datetime_profile(name, series, dtype, count, missing, missing_pct))
        elif is_numeric_dtype(series):
            profiles.append(_numeric_profile(name, series, dtype, count, missing, missing_pct))
        else:
            profiles.append(_categorical_profile(name, series, dtype, count, missing, missing_pct))
    return profiles
