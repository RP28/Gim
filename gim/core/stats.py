from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats


class StatisticalTestError(ValueError):
    pass


@dataclass(slots=True)
class StatisticalResult:
    test: str
    statistic: float
    p_value: float
    interpretation: str
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _numeric(dataframe: pd.DataFrame, column: str) -> pd.Series:
    if column not in dataframe.columns:
        raise StatisticalTestError(f"Unknown column: {column}")
    values = pd.to_numeric(dataframe[column], errors="coerce").dropna()
    if values.empty:
        raise StatisticalTestError(f"{column} has no numeric values")
    return values


def _interpret(p_value: float, alpha: float) -> str:
    if np.isnan(p_value):
        return "The p-value is undefined for this input."
    if p_value < alpha:
        return f"p < {alpha:g}: evidence against the null hypothesis at the chosen significance level."
    return f"p ≥ {alpha:g}: insufficient evidence to reject the null hypothesis at the chosen significance level."


def run_statistical_test(
    dataframe: pd.DataFrame,
    test: str,
    column_a: str,
    column_b: str | None = None,
    *,
    group_column: str | None = None,
    alpha: float = 0.05,
) -> StatisticalResult:
    if not 0 < alpha < 1:
        raise StatisticalTestError("alpha must be between 0 and 1")
    test_key = test.strip().lower().replace("–", "-").replace("—", "-")

    if test_key in {"pearson", "spearman"}:
        if not column_b:
            raise StatisticalTestError("Two numeric columns are required")
        pair = dataframe[[column_a, column_b]].apply(pd.to_numeric, errors="coerce").dropna()
        if len(pair) < 2:
            raise StatisticalTestError("At least two paired observations are required")
        function = stats.pearsonr if test_key == "pearson" else stats.spearmanr
        statistic, p_value = function(pair[column_a], pair[column_b])
        return StatisticalResult(
            test=f"{test_key.title()} correlation",
            statistic=float(statistic),
            p_value=float(p_value),
            interpretation=_interpret(float(p_value), alpha),
            details={"n": len(pair), "column_a": column_a, "column_b": column_b, "alpha": alpha},
        )

    if test_key in {"mann-whitney u", "mann whitney u", "u test", "independent t-test", "welch t-test"}:
        if not column_b:
            raise StatisticalTestError("Select a grouping column")
        if column_a not in dataframe.columns or column_b not in dataframe.columns:
            raise StatisticalTestError("Selected columns do not exist")
        clean = dataframe[[column_a, column_b]].dropna()
        groups = list(clean.groupby(column_b, observed=True))
        if len(groups) != 2:
            raise StatisticalTestError("This test requires exactly two groups")
        first = pd.to_numeric(groups[0][1][column_a], errors="coerce").dropna()
        second = pd.to_numeric(groups[1][1][column_a], errors="coerce").dropna()
        if first.empty or second.empty:
            raise StatisticalTestError("Both groups need numeric observations")
        if test_key in {"mann-whitney u", "mann whitney u", "u test"}:
            statistic, p_value = stats.mannwhitneyu(first, second, alternative="two-sided")
            name = "Mann–Whitney U"
        else:
            statistic, p_value = stats.ttest_ind(first, second, equal_var=test_key == "independent t-test", nan_policy="omit")
            name = "Independent t-test" if test_key == "independent t-test" else "Welch t-test"
        return StatisticalResult(
            test=name,
            statistic=float(statistic),
            p_value=float(p_value),
            interpretation=_interpret(float(p_value), alpha),
            details={
                "value_column": column_a,
                "group_column": column_b,
                "groups": [str(groups[0][0]), str(groups[1][0])],
                "sizes": [len(first), len(second)],
                "alpha": alpha,
            },
        )

    if test_key in {"anova f", "f test", "anova"}:
        grouping = group_column or column_b
        if not grouping:
            raise StatisticalTestError("Select a grouping column")
        clean = dataframe[[column_a, grouping]].dropna()
        groups = [pd.to_numeric(group[column_a], errors="coerce").dropna() for _, group in clean.groupby(grouping, observed=True)]
        groups = [group for group in groups if not group.empty]
        if len(groups) < 2:
            raise StatisticalTestError("ANOVA requires at least two non-empty groups")
        statistic, p_value = stats.f_oneway(*groups)
        return StatisticalResult(
            test="One-way ANOVA F-test",
            statistic=float(statistic),
            p_value=float(p_value),
            interpretation=_interpret(float(p_value), alpha),
            details={"value_column": column_a, "group_column": grouping, "group_sizes": [len(group) for group in groups], "alpha": alpha},
        )

    if test_key in {"chi-square", "chi square", "chi2"}:
        if not column_b:
            raise StatisticalTestError("Two categorical columns are required")
        contingency = pd.crosstab(dataframe[column_a], dataframe[column_b], dropna=False)
        if contingency.empty or min(contingency.shape) < 2:
            raise StatisticalTestError("Chi-square requires at least a 2×2 contingency table")
        statistic, p_value, degrees, expected = stats.chi2_contingency(contingency)
        return StatisticalResult(
            test="Chi-square independence test",
            statistic=float(statistic),
            p_value=float(p_value),
            interpretation=_interpret(float(p_value), alpha),
            details={
                "column_a": column_a,
                "column_b": column_b,
                "degrees_of_freedom": int(degrees),
                "minimum_expected": float(np.min(expected)),
                "alpha": alpha,
            },
        )

    raise StatisticalTestError(f"Unknown statistical test: {test}")


TEST_NAMES = (
    "Mann–Whitney U",
    "Independent t-test",
    "Welch t-test",
    "ANOVA F",
    "Pearson",
    "Spearman",
    "Chi-square",
)
