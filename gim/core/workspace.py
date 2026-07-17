from __future__ import annotations

from collections import OrderedDict, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import pandas as pd

from .models import ArtifactKind, HistoryNode, NodeKind, OperationSpec, SavedArtifact, WorkspaceManifest
from .operations import get_operation


@dataclass(slots=True)
class SourceRecord:
    id: str
    alias: str
    dataframe: pd.DataFrame
    source_path: str | None = None
    read_options: dict[str, Any] | None = None


class Workspace:
    def __init__(self, name: str = "Untitled workspace", cache_size: int = 8) -> None:
        self.name = name
        self.cache_size = max(2, int(cache_size))
        self.nodes: dict[str, HistoryNode] = {}
        self.children: dict[str, list[str]] = defaultdict(list)
        self.sources: dict[str, SourceRecord] = {}
        self.artifacts: dict[str, SavedArtifact] = {}
        self.selected_node_id: str | None = None
        self._cache: OrderedDict[str, pd.DataFrame] = OrderedDict()
        self._next_sequence = 0
        self._next_branch_rank = 0

    def add_source(
        self,
        dataframe: pd.DataFrame,
        alias: str,
        *,
        source_path: str | None = None,
        read_options: dict[str, Any] | None = None,
        source_id: str | None = None,
        node_id: str | None = None,
    ) -> HistoryNode:
        if not isinstance(dataframe, pd.DataFrame):
            raise TypeError("Source must be a pandas DataFrame")
        cleaned_alias = alias.strip() or f"data_{len(self.sources) + 1}"
        source_id = source_id or self._new_id()
        node = HistoryNode.create(
            kind=NodeKind.SOURCE,
            label=f"File uploaded · {cleaned_alias}",
            alias=cleaned_alias,
            parents=(),
            branch_rank=self._next_branch_rank,
            sequence=self._consume_sequence(),
            operation=OperationSpec("source", {}),
            source_id=source_id,
        )
        if node_id:
            node.id = node_id
        self._next_branch_rank += 1
        self.sources[source_id] = SourceRecord(
            id=source_id,
            alias=cleaned_alias,
            dataframe=dataframe.copy(deep=True),
            source_path=source_path,
            read_options=read_options,
        )
        self._register_node(node)
        self._remember(node.id, self.sources[source_id].dataframe)
        self.selected_node_id = node.id
        return node

    @staticmethod
    def _new_id() -> str:
        from uuid import uuid4

        return uuid4().hex

    def _consume_sequence(self) -> int:
        value = self._next_sequence
        self._next_sequence += 1
        return value

    def _register_node(self, node: HistoryNode) -> None:
        if node.id in self.nodes:
            raise ValueError(f"Duplicate node id: {node.id}")
        for parent in node.parents:
            if parent not in self.nodes:
                raise KeyError(f"Unknown parent node: {parent}")
        self.nodes[node.id] = node
        for parent in node.parents:
            self.children[parent].append(node.id)

    def apply_transform(self, parent_id: str, code: str, label: str | None = None) -> HistoryNode:
        parent = self.require_node(parent_id)
        if not code.strip():
            raise ValueError("Transformation code cannot be empty")
        # Validate before adding the history node.
        result = get_operation("dsl").function((self.materialize(parent_id),), {"code": code})
        node = HistoryNode.create(
            kind=NodeKind.TRANSFORM,
            label=label or self._summarise_code(code),
            alias=parent.alias,
            parents=(parent_id,),
            branch_rank=parent.branch_rank,
            sequence=self._consume_sequence(),
            operation=OperationSpec("dsl", {"code": code}),
        )
        self._register_node(node)
        self._remember(node.id, result)
        self.selected_node_id = node.id
        return node

    def duplicate(self, parent_id: str, alias: str | None = None) -> HistoryNode:
        parent = self.require_node(parent_id)
        branch_rank = self._next_branch_rank
        self._next_branch_rank += 1
        node = HistoryNode.create(
            kind=NodeKind.DUPLICATE,
            label="Duplicate copy",
            alias=(alias or f"{parent.alias} copy").strip(),
            parents=(parent_id,),
            branch_rank=branch_rank,
            sequence=self._consume_sequence(),
            operation=OperationSpec("identity", {}),
        )
        self._register_node(node)
        self._remember(node.id, self.materialize(parent_id).copy(deep=False))
        self.selected_node_id = node.id
        return node

    def merge(
        self,
        left_id: str,
        right_id: str,
        *,
        how: str,
        left_on: str,
        right_on: str,
        alias: str | None = None,
    ) -> HistoryNode:
        if left_id == right_id:
            raise ValueError("Select two different nodes to merge")
        left_node = self.require_node(left_id)
        right_node = self.require_node(right_id)
        params = {"how": how, "left_on": left_on, "right_on": right_on, "suffixes": ["_left", "_right"]}
        result = get_operation("merge").function(
            (self.materialize(left_id), self.materialize(right_id)),
            params,
        )
        node = HistoryNode.create(
            kind=NodeKind.MERGE,
            label=f"{how.title()} join · {left_on} ↔ {right_on}",
            alias=(alias or f"{left_node.alias} + {right_node.alias}").strip(),
            parents=(left_id, right_id),
            branch_rank=self._next_branch_rank,
            sequence=self._consume_sequence(),
            operation=OperationSpec("merge", params),
        )
        self._next_branch_rank += 1
        self._register_node(node)
        self._remember(node.id, result)
        self.selected_node_id = node.id
        return node

    def materialize(self, node_id: str) -> pd.DataFrame:
        self.require_node(node_id)
        if node_id in self._cache:
            frame = self._cache.pop(node_id)
            self._cache[node_id] = frame
            return frame
        node = self.nodes[node_id]
        if node.kind == NodeKind.SOURCE:
            if not node.source_id or node.source_id not in self.sources:
                raise KeyError(f"Missing source payload for node {node_id}")
            frame = self.sources[node.source_id].dataframe
        else:
            parents = tuple(self.materialize(parent_id) for parent_id in node.parents)
            frame = get_operation(node.operation.name).function(parents, node.operation.params)
        self._remember(node_id, frame)
        return frame

    def _remember(self, node_id: str, dataframe: pd.DataFrame) -> None:
        self._cache.pop(node_id, None)
        self._cache[node_id] = dataframe
        while len(self._cache) > self.cache_size:
            key, evicted = self._cache.popitem(last=False)
            if key == self.selected_node_id and self._cache:
                # Keep the active frame hot when possible, then evict the next oldest.
                self._cache[key] = evicted
                self._cache.popitem(last=False)

    def clear_cache(self) -> None:
        self._cache.clear()

    def require_node(self, node_id: str) -> HistoryNode:
        try:
            return self.nodes[node_id]
        except KeyError as exc:
            raise KeyError(f"Unknown node: {node_id}") from exc

    def add_artifact(
        self,
        *,
        kind: ArtifactKind,
        node_id: str,
        title: str,
        config: dict[str, Any],
        local_code: str = "",
        result: dict[str, Any] | None = None,
    ) -> SavedArtifact:
        self.require_node(node_id)
        artifact = SavedArtifact.create(
            kind=kind,
            node_id=node_id,
            title=title.strip() or kind.value.title(),
            config=config,
            local_code=local_code,
            result=result,
        )
        self.artifacts[artifact.id] = artifact
        return artifact

    def artifacts_for_node(self, node_id: str) -> list[SavedArtifact]:
        return sorted(
            (artifact for artifact in self.artifacts.values() if artifact.node_id == node_id),
            key=lambda item: item.created_at,
        )

    def latest_nodes_by_branch(self) -> dict[int, HistoryNode]:
        latest: dict[int, HistoryNode] = {}
        for node in self.nodes.values():
            current = latest.get(node.branch_rank)
            if current is None or node.sequence > current.sequence:
                latest[node.branch_rank] = node
        return latest

    @staticmethod
    def _summarise_code(code: str) -> str:
        first = next((line.strip() for line in code.splitlines() if line.strip() and not line.strip().startswith("#")), "Transform")
        return first if len(first) <= 42 else first[:39] + "…"

    def to_manifest(self) -> WorkspaceManifest:
        return WorkspaceManifest(
            name=self.name,
            nodes=sorted(self.nodes.values(), key=lambda item: item.sequence),
            artifacts=sorted(self.artifacts.values(), key=lambda item: item.created_at),
            selected_node_id=self.selected_node_id,
        )

    @classmethod
    def from_manifest(
        cls,
        manifest: WorkspaceManifest,
        source_frames: dict[str, pd.DataFrame],
    ) -> "Workspace":
        workspace = cls(name=manifest.name)
        for node in sorted(manifest.nodes, key=lambda item: item.sequence):
            if node.kind == NodeKind.SOURCE:
                if not node.source_id or node.source_id not in source_frames:
                    raise ValueError(f"Workspace is missing source data for {node.alias}")
                workspace.sources[node.source_id] = SourceRecord(
                    id=node.source_id,
                    alias=node.alias,
                    dataframe=source_frames[node.source_id],
                )
            workspace._register_node(node)
        workspace.artifacts = {item.id: item for item in manifest.artifacts}
        workspace.selected_node_id = manifest.selected_node_id if manifest.selected_node_id in workspace.nodes else None
        workspace._next_sequence = max((node.sequence for node in workspace.nodes.values()), default=-1) + 1
        workspace._next_branch_rank = max((node.branch_rank for node in workspace.nodes.values()), default=-1) + 1
        return workspace
