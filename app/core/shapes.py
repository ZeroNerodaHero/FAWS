"""Shapes: a named checklist of functions + events a module must have.

A module "fits" a shape if it has every function (callable attribute) and
declares every event. Names are labels; the check is structural.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Shape:
    name: str
    funcs: tuple[str, ...] = ()
    events: tuple[str, ...] = ()

    def missing(self, obj) -> list[str]:
        """Everything `obj` lacks to fit this shape. Empty list = fits."""
        gaps = [f for f in self.funcs if not callable(getattr(obj, f, None))]
        declared = set(getattr(obj, "events", ()))
        gaps += [f"event:{e}" for e in self.events if e not in declared]
        return gaps

    def fits(self, obj) -> bool:
        return not self.missing(obj)

    def __str__(self) -> str:
        return self.name


# --- built-in shapes ------------------------------------------------------

TextSource = Shape(
    "TextSource",
    funcs=("get_text", "get_paragraphs", "get_range", "replace_range", "resolve_anchor"),
    events=("changed",),
)

Headings = Shape(
    "Headings",
    funcs=("get_headings", "scroll_to", "set_style"),
    events=("headings_changed",),
)

Selection = Shape(
    "Selection",
    funcs=("get_selection",),
    events=("selection_changed",),
)

Highlights = Shape(
    "Highlights",
    funcs=("highlight", "clear_highlights"),
)

Comments = Shape(
    "Comments",
    funcs=("get_comments", "add_comment", "resolve_comment"),
    events=("comments_changed",),
)


def as_shapes(spec) -> tuple[Shape, ...]:
    """`needs` values may be one Shape or several. Normalise to a tuple."""
    if isinstance(spec, Shape):
        return (spec,)
    return tuple(spec)
