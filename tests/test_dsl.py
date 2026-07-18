from __future__ import annotations

import pandas as pd
import pytest

from gim.core.dsl import DslError, LocalTransformEngine


@pytest.fixture
def frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Order Date": ["2025-01-01", "2025-01-02", "2025-01-02", None],
            "revenue": [100.0, 200.0, 200.0, None],
            "cost": [60.0, 80.0, 80.0, 10.0],
            "status": ["active", "active", "active", "inactive"],
            "city": ["Sydney", "Melbourne", "Melbourne", None],
        }
    )


def test_combined_transform_language(frame: pd.DataFrame) -> None:
    result = LocalTransformEngine().apply(
        frame,
        """
        where @status == "active"
        derive margin = @revenue - @cost
        cast @{Order Date} as datetime
        dedupe @{Order Date}, @revenue
        sort @margin desc
        """,
    )
    assert list(result["margin"]) == [120.0, 40.0]
    assert str(result["Order Date"].dtype).startswith("datetime64")


def test_column_tokens_with_spaces_and_helpers(frame: pd.DataFrame) -> None:
    result = LocalTransformEngine().apply(frame, 'where contains(@city, "syd") | keep @{Order Date}, @city')
    assert len(result) == 1
    assert list(result.columns) == ["Order Date", "city"]


def test_natural_null_checks(frame: pd.DataFrame) -> None:
    engine = LocalTransformEngine()

    present = engine.apply(frame, "where @city not null")
    missing = engine.apply(frame, "where @city is null")
    also_present = engine.apply(frame, "where @city is not null")
    comparison_present = engine.apply(frame, "where @city != null")
    comparison_missing = engine.apply(frame, "where @city == null")

    assert len(present) == 3
    assert len(missing) == 1
    assert list(also_present.index) == list(present.index)
    assert list(comparison_present.index) == list(present.index)
    assert list(comparison_missing.index) == list(missing.index)


def test_fill_rename_cast_and_sample(frame: pd.DataFrame) -> None:
    result = LocalTransformEngine().apply(
        frame,
        "fill @revenue = median\nrename @revenue as Revenue\ncast @Revenue as float\nsample 100",
    )
    assert result["Revenue"].isna().sum() == 0
    assert len(result) == len(frame)


def test_update_existing_column_and_cast_to_date() -> None:
    frame = pd.DataFrame({"PriceUpdatedDate": ["2026-03-01 00:05:26", "2026-03-14 12:00:49"]})

    result = LocalTransformEngine().apply(frame, "update @PriceUpdatedDate = date(@PriceUpdatedDate)")

    assert str(result["PriceUpdatedDate"].dtype).startswith("datetime64")
    assert list(result["PriceUpdatedDate"].dt.strftime("%Y-%m-%d")) == ["2026-03-01", "2026-03-14"]


def test_cast_column_to_date() -> None:
    frame = pd.DataFrame({"PriceUpdatedDate": ["2026-03-01 00:05:26", None]})

    result = LocalTransformEngine().apply(frame, "cast @PriceUpdatedDate as date")

    assert str(result["PriceUpdatedDate"].dtype).startswith("datetime64")
    assert result["PriceUpdatedDate"].dt.strftime("%Y-%m-%d").iloc[0] == "2026-03-01"
    assert pd.isna(result["PriceUpdatedDate"].iloc[1])


def test_unknown_column_is_clear_error(frame: pd.DataFrame) -> None:
    with pytest.raises(DslError, match="Unknown column"):
        LocalTransformEngine().apply(frame, "drop @missing")


def test_unsafe_python_is_rejected(frame: pd.DataFrame) -> None:
    with pytest.raises(DslError):
        LocalTransformEngine().apply(frame, 'derive bad = __import__("os").system("echo unsafe")')


def test_where_must_return_boolean(frame: pd.DataFrame) -> None:
    with pytest.raises(DslError, match="boolean"):
        LocalTransformEngine().apply(frame, "where @revenue + 1")


def test_negative_head_rejected(frame: pd.DataFrame) -> None:
    with pytest.raises(DslError, match="negative"):
        LocalTransformEngine().apply(frame, "head -1")
