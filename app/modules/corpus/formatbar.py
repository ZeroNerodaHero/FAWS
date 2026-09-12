"""Writing controls that live in the slot's title bar, next to "corpus #main".

One quiet row: style · font · size · B I U S · align · lists · clear · fit-width.
Groups have a priority; when the slot is too narrow the least important ones
hide (font first, then size, lists, alignment…) so the bar never wraps or clips.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QTextCharFormat
from PySide6.QtWidgets import QComboBox, QFontComboBox, QFrame, QHBoxLayout, QToolButton, QWidget

from .editor import PageEditor
from .styles import STYLES, family_for, style_for

SIZES = [8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 36, 48, 72]

# sits on the slot title bar (#3f3d47); controls are flat until you touch them
STYLE = """
QWidget#corpusHeader { background: transparent; }
QWidget#hdrGroup { background: transparent; }
QToolButton#hdrBtn {
    color: #e0d6c4; background: transparent; border: 1px solid transparent; border-radius: 3px;
    min-width: 20px; max-width: 26px; min-height: 20px; max-height: 20px; padding: 0 2px; font-size: 12px;
}
QToolButton#hdrBtn:hover { background: #5a5763; }
QToolButton#hdrBtn:checked { background: #1a191d; color: #cdb27b; border-color: #26252b; }
QToolButton#hdrBtn:disabled { color: #7d7469; }
QFrame#hdrSep { color: #5a5763; max-width: 1px; margin: 4px 3px; }
QComboBox#hdrCombo, QFontComboBox#hdrCombo {
    color: #e0d6c4; background: #34333a; border: 1px solid #4b4954; border-radius: 3px;
    padding: 0 6px; min-height: 20px; max-height: 20px; font-size: 11px;
}
QComboBox#hdrCombo:hover, QFontComboBox#hdrCombo:hover { border-color: #8b7d73; }
QComboBox#hdrCombo::drop-down, QFontComboBox#hdrCombo::drop-down { border: none; width: 14px; }
QComboBox#hdrCombo QAbstractItemView, QFontComboBox#hdrCombo QAbstractItemView {
    background: #1a191d; color: #e0d6c4; border: 1px solid #3f3d47;
    selection-background-color: #3f3d47; selection-color: #cdb27b; outline: none;
}
QComboBox#hdrCombo QLineEdit { background: transparent; color: #e0d6c4; border: none; padding: 0; }
"""


def _btn(text: str, tip: str, checkable: bool = False) -> QToolButton:
    b = QToolButton()
    b.setText(text)
    b.setToolTip(tip)
    b.setCheckable(checkable)
    b.setObjectName("hdrBtn")
    b.setCursor(Qt.CursorShape.ArrowCursor)
    b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    return b


def _sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.VLine)
    f.setObjectName("hdrSep")
    return f


class Group(QWidget):
    """A run of controls that hides as one unit. Lower priority hides first."""

    def __init__(self, priority: int, *widgets: QWidget, sep: bool = True):
        super().__init__()
        self.setObjectName("hdrGroup")
        self.priority = priority
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(1)
        if sep:
            row.addWidget(_sep())
        for w in widgets:
            row.addWidget(w)


class FormatBar(QWidget):
    def __init__(self, editor: PageEditor, on_fit_width: Callable[[bool], None], parent=None):
        super().__init__(parent)
        self.editor = editor
        self.setObjectName("corpusHeader")
        self.setStyleSheet(STYLE)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self._syncing = False
        self._on_fit_width = on_fit_width

        row = QHBoxLayout(self)
        row.setContentsMargins(6, 0, 0, 0)
        row.setSpacing(1)

        self.style_box = QComboBox()
        self.style_box.setObjectName("hdrCombo")
        for key, st in STYLES.items():
            self.style_box.addItem(st.label, key)
        self.style_box.setFixedWidth(104)
        self.style_box.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.style_box.currentIndexChanged.connect(self._style_changed)

        self.font_box = QFontComboBox()
        self.font_box.setObjectName("hdrCombo")
        self.font_box.setFixedWidth(130)
        self.font_box.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.font_box.currentFontChanged.connect(self._font_changed)

        self.size_box = QComboBox()
        self.size_box.setObjectName("hdrCombo")
        self.size_box.setEditable(True)
        self.size_box.addItems([str(s) for s in SIZES])
        self.size_box.setFixedWidth(54)
        self.size_box.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.size_box.currentTextChanged.connect(self._size_changed)

        self.bold_btn = _btn("B", "bold (Cmd+B)", True)
        f = self.bold_btn.font(); f.setBold(True); self.bold_btn.setFont(f)
        self.italic_btn = _btn("I", "italic (Cmd+I)", True)
        f = self.italic_btn.font(); f.setItalic(True); self.italic_btn.setFont(f)
        self.underline_btn = _btn("U", "underline (Cmd+U)", True)
        f = self.underline_btn.font(); f.setUnderline(True); self.underline_btn.setFont(f)
        self.strike_btn = _btn("S", "strikethrough", True)
        f = self.strike_btn.font(); f.setStrikeOut(True); self.strike_btn.setFont(f)
        self.bold_btn.clicked.connect(self._bold)
        self.italic_btn.clicked.connect(self._italic)
        self.underline_btn.clicked.connect(self._underline)
        self.strike_btn.clicked.connect(self._strike)

        self.align_btns = {
            Qt.AlignmentFlag.AlignLeft: _btn("⯇", "align left", True),
            Qt.AlignmentFlag.AlignHCenter: _btn("☰", "centre", True),
            Qt.AlignmentFlag.AlignRight: _btn("⯈", "align right", True),
            Qt.AlignmentFlag.AlignJustify: _btn("▤", "justify", True),
        }
        for flag, b in self.align_btns.items():
            b.clicked.connect(lambda _=False, fl=flag: self._align(fl))

        self.bullet_btn = _btn("•", "bullet list", True)
        self.number_btn = _btn("1.", "numbered list", True)
        self.bullet_btn.clicked.connect(lambda: self._list("bullet"))
        self.number_btn.clicked.connect(lambda: self._list("number"))

        self.clear_btn = _btn("Tx", "clear formatting (back to the paragraph style)")
        self.clear_btn.clicked.connect(self._clear)

        self.fit_btn = _btn("⇔", "fit the page to the slot width (off = a fixed 8.5in page)", True)
        self.fit_btn.toggled.connect(self._fit_toggled)

        # priority: higher stays longest. Style and B/I/U are the essentials.
        self.groups = [
            Group(9, self.style_box, sep=False),
            Group(2, self.font_box),
            Group(4, self.size_box),
            Group(8, self.bold_btn, self.italic_btn, self.underline_btn, self.strike_btn),
            Group(5, *self.align_btns.values()),
            Group(6, self.bullet_btn, self.number_btn),
            Group(3, self.clear_btn),
            Group(7, self.fit_btn),
        ]
        for g in self.groups:
            row.addWidget(g)
        row.addStretch(1)

        editor.cursorPositionChanged.connect(self.sync)
        editor.currentCharFormatChanged.connect(lambda _: self.sync())
        editor.selectionChanged.connect(self.sync)
        self.sync()

    # --- adaptive width ------------------------------------------------------------------

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit_groups(event.size().width())

    def _fit_groups(self, available: int) -> None:
        spacing = self.layout().spacing()
        widths = {g: g.sizeHint().width() + spacing for g in self.groups}
        total = sum(widths.values()) + 6
        visible = set(self.groups)
        for g in sorted(self.groups, key=lambda g: g.priority):
            if total <= available:
                break
            visible.discard(g)
            total -= widths[g]
        for g in self.groups:
            g.setVisible(g in visible)

    def set_fit_width(self, on: bool) -> None:
        self.fit_btn.blockSignals(True)
        self.fit_btn.setChecked(on)
        self.fit_btn.blockSignals(False)

    # --- editor -> bar --------------------------------------------------------------

    def sync(self) -> None:
        if self._syncing:
            return
        self._syncing = True
        try:
            cursor = self.editor.textCursor()
            block = cursor.block()
            cf = self.editor.currentCharFormat()
            key = self.editor.style_key(block)
            idx = self.style_box.findData(key)
            if idx >= 0:
                self.style_box.setCurrentIndex(idx)
            families = cf.fontFamilies()
            family = families[0] if families else family_for(style_for(key))
            if family != self.font_box.currentFont().family():
                self.font_box.setCurrentFont(QFont(family))
            size = cf.fontPointSize() or style_for(key).size
            self.size_box.setCurrentText(str(int(size) if float(size).is_integer() else size))
            self.bold_btn.setChecked(int(cf.fontWeight()) >= int(QFont.Weight.Bold))
            self.italic_btn.setChecked(cf.fontItalic())
            self.underline_btn.setChecked(cf.fontUnderline())
            self.strike_btn.setChecked(cf.fontStrikeOut())
            align = block.blockFormat().alignment() & Qt.AlignmentFlag.AlignHorizontal_Mask
            if not int(align):
                align = Qt.AlignmentFlag.AlignLeft
            for flag, b in self.align_btns.items():
                b.setChecked(align == flag)
            kind = self.editor.list_kind(block)
            self.bullet_btn.setChecked(kind == "bullet")
            self.number_btn.setChecked(kind == "number")
        finally:
            self._syncing = False

    # --- bar -> editor --------------------------------------------------------------

    def _style_changed(self, idx: int) -> None:
        if self._syncing:
            return
        self.editor.apply_style_to_selection(self.style_box.itemData(idx))
        self.editor.setFocus()

    def _font_changed(self, font: QFont) -> None:
        if self._syncing:
            return
        fmt = QTextCharFormat()
        fmt.setFontFamilies([font.family()])
        self.editor.merge_format(fmt)
        self.editor.setFocus()

    def _size_changed(self, text: str) -> None:
        if self._syncing:
            return
        try:
            size = float(text)
        except ValueError:
            return
        if size <= 0:
            return
        fmt = QTextCharFormat()
        fmt.setFontPointSize(size)
        self.editor.merge_format(fmt)

    def _bold(self, on: bool) -> None:
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Weight.Bold if on else QFont.Weight.Normal)
        self.editor.merge_format(fmt)

    def _italic(self, on: bool) -> None:
        fmt = QTextCharFormat()
        fmt.setFontItalic(on)
        self.editor.merge_format(fmt)

    def _underline(self, on: bool) -> None:
        fmt = QTextCharFormat()
        fmt.setFontUnderline(on)
        self.editor.merge_format(fmt)

    def _strike(self, on: bool) -> None:
        fmt = QTextCharFormat()
        fmt.setFontStrikeOut(on)
        self.editor.merge_format(fmt)

    def _align(self, flag: Qt.AlignmentFlag) -> None:
        self.editor.setAlignment(flag)
        self.sync()
        self.editor.setFocus()

    def _list(self, kind: str) -> None:
        self.editor.toggle_list(kind)
        self.sync()
        self.editor.setFocus()

    def _clear(self) -> None:
        self.editor.clear_inline_formatting()
        self.sync()

    def _fit_toggled(self, on: bool) -> None:
        self._on_fit_width(on)
