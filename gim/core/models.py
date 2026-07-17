from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4


class NodeKind(StrEnum):
    SOURCE = "source"
    TRANSFORM = "transform"
    DUPLICATE = "duplicate"
    MERGE = "merge"


class ArtifactKind(StrEnum):
    PLOT = "plot"
    STAT = "stat"
    CORRELATION = "correlation"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class OperationSpec:
    name: str
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "params": self.params}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "OperationSpec":
        return cls(name=value["name"], params=dict(value.get("params", {})))


@dataclass(slots=True)
class HistoryNode:
    id: str
    kind: NodeKind
    label: str
    alias: str
    parents: tuple[str, ...]
    branch_rank: int
    sequence: int
    operation: OperationSpec
    source_id: str | None = None
    created_at: str = field(default_factory=utc_now)

    @classmethod
    def create(
        cls,
        *,
        kind: NodeKind,
        label: str,
        alias: str,
        parents: tuple[str, ...],
        branch_rank: int,
        sequence: int,
        operation: OperationSpec,
        source_id: str | None = None,
    ) -> "HistoryNode":
        return cls(
            id=uuid4().hex,
            kind=kind,
            label=label,
            alias=alias,
            parents=parents,
            branch_rank=branch_rank,
            sequence=sequence,
            operation=operation,
            source_id=source_id,
        )

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["kind"] = self.kind.value
        result["parents"] = list(self.parents)
        result["operation"] = self.operation.to_dict()
        return result

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "HistoryNode":
        return cls(
            id=value["id"],
            kind=NodeKind(value["kind"]),
            label=value["label"],
            alias=value.get("alias", value["label"]),
            parents=tuple(value.get("parents", ())),
            branch_rank=int(value.get("branch_rank", 0)),
            sequence=int(value.get("sequence", 0)),
            operation=OperationSpec.from_dict(value["operation"]),
            source_id=value.get("source_id"),
            created_at=value.get("created_at", utc_now()),
        )


@dataclass(slots=True)
class SavedArtifact:
    id: str
    kind: ArtifactKind
    node_id: str
    title: str
    config: dict[str, Any]
    local_code: str = ""
    result: dict[str, Any] | None = None
    created_at: str = field(default_factory=utc_now)

    @classmethod
    def create(
        cls,
        *,
        kind: ArtifactKind,
        node_id: str,
        title: str,
        config: dict[str, Any],
        local_code: str = "",
        result: dict[str, Any] | None = None,
    ) -> "SavedArtifact":
        return cls(
            id=uuid4().hex,
            kind=kind,
            node_id=node_id,
            title=title,
            config=config,
            local_code=local_code,
            result=result,
        )

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["kind"] = self.kind.value
        return result

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SavedArtifact":
        return cls(
            id=value["id"],
            kind=ArtifactKind(value["kind"]),
            node_id=value["node_id"],
            title=value["title"],
            config=dict(value.get("config", {})),
            local_code=value.get("local_code", ""),
            result=value.get("result"),
            created_at=value.get("created_at", utc_now()),
        )


@dataclass(slots=True)
class WorkspaceManifest:
    version: int = 1
    name: str = "Untitled workspace"
    nodes: list[HistoryNode] = field(default_factory=list)
    artifacts: list[SavedArtifact] = field(default_factory=list)
    selected_node_id: str | None = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "name": self.name,
            "nodes": [node.to_dict() for node in self.nodes],
            "artifacts": [item.to_dict() for item in self.artifacts],
            "selected_node_id": self.selected_node_id,
            "created_at": self.created_at,
            "updated_at": utc_now(),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "WorkspaceManifest":
        return cls(
            version=int(value.get("version", 1)),
            name=value.get("name", "Untitled workspace"),
            nodes=[HistoryNode.from_dict(item) for item in value.get("nodes", [])],
            artifacts=[SavedArtifact.from_dict(item) for item in value.get("artifacts", [])],
            selected_node_id=value.get("selected_node_id"),
            created_at=value.get("created_at", utc_now()),
            updated_at=value.get("updated_at", utc_now()),
        )
