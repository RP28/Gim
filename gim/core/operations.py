from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pandas as pd

OperationFunction = Callable[[tuple[pd.DataFrame, ...], dict[str, Any]], pd.DataFrame]


@dataclass(frozen=True, slots=True)
class RegisteredOperation:
    name: str
    label: str
    function: OperationFunction


_REGISTRY: dict[str, RegisteredOperation] = {}


def operation(name: str, label: str) -> Callable[[OperationFunction], OperationFunction]:
    """Register a replayable data operation.

    Registered operations are deliberately pure: they receive parent frames and
    JSON-serialisable parameters, and return a new frame.
    """

    def decorator(function: OperationFunction) -> OperationFunction:
        if name in _REGISTRY:
            raise ValueError(f"Operation {name!r} is already registered")
        _REGISTRY[name] = RegisteredOperation(name=name, label=label, function=function)
        return function

    return decorator


def get_operation(name: str) -> RegisteredOperation:
    try:
        return _REGISTRY[name]
    except KeyError as exc:
        raise KeyError(f"Unknown operation: {name}") from exc


def registered_operations() -> tuple[RegisteredOperation, ...]:
    return tuple(_REGISTRY.values())


@operation("identity", "Duplicate data")
def identity(parents: tuple[pd.DataFrame, ...], params: dict[str, Any]) -> pd.DataFrame:
    del params
    return parents[0].copy(deep=False)


@operation("dsl", "Transform data")
def apply_dsl(parents: tuple[pd.DataFrame, ...], params: dict[str, Any]) -> pd.DataFrame:
    from .dsl import LocalTransformEngine

    code = str(params.get("code", ""))
    return LocalTransformEngine().apply(parents[0], code)


@operation("merge", "Merge data")
def merge_frames(parents: tuple[pd.DataFrame, ...], params: dict[str, Any]) -> pd.DataFrame:
    if len(parents) != 2:
        raise ValueError("Merge requires exactly two parent dataframes")
    how = str(params.get("how", "inner"))
    if how not in {"left", "right", "inner", "outer"}:
        raise ValueError(f"Unsupported merge type: {how}")
    left_on = params.get("left_on")
    right_on = params.get("right_on")
    if not left_on or not right_on:
        raise ValueError("Both merge keys are required")
    suffixes = tuple(params.get("suffixes", ["_left", "_right"]))
    return pd.merge(
        parents[0],
        parents[1],
        how=how,
        left_on=left_on,
        right_on=right_on,
        suffixes=suffixes,
        copy=False,
    )
