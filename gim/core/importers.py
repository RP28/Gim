from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(slots=True)
class ImportedFrame:
    alias: str
    dataframe: pd.DataFrame
    source_path: str | None = None
    read_options: dict[str, Any] | None = None


class CsvReadError(ValueError):
    pass


def read_csv_robust(
    path_or_buffer: str | Path | bytes | bytearray | BytesIO,
    *,
    encoding: str | None = None,
    delimiter: str | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Read a CSV with conservative delimiter and encoding fallbacks."""

    encodings = [encoding] if encoding else ["utf-8-sig", "utf-8", "cp1252", "latin-1"]
    delimiters: list[str | None] = [delimiter] if delimiter is not None else [None, ",", ";", "\t", "|"]
    failures: list[str] = []

    for current_encoding in encodings:
        for current_delimiter in delimiters:
            try:
                source: Any
                if isinstance(path_or_buffer, (bytes, bytearray)):
                    source = BytesIO(bytes(path_or_buffer))
                elif isinstance(path_or_buffer, BytesIO):
                    source = BytesIO(path_or_buffer.getvalue())
                else:
                    source = path_or_buffer
                kwargs: dict[str, Any] = {
                    "encoding": current_encoding,
                    "low_memory": False,
                }
                if current_delimiter is None:
                    kwargs.update({"sep": None, "engine": "python"})
                else:
                    kwargs["sep"] = current_delimiter
                frame = pd.read_csv(source, **kwargs)
                if len(frame.columns) == 1:
                    header = str(frame.columns[0])
                    separators = [",", ";", "\t", "|"]
                    if any(candidate in header for candidate in separators):
                        raise ValueError("delimiter selection produced a single suspicious column")
                return frame, {
                    "encoding": current_encoding,
                    "delimiter": current_delimiter if current_delimiter is not None else "auto",
                }
            except Exception as exc:
                failures.append(f"{current_encoding}/{current_delimiter!r}: {exc}")
    raise CsvReadError("Unable to read CSV. Attempts:\n" + "\n".join(failures[-8:]))


def _frame_from_object(value: Any) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value.copy(deep=False)
    if hasattr(value, "to_pandas") and callable(value.to_pandas):
        converted = value.to_pandas()
        if not isinstance(converted, pd.DataFrame):
            raise TypeError("to_pandas() did not return a pandas DataFrame")
        return converted
    if hasattr(value, "__dataframe__"):
        try:
            from pandas.api.interchange import from_dataframe

            return from_dataframe(value)
        except Exception as exc:
            raise TypeError(f"Could not convert dataframe interchange object: {exc}") from exc
    raise TypeError(f"Unsupported data object: {type(value).__name__}")


def normalise_sources(*sources: Any) -> list[ImportedFrame]:
    """Normalise paths, DataFrames, mappings, tuples and dataframe-like objects."""

    imported: list[ImportedFrame] = []
    counter = 1

    def visit(value: Any, alias_hint: str | None = None) -> None:
        nonlocal counter
        if value is None:
            return
        if isinstance(value, Mapping):
            for alias, item in value.items():
                visit(item, str(alias))
            return
        if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], str):
            visit(value[1], value[0])
            return
        if isinstance(value, (list, tuple)):
            for item in value:
                visit(item)
            return
        if isinstance(value, (str, Path)):
            path = Path(value).expanduser().resolve()
            frame, options = read_csv_robust(path)
            imported.append(
                ImportedFrame(
                    alias=alias_hint or path.stem,
                    dataframe=frame,
                    source_path=str(path),
                    read_options=options,
                )
            )
            counter += 1
            return
        frame = _frame_from_object(value)
        imported.append(ImportedFrame(alias=alias_hint or f"data_{counter}", dataframe=frame))
        counter += 1

    for source in sources:
        visit(source)
    return imported
