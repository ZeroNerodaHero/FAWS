"""The Hub: registry + event bus + wiring check. Deliberately small."""

from __future__ import annotations

from collections import defaultdict
from typing import Callable

from .shapes import as_shapes


class WireError(Exception):
    pass


class Hub:
    def __init__(self):
        self._modules: dict[str, object] = {}
        self._listeners: dict[tuple[str, str], list[Callable]] = defaultdict(list)

    # --- registry ---------------------------------------------------------

    def register(self, module) -> None:
        if module.id in self._modules:
            raise ValueError(f"duplicate module id: {module.id!r}")
        self._modules[module.id] = module

    def unregister(self, module_id: str) -> None:
        self._modules.pop(module_id)
        for key in [k for k in self._listeners if k[0] == module_id]:
            del self._listeners[key]

    def get(self, module_id: str):
        return self._modules[module_id]

    def has(self, module_id: str) -> bool:
        return module_id in self._modules

    def modules(self) -> dict[str, object]:
        return dict(self._modules)

    def dependents(self, module_id: str) -> list[tuple[str, str]]:
        """(module_id, role) pairs currently wired to this module."""
        return [(m.id, role) for m in self._modules.values()
                for role, target in m.wired.items() if target.id == module_id]

    def candidates(self, module_or_cls, role: str, exclude: str | None = None) -> list[str]:
        """Module ids that fit every shape `role` needs."""
        shapes = as_shapes(module_or_cls.needs[role])
        return [mid for mid, m in self._modules.items()
                if mid != exclude and all(shape.fits(m) for shape in shapes)]

    # --- events -----------------------------------------------------------

    def on(self, module_id: str, event: str, callback: Callable) -> None:
        self._listeners[(module_id, event)].append(callback)

    def emit(self, module_id: str, event: str, payload=None) -> None:
        for cb in list(self._listeners.get((module_id, event), ())):
            cb(payload)

    # --- wiring -----------------------------------------------------------

    def check_wire(self, module, role: str, target_id: str) -> list[str]:
        """Problems with wiring module.role -> target_id. Empty list = fine."""
        if role not in module.needs:
            return [f"wire error: {module.id}.{role} is not a need of kind {module.kind!r}"]
        target = self._modules.get(target_id)
        if target is None:
            return [f"wire error: {module.id}.{role} -> {target_id!r} (no such module)"]
        if target is module:
            return [f"wire error: {module.id}.{role} cannot point at itself"]
        problems = []
        for shape in as_shapes(module.needs[role]):
            gaps = shape.missing(target)
            if gaps:
                problems.append(
                    f"wire error: {module.id}.{role} -> {target_id}\n"
                    f"  needs {shape}, {target_id} is missing: {', '.join(gaps)}"
                )
        return problems

    def wire(self, module_id: str, role: str, target_id: str) -> None:
        module = self._modules[module_id]
        problems = self.check_wire(module, role, target_id)
        if problems:
            raise WireError("\n".join(problems))
        module.wire(role, self._modules[target_id])

    def wire_all(self, wiring: dict[str, dict[str, str]]) -> None:
        """wiring = {module_id: {role: target_id}}. Checks everything first,
        reports all problems at once, then wires."""
        problems: list[str] = []
        plan: list[tuple[str, str, str]] = []

        for module_id, roles in wiring.items():
            module = self._modules.get(module_id)
            if module is None:
                problems.append(f"wire error: unknown module {module_id!r}")
                continue
            for role, target_id in roles.items():
                found = self.check_wire(module, role, target_id)
                problems += found
                if not found:
                    plan.append((module_id, role, target_id))

        for module_id, module in self._modules.items():
            unwired = set(module.needs) - set(wiring.get(module_id, {}))
            for role in sorted(unwired):
                problems.append(f"wire error: {module_id}.{role} is required but not wired")

        if problems:
            raise WireError("\n".join(problems))
        for module_id, role, target_id in plan:
            self.wire(module_id, role, target_id)
