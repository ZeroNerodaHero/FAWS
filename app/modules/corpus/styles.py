"""Paragraph styles, Word-style: Normal, Heading 1-3, Quote, Code.

A style lives on the block format (undo-safe, copied to the next paragraph on
Enter). Inline bold/italic/etc. is ordinary character formatting on top.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import (QBrush, QColor, QFont, QFontDatabase, QTextBlockFormat, QTextCharFormat,
                           QTextFormat)

STYLE_PROP = int(QTextFormat.Property.UserProperty) + 1     # block format: style key

# first installed family wins; Word's default, its metric-compatible clone, then platform standards
PREFERRED_FAMILIES = ("Calibri", "Carlito", "Helvetica Neue", "Segoe UI", "Arial", "Liberation Sans")
PREFERRED_MONO = ("Menlo", "Consolas", "DejaVu Sans Mono", "Courier New")
DEFAULT_SIZE = 11
_resolved: dict[str, str] = {}


def _pick(candidates: tuple[str, ...], fallback: str) -> str:
    installed = set(QFontDatabase.families())
    return next((f for f in candidates if f in installed), fallback)


def default_family() -> str:
    """Resolved once, after QApplication exists (font database needs it)."""
    if "body" not in _resolved:
        _resolved["body"] = _pick(PREFERRED_FAMILIES, QFont().family())
    return _resolved["body"]


def mono_family() -> str:
    if "mono" not in _resolved:
        _resolved["mono"] = _pick(PREFERRED_MONO, QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family())
    return _resolved["mono"]


@dataclass(frozen=True)
class ParaStyle:
    key: str
    label: str
    size: float
    bold: bool = False
    italic: bool = False
    level: int = 0                      # heading level, 0 = body
    mono: bool = False
    color: str | None = None
    background: str | None = None
    space_before: int = 0
    space_after: int = 8
    left_margin: int = 0


STYLES: dict[str, ParaStyle] = {
    "p":     ParaStyle("p", "Normal", DEFAULT_SIZE),
    "h1":    ParaStyle("h1", "Heading 1", 20, bold=True, level=1, color="#2f5496", space_before=16, space_after=4),
    "h2":    ParaStyle("h2", "Heading 2", 16, bold=True, level=2, color="#2f5496", space_before=12, space_after=4),
    "h3":    ParaStyle("h3", "Heading 3", 13, bold=True, level=3, color="#1f3763", space_before=10, space_after=4),
    "quote": ParaStyle("quote", "Quote", DEFAULT_SIZE, italic=True, color="#595959", left_margin=36, space_after=8),
    "code":  ParaStyle("code", "Code", 10, mono=True, background="#f2f2f2", space_after=8),
}

HEADING_KEYS = ("h1", "h2", "h3")


def style_for(key: str | None) -> ParaStyle:
    return STYLES.get(key or "p", STYLES["p"])


def family_for(style: ParaStyle) -> str:
    return mono_family() if style.mono else default_family()


def block_format_for(style: ParaStyle) -> QTextBlockFormat:
    """Every property is set explicitly so merging it resets the previous style."""
    fmt = QTextBlockFormat()
    fmt.setHeadingLevel(style.level)
    fmt.setTopMargin(style.space_before)
    fmt.setBottomMargin(style.space_after)
    fmt.setLeftMargin(style.left_margin)
    fmt.setBackground(QBrush(QColor(style.background)) if style.background else QBrush(Qt.BrushStyle.NoBrush))
    fmt.setProperty(STYLE_PROP, style.key)
    return fmt


def char_format_for(style: ParaStyle) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setFontFamilies([family_for(style)])
    fmt.setFontPointSize(style.size)
    fmt.setFontWeight(QFont.Weight.Bold if style.bold else QFont.Weight.Normal)
    fmt.setFontItalic(style.italic)
    fmt.setFontUnderline(False)
    fmt.setFontStrikeOut(False)
    fmt.setForeground(QBrush(QColor(style.color)) if style.color else QBrush(QColor("#000000")))
    return fmt


def base_font() -> QFont:
    return QFont(default_family(), DEFAULT_SIZE)
