"""App-level preferences (not project data). Stored per user via QSettings."""

from __future__ import annotations

from PySide6.QtCore import QSettings


class Prefs:
    def __init__(self):
        self._s = QSettings("faws", "faws")

    def _bool(self, key: str, default: bool) -> bool:
        v = self._s.value(key, default)
        return v in (True, "true", "True", 1, "1")

    @property
    def snap(self) -> bool:
        return self._bool("layout/snap", True)

    @snap.setter
    def snap(self, on: bool) -> None:
        self._s.setValue("layout/snap", bool(on))

    @property
    def autosave(self) -> bool:
        return self._bool("project/autosave", True)

    @autosave.setter
    def autosave(self, on: bool) -> None:
        self._s.setValue("project/autosave", bool(on))

    @property
    def last_project(self) -> str | None:
        v = self._s.value("project/last", None)
        return str(v) if v else None

    @last_project.setter
    def last_project(self, path: str | None) -> None:
        if path:
            self._s.setValue("project/last", str(path))
        else:
            self._s.remove("project/last")
