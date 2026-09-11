"""Module base class. Every module on the grid is a subclass of this."""

from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import QWidget


class Module:
    kind: str = "module"          # type name used in project JSON
    title: str = "Module"         # shown in the slot's title bar
    provides: tuple = ()          # shapes this module offers (documentation + self-check)
    needs: dict = {}              # role -> Shape or (Shape, ...)
    events: tuple = ()            # events this module may emit
    min_size: tuple[int, int] = (160, 100)   # pixels (w, h)

    def __init__(self, hub, module_id: str, config: dict | None = None):
        self.hub = hub
        self.id = module_id
        self.config = config or {}
        self.wired: dict[str, object] = {}
        self._widget: QWidget | None = None
        self.self_check()

    # --- lifecycle --------------------------------------------------------

    def widget(self) -> QWidget:
        if self._widget is None:
            self._widget = self.build_widget()
        return self._widget

    def build_widget(self) -> QWidget:
        raise NotImplementedError

    def wire(self, role: str, other) -> None:
        self.wired[role] = other

    def save(self) -> dict:
        return {}

    def load(self, data: dict) -> None:
        pass

    def menu_items(self) -> list[tuple[str, Callable[[], str | None]] | None]:
        """Module-specific entries for the slot's dropdown.

        Each entry is (label, callback); None is a separator. A callback may
        return a string to show in the status bar.
        """
        return []

    # --- helpers ----------------------------------------------------------

    def emit(self, event: str, payload=None) -> None:
        if event not in self.events:
            raise ValueError(f"{self.kind} emits undeclared event {event!r}")
        self.hub.emit(self.id, event, payload)

    def self_check(self) -> None:
        """A module that claims to provide a shape must actually fit it."""
        for shape in self.provides:
            gaps = shape.missing(self)
            if gaps:
                raise TypeError(
                    f"{type(self).__name__} claims {shape} but is missing: {', '.join(gaps)}"
                )
