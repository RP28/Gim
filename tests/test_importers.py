from __future__ import annotations

import pandas as pd

from gim.core.importers import normalise_sources, read_csv_robust


def test_semicolon_and_cp1252_detection(tmp_path) -> None:
    path = tmp_path / "people.csv"
    path.write_bytes("name;city\nAndré;Montréal\n".encode("cp1252"))
    frame, options = read_csv_robust(path)
    assert list(frame.columns) == ["name", "city"]
    assert frame.iloc[0, 0] == "André"
    assert options["encoding"] in {"cp1252", "latin-1"}


def test_normalise_multiple_object_forms(tmp_path) -> None:
    path = tmp_path / "one.csv"
    path.write_text("x\n1\n", encoding="utf-8")
    frames = normalise_sources(
        ("custom", pd.DataFrame({"a": [1]})),
        {"mapped": pd.DataFrame({"b": [2]})},
        [path],
    )
    assert [item.alias for item in frames] == ["custom", "mapped", "one"]


class DataframeLike:
    def to_pandas(self):
        return pd.DataFrame({"x": [1, 2]})


def test_to_pandas_adapter() -> None:
    frames = normalise_sources(DataframeLike())
    assert frames[0].dataframe.shape == (2, 1)
