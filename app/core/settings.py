"""Settings window (core, not a module). Modules · Layout · Project · Preferences.

Non-modal so you can drag a module button from here straight onto the grid.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import (QApplication, QCheckBox, QDialog, QFormLayout, QFrame, QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QPushButton, QScrollArea, QStackedWidget, QToolButton, QVBoxLayout,
                               QWidget)

from .grid import GhostDrag, GridContainer
from .shapes import as_shapes
from .workspace import bind


class DragButton(QToolButton):
    """Click to add the module somewhere sensible; drag onto a slot to choose where."""

    def __init__(self, label: str, payload: str, on_click: Callable[[str], None],
                 get_grid: Callable[[], GridContainer], parent=None):
        super().__init__(parent)
        self.setText(label)
        self.setObjectName("addBtn")
        self.setToolTip("click to add, or drag onto a slot edge")
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.payload = payload
        self._on_click = on_click
        self._get_grid = get_grid
        self._press: QPoint | None = None
        self._drag: GhostDrag | None = None

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._press is None:
            return
        p = event.position().toPoint()
        if self._drag is None:
            if (p - self._press).manhattanLength() < QApplication.startDragDistance():
                return
            self.setDown(False)
            pixmap = self.grab()
            self._drag = self._get_grid().begin_ghost(
                self.payload, pixmap, QPoint(pixmap.width() // 2, pixmap.height() // 2))
        self._drag.move(self.mapToGlobal(p))

    def mouseReleaseEvent(self, event) -> None:
        if self._drag is not None:
            self._drag.finish(self.mapToGlobal(event.position().toPoint()))
            self._drag = None
            self._press = None
            self.setDown(False)
            return
        if self._press is not None:
            self._press = None
            self._on_click(self.payload)
        super().mouseReleaseEvent(event)


def _heading(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("settingsHeading")
    return label


def _hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("settingsHint")
    label.setWordWrap(True)
    return label


def _clear(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.deleteLater()
        elif item.layout() is not None:
            _clear(item.layout())


class SettingsDialog(QDialog):
    PAGES = ("Modules", "Layout", "Project", "Preferences")

    def __init__(self, win, registry: dict, layouts_dir: Path, prefs):
        super().__init__(win, Qt.WindowType.Tool)
        self.win = win
        self.registry = registry
        self.layouts_dir = layouts_dir
        self.prefs = prefs
        self.setWindowTitle("FAWS settings")
        self.setObjectName("settings")
        self.resize(720, 520)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        self.nav = QListWidget()
        self.nav.setObjectName("settingsNav")
        self.nav.setFixedWidth(150)
        for name in self.PAGES:
            self.nav.addItem(QListWidgetItem(name))
        self.pages = QStackedWidget()
        row.addWidget(self.nav)
        row.addWidget(self.pages, 1)

        self.modules_page = self._scroll(self._build_modules_page())
        self.layout_page = self._scroll(self._build_layout_page())
        self.project_page = self._scroll(self._build_project_page())
        self.prefs_page = self._scroll(self._build_prefs_page())
        for p in (self.modules_page, self.layout_page, self.project_page, self.prefs_page):
            self.pages.addWidget(p)
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.nav.setCurrentRow(0)

    # --- plumbing ------------------------------------------------------------------

    @property
    def ws(self):
        return self.win.workspace

    def _grid(self) -> GridContainer:
        return self.ws.grid

    def _scroll(self, inner: QWidget) -> QScrollArea:
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.Shape.NoFrame)
        area.setWidget(inner)
        return area

    def open_page(self, name: str = "Modules") -> None:
        self.nav.setCurrentRow(self.PAGES.index(name))
        self.refresh()
        self.show()
        self.raise_()
        self.activateWindow()

    def showEvent(self, event) -> None:
        self.refresh()
        super().showEvent(event)

    def refresh(self) -> None:
        if self.ws is None:
            return
        self._fill_modules()
        self._fill_layouts()
        self._fill_project()
        self._fill_prefs()

    # --- Modules ---------------------------------------------------------------------

    def _build_modules_page(self) -> QWidget:
        page = QWidget()
        col = QVBoxLayout(page)
        col.setContentsMargins(20, 16, 20, 16)
        col.setSpacing(10)
        col.addWidget(_heading("Add a module"))
        col.addWidget(_hint("Click to add it to the first empty slot (or split the largest one). "
                            "Drag it onto a slot edge to choose where it goes."))
        self.add_grid = QGridLayout()
        self.add_grid.setHorizontalSpacing(12)
        self.add_grid.setVerticalSpacing(6)
        col.addLayout(self.add_grid)

        col.addSpacing(10)
        col.addWidget(_heading("Hidden modules"))
        col.addWidget(_hint("Closed with × but still in the project. Click or drag to show again."))
        self.hidden_col = QVBoxLayout()
        col.addLayout(self.hidden_col)

        col.addSpacing(10)
        col.addWidget(_heading("In this project"))
        self.project_grid = QGridLayout()
        self.project_grid.setHorizontalSpacing(12)
        self.project_grid.setVerticalSpacing(4)
        col.addLayout(self.project_grid)
        col.addStretch(1)
        return page

    def _fill_modules(self) -> None:
        _clear(self.add_grid)
        for r, (kind, cls) in enumerate(self.registry.items()):
            btn = DragButton(f"+ {kind}", f"kind:{kind}", self.win.add_module, self._grid)
            self.add_grid.addWidget(btn, r, 0)
            self.add_grid.addWidget(_hint(getattr(cls, "description", "")), r, 1)
        self.add_grid.setColumnStretch(1, 1)

        _clear(self.hidden_col)
        hidden = self.ws.offscreen_ids()
        if not hidden:
            self.hidden_col.addWidget(_hint("nothing hidden"))
        for mid in hidden:
            kind = self.ws.project.specs[mid]["kind"]
            btn = DragButton(f"{mid}  ({kind})", f"id:{mid}", self.win.add_module, self._grid)
            self.hidden_col.addWidget(btn, 0, Qt.AlignmentFlag.AlignLeft)

        _clear(self.project_grid)
        hub = self.ws.project.hub
        for r, (mid, spec) in enumerate(self.ws.project.specs.items()):
            module = hub.get(mid)
            wired = ", ".join(f"{role} → {t.id}" for role, t in module.wired.items()) or "—"
            self.project_grid.addWidget(QLabel(f"<b>{mid}</b>"), r, 0)
            self.project_grid.addWidget(_hint(spec["kind"]), r, 1)
            self.project_grid.addWidget(_hint(wired), r, 2)
            actions = QHBoxLayout()
            if module.needs:
                b = QPushButton("wiring…")
                b.setObjectName("smallBtn")
                b.clicked.connect(bind(self._rewire, mid))
                actions.addWidget(b)
            b = QPushButton("remove")
            b.setObjectName("smallBtn")
            b.clicked.connect(bind(self._remove, mid))
            actions.addWidget(b)
            actions.addStretch(1)
            self.project_grid.addLayout(actions, r, 3)
        self.project_grid.setColumnStretch(2, 1)

    def _rewire(self, mid: str) -> None:
        self.ws.rewire(self.ws.project.hub.get(mid))
        self.refresh()

    def _remove(self, mid: str) -> None:
        self.ws.remove_module(mid)
        self.refresh()

    # --- Layout -------------------------------------------------------------------------

    def _build_layout_page(self) -> QWidget:
        page = QWidget()
        col = QVBoxLayout(page)
        col.setContentsMargins(20, 16, 20, 16)
        col.setSpacing(10)
        col.addWidget(_heading("Presets"))
        col.addWidget(_hint("A preset only rearranges the slots; your modules and their content stay. "
                            "Slots naming a module this project doesn't have show up empty."))
        self.preset_list = QListWidget()
        self.preset_list.setObjectName("presetList")
        self.preset_list.itemActivated.connect(lambda item: self._apply_preset(item.data(Qt.ItemDataRole.UserRole)))
        col.addWidget(self.preset_list)
        row = QHBoxLayout()
        apply_btn = QPushButton("apply selected")
        apply_btn.clicked.connect(self._apply_selected)
        save_btn = QPushButton("save current layout as preset…")
        save_btn.clicked.connect(self.win.save_layout_preset)
        row.addWidget(apply_btn)
        row.addWidget(save_btn)
        row.addStretch(1)
        col.addLayout(row)
        col.addStretch(1)
        return page

    def _fill_layouts(self) -> None:
        self.preset_list.clear()
        for path in sorted(self.layouts_dir.glob("*.json")) if self.layouts_dir.is_dir() else []:
            item = QListWidgetItem(path.stem)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self.preset_list.addItem(item)

    def _apply_selected(self) -> None:
        item = self.preset_list.currentItem()
        if item is not None:
            self._apply_preset(item.data(Qt.ItemDataRole.UserRole))

    def _apply_preset(self, path: str) -> None:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            self.win.show_status(f"cannot read preset: {e}")
            return
        self.ws.apply_layout(data)
        self.win.show_status(f"layout: {Path(path).stem}")
        self.refresh()

    # --- Project ------------------------------------------------------------------------

    def _build_project_page(self) -> QWidget:
        page = QWidget()
        col = QVBoxLayout(page)
        col.setContentsMargins(20, 16, 20, 16)
        col.setSpacing(10)
        col.addWidget(_heading("Project"))
        form = QFormLayout()
        self.title_edit = QLineEdit()
        self.title_edit.editingFinished.connect(self._title_changed)
        self.path_label = _hint("")
        form.addRow("title", self.title_edit)
        form.addRow("file", self.path_label)
        col.addLayout(form)
        row = QHBoxLayout()
        for text, cb in (("open…", self.win.open_project_dialog),
                         ("save", self.win.save_project),
                         ("save as…", self.win.save_project_as)):
            b = QPushButton(text)
            b.clicked.connect(bind(cb))
            row.addWidget(b)
        row.addStretch(1)
        col.addLayout(row)
        col.addStretch(1)
        return page

    def _fill_project(self) -> None:
        self.title_edit.setText(self.ws.project.title)
        self.path_label.setText(str(self.ws.project.path or "(unsaved)"))

    def _title_changed(self) -> None:
        text = self.title_edit.text().strip()
        if text and text != self.ws.project.title:
            self.ws.project.title = text
            self.win.refresh_title()
            self.ws.changed.emit()

    # --- Preferences ---------------------------------------------------------------------

    def _build_prefs_page(self) -> QWidget:
        page = QWidget()
        col = QVBoxLayout(page)
        col.setContentsMargins(20, 16, 20, 16)
        col.setSpacing(10)
        col.addWidget(_heading("Preferences"))
        col.addWidget(_hint("These are yours, not the project's. They apply to every project you open."))
        self.snap_box = QCheckBox("snap slot edges to the 25-unit grid and to other edges (hold Alt to bypass)")
        self.snap_box.toggled.connect(self._snap_toggled)
        self.autosave_box = QCheckBox("autosave the project 1.5 s after any change")
        self.autosave_box.toggled.connect(self._autosave_toggled)
        col.addWidget(self.snap_box)
        col.addWidget(self.autosave_box)
        col.addStretch(1)
        return page

    def _fill_prefs(self) -> None:
        self.snap_box.setChecked(self.prefs.snap)
        self.autosave_box.setChecked(self.prefs.autosave)

    def _snap_toggled(self, on: bool) -> None:
        self.prefs.snap = on
        self._grid().snap_enabled = on

    def _autosave_toggled(self, on: bool) -> None:
        self.prefs.autosave = on
        self.ws.autosave_enabled = on
