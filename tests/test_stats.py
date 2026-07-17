from __future__ import annotations

import pandas as pd
import pytest

from gim.core.stats import StatisticalTestError, run_statistical_test


@pytest.fixture
def frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "value": [1, 2, 3, 7, 8, 9],
            "other": [2, 4, 6, 14, 16, 18],
            "group": ["A", "A", "A", "B", "B", "B"],
            "category": ["X", "X", "Y", "Y", "Y", "X"],
        }
    )


@pytest.mark.parametrize("name", ["Mann–Whitney U", "Independent t-test", "Welch t-test"])
def test_two_group_tests(frame, name) -> None:
    result = run_statistical_test(frame, name, "value", "group")
    assert 0 <= result.p_value <= 1


def test_anova(frame) -> None:
    result = run_statistical_test(frame, "ANOVA F", "value", "group")
    assert result.statistic > 0


def test_correlations(frame) -> None:
    assert run_statistical_test(frame, "Pearson", "value", "other").statistic > 0.99
    assert run_statistical_test(frame, "Spearman", "value", "other").statistic > 0.99


def test_chi_square(frame) -> None:
    result = run_statistical_test(frame, "Chi-square", "group", "category")
    assert result.details["degrees_of_freedom"] >= 1


def test_u_test_requires_two_groups(frame) -> None:
    data = frame.assign(group="A")
    with pytest.raises(StatisticalTestError, match="exactly two"):
        run_statistical_test(data, "U test", "value", "group")
