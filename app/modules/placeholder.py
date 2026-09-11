"""Placeholder module: shows what the module is supposed to be, nothing else.

The real modules subclass this for now. As each one gets built it replaces
build_widget() and the stub API methods; the class layout stays the same.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.core.module import Module
from app.core.shapes import as_shapes


class PlaceholderModule(Module):
    description: str = ""

    def build_widget(self) -> QWidget:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 8, 16, 8)

        head = QLabel(self.title)
        head.setObjectName("placeholderHead")
        head.setAlignment(Qt.AlignmentFlag.AlignCenter)

        body = QLabel(self.description)
        body.setObjectName("placeholderText")
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.setWordWrap(True)

        api = QLabel(self._api_summary())
        api.setObjectName("placeholderApi")
        api.setAlignment(Qt.AlignmentFlag.AlignCenter)
        api.setWordWrap(True)

        layout.addStretch(1)
        layout.addWidget(head)
        layout.addWidget(body)
        layout.addSpacing(12)
        layout.addWidget(api)
        layout.addStretch(1)
        return root

    def _api_summary(self) -> str:
        lines = []
        if self.provides:
            lines.append("provides: " + ", ".join(s.name for s in self.provides))
        for role, spec in self.needs.items():
            shapes = " + ".join(s.name for s in as_shapes(spec))
            target = self.wired.get(role)
            arrow = f" -> {target.id}" if target is not None else " (unwired)"
            lines.append(f"needs {role}: {shapes}{arrow}")
        return "\n".join(lines) or "no API yet"
