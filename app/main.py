"""FAWS entry point.  Run from the repo root:  python -m app.main [project.faws.json]"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow, QMessageBox

from app.core.hub import WireError
from app.core.layout import LayoutError
from app.core.prefs import Prefs
from app.core.project import Project, ProjectError, load_project
from app.core.settings import SettingsDialog
from app.core.toolbar import TopBar
from app.core.workspace import Workspace
from app.modules import REGISTRY

ROOT = Path(__file__).resolve().parent.parent      # repo root; layouts/ and examples/ live there
DEFAULT_PROJECT = ROOT / "examples" / "example.faws.json"
LAYOUTS_DIR = ROOT / "layouts"
FILE_FILTER = "FAWS project (*.faws.json *.json)"
OPEN_ERRORS = (ProjectError, LayoutError, WireError, TypeError)

# palette carried over from the old LÖVE prototype's config.json
STYLE = """
QMainWindow, GridContainer, Workspace { background: #0c0c0d; }
QToolBar#topBar { background: #16151a; border-bottom: 1px solid #3f3d47; padding: 3px 8px; spacing: 6px; }
QLabel#brand { color: #cdb27b; font-size: 13px; font-weight: 700; letter-spacing: 1px; padding: 0 6px; }
QLabel#barLabel { color: #8b7d73; font-size: 12px; padding: 0 6px; }
QToolButton#addBtn, QToolButton#barBtn, QPushButton, QPushButton#smallBtn {
    color: #cdb27b; background: #26252b; border: 1px solid #3f3d47; border-radius: 4px;
    padding: 4px 10px; font-size: 12px;
}
QPushButton#smallBtn { padding: 2px 8px; font-size: 11px; }
QToolButton#addBtn:hover, QToolButton#barBtn:hover, QPushButton:hover { background: #3f3d47; }
QToolButton#barBtn::menu-indicator { image: none; }

QFrame#slot { background: #1a191d; border: 1px solid #3f3d47; border-radius: 4px; }
QWidget#slotTitleBar {
    background: #3f3d47; border-top-left-radius: 3px; border-top-right-radius: 3px;
}
QLabel#slotTitleText { color: #cdb27b; font-size: 12px; font-weight: 600; background: transparent; }
QToolButton#slotBtn {
    color: #cdb27b; background: transparent; border: none; border-radius: 3px;
    font-size: 14px; font-weight: 700; padding: 0 5px; min-width: 16px;
}
QToolButton#slotBtn:hover { background: #5a5763; }

QLabel#placeholderHead { color: #cdb27b; font-size: 22px; font-weight: 700; }
QLabel#placeholderText { color: #8b7d73; font-size: 13px; }
QLabel#placeholderApi  { color: #6b6360; font-size: 11px; font-family: Menlo, monospace; }
QPushButton#pickBtn {
    color: #cdb27b; background: #26252b; border: 1px solid #3f3d47; border-radius: 4px; padding: 5px 12px;
}
QPushButton#pickBtn:hover { background: #3f3d47; }

QMenu { background: #1a191d; color: #e0d6c4; border: 1px solid #3f3d47; padding: 4px; }
QMenu::item { padding: 5px 22px 5px 12px; border-radius: 3px; }
QMenu::item:selected { background: #3f3d47; }
QMenu::item:disabled { color: #6b6360; }
QMenu::separator { height: 1px; background: #3f3d47; margin: 4px 6px; }

QDialog { background: #1a191d; color: #e0d6c4; }
QDialog QLabel { color: #e0d6c4; }
QLabel#settingsHeading { color: #cdb27b; font-size: 15px; font-weight: 700; padding-top: 4px; }
QLabel#settingsHint { color: #8b7d73; font-size: 12px; }
QListWidget#settingsNav { background: #16151a; color: #cdb27b; border: none; border-right: 1px solid #3f3d47; font-size: 13px; padding-top: 8px; }
QListWidget#settingsNav::item { padding: 8px 14px; }
QListWidget#settingsNav::item:selected { background: #3f3d47; color: #e0d6c4; border-radius: 0; }
QListWidget#presetList { background: #16151a; color: #e0d6c4; border: 1px solid #3f3d47; border-radius: 4px; }
QListWidget#presetList::item { padding: 6px 10px; }
QListWidget#presetList::item:selected { background: #3f3d47; }
QScrollArea { background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QLineEdit { background: #26252b; color: #e0d6c4; border: 1px solid #3f3d47; border-radius: 3px; padding: 4px 8px; }
QCheckBox { color: #e0d6c4; font-size: 12px; spacing: 8px; }
QComboBox { background: #26252b; color: #e0d6c4; border: 1px solid #3f3d47; border-radius: 3px; padding: 3px 8px; }
QComboBox QAbstractItemView { background: #1a191d; color: #e0d6c4; selection-background-color: #3f3d47; }
QStatusBar { background: #0c0c0d; color: #8b7d73; }
"""


class MainWindow(QMainWindow):
    def __init__(self, project: Project, prefs: Prefs):
        super().__init__()
        self.prefs = prefs
        self.resize(1280, 800)
        self.workspace: Workspace | None = None
        self.top_bar = TopBar(self)
        self.addToolBar(self.top_bar)
        self.settings = SettingsDialog(self, REGISTRY, LAYOUTS_DIR, prefs)
        QShortcut(QKeySequence.StandardKey.Save, self, self.save_project)
        QShortcut(QKeySequence.StandardKey.Open, self, self.open_project_dialog)
        QShortcut(QKeySequence.StandardKey.Preferences, self, self.open_settings)
        self.set_project(project)

    def set_project(self, project: Project) -> None:
        if self.workspace is not None:
            self.workspace.flush()
        self.workspace = Workspace(project, REGISTRY)
        self.workspace.autosave_enabled = self.prefs.autosave
        self.workspace.grid.snap_enabled = self.prefs.snap
        self.workspace.status.connect(self.show_status)
        self.workspace.changed.connect(self._on_changed)
        self.setCentralWidget(self.workspace)
        self.refresh_title()
        if project.path is not None:
            self.prefs.last_project = str(project.path)
        self.show_status("drag gutters to resize  ·  hold a slot's title bar to move it  ·  ⚙ settings to add modules")

    def refresh_title(self) -> None:
        title = self.workspace.project.title
        self.setWindowTitle(f"FAWS — {title}")
        self.top_bar.set_title(title)

    def show_status(self, text: str) -> None:
        self.statusBar().showMessage(text)

    def _on_changed(self) -> None:
        if self.settings.isVisible():
            self.settings.refresh()

    def closeEvent(self, event) -> None:
        if self.workspace is not None:
            self.workspace.flush()
        self.settings.close()
        super().closeEvent(event)

    # --- actions (settings window and shortcuts call these) --------------------------

    def open_settings(self) -> None:
        self.settings.open_page("Modules")

    def add_module(self, payload: str) -> None:
        self.workspace.add_module_auto(payload)

    def save_project(self) -> None:
        if self.workspace.project.path is None:
            self.save_project_as()
        else:
            self.workspace.save()

    def save_project_as(self) -> None:
        start = str(self.workspace.project.path or ROOT)
        path, _ = QFileDialog.getSaveFileName(self, "Save project as", start, FILE_FILTER)
        if path:
            self.workspace.save(path)
            self.prefs.last_project = path
            self.refresh_title()

    def open_project_dialog(self) -> None:
        start = str((self.workspace.project.path or DEFAULT_PROJECT).parent)
        path, _ = QFileDialog.getOpenFileName(self, "Open project", start, FILE_FILTER)
        if not path:
            return
        try:
            project = load_project(path, REGISTRY)
        except OPEN_ERRORS as e:
            QMessageBox.critical(self, "FAWS — could not open project", str(e))
            return
        self.set_project(project)

    def save_layout_preset(self) -> None:
        LAYOUTS_DIR.mkdir(exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(self, "Save layout preset", str(LAYOUTS_DIR), "layout (*.json)")
        if not path:
            return
        Path(path).write_text(json.dumps(self.workspace.layout_model.to_json(), indent=2) + "\n", encoding="utf-8")
        self.show_status(f"preset saved: {Path(path).stem}")
        self.settings.refresh()


def pick_start_project(argv: list[str], prefs: Prefs) -> Path:
    if len(argv) > 1:
        return Path(argv[1])
    last = prefs.last_project
    if last and Path(last).is_file():
        return Path(last)
    return DEFAULT_PROJECT


def main(argv: list[str]) -> int:
    app = QApplication(argv)
    app.setStyleSheet(STYLE)
    prefs = Prefs()

    path = pick_start_project(argv, prefs)
    try:
        project = load_project(path, REGISTRY)
    except OPEN_ERRORS as e:
        if path != DEFAULT_PROJECT and len(argv) <= 1:
            prefs.last_project = None        # last project is gone/broken; fall back next time
        QMessageBox.critical(None, "FAWS — could not open project", str(e))
        print(e, file=sys.stderr)
        return 1

    window = MainWindow(project, prefs)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
