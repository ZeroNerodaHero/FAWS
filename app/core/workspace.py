"""Workspace: one project on one grid. All layout edits go through here."""

from __future__ import annotations

from pathlib import Path

from datetime import datetime

from PySide6.QtCore import QPoint, QTimer, Signal
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel,
                               QMenu, QVBoxLayout, QWidget)

from .grid import EmptySlotFrame, GridContainer, ModuleSlotFrame, SlotFrame
from .hub import WireError
from .layout import SIDES, LayoutError, LayoutModel, Slot
from .module import Module
from .project import Project, ProjectError
from .shapes import as_shapes


def bind(fn, *args):
    """Menu callback that ignores whatever Qt passes (the `checked` bool)."""
    return lambda *_: fn(*args)


class WireDialog(QDialog):
    """One dropdown per need, listing only modules that fit the required shapes."""

    def __init__(self, title: str, needs: dict, candidates: dict[str, list[str]],
                 current: dict[str, str] | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self._boxes: dict[str, QComboBox] = {}
        col = QVBoxLayout(self)
        col.addWidget(QLabel("Each need must point at a module that provides the right shapes."))
        form = QFormLayout()
        for role, spec in needs.items():
            shapes = " + ".join(s.name for s in as_shapes(spec))
            box = QComboBox()
            box.addItems(candidates[role])
            if current and current.get(role) in candidates[role]:
                box.setCurrentText(current[role])
            self._boxes[role] = box
            form.addRow(f"{role}  ({shapes})", box)
        col.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        col.addWidget(buttons)

    def wiring(self) -> dict[str, str]:
        return {role: box.currentText() for role, box in self._boxes.items()}


AUTOSAVE_DELAY_MS = 1000    # written this long after the last change (any module, any layout edit)


class Workspace(QWidget):
    status = Signal(str)
    changed = Signal()      # layout or module set changed; schedules an autosave

    def __init__(self, project: Project, registry: dict[str, type[Module]], parent=None):
        super().__init__(parent)
        self.project = project
        self.registry = registry
        frames = [self.make_frame(slot) for slot in project.layout.slots]
        self.grid = GridContainer(project.layout, frames)
        self.grid.drop_allowed = self.drop_allowed
        self.grid.dropped.connect(self.handle_drop)
        self.grid.modelChanged.connect(self.changed)
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.addWidget(self.grid)

        # Every change restarts the timer; the project is written once things settle.
        self.autosave_enabled = True
        self._autosave = QTimer(self)
        self._autosave.setSingleShot(True)
        self._autosave.setInterval(AUTOSAVE_DELAY_MS)
        self._autosave.timeout.connect(self.autosave)
        self.changed.connect(self._schedule_autosave)
        project.hub.on_dirty(lambda _module_id: self._schedule_autosave())

    # --- autosave -----------------------------------------------------------------

    def _schedule_autosave(self) -> None:
        if self.autosave_enabled and self.project.path is not None:
            self._autosave.start()

    def autosave(self) -> None:
        if self.project.path is None:
            return
        try:
            self.project.save()
        except (ProjectError, OSError) as e:
            self.status.emit(f"autosave failed: {e}")
            return
        self.status.emit(f"autosaved {datetime.now():%H:%M:%S}  ·  {self.project.path.name}")

    def flush(self) -> None:
        """Write now if a change is still waiting on the timer (call before quitting)."""
        if self._autosave.isActive():
            self._autosave.stop()
            self.autosave()

    # --- frames -------------------------------------------------------------

    def make_frame(self, slot: Slot) -> SlotFrame:
        if slot.module is None:
            frame = EmptySlotFrame(slot)
        else:
            frame = ModuleSlotFrame(slot, self.project.hub.get(slot.module))
        frame.closeRequested.connect(self.close_slot)
        frame.menuRequested.connect(self.show_slot_menu)
        return frame

    def _refresh_frame(self, slot: Slot) -> None:
        """Rebuild the frame for a slot whose module changed."""
        idx = self.project.layout.index(slot)
        self.grid.replace_frame(idx, self.make_frame(slot))
        self.changed.emit()

    # --- queries ------------------------------------------------------------

    @property
    def layout_model(self) -> LayoutModel:
        return self.project.layout

    def on_screen_ids(self) -> set[str]:
        return {s.module for s in self.layout_model.slots if s.module is not None}

    def offscreen_ids(self) -> list[str]:
        return [mid for mid in self.project.specs if mid not in self.on_screen_ids()]

    def largest_slot(self) -> Slot:
        return max(self.layout_model.slots, key=lambda s: s.rect.area)

    # --- close ----------------------------------------------------------------

    def close_slot(self, frame: SlotFrame) -> None:
        """Remove the slot from screen. Its module stays in the project."""
        model = self.layout_model
        idx = model.index(frame.slot)
        module_id = frame.slot.module
        if len(model.slots) == 1 or not model.fill_hole(idx, self.grid.min_units_for):
            if module_id is None:
                self.status.emit("nothing around this slot can grow into it; it stays empty")
                return
            frame.slot.module = None
            self._refresh_frame(frame.slot)
            self.status.emit(f"{module_id} hidden; slot kept empty (neighbours can't fill it)")
            return
        self.grid.remove_slot(idx)
        self.changed.emit()
        if module_id:
            self.status.emit(f"{module_id} hidden; still in the project under 'existing'")

    # --- split ----------------------------------------------------------------

    def _split_mins(self, frame: SlotFrame, incoming_px: tuple[int, int] | None):
        keep_min = self.grid.min_units_for(frame.slot)
        new_min = self.grid.units_for_px(incoming_px or EmptySlotFrame.min_px)
        return keep_min, new_min

    def can_split(self, frame: SlotFrame, side: str, incoming_px: tuple[int, int] | None = None) -> bool:
        idx = self.layout_model.index(frame.slot)
        return self.layout_model.can_split(idx, side, *self._split_mins(frame, incoming_px))

    def split_slot(self, frame: SlotFrame, side: str,
                   incoming_px: tuple[int, int] | None = None) -> Slot | None:
        """Cut the slot; `incoming_px` is the min size of whatever will fill the new half."""
        idx = self.layout_model.index(frame.slot)
        new_slot = self.layout_model.split(idx, side, *self._split_mins(frame, incoming_px))
        if new_slot is None:
            self.status.emit("too small to split that way")
            return None
        self.grid.add_slot(new_slot, self.make_frame(new_slot))
        self.changed.emit()
        return new_slot

    def payload_min_px(self, payload: str) -> tuple[int, int] | None:
        tag, _, value = payload.partition(":")
        if tag == "id" and self.project.hub.has(value):
            return tuple(self.project.hub.get(value).min_size)
        if tag == "kind" and value in self.registry:
            return tuple(self.registry[value].min_size)
        return None

    # --- placing modules -----------------------------------------------------

    def place_module(self, module_id: str, slot: Slot) -> None:
        """Show module_id in `slot`. If it was on screen elsewhere, swap."""
        model = self.layout_model
        source = model.find(module_id)
        if source is slot:
            return
        if source is not None:
            source.module, slot.module = slot.module, module_id
            self._refresh_frame(source)
        else:
            slot.module = module_id
        self._refresh_frame(slot)

    def new_module(self, kind: str) -> str | None:
        """Create a module of `kind`, asking for wiring if it has needs."""
        cls = self.registry.get(kind)
        if cls is None:
            self.status.emit(f"unknown module kind {kind!r}")
            return None
        wiring: dict[str, str] = {}
        if cls.needs:
            candidates = {role: self.project.hub.candidates(cls, role) for role in cls.needs}
            missing = [role for role, c in candidates.items() if not c]
            if missing:
                role = missing[0]
                shapes = " + ".join(s.name for s in as_shapes(cls.needs[role]))
                self.status.emit(f"can't add {kind}: nothing in the project provides {shapes} for '{role}'")
                return None
            dlg = WireDialog(f"wire new {kind}", cls.needs, candidates, parent=self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return None
            wiring = dlg.wiring()
        try:
            module = self.project.add_module(cls, wiring)
        except WireError as e:
            self.status.emit(str(e))
            return None
        self.changed.emit()
        return module.id

    def resolve_payload(self, payload: str) -> str | None:
        """Turn a drop payload into a module id, creating the module if needed."""
        tag, _, value = payload.partition(":")
        if tag == "id":
            return value if self.project.hub.has(value) else None
        if tag == "kind":
            return self.new_module(value)
        return None

    def add_module_auto(self, payload: str) -> None:
        """Toolbar click: first empty slot, else split the largest slot."""
        module_id = self.resolve_payload(payload)
        if module_id is None:
            return
        empty = next((s for s in self.layout_model.slots if s.module is None), None)
        if empty is not None:
            self.place_module(module_id, empty)
            return
        big = self.largest_slot()
        frame = self.grid.frame_for(big)
        side = "right" if big.rect.w * self.grid.width() >= big.rect.h * self.grid.height() else "bottom"
        new_slot = self.split_slot(frame, side, self.payload_min_px(f"id:{module_id}"))
        if new_slot is not None:
            self.place_module(module_id, new_slot)

    # --- drag and drop -------------------------------------------------------

    def drop_allowed(self, payload: str, frame: SlotFrame, zone: str) -> bool:
        """Only highlight drops that will actually work."""
        tag, _, value = payload.partition(":")
        if tag == "id" and frame.slot.module == value:
            return False                        # dropping on itself
        if zone == "center":
            if frame.slot.module is None:
                return True
            return tag == "id"                  # swap only for modules already in the project
        return self.can_split(frame, zone, self.payload_min_px(payload))

    def handle_drop(self, payload: str, frame: SlotFrame, zone: str) -> None:
        incoming_px = self.payload_min_px(payload)
        module_id = self.resolve_payload(payload)
        if module_id is None:
            return
        if zone == "center":
            self.place_module(module_id, frame.slot)
            return
        new_slot = self.split_slot(frame, zone, incoming_px)
        if new_slot is not None:
            self.place_module(module_id, new_slot)

    # --- project-level ------------------------------------------------------

    def remove_module(self, module_id: str) -> None:
        slot = self.layout_model.find(module_id)
        try:
            self.project.remove_module(module_id)
        except ProjectError as e:
            self.status.emit(str(e))
            return
        if slot is not None:
            self._refresh_frame(slot)
        self.changed.emit()
        self.status.emit(f"{module_id} removed from the project")

    def rewire(self, module: Module) -> None:
        candidates = {role: self.project.hub.candidates(module, role, exclude=module.id) for role in module.needs}
        current = {role: target.id for role, target in module.wired.items()}
        dlg = WireDialog(f"wiring for {module.id}", module.needs, candidates, current, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        for role, target_id in dlg.wiring().items():
            if current.get(role) != target_id:
                try:
                    self.project.rewire(module.id, role, target_id)
                except WireError as e:
                    self.status.emit(str(e))
                    return
        slot = self.layout_model.find(module.id)
        if slot is not None:
            self._refresh_frame(slot)
        self.changed.emit()

    def apply_layout(self, data: dict) -> None:
        """Replace the slot arrangement; modules stay. Unknown ids become empty slots."""
        try:
            model = LayoutModel.from_json(data)
        except LayoutError as e:
            self.status.emit(f"bad layout: {e}")
            return
        seen: set[str] = set()
        for slot in model.slots:
            if slot.module is not None and (slot.module not in self.project.specs or slot.module in seen):
                slot.module = None
            if slot.module is not None:
                seen.add(slot.module)
        self.project.layout = model
        self.grid.set_model(model, [self.make_frame(s) for s in model.slots])
        self.changed.emit()

    def save(self, path: str | Path | None = None) -> Path | None:
        self._autosave.stop()
        try:
            saved = self.project.save(path)
        except (ProjectError, OSError) as e:
            self.status.emit(f"save failed: {e}")
            return None
        self.status.emit(f"saved {saved}")
        return saved

    # --- slot menu -------------------------------------------------------------

    def show_slot_menu(self, frame: SlotFrame, pos: QPoint) -> None:
        menu = QMenu(self)
        slot = frame.slot

        if slot.module is None:
            new = menu.addMenu("new module")
            for kind in self.registry:
                new.addAction(kind, bind(self._pick, f"kind:{kind}", slot))
            existing = menu.addMenu("existing module")
            off = self.offscreen_ids()
            if not off:
                existing.addAction("(everything is on screen)").setEnabled(False)
            for mid in off:
                existing.addAction(mid, bind(self._pick, f"id:{mid}", slot))
            menu.addSeparator()
        else:
            module = self.project.hub.get(slot.module)
            items = module.menu_items()
            for item in items:
                if item is None:
                    menu.addSeparator()
                else:
                    label, cb = item
                    menu.addAction(label, bind(self._run_item, cb))
            if items:
                menu.addSeparator()
            if module.needs:
                menu.addAction("wiring…", bind(self.rewire, module))

        split = menu.addMenu("split")
        for side in SIDES:
            split.addAction(side, bind(self.split_slot, frame, side))

        if slot.module is not None:
            menu.addAction("remove from project", bind(self.remove_module, slot.module))
        menu.addAction("close slot", bind(self.close_slot, frame))
        menu.exec(pos)

    def _pick(self, payload: str, slot: Slot) -> None:
        module_id = self.resolve_payload(payload)
        if module_id is not None:
            self.place_module(module_id, slot)

    def _run_item(self, cb) -> None:
        msg = cb()
        if isinstance(msg, str):
            self.status.emit(msg)
