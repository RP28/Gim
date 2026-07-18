from __future__ import annotations

import pandas as pd

from gim.core.profile import build_column_detail, build_column_profiles


def test_profile_summarises_mixed_dataframe() -> None:
    frame = pd.DataFrame(
        {
            "sales": [10.0, 20.0, None, 40.0],
            "city": ["Sydney", "Sydney", "Melbourne", None],
            "ordered_at": pd.to_datetime(["2024-01-01", "2024-01-03", None, "2024-01-04"]),
            "priority": pd.Series([True, False, True, pd.NA], dtype="boolean"),
        }
    )

    profiles = {profile.name: profile for profile in build_column_profiles(frame)}

    assert profiles["sales"].kind == "numeric"
    assert profiles["sales"].missing == 1
    assert profiles["sales"].unique == 3
    assert "mean" in profiles["sales"].headline
    assert "75%" in profiles["sales"].details

    assert profiles["city"].kind == "text"
    assert profiles["city"].headline == "top Sydney"
    assert "freq 2" in profiles["city"].details

    assert profiles["ordered_at"].kind == "date"
    assert profiles["ordered_at"].headline == "2024-01-01 to 2024-01-04"

    assert profiles["priority"].kind == "boolean"
    assert "True" in profiles["priority"].headline


def test_profile_handles_empty_dataframe() -> None:
    frame = pd.DataFrame({"amount": pd.Series(dtype="float64"), "label": pd.Series(dtype="object")})

    profiles = {profile.name: profile for profile in build_column_profiles(frame)}

    assert profiles["amount"].count == 0
    assert profiles["amount"].missing == 0
    assert profiles["amount"].headline == "-"
    assert profiles["label"].headline == "-"


def test_profile_detail_includes_top_values_and_samples() -> None:
    frame = pd.DataFrame({"city": ["Sydney", "Sydney", "Melbourne", None], "sales": [10, 20, 30, 40]})
    profiles = {profile.name: profile for profile in build_column_profiles(frame)}

    detail = build_column_detail(profiles["city"], frame["city"], sample_size=3, top_size=2)

    assert ("Type", "object") in detail.summary
    assert ("Top", "Sydney") in detail.summary
    assert detail.top_values[0] == ("Sydney", "2", "50.0%")
    assert detail.sample_values == [("0", "Sydney"), ("1", "Sydney"), ("2", "Melbourne")]


def test_profile_detail_keeps_numeric_quantiles() -> None:
    frame = pd.DataFrame({"sales": [10, 20, 30, 40]})
    profile = build_column_profiles(frame)[0]

    detail = build_column_detail(profile, frame["sales"])

    assert ("Mean", "25") in detail.summary
    assert ("Median", "25") in detail.summary
