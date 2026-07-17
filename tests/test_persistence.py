from __future__ import annotations

import json
import zipfile

import pandas as pd
import pytest

from gim.core.models import ArtifactKind
from gim.core.persistence import WorkspaceFormatError, load_workspace, save_workspace
from gim.core.workspace import Workspace


def test_round_trip_replays_operations_and_artifacts(tmp_path) -> None:
    workspace = Workspace("demo")
    first = workspace.add_source(pd.DataFrame({"id": [1, 2], "x": [10, 20]}), "first")
    second = workspace.add_source(pd.DataFrame({"id": [1, 2], "y": [3, 4]}), "second")
    derived = workspace.apply_transform(first.id, "derive doubled = @x * 2")
    merged = workspace.merge(derived.id, second.id, how="inner", left_on="id", right_on="id")
    workspace.add_artifact(kind=ArtifactKind.PLOT, node_id=merged.id, title="Saved", config={"family": "Scatter"})

    path = save_workspace(workspace, tmp_path / "analysis")
    loaded = load_workspace(path)

    pd.testing.assert_frame_equal(loaded.materialize(merged.id), workspace.materialize(merged.id))
    assert len(loaded.artifacts) == 1
    assert path.suffix == ".gim"


def test_archive_contains_only_manifest_and_original_sources(tmp_path) -> None:
    workspace = Workspace()
    source = workspace.add_source(pd.DataFrame({"x": [1, 2]}), "source")
    workspace.apply_transform(source.id, "derive y = @x * 2")
    path = save_workspace(workspace, tmp_path / "only-originals.gim")

    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        assert names.count("manifest.json") == 1
        assert len([name for name in names if name.startswith("sources/")]) == 1
        assert not any("derived" in name for name in names)
        manifest = json.loads(archive.read("manifest.json"))
        assert len(manifest["nodes"]) == 2


def test_invalid_extension_rejected(tmp_path) -> None:
    path = tmp_path / "bad.txt"
    path.write_text("not a workspace")
    with pytest.raises(WorkspaceFormatError, match=".gim"):
        load_workspace(path)


def test_damaged_zip_rejected(tmp_path) -> None:
    path = tmp_path / "bad.gim"
    path.write_bytes(b"not a zip")
    with pytest.raises(WorkspaceFormatError, match="damaged"):
        load_workspace(path)
