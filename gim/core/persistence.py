from __future__ import annotations

import json
import os
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path

import pandas as pd

from .models import WorkspaceManifest
from .workspace import Workspace

FORMAT_VERSION = 1
MANIFEST_NAME = "manifest.json"


class WorkspaceFormatError(ValueError):
    pass


def save_workspace(workspace: Workspace, path: str | Path) -> Path:
    target = Path(path).expanduser()
    if target.suffix.lower() != ".gim":
        target = target.with_suffix(".gim")
    target.parent.mkdir(parents=True, exist_ok=True)

    manifest = workspace.to_manifest().to_dict()
    manifest["format"] = "gim-workspace"
    manifest["version"] = FORMAT_VERSION

    file_descriptor, temporary_name = tempfile.mkstemp(prefix="gim_", suffix=".tmp", dir=target.parent)
    os.close(file_descriptor)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            archive.writestr(MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2))
            for source_id, record in workspace.sources.items():
                csv_bytes = record.dataframe.to_csv(index=False).encode("utf-8")
                archive.writestr(f"sources/{source_id}.csv", csv_bytes)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def load_workspace(path: str | Path) -> Workspace:
    source_path = Path(path).expanduser().resolve()
    if source_path.suffix.lower() != ".gim":
        raise WorkspaceFormatError("Workspace files must use the .gim extension")
    if not source_path.exists():
        raise FileNotFoundError(source_path)

    try:
        with zipfile.ZipFile(source_path, "r") as archive:
            names = set(archive.namelist())
            if MANIFEST_NAME not in names:
                raise WorkspaceFormatError("manifest.json is missing")
            raw_manifest = json.loads(archive.read(MANIFEST_NAME).decode("utf-8"))
            if raw_manifest.get("format") != "gim-workspace":
                raise WorkspaceFormatError("Not a GIM workspace")
            if int(raw_manifest.get("version", 0)) > FORMAT_VERSION:
                raise WorkspaceFormatError("This workspace was created by a newer GIM version")
            manifest = WorkspaceManifest.from_dict(raw_manifest)
            source_frames: dict[str, pd.DataFrame] = {}
            for node in manifest.nodes:
                if node.source_id and node.source_id not in source_frames:
                    member = f"sources/{node.source_id}.csv"
                    if member not in names:
                        raise WorkspaceFormatError(f"Missing source payload: {member}")
                    source_frames[node.source_id] = pd.read_csv(BytesIO(archive.read(member)), low_memory=False)
    except zipfile.BadZipFile as exc:
        raise WorkspaceFormatError("The .gim file is damaged or is not a ZIP-based workspace") from exc
    except json.JSONDecodeError as exc:
        raise WorkspaceFormatError("The workspace manifest is invalid JSON") from exc

    return Workspace.from_manifest(manifest, source_frames)
