"""Top bar: add modules (click or drag), re-show hidden ones, layouts, file."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import (QApplication, QLabel, QMenu, QSizePolicy, QToolBar, QToolButton,
                               QWidget)

from .grid import GhostDrag, GridContainer
from .workspace import bind


class DragButton(QToolButton):
    """Click to add the module somewhere sensible; drag onto a slot to choose where."""

    def __init__(self, label: str, payload: str, on_click: Callable[[str], None],
                 get_grid: Callable[[], GridContainer], parent=None):
        super().__init__(parent)
        self.setText(label)
        self.setObjectName("addBtn")
        self.setToolTip(f"click to add, or drag onto a slot edge\n{payload}")
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


class TopBar(QToolBar):
    def __init__(self, win, registry: dict, layouts_dir: Path):
        super().__init__("top bar", win)
        self.win = win
        self.layouts_dir = layouts_dir
        self.setMovable(False)
        self.setFloatable(False)
        self.setObjectName("topBar")

        self.addWidget(self._label("add"))
        for kind in registry:
            self.addWidget(DragButton(f"+ {kind}", f"kind:{kind}", win.add_module,
                                      lambda: win.workspace.grid))

        self.addSeparator()
        self.addWidget(self._menu_button("existing ▾", self._fill_existing))

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.addWidget(spacer)

        self.addWidget(self._menu_button("layout ▾", self._fill_layouts))
        self.addWidget(self._menu_button("file ▾", self._fill_file))

    def _label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("barLabel")
        return label

    def _menu_button(self, text: str, fill: Callable[[QMenu], None]) -> QToolButton:
        btn = QToolButton(self)
        btn.setText(text)
        btn.setObjectName("barBtn")
        btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(btn)
        menu.aboutToShow.connect(lambda: (menu.clear(), fill(menu)))
        btn.setMenu(menu)
        return btn

    # --- menu contents (rebuilt each time they open) ---------------------------

    def _fill_existing(self, menu: QMenu) -> None:
        ws = self.win.workspace
        off = ws.offscreen_ids()
        if not off:
            menu.addAction("every module is on screen").setEnabled(False)
        for mid in off:
            kind = ws.project.specs[mid]["kind"]
            menu.addAction(f"{mid}  ({kind})", bind(self.win.add_module, f"id:{mid}"))

    def _fill_layouts(self, menu: QMenu) -> None:
        presets = sorted(self.layouts_dir.glob("*.json")) if self.layouts_dir.is_dir() else []
        if not presets:
            menu.addAction("no presets in layouts/").setEnabled(False)
        for path in presets:
            menu.addAction(path.stem, bind(self._apply_preset, path))
        menu.addSeparator()
        menu.addAction("save current as preset…", bind(self.win.save_layout_preset))

    def _fill_file(self, menu: QMenu) -> None:
        menu.addAction("open…  (Ctrl+O)", bind(self.win.open_project_dialog))
        menu.addAction("save  (Ctrl+S)", bind(self.win.save_project))
        menu.addAction("save as…", bind(self.win.save_project_as))

    def _apply_preset(self, path: Path) -> None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            self.win.show_status(f"cannot read preset: {e}")
            return
        self.win.workspace.apply_layout(data)
        self.win.show_status(f"layout: {path.stem}")
