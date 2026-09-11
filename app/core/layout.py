"""Layout model: slots as rectangles on a 1000x1000 grid. Pure Python, no Qt.

Invariant: the slots tile the grid exactly. Every operation here either keeps
that true or returns None to say "refused".
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable

GRID = 1000
SNAP_UNITS = 25

SIDES = ("left", "right", "top", "bottom")


class LayoutError(Exception):
    pass


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int

    @property
    def right(self) -> int:
        return self.x + self.w

    @property
    def bottom(self) -> int:
        return self.y + self.h

    @property
    def area(self) -> int:
        return self.w * self.h

    def overlaps(self, other: Rect) -> bool:
        return (self.x < other.right and other.x < self.right
                and self.y < other.bottom and other.y < self.bottom)

    def span(self, axis: str) -> tuple[int, int]:
        """Extent along the line direction. axis 'v' = vertical line, so span is y."""
        return (self.y, self.bottom) if axis == "v" else (self.x, self.right)

    def edge_pos(self, axis: str, side: str) -> int:
        """Coordinate of one edge. side is 'near' (x/y) or 'far' (right/bottom)."""
        if axis == "v":
            return self.x if side == "near" else self.right
        return self.y if side == "near" else self.bottom

    def to_list(self) -> list[int]:
        return [self.x, self.y, self.w, self.h]

    @classmethod
    def from_list(cls, v) -> Rect:
        if not (isinstance(v, (list, tuple)) and len(v) == 4):
            raise LayoutError(f"rect must be [x, y, w, h], got {v!r}")
        return cls(*(int(n) for n in v))


@dataclass(eq=False)
class Slot:
    module: str | None
    rect: Rect


@dataclass(frozen=True)
class Edge:
    """A shared boundary between slots.

    axis 'v': vertical line at x=pos. axis 'h': horizontal line at y=pos.
    a..b is the segment along the line. Slots on the low side have this as
    their far edge, slots on the high side have it as their near edge.
    """
    axis: str
    pos: int
    a: int
    b: int


MinUnits = Callable[[Slot], tuple[int, int]]


def _spans_overlap(a1: int, b1: int, a2: int, b2: int) -> bool:
    return a1 < b2 and a2 < b1


def _half(length: int) -> int:
    """Split point for a length, snapped to the grid step when that leaves room."""
    snapped = round(length / 2 / SNAP_UNITS) * SNAP_UNITS
    return snapped if 0 < snapped < length else length // 2


class LayoutModel:
    def __init__(self, slots: list[Slot], check: bool = True):
        self.slots = slots
        if check:
            self.validate()

    # --- (de)serialisation -----------------------------------------------

    @classmethod
    def from_json(cls, data: dict) -> LayoutModel:
        grid = data.get("grid", [GRID, GRID])
        if list(grid) != [GRID, GRID]:
            raise LayoutError(f"only a {GRID}x{GRID} grid is supported, got {grid}")
        slots = [Slot(s.get("module"), Rect.from_list(s["rect"])) for s in data.get("slots", [])]
        if not slots:
            raise LayoutError("layout has no slots")
        return cls(slots)

    def to_json(self) -> dict:
        return {
            "grid": [GRID, GRID],
            "slots": [{"module": s.module, "rect": s.rect.to_list()} for s in self.slots],
        }

    # --- invariant --------------------------------------------------------

    def validate(self) -> None:
        for s in self.slots:
            r = s.rect
            if r.w <= 0 or r.h <= 0:
                raise LayoutError(f"slot {s.module!r} has non-positive size: {r.to_list()}")
            if r.x < 0 or r.y < 0 or r.right > GRID or r.bottom > GRID:
                raise LayoutError(f"slot {s.module!r} is outside the grid: {r.to_list()}")
        for i, a in enumerate(self.slots):
            for b in self.slots[i + 1:]:
                if a.rect.overlaps(b.rect):
                    raise LayoutError(
                        f"slots {a.module!r} {a.rect.to_list()} and "
                        f"{b.module!r} {b.rect.to_list()} overlap"
                    )
        total = sum(s.rect.area for s in self.slots)
        if total != GRID * GRID:
            raise LayoutError(
                f"slots cover {total} of {GRID * GRID} units; there is a hole of "
                f"{GRID * GRID - total} units"
            )

    def index(self, slot: Slot) -> int:
        for i, s in enumerate(self.slots):
            if s is slot:
                return i
        raise ValueError("slot is not in this layout")

    def find(self, module_id: str) -> Slot | None:
        return next((s for s in self.slots if s.module == module_id), None)

    # --- edge queries -----------------------------------------------------

    def edge_between(self, low: Slot, high: Slot) -> Edge | None:
        """The boundary two slots share, if any. `low` is left/above `high`."""
        for axis in ("v", "h"):
            if low.rect.edge_pos(axis, "far") != high.rect.edge_pos(axis, "near"):
                continue
            a1, b1 = low.rect.span(axis)
            a2, b2 = high.rect.span(axis)
            if _spans_overlap(a1, b1, a2, b2):
                return Edge(axis, low.rect.edge_pos(axis, "far"), max(a1, a2), min(b1, b2))
        return None

    def slots_on_edge(self, edge: Edge) -> tuple[list[Slot], list[Slot], Edge]:
        """Everything touching the edge, with the segment grown to closure.

        Grabbing a short segment must drag every slot whose edge overlaps it,
        and those slots' full extents in turn pull in more slots (pinwheel
        overhangs). Iterate until the segment stops growing.
        """
        a, b = edge.a, edge.b
        while True:
            low = [s for s in self.slots
                   if s.rect.edge_pos(edge.axis, "far") == edge.pos
                   and _spans_overlap(*s.rect.span(edge.axis), a, b)]
            high = [s for s in self.slots
                    if s.rect.edge_pos(edge.axis, "near") == edge.pos
                    and _spans_overlap(*s.rect.span(edge.axis), a, b)]
            spans = [s.rect.span(edge.axis) for s in low + high]
            if not spans:
                return [], [], edge
            na, nb = min(a for a, _ in spans), max(b for _, b in spans)
            if (na, nb) == (a, b):
                return low, high, Edge(edge.axis, edge.pos, a, b)
            a, b = na, nb

    def snap_targets(self, axis: str, exclude_pos: int) -> list[int]:
        targets = set(range(0, GRID + 1, SNAP_UNITS))
        for s in self.slots:
            targets.add(s.rect.edge_pos(axis, "near"))
            targets.add(s.rect.edge_pos(axis, "far"))
        targets.discard(exclude_pos)
        return sorted(targets)

    # --- the one operation ------------------------------------------------

    def sweep(self, edge: Edge, new_pos: int,
              min_units: MinUnits | None = None) -> dict[int, Rect] | None:
        """Move an edge to new_pos. Returns {slot_index: new_rect} or None if refused.

        Refused if any touched slot would shrink below 1 unit or below
        min_units(slot). A side may be empty (that's how holes get filled).
        """
        low, high, edge = self.slots_on_edge(edge)
        if not low and not high:
            return None
        changes: dict[int, Rect] = {}
        for s in low:
            r = s.rect
            nr = replace(r, w=new_pos - r.x) if edge.axis == "v" else replace(r, h=new_pos - r.y)
            changes[self.index(s)] = nr
        for s in high:
            r = s.rect
            if edge.axis == "v":
                nr = replace(r, x=new_pos, w=r.right - new_pos)
            else:
                nr = replace(r, y=new_pos, h=r.bottom - new_pos)
            changes[self.index(s)] = nr
        if not self._sizes_ok(changes, min_units):
            return None
        return changes

    def _sizes_ok(self, changes: dict[int, Rect], min_units: MinUnits | None) -> bool:
        for idx, nr in changes.items():
            if nr.w < 1 or nr.h < 1:
                return False
            if min_units is not None:
                mw, mh = min_units(self.slots[idx])
                if nr.w < mw or nr.h < mh:
                    return False
        return True

    def apply(self, changes: dict[int, Rect]) -> None:
        for idx, nr in changes.items():
            self.slots[idx].rect = nr
        self.validate()

    # --- split ------------------------------------------------------------

    def split_rects(self, idx: int, side: str) -> tuple[Rect, Rect] | None:
        """(kept rect, new rect) if slot idx were cut with the new half on `side`.
        Pure; nothing changes. None if there's no room to cut at all."""
        if side not in SIDES:
            raise ValueError(f"bad side {side!r}")
        r = self.slots[idx].rect
        if side in ("left", "right"):
            if r.w < 2:
                return None
            cut = _half(r.w)
            first, second = replace(r, w=cut), replace(r, x=r.x + cut, w=r.w - cut)
            return (second, first) if side == "left" else (first, second)
        if r.h < 2:
            return None
        cut = _half(r.h)
        first, second = replace(r, h=cut), replace(r, y=r.y + cut, h=r.h - cut)
        return (second, first) if side == "top" else (first, second)

    def can_split(self, idx: int, side: str, keep_min: tuple[int, int] | None = None,
                  new_min: tuple[int, int] | None = None) -> bool:
        rects = self.split_rects(idx, side)
        if rects is None:
            return False
        for rect, mn in zip(rects, (keep_min, new_min)):
            if mn is not None and (rect.w < mn[0] or rect.h < mn[1]):
                return False
        return True

    def split(self, idx: int, side: str, keep_min: tuple[int, int] | None = None,
              new_min: tuple[int, int] | None = None) -> Slot | None:
        """Cut slot idx in two; the new empty slot goes on `side`. None if too small."""
        if not self.can_split(idx, side, keep_min, new_min):
            return None
        keep, new = self.split_rects(idx, side)
        self.slots[idx].rect = keep
        new_slot = Slot(None, new)
        self.slots.append(new_slot)
        self.validate()
        return new_slot

    # --- close ------------------------------------------------------------

    def fill_hole(self, idx: int, min_units: MinUnits | None = None) -> bool:
        """Remove slot idx and grow neighbours into the hole by sweeping one of
        its edges across it. Returns False (and changes nothing) if no sweep is
        valid; the caller then keeps the slot as an empty one.
        """
        hole = self.slots[idx]
        rest = [s for i, s in enumerate(self.slots) if i != idx]
        h = hole.rect
        trials = (
            (Edge("h", h.y, h.x, h.right), h.bottom),      # slots above grow down
            (Edge("h", h.bottom, h.x, h.right), h.y),      # slots below grow up
            (Edge("v", h.x, h.y, h.bottom), h.right),      # slots left grow right
            (Edge("v", h.right, h.y, h.bottom), h.x),      # slots right grow left
        )
        tmp = LayoutModel(rest, check=False)
        best: tuple[tuple[int, int], dict[int, Rect]] | None = None
        for edge, new_pos in trials:
            changes = tmp.sweep(edge, new_pos, min_units)
            if not changes:
                continue
            try:
                LayoutModel([Slot(s.module, changes.get(i, s.rect)) for i, s in enumerate(rest)])
            except LayoutError:
                continue
            _, _, closure = tmp.slots_on_edge(edge)
            score = (len(changes), -(closure.b - closure.a))
            if best is None or score < best[0]:
                best = (score, changes)
        if best is None:
            return False
        for i, nr in best[1].items():
            rest[i].rect = nr
        self.slots = rest
        self.validate()
        return True
