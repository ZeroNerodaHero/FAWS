"""Qt side of the layout: SlotFrame (one rectangle) and GridContainer (the grid).

GridContainer maps grid units to pixels, places every SlotFrame, turns mouse
drags in the gutters into LayoutModel.sweep calls, and runs the ghost drag
used to move/add modules. It does not decide what a drop means; Workspace does.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QPushButton,
                               QToolButton, QVBoxLayout, QWidget)

from .layout import GRID, Edge, LayoutModel, Slot

GAP = 6            # px between slots; this is where edge handles live
SNAP_PX = 8        # snap when within this many pixels of a target
HANDLE_HIT_PX = GAP
DROP_EDGE_BAND = 0.25   # fraction of a slot that counts as its edge for drops
HOLD_MS = 250           # press-and-hold this long on a title bar to lift the slot
GHOST_WIDTH = 240

ACCENT = QColor("#cdb27b")


class GhostDrag:
    """Mouse-driven drag of a module payload. Widgets that start one keep
    feeding it global positions until release; the grid draws the ghost."""

    def __init__(self, grid: GridContainer, payload: str, pixmap: QPixmap, hotspot: QPoint):
        self.grid = grid
        self.payload = payload
        self.pixmap = pixmap
        self.hotspot = hotspot
        QApplication.setOverrideCursor(Qt.CursorShape.ClosedHandCursor)

    def move(self, global_pos: QPoint) -> None:
        self.grid._ghost_move(self, global_pos)

    def finish(self, global_pos: QPoint) -> None:
        QApplication.restoreOverrideCursor()
        self.grid._ghost_finish(self, global_pos)

    def cancel(self) -> None:
        QApplication.restoreOverrideCursor()
        self.grid._ghost_clear()


class DragOverlay(QWidget):
    """Transparent layer above every slot. Draws drop zones and the ghost."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.zone: QRect | None = None
        self.ghost: QPixmap | None = None
        self.ghost_pos = QPoint()
        self.hide()

    def set_state(self, zone: QRect | None, ghost: QPixmap | None, ghost_pos: QPoint) -> None:
        self.zone, self.ghost, self.ghost_pos = zone, ghost, ghost_pos
        self.setVisible(zone is not None or ghost is not None)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        if self.zone is not None:
            painter.fillRect(self.zone, QColor(205, 178, 123, 70))
            painter.setPen(QPen(ACCENT, 2))
            painter.drawRect(self.zone.adjusted(1, 1, -1, -1))
        if self.ghost is not None:
            painter.setOpacity(0.8)
            painter.drawPixmap(self.ghost_pos, self.ghost)
            painter.setOpacity(1.0)
            painter.setPen(QPen(ACCENT, 1))
            painter.drawRect(QRect(self.ghost_pos, self.ghost.size()).adjusted(0, 0, -1, -1))
        painter.end()


TITLE_H = 24
TITLE_H_WITH_HEADER = 30


class SlotTitleBar(QWidget):
    """Title on the left, dropdown and close on the right. Hold or drag it to move the slot.
    A module may put its own controls (header widget) in the middle."""

    def __init__(self, frame: SlotFrame):
        super().__init__(frame)
        self.frame = frame
        self.setObjectName("slotTitleBar")
        self.setFixedHeight(TITLE_H)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        row = QHBoxLayout(self)
        self._row = row
        row.setContentsMargins(8, 0, 4, 0)
        row.setSpacing(2)
        self.label = QLabel(self)
        self.label.setObjectName("slotTitleText")
        # rich-text labels grab mouse presses for link handling; we want them
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        row.addWidget(self.label, 1)
        self.header: QWidget | None = None
        self.menu_btn = QToolButton(self)
        self.menu_btn.setObjectName("slotBtn")
        self.menu_btn.setText("▾")
        self.menu_btn.setToolTip("slot menu")
        self.menu_btn.setCursor(Qt.CursorShape.ArrowCursor)
        self.menu_btn.clicked.connect(
            lambda: frame.menuRequested.emit(frame, self.menu_btn.mapToGlobal(QPoint(0, self.menu_btn.height())))
        )
        row.addWidget(self.menu_btn)
        self.close_btn = QToolButton(self)
        self.close_btn.setObjectName("slotBtn")
        self.close_btn.setText("×")
        self.close_btn.setToolTip("close slot")
        self.close_btn.setCursor(Qt.CursorShape.ArrowCursor)
        self.close_btn.clicked.connect(lambda: frame.closeRequested.emit(frame))
        row.addWidget(self.close_btn)

        self._press: QPoint | None = None
        self._drag: GhostDrag | None = None
        self._hold = QTimer(self)
        self._hold.setSingleShot(True)
        self._hold.setInterval(HOLD_MS)
        self._hold.timeout.connect(self._lift)

    def set_text(self, title: str, module_id: str | None) -> None:
        tag = module_id or "empty"
        self.label.setText(f"{title} <span style='color:#7d7469'>#{tag}</span>")

    def set_header(self, widget: QWidget | None) -> None:
        if self.header is not None:
            self._row.removeWidget(self.header)
            if self.header.parent() is self:
                self.header.setParent(None)
        self.header = widget
        if widget is None:
            self._row.setStretch(self._row.indexOf(self.label), 1)
            self.setFixedHeight(TITLE_H)
            return
        self._row.setStretch(self._row.indexOf(self.label), 0)
        self._row.insertWidget(1, widget, 1)
        widget.show()
        self.setFixedHeight(TITLE_H_WITH_HEADER)

    def _grid(self) -> GridContainer | None:
        parent = self.frame.parentWidget()
        return parent if isinstance(parent, GridContainer) else None

    def _lift(self) -> None:
        grid = self._grid()
        if self._drag is not None or grid is None or self.frame.slot.module is None:
            return
        pixmap = self.frame.grab().scaledToWidth(GHOST_WIDTH, Qt.TransformationMode.SmoothTransformation)
        self._drag = grid.begin_ghost(f"id:{self.frame.slot.module}", pixmap, QPoint(pixmap.width() // 2, 12))
        self._drag.move(self.mapToGlobal(self._press or QPoint(0, 0)))

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.frame.slot.module is not None:
            self._press = event.position().toPoint()
            self._hold.start()

    def mouseMoveEvent(self, event) -> None:
        if self._press is None:
            return
        p = event.position().toPoint()
        if self._drag is None:
            if (p - self._press).manhattanLength() < QApplication.startDragDistance():
                return
            self._hold.stop()
            self._lift()
        if self._drag is not None:
            self._drag.move(self.mapToGlobal(p))

    def mouseReleaseEvent(self, event) -> None:
        self._hold.stop()
        if self._drag is not None:
            self._drag.finish(self.mapToGlobal(event.position().toPoint()))
            self._drag = None
        self._press = None


class SlotFrame(QFrame):
    """Base class for everything placed on the grid.

    Knows its Slot (grid rect), its minimum pixel size, and draws a title bar
    over some content. Subclasses decide what the content is.
    """

    closeRequested = Signal(object)          # SlotFrame
    menuRequested = Signal(object, QPoint)   # SlotFrame, global position

    min_px: tuple[int, int] = (120, 80)

    def __init__(self, slot: Slot, parent: QWidget | None = None):
        super().__init__(parent)
        self.slot = slot
        self.setObjectName("slot")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self.title_bar = SlotTitleBar(self)
        self._layout.addWidget(self.title_bar)
        self._content: QWidget | None = None
        self.set_title("")

    def set_title(self, text: str) -> None:
        self.title_bar.set_text(text, self.slot.module)

    def set_content(self, widget: QWidget) -> None:
        if self._content is not None:
            self._layout.removeWidget(self._content)
            self._content.setParent(None)
        self._content = widget
        self._layout.addWidget(widget, 1)

    def dispose(self) -> None:
        """Called before the frame is deleted. Subclasses detach shared widgets."""


class EmptySlotFrame(SlotFrame):
    def __init__(self, slot: Slot, parent=None):
        super().__init__(slot, parent)
        self.set_title("empty slot")
        self.title_bar.setCursor(Qt.CursorShape.ArrowCursor)
        box = QWidget()
        col = QVBoxLayout(box)
        col.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint = QLabel("nothing here yet\ndrop a module on this slot, or")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setObjectName("placeholderText")
        pick = QPushButton("pick a module  ▾")
        pick.setObjectName("pickBtn")
        pick.clicked.connect(
            lambda: self.menuRequested.emit(self, pick.mapToGlobal(QPoint(0, pick.height())))
        )
        col.addWidget(hint)
        col.addSpacing(8)
        col.addWidget(pick, 0, Qt.AlignmentFlag.AlignHCenter)
        self.set_content(box)


class ModuleSlotFrame(SlotFrame):
    def __init__(self, slot: Slot, module, parent=None):
        super().__init__(slot, parent)
        self.module = module
        self.min_px = tuple(module.min_size)
        self.set_title(module.title)
        self.title_bar.set_header(module.header_widget())
        self.set_content(module.widget())

    def dispose(self) -> None:
        # the module's widgets outlive this frame; they may be shown again later.
        # During a swap the new frame may already have taken them, hence the parent checks.
        self.title_bar.set_header(None)
        if self._content is not None:
            self._layout.removeWidget(self._content)
            if self._content.parent() is self:
                self._content.setParent(None)
            self._content = None


class GridContainer(QWidget):
    """Lays SlotFrames out on the 1000x1000 grid, sweeps edges, hosts ghost drags."""

    dropped = Signal(str, object, str)      # payload, target SlotFrame, zone
    modelChanged = Signal()                 # slot rects changed by a sweep (not by window resize)

    def __init__(self, model: LayoutModel, frames: list[SlotFrame], parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.model: LayoutModel = model
        self.frames: list[SlotFrame] = []
        self._hover: Edge | None = None
        self._drag: Edge | None = None
        self.snap_enabled = True
        self.overlay = DragOverlay(self)
        # Workspace installs this to say whether a drop makes sense
        self.drop_allowed = lambda payload, frame, zone: True
        self.set_model(model, frames)

    # --- slot bookkeeping (model and frames stay parallel) ------------------

    def set_model(self, model: LayoutModel, frames: list[SlotFrame]) -> None:
        for f in self.frames:
            f.dispose()
            f.setParent(None)
            f.deleteLater()
        assert len(frames) == len(model.slots)
        self.model = model
        self.frames = []
        for f in frames:
            self._adopt(f)
        self.relayout()

    def _adopt(self, frame: SlotFrame) -> None:
        frame.setParent(self)
        frame.show()
        self.frames.append(frame)

    def frame_for(self, slot: Slot) -> SlotFrame:
        return self.frames[self.model.index(slot)]

    def add_slot(self, slot: Slot, frame: SlotFrame) -> None:
        """Slot must already be in the model (e.g. returned by model.split)."""
        assert self.model.slots[-1] is slot
        self._adopt(frame)
        self.relayout()

    def remove_slot(self, idx: int) -> None:
        """Model has already dropped the slot (fill_hole); drop the frame to match."""
        frame = self.frames.pop(idx)
        frame.dispose()
        frame.setParent(None)
        frame.deleteLater()
        self.relayout()

    def replace_frame(self, idx: int, frame: SlotFrame) -> None:
        old = self.frames[idx]
        old.dispose()
        old.setParent(None)
        old.deleteLater()
        frame.setParent(self)
        frame.show()
        self.frames[idx] = frame
        self.relayout()

    # --- units <-> pixels -------------------------------------------------

    @property
    def scale(self) -> tuple[float, float]:
        return (max(self.width(), 1) / GRID, max(self.height(), 1) / GRID)

    def px_x(self, u: int) -> int:
        return round(u * self.width() / GRID)

    def px_y(self, u: int) -> int:
        return round(u * self.height() / GRID)

    def units_x(self, px: int) -> int:
        return round(px * GRID / max(self.width(), 1))

    def units_y(self, px: int) -> int:
        return round(px * GRID / max(self.height(), 1))

    def units_for_px(self, min_px: tuple[int, int]) -> tuple[int, int]:
        """A pixel minimum expressed in grid units at the current window size."""
        sx, sy = self.scale
        mw, mh = min_px
        return (math.ceil((mw + GAP) / sx), math.ceil((mh + GAP) / sy))

    def min_units_for(self, slot: Slot) -> tuple[int, int]:
        """Min size in units for a slot; slots without a frame yet count as empty."""
        try:
            min_px = self.frame_for(slot).min_px
        except ValueError:
            min_px = EmptySlotFrame.min_px
        return self.units_for_px(min_px)

    def frame_geometry(self, slot: Slot) -> QRect:
        r = slot.rect
        g = GAP // 2
        left, top = self.px_x(r.x), self.px_y(r.y)
        right, bottom = self.px_x(r.right), self.px_y(r.bottom)
        return QRect(left + g, top + g, right - left - GAP, bottom - top - GAP)

    def relayout(self) -> None:
        for f in self.frames:
            f.setGeometry(self.frame_geometry(f.slot))
        self.overlay.setGeometry(self.rect())
        self.overlay.raise_()
        self.update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.relayout()

    # --- edge hit testing -------------------------------------------------

    def edge_at(self, mx: int, my: int) -> Edge | None:
        """Interior edge nearest the mouse, or None. Only far edges are tested;
        every interior edge is some slot's right or bottom edge."""
        best: tuple[int, Edge] | None = None
        for s in self.model.slots:
            r = s.rect
            if r.right < GRID:
                px = self.px_x(r.right)
                if abs(mx - px) <= HANDLE_HIT_PX and self.px_y(r.y) <= my <= self.px_y(r.bottom):
                    d = abs(mx - px)
                    if best is None or d < best[0]:
                        best = (d, Edge("v", r.right, r.y, r.bottom))
            if r.bottom < GRID:
                py = self.px_y(r.bottom)
                if abs(my - py) <= HANDLE_HIT_PX and self.px_x(r.x) <= mx <= self.px_x(r.right):
                    d = abs(my - py)
                    if best is None or d < best[0]:
                        best = (d, Edge("h", r.bottom, r.x, r.right))
        if best is None:
            return None
        _, _, closure = self.model.slots_on_edge(best[1])
        return closure

    def _snap(self, edge: Edge, pos: int) -> int:
        sx, sy = self.scale
        threshold = SNAP_PX / (sx if edge.axis == "v" else sy)
        targets = self.model.snap_targets(edge.axis, edge.pos)
        nearest = min(targets, key=lambda t: abs(t - pos), default=None)
        if nearest is not None and abs(nearest - pos) <= threshold:
            return nearest
        return pos

    # --- mouse: edge sweeping ---------------------------------------------

    def mouseMoveEvent(self, event) -> None:
        p = event.position().toPoint()
        if self._drag is not None:
            pos = self.units_x(p.x()) if self._drag.axis == "v" else self.units_y(p.y())
            if self.snap_enabled and not (event.modifiers() & Qt.KeyboardModifier.AltModifier):
                pos = self._snap(self._drag, pos)
            changes = self.model.sweep(self._drag, pos, self.min_units_for)
            if changes is not None:
                self.model.apply(changes)
                self._drag = Edge(self._drag.axis, pos, self._drag.a, self._drag.b)
                self.relayout()
                self.modelChanged.emit()
            return
        edge = self.edge_at(p.x(), p.y())
        if edge != self._hover:
            self._hover = edge
            self.update()
        if edge is None:
            self.unsetCursor()
        elif edge.axis == "v":
            self.setCursor(Qt.CursorShape.SplitHCursor)
        else:
            self.setCursor(Qt.CursorShape.SplitVCursor)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._hover is not None:
            self._drag = self._hover
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if self._drag is not None:
            self._drag = None
            p = event.position().toPoint()
            self._hover = self.edge_at(p.x(), p.y())
            self.update()

    def leaveEvent(self, event) -> None:
        if self._drag is None and self._hover is not None:
            self._hover = None
            self.update()

    # --- ghost drag: placing modules ------------------------------------------

    def begin_ghost(self, payload: str, pixmap: QPixmap, hotspot: QPoint) -> GhostDrag:
        return GhostDrag(self, payload, pixmap, hotspot)

    def drop_zone_at(self, p: QPoint) -> tuple[SlotFrame, str] | None:
        for frame in self.frames:
            g = frame.geometry()
            if not g.contains(p):
                continue
            fx = (p.x() - g.left()) / max(g.width(), 1)
            fy = (p.y() - g.top()) / max(g.height(), 1)
            dists = {"left": fx, "right": 1 - fx, "top": fy, "bottom": 1 - fy}
            side = min(dists, key=dists.get)
            return frame, (side if dists[side] < DROP_EDGE_BAND else "center")
        return None

    def zone_rect(self, frame: SlotFrame, zone: str) -> QRect:
        g = frame.geometry()
        if zone == "left":
            return QRect(g.left(), g.top(), g.width() // 2, g.height())
        if zone == "right":
            return QRect(g.left() + g.width() // 2, g.top(), g.width() - g.width() // 2, g.height())
        if zone == "top":
            return QRect(g.left(), g.top(), g.width(), g.height() // 2)
        if zone == "bottom":
            return QRect(g.left(), g.top() + g.height() // 2, g.width(), g.height() - g.height() // 2)
        return g

    def _ghost_target(self, payload: str, local: QPoint) -> tuple[SlotFrame, str] | None:
        if not self.rect().contains(local):
            return None
        target = self.drop_zone_at(local)
        if target is not None and not self.drop_allowed(payload, *target):
            return None
        return target

    def _ghost_move(self, drag: GhostDrag, global_pos: QPoint) -> None:
        local = self.mapFromGlobal(global_pos)
        target = self._ghost_target(drag.payload, local)
        zone = self.zone_rect(*target) if target else None
        self.overlay.set_state(zone, drag.pixmap, local - drag.hotspot)

    def _ghost_finish(self, drag: GhostDrag, global_pos: QPoint) -> None:
        local = self.mapFromGlobal(global_pos)
        target = self._ghost_target(drag.payload, local)
        self._ghost_clear()
        if target is not None:
            self.dropped.emit(drag.payload, target[0], target[1])

    def _ghost_clear(self) -> None:
        self.overlay.set_state(None, None, QPoint())

    # --- paint (only the gutters are visible here; the overlay is above slots) ---

    def paintEvent(self, event) -> None:
        edge = self._drag or self._hover
        if edge is None:
            return
        painter = QPainter(self)
        painter.setPen(QPen(ACCENT if self._drag else QColor("#8b7d73"), 2))
        if edge.axis == "v":
            x = self.px_x(edge.pos)
            painter.drawLine(x, self.px_y(edge.a), x, self.px_y(edge.b))
        else:
            y = self.px_y(edge.pos)
            painter.drawLine(self.px_x(edge.a), y, self.px_x(edge.b), y)
        painter.end()
