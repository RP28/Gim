from __future__ import annotations

import pandas as pd
import pytest

from gim.core.models import ArtifactKind, NodeKind
from gim.core.workspace import Workspace


def test_branching_merge_and_latest_nodes() -> None:
    workspace = Workspace(cache_size=3)
    left = workspace.add_source(pd.DataFrame({"id": [1, 2, 2], "value": [10, 20, 30]}), "orders")
    cleaned = workspace.apply_transform(left.id, "dedupe @id")
    copied = workspace.duplicate(cleaned.id, "scenario")
    right = workspace.add_source(pd.DataFrame({"key": [1, 2], "region": ["NSW", "VIC"]}), "regions")
    merged = workspace.merge(cleaned.id, right.id, how="inner", left_on="id", right_on="key")

    assert copied.kind == NodeKind.DUPLICATE
    assert copied.branch_rank != cleaned.branch_rank
    assert merged.parents == (cleaned.id, right.id)
    assert list(workspace.materialize(merged.id)["region"]) == ["NSW", "VIC"]
    assert workspace.latest_nodes_by_branch()[copied.branch_rank].id == copied.id


def test_transform_is_validated_before_history_mutation() -> None:
    workspace = Workspace()
    source = workspace.add_source(pd.DataFrame({"x": [1]}), "source")
    before = len(workspace.nodes)
    with pytest.raises(Exception):
        workspace.apply_transform(source.id, "drop @missing")
    assert len(workspace.nodes) == before


def test_merge_rejects_same_node() -> None:
    workspace = Workspace()
    source = workspace.add_source(pd.DataFrame({"id": [1]}), "source")
    with pytest.raises(ValueError, match="different"):
        workspace.merge(source.id, source.id, how="inner", left_on="id", right_on="id")


def test_artifacts_attach_to_exact_node() -> None:
    workspace = Workspace()
    source = workspace.add_source(pd.DataFrame({"x": [1, 2]}), "source")
    artifact = workspace.add_artifact(
        kind=ArtifactKind.PLOT,
        node_id=source.id,
        title="Histogram",
        config={"family": "Distribution"},
        local_code="where @x > 1",
    )
    assert workspace.artifacts_for_node(source.id) == [artifact]


def test_cache_is_bounded() -> None:
    workspace = Workspace(cache_size=2)
    node = workspace.add_source(pd.DataFrame({"x": range(20)}), "source")
    for index in range(5):
        node = workspace.apply_transform(node.id, f"head {20 - index}")
    assert len(workspace._cache) <= 2
