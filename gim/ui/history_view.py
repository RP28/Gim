from __future__ import annotations

from collections import defaultdict

from PySide6.QtCore import QEasingCurve, Property, QPropertyAnimation, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QWheelEvent
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsView,
    QStyleOptionGraphicsItem,
    QWidget,
)

from gim.config.theme import NODE_HEIGHT, NODE_WIDTH, NODE_X_GAP, NODE_Y_GAP, PALETTE
from gim.core.models import ArtifactKind, HistoryNode, NodeKind
from gim.core.workspace import Workspace


class HistoryNodeItem(QGraphicsObject):
    clicked = Signal(str, bool)

    def __init__(self, node: HistoryNode, artifact_counts: dict[ArtifactKind, int]) -> None:
        super().__init__()
        self.node = node
        self.artifact_counts = artifact_counts
        self._selected = False
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"{node.alias}\n{node.label}")

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, NODE_WIDTH, NODE_HEIGHT)

    def set_selected(self, selected: bool) -> None:
        if self._selected != selected:
            self._selected = selected
            self.update()

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        del option, widget
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = {
            NodeKind.SOURCE: PALETTE.success,
            NodeKind.TRANSFORM: PALETTE.accent,
            NodeKind.DUPLICATE: PALETTE.warning,
            NodeKind.MERGE: "#A57DE8",
        }[self.node.kind]
        border = QColor(color)
        if self._selected:
            border = QColor(PALETTE.text)
        painter.setPen(QPen(border, 2.4 if self._selected else 1.6))
        painter.setBrush(QBrush(QColor(PALETTE.surface_alt)))
        painter.drawRoundedRect(self.boundingRect(), 12, 12)

        painter.setPen(QPen(QColor(color), 4))
        painter.drawLine(12, 12, 12, NODE_HEIGHT - 12)

        painter.setPen(QColor(PALETTE.text))
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(10)
        painter.setFont(title_font)
        alias = self.node.alias if len(self.node.alias) <= 22 else self.node.alias[:19] + "…"
        painter.drawText(QRectF(24, 8, NODE_WIDTH - 34, 22), Qt.AlignmentFlag.AlignVCenter, alias)

        painter.setPen(QColor(PALETTE.muted))
        detail_font = QFont()
        detail_font.setPointSize(8)
        painter.setFont(detail_font)
        label = self.node.label if len(self.node.label) <= 31 else self.node.label[:28] + "…"
        painter.drawText(QRectF(24, 31, NODE_WIDTH - 36, 20), Qt.AlignmentFlag.AlignVCenter, label)

        badges: list[str] = []
        if self.artifact_counts.get(ArtifactKind.PLOT):
            badges.append(f"P{self.artifact_counts[ArtifactKind.PLOT]}")
        stat_count = self.artifact_counts.get(ArtifactKind.STAT, 0) + self.artifact_counts.get(ArtifactKind.CORRELATION, 0)
        if stat_count:
            badges.append(f"S{stat_count}")
        if badges:
            text = " · ".join(badges)
            painter.setPen(QColor(PALETTE.warning))
            painter.drawText(QRectF(NODE_WIDTH - 68, 40, 58, 16), Qt.AlignmentFlag.AlignRight, text)

    def mousePressEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        self.clicked.emit(self.node.id, shift)
        event.accept()


class HistoryGraphView(QGraphicsView):
    nodeSelected = Signal(str)
    mergePairSelected = Signal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setBackgroundBrush(QColor(PALETTE.background))
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self._items: dict[str, HistoryNodeItem] = {}
        self._selected: list[str] = []
        self._animations: list[QPropertyAnimation] = []
        self._workspace: Workspace | None = None

    def set_workspace(self, workspace: Workspace, animate_node_id: str | None = None) -> None:
        self._workspace = workspace
        self._scene.clear()
        self._items.clear()
        self._animations.clear()
        if not workspace.nodes:
            self._scene.setSceneRect(0, 0, 320, 500)
            return

        max_sequence = max(node.sequence for node in workspace.nodes.values())
        counts: dict[str, dict[ArtifactKind, int]] = defaultdict(lambda: defaultdict(int))
        for artifact in workspace.artifacts.values():
            counts[artifact.node_id][artifact.kind] += 1

        positions: dict[str, tuple[float, float]] = {}
        for node in sorted(workspace.nodes.values(), key=lambda item: item.sequence):
            x = 36 + node.branch_rank * NODE_X_GAP
            y = 38 + (max_sequence - node.sequence) * NODE_Y_GAP
            positions[node.id] = (x, y)

        for node in workspace.nodes.values():
            child_x, child_y = positions[node.id]
            for parent_id in node.parents:
                parent_x, parent_y = positions[parent_id]
                path = QPainterPath()
                start_x = parent_x + NODE_WIDTH / 2
                start_y = parent_y
                end_x = child_x + NODE_WIDTH / 2
                end_y = child_y + NODE_HEIGHT
                path.moveTo(start_x, start_y)
                vertical_distance = abs(end_y - start_y)
                control = max(44.0, vertical_distance * 0.46)
                path.cubicTo(start_x, start_y - control, end_x, end_y + control, end_x, end_y)
                edge = QGraphicsPathItem(path)
                edge.setPen(QPen(QColor("#46505D"), 2.0))
                edge.setZValue(-1)
                self._scene.addItem(edge)

        for node in workspace.nodes.values():
            item = HistoryNodeItem(node, counts[node.id])
            item.clicked.connect(self._on_item_clicked)
            x, y = positions[node.id]
            item.setPos(x, y)
            self._scene.addItem(item)
            self._items[node.id] = item
            if node.id == animate_node_id:
                item.setOpacity(0.0)
                animation = QPropertyAnimation(item, b"opacity", self)
                animation.setDuration(260)
                animation.setStartValue(0.0)
                animation.setEndValue(1.0)
                animation.setEasingCurve(QEasingCurve.Type.OutCubic)
                animation.start()
                self._animations.append(animation)

        width = (max(node.branch_rank for node in workspace.nodes.values()) + 1) * NODE_X_GAP + 80
        height = (max_sequence + 1) * NODE_Y_GAP + 120
        self._scene.setSceneRect(0, 0, max(width, 320), max(height, 500))
        if workspace.selected_node_id:
            self.select_node(workspace.selected_node_id, emit=False)
        self.ensureVisible(self._scene.itemsBoundingRect(), 24, 24)

    def select_node(self, node_id: str, *, emit: bool = True, additive: bool = False) -> None:
        if node_id not in self._items:
            return
        if additive:
            if node_id in self._selected:
                self._selected.remove(node_id)
            else:
                self._selected.append(node_id)
            self._selected = self._selected[-2:]
        else:
            self._selected = [node_id]
        for current_id, item in self._items.items():
            item.set_selected(current_id in self._selected)
        self.centerOn(self._items[node_id])
        if emit:
            self.nodeSelected.emit(node_id)
        if additive and len(self._selected) == 2:
            self.mergePairSelected.emit(self._selected[0], self._selected[1])

    def selected_node_ids(self) -> list[str]:
        return list(self._selected)

    def _on_item_clicked(self, node_id: str, shift: bool) -> None:
        self.select_node(node_id, emit=True, additive=shift)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.16 if event.angleDelta().y() > 0 else 1 / 1.16
            self.scale(factor, factor)
            event.accept()
            return
        super().wheelEvent(event)
