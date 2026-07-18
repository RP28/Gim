from __future__ import annotations

import ast
import math
import operator
import re
from dataclasses import dataclass
from importlib.resources import files
from typing import Any

import numpy as np
import pandas as pd

_COLUMN_TOKEN = re.compile(r"@\{([^}]+)\}|@([A-Za-z_][A-Za-z0-9_]*)")
_COLUMN_TOKEN_TEXT = r"(?:@\{[^}]+\}|@[A-Za-z_][A-Za-z0-9_]*)"


class DslError(ValueError):
    pass


@dataclass(slots=True)
class ParsedExpression:
    expression: str
    columns: dict[str, str]


def _replace_column_tokens(expression: str, columns: pd.Index) -> ParsedExpression:
    mapping: dict[str, str] = {}
    known = {str(column) for column in columns}

    def replacer(match: re.Match[str]) -> str:
        column = match.group(1) or match.group(2)
        if column not in known:
            raise DslError(f"Unknown column: {column}")
        key = f"__column_{len(mapping)}"
        mapping[key] = column
        return key

    return ParsedExpression(_COLUMN_TOKEN.sub(replacer, expression), mapping)


def _normalise_null_checks(expression: str) -> str:
    def call(name: str) -> Any:
        return lambda match: f"{name}({match.group('column')})"

    expression = re.sub(
        rf"(?P<column>{_COLUMN_TOKEN_TEXT})\s+(?:is\s+)?not\s+null\b",
        call("notnull"),
        expression,
        flags=re.I,
    )
    expression = re.sub(
        rf"(?P<column>{_COLUMN_TOKEN_TEXT})\s+is\s+null\b",
        call("isnull"),
        expression,
        flags=re.I,
    )
    expression = re.sub(
        rf"(?P<column>{_COLUMN_TOKEN_TEXT})\s*!=\s*(?:null|None)\b",
        call("notnull"),
        expression,
        flags=re.I,
    )
    expression = re.sub(
        rf"(?P<column>{_COLUMN_TOKEN_TEXT})\s*(?:==|=)\s*(?:null|None)\b",
        call("isnull"),
        expression,
        flags=re.I,
    )
    return expression


class SafeExpressionEvaluator(ast.NodeVisitor):
    _binary = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }
    _comparison = {
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
        ast.In: lambda left, right: left.isin(right) if isinstance(left, pd.Series) else left in right,
        ast.NotIn: lambda left, right: ~left.isin(right) if isinstance(left, pd.Series) else left not in right,
    }

    def __init__(self, dataframe: pd.DataFrame, column_mapping: dict[str, str]) -> None:
        self.dataframe = dataframe
        self.column_mapping = column_mapping

    def evaluate(self, expression: str) -> Any:
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as exc:
            raise DslError(f"Invalid expression: {exc.msg}") from exc
        return self.visit(tree.body)

    def visit_Name(self, node: ast.Name) -> Any:
        if node.id in self.column_mapping:
            return self.dataframe[self.column_mapping[node.id]]
        if node.id in {"True", "False", "None"}:
            return {"True": True, "False": False, "None": None}[node.id]
        raise DslError(f"Unknown name: {node.id}")

    def visit_Constant(self, node: ast.Constant) -> Any:
        return node.value

    def visit_List(self, node: ast.List) -> list[Any]:
        return [self.visit(value) for value in node.elts]

    def visit_Tuple(self, node: ast.Tuple) -> tuple[Any, ...]:
        return tuple(self.visit(value) for value in node.elts)

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        function = self._binary.get(type(node.op))
        if function is None:
            raise DslError(f"Operator {type(node.op).__name__} is not allowed")
        return function(self.visit(node.left), self.visit(node.right))

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        value = self.visit(node.operand)
        if isinstance(node.op, ast.Not):
            return ~value if isinstance(value, pd.Series) else not value
        if isinstance(node.op, ast.Invert):
            return ~value
        if isinstance(node.op, ast.USub):
            return -value
        if isinstance(node.op, ast.UAdd):
            return +value
        raise DslError(f"Unary operator {type(node.op).__name__} is not allowed")

    def visit_BoolOp(self, node: ast.BoolOp) -> Any:
        values = [self.visit(value) for value in node.values]
        if not values:
            raise DslError("Boolean expression is empty")
        result = values[0]
        for value in values[1:]:
            if isinstance(node.op, ast.And):
                result = result & value
            elif isinstance(node.op, ast.Or):
                result = result | value
            else:
                raise DslError("Unsupported boolean operator")
        return result

    def visit_Compare(self, node: ast.Compare) -> Any:
        left = self.visit(node.left)
        result: Any = True
        for operation_node, comparator_node in zip(node.ops, node.comparators, strict=True):
            right = self.visit(comparator_node)
            function = self._comparison.get(type(operation_node))
            if function is None:
                raise DslError(f"Comparison {type(operation_node).__name__} is not allowed")
            current = function(left, right)
            result = current if result is True else result & current
            left = right
        return result

    def visit_Call(self, node: ast.Call) -> Any:
        if not isinstance(node.func, ast.Name):
            raise DslError("Only named helper functions are allowed")
        name = node.func.id
        args = [self.visit(arg) for arg in node.args]
        kwargs = {item.arg: self.visit(item.value) for item in node.keywords if item.arg}
        helpers = {
            "abs": lambda value: value.abs() if isinstance(value, pd.Series) else abs(value),
            "sqrt": np.sqrt,
            "log": np.log,
            "log10": np.log10,
            "round": lambda value, digits=0: value.round(digits) if hasattr(value, "round") else round(value, digits),
            "lower": lambda value: value.astype("string").str.lower(),
            "upper": lambda value: value.astype("string").str.upper(),
            "contains": lambda value, text, case=False: value.astype("string").str.contains(str(text), case=bool(case), na=False),
            "isnull": pd.isna,
            "notnull": pd.notna,
            "year": lambda value: pd.to_datetime(value, errors="coerce").dt.year,
            "month": lambda value: pd.to_datetime(value, errors="coerce").dt.month,
            "day": lambda value: pd.to_datetime(value, errors="coerce").dt.day,
            "clip": lambda value, low=None, high=None: value.clip(lower=low, upper=high),
        }
        helper = helpers.get(name)
        if helper is None:
            raise DslError(f"Function {name!r} is not allowed")
        try:
            return helper(*args, **kwargs)
        except Exception as exc:
            raise DslError(f"{name} failed: {exc}") from exc

    def generic_visit(self, node: ast.AST) -> Any:
        raise DslError(f"Syntax {type(node).__name__} is not allowed")


class LocalTransformEngine:
    """Apply a compact, replayable dataframe transformation language."""

    def apply(self, dataframe: pd.DataFrame, code: str) -> pd.DataFrame:
        result = dataframe.copy(deep=False)
        statements = self._statements(code)
        for statement in statements:
            result = self._apply_statement(result, statement)
        return result

    @staticmethod
    def _statements(code: str) -> list[str]:
        statements: list[str] = []
        for line in code.replace("|", "\n").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                statements.append(stripped)
        return statements

    def _evaluate(self, dataframe: pd.DataFrame, expression: str) -> Any:
        expression = _normalise_null_checks(expression)
        parsed = _replace_column_tokens(expression, dataframe.columns)
        return SafeExpressionEvaluator(dataframe, parsed.columns).evaluate(parsed.expression)

    def _column_list(self, dataframe: pd.DataFrame, text: str) -> list[str]:
        tokens = [item.strip() for item in text.split(",") if item.strip()]
        columns: list[str] = []
        for token in tokens:
            match = _COLUMN_TOKEN.fullmatch(token)
            if not match:
                raise DslError(f"Expected a column token, got {token!r}")
            column = match.group(1) or match.group(2)
            if column not in dataframe.columns:
                raise DslError(f"Unknown column: {column}")
            columns.append(column)
        return columns

    def _apply_statement(self, dataframe: pd.DataFrame, statement: str) -> pd.DataFrame:
        command, _, rest = statement.partition(" ")
        command = command.lower()
        rest = rest.strip()

        if command == "where":
            mask = self._evaluate(dataframe, rest)
            if not isinstance(mask, pd.Series) or not pd.api.types.is_bool_dtype(mask.dtype):
                raise DslError("where must produce a boolean series")
            return dataframe.loc[mask.fillna(False)].copy()

        if command == "keep":
            return dataframe.loc[:, self._column_list(dataframe, rest)].copy()

        if command == "drop":
            return dataframe.drop(columns=self._column_list(dataframe, rest)).copy()

        if command == "dedupe":
            columns = self._column_list(dataframe, rest) if rest else None
            return dataframe.drop_duplicates(subset=columns).copy()

        if command == "rename":
            match = re.fullmatch(r"(@\{[^}]+\}|@[A-Za-z_][A-Za-z0-9_]*)\s+as\s+(.+)", rest, flags=re.I)
            if not match:
                raise DslError("rename syntax: rename @old as New name")
            old = self._column_list(dataframe, match.group(1))[0]
            new = match.group(2).strip()
            if not new:
                raise DslError("New column name cannot be empty")
            if new in dataframe.columns and new != old:
                raise DslError(f"Column already exists: {new}")
            return dataframe.rename(columns={old: new}).copy()

        if command == "derive":
            name, separator, expression = rest.partition("=")
            if not separator or not name.strip() or not expression.strip():
                raise DslError("derive syntax: derive new_name = expression")
            name = name.strip()
            result = dataframe.copy()
            result[name] = self._evaluate(result, expression.strip())
            return result

        if command == "sort":
            match = re.fullmatch(r"(@\{[^}]+\}|@[A-Za-z_][A-Za-z0-9_]*)(?:\s+(asc|desc))?", rest, flags=re.I)
            if not match:
                raise DslError("sort syntax: sort @column [asc|desc]")
            column = self._column_list(dataframe, match.group(1))[0]
            ascending = (match.group(2) or "asc").lower() == "asc"
            return dataframe.sort_values(column, ascending=ascending, kind="mergesort").copy()

        if command in {"head", "tail", "sample"}:
            try:
                count = int(rest)
            except ValueError as exc:
                raise DslError(f"{command} requires an integer") from exc
            if count < 0:
                raise DslError("Row count cannot be negative")
            if command == "head":
                return dataframe.head(count).copy()
            if command == "tail":
                return dataframe.tail(count).copy()
            return dataframe.sample(n=min(count, len(dataframe)), random_state=0).copy()

        if command == "fill":
            match = re.fullmatch(r"(@\{[^}]+\}|@[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)", rest)
            if not match:
                raise DslError("fill syntax: fill @column = median|mean|mode|value")
            column = self._column_list(dataframe, match.group(1))[0]
            raw = match.group(2).strip()
            series = dataframe[column]
            if raw == "median":
                value = series.median()
            elif raw == "mean":
                value = series.mean()
            elif raw == "mode":
                mode = series.mode(dropna=True)
                value = mode.iloc[0] if not mode.empty else None
            else:
                try:
                    value = ast.literal_eval(raw)
                except (ValueError, SyntaxError):
                    value = raw.strip('"\'')
            result = dataframe.copy()
            result[column] = result[column].fillna(value)
            return result

        if command == "cast":
            match = re.fullmatch(r"(@\{[^}]+\}|@[A-Za-z_][A-Za-z0-9_]*)\s+as\s+(string|int|float|bool|datetime|category)", rest, flags=re.I)
            if not match:
                raise DslError("cast syntax: cast @column as string|int|float|bool|datetime|category")
            column = self._column_list(dataframe, match.group(1))[0]
            dtype = match.group(2).lower()
            result = dataframe.copy()
            if dtype == "datetime":
                result[column] = pd.to_datetime(result[column], errors="coerce")
            elif dtype == "int":
                result[column] = pd.to_numeric(result[column], errors="coerce").astype("Int64")
            elif dtype == "float":
                result[column] = pd.to_numeric(result[column], errors="coerce")
            elif dtype == "string":
                result[column] = result[column].astype("string")
            elif dtype == "bool":
                result[column] = result[column].astype("boolean")
            else:
                result[column] = result[column].astype("category")
            return result

        raise DslError(f"Unknown command: {command}")


CHEATSHEET = files("gim").joinpath("CHEATSHEET.md").read_text(encoding="utf-8")
