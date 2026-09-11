"""Project: the modules, their wiring, the layout, and the file they live in."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from .hub import Hub
from .layout import LayoutModel
from .module import Module

FORMAT_VERSION = 1


class ProjectError(Exception):
    pass


class MissingModule(Module):
    """Stands in for a module kind this build doesn't have.

    Keeps the data it was given so saving writes it back untouched.
    """

    kind = "missing"
    title = "missing module"

    def __init__(self, hub, module_id, config=None, *, wanted_kind: str):
        self.wanted_kind = wanted_kind
        self._data: dict = {}
        super().__init__(hub, module_id, config)

    def build_widget(self):
        label = QLabel(f"module kind '{self.wanted_kind}'\nis not available in this build")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setObjectName("placeholderText")
        return label

    def save(self) -> dict:
        return self._data

    def load(self, data: dict) -> None:
        self._data = data


@dataclass
class Project:
    path: Path | None
    title: str
    hub: Hub
    layout: LayoutModel
    specs: dict[str, dict] = field(default_factory=dict)   # id -> {kind, wire, config}

    # --- modules ----------------------------------------------------------

    def new_module_id(self, kind: str) -> str:
        if kind not in self.specs and not self.hub.has(kind):
            return kind
        taken = {int(m.group(1)) for mid in self.specs
                 if (m := re.fullmatch(re.escape(kind) + r"(\d+)", mid))}
        n = 2
        while n in taken:
            n += 1
        return f"{kind}{n}"

    def add_module(self, cls: type[Module], wiring: dict[str, str]) -> Module:
        """Create, register and wire a new instance. Raises WireError if a wire is bad."""
        module_id = self.new_module_id(cls.kind)
        module = cls(self.hub, module_id)
        self.hub.register(module)
        try:
            for role, target_id in wiring.items():
                self.hub.wire(module_id, role, target_id)
        except Exception:
            self.hub.unregister(module_id)
            raise
        self.specs[module_id] = {"kind": cls.kind, "wire": dict(wiring)}
        return module

    def remove_module(self, module_id: str) -> None:
        deps = self.hub.dependents(module_id)
        if deps:
            who = ", ".join(f"{m}.{role}" for m, role in deps)
            raise ProjectError(f"cannot remove {module_id}: still used by {who}")
        self.hub.unregister(module_id)
        self.specs.pop(module_id, None)
        for slot in self.layout.slots:
            if slot.module == module_id:
                slot.module = None

    def rewire(self, module_id: str, role: str, target_id: str) -> None:
        self.hub.wire(module_id, role, target_id)
        self.specs[module_id].setdefault("wire", {})[role] = target_id

    # --- file -------------------------------------------------------------

    def to_json(self) -> dict:
        modules = {}
        for module_id, spec in self.specs.items():
            module = self.hub.get(module_id)
            kind = module.wanted_kind if isinstance(module, MissingModule) else module.kind
            entry = {"kind": kind}
            if spec.get("wire"):
                entry["wire"] = spec["wire"]
            if spec.get("config"):
                entry["config"] = spec["config"]
            entry["data"] = module.save()
            modules[module_id] = entry
        return {
            "faws": FORMAT_VERSION,
            "title": self.title,
            "layout": self.layout.to_json(),
            "modules": modules,
        }

    def save(self, path: str | Path | None = None) -> Path:
        path = Path(path) if path else self.path
        if path is None:
            raise ProjectError("no path to save to")
        tmp = path.with_name(path.name + "~")
        tmp.write_text(json.dumps(self.to_json(), indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, path)
        self.path = path
        return path


def load_project(path: str | Path, registry: dict[str, type[Module]]) -> Project:
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ProjectError(f"cannot read {path}: {e}") from e

    version = data.get("faws")
    if version != FORMAT_VERSION:
        raise ProjectError(f"{path}: unsupported format version {version!r}")

    hub = Hub()
    specs: dict[str, dict] = data.get("modules", {})
    for module_id, spec in specs.items():
        kind = spec.get("kind")
        cls = registry.get(kind)
        if cls is None:
            module = MissingModule(hub, module_id, spec.get("config"), wanted_kind=kind)
        else:
            module = cls(hub, module_id, spec.get("config"))
        module.load(spec.get("data", {}))
        hub.register(module)

    hub.wire_all({mid: spec.get("wire", {}) for mid, spec in specs.items()})

    layout = LayoutModel.from_json(data.get("layout", {}))
    seen: set[str] = set()
    for slot in layout.slots:
        if slot.module is not None and (slot.module not in specs or slot.module in seen):
            slot.module = None      # unknown or duplicated id -> empty slot
        if slot.module is not None:
            seen.add(slot.module)

    return Project(path=path, title=data.get("title", path.stem), hub=hub,
                   layout=layout, specs=specs)
