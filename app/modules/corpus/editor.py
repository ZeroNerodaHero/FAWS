"""PageEditor: a QTextEdit that looks like a Word page and knows about paragraphs.

Responsibilities kept here (no hub, no shapes):
- every paragraph (QTextBlock) has a stable id in its user data
- paragraph styles from styles.py, applied per block
- anchors ({para, start, end, quote}) <-> cursors, with quote-based re-anchoring
- tagged highlights as extra selections (never part of the saved text)
- bullet / numbered lists
"""

from __future__ import annotations

import secrets
from typing import Iterator

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (QColor, QFont, QKeyEvent, QTextBlock, QTextBlockUserData,
                           QTextCharFormat, QTextCursor, QTextDocument, QTextListFormat)
from PySide6.QtWidgets import QSizePolicy, QTextEdit

from .styles import (HEADING_KEYS, STYLE_PROP, STYLES, base_font, block_format_for,
                     char_format_for, style_for)

PAGE_WIDTH = 816        # 8.5in at 96 dpi
PAGE_MARGIN = 72        # 1in

LIST_STYLES = {
    "bullet": QTextListFormat.Style.ListDisc,
    "number": QTextListFormat.Style.ListDecimal,
}


def new_para_id() -> str:
    return "p_" + secrets.token_hex(3)


class ParaData(QTextBlockUserData):
    def __init__(self, para_id: str):
        super().__init__()
        self.id = para_id


class PageEditor(QTextEdit):
    parasChanged = Signal(list)         # ids of paragraphs touched by an edit

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("corpusPage")
        self.setFrameShape(QTextEdit.Shape.NoFrame)
        self.setAcceptRichText(False)           # paste comes in as text; our styles stay in charge
        self.setCursorWidth(2)
        self.setTabStopDistance(36)
        self.setMaximumWidth(PAGE_WIDTH)
        self.setMinimumWidth(320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        doc = self.document()
        doc.setDocumentMargin(PAGE_MARGIN)
        doc.setDefaultFont(base_font())
        self.setFont(base_font())
        doc.contentsChange.connect(self._on_contents_change)

        self._ud_refs: dict[str, ParaData] = {}     # keep Python wrappers alive for Qt
        self._highlights: dict[str, list[tuple[QTextCursor, QColor]]] = {}
        self.loading = False                        # serializer sets this to silence parasChanged
        self.fit_width = False
        self.apply_style(doc.firstBlock(), "p")
        self.ensure_ids()

    # --- paragraphs ------------------------------------------------------------

    def blocks(self) -> Iterator[QTextBlock]:
        block = self.document().begin()
        while block.isValid():
            yield block
            block = block.next()

    def para_id(self, block: QTextBlock) -> str | None:
        return getattr(block.userData(), "id", None)

    def set_para_id(self, block: QTextBlock, para_id: str) -> None:
        data = ParaData(para_id)
        self._ud_refs[para_id] = data
        block.setUserData(data)

    def ensure_ids(self) -> None:
        """Give every paragraph a unique id. New blocks (Enter, paste, undo) arrive without one."""
        seen: set[str] = set()
        for block in self.blocks():
            pid = self.para_id(block)
            if not pid or pid in seen:
                pid = new_para_id()
                self.set_para_id(block, pid)
            seen.add(pid)

    def block_by_id(self, para_id: str) -> QTextBlock | None:
        for block in self.blocks():
            if self.para_id(block) == para_id:
                return block
        return None

    def style_key(self, block: QTextBlock) -> str:
        key = block.blockFormat().property(STYLE_PROP)
        return key if key in STYLES else "p"

    def apply_style(self, block: QTextBlock, key: str) -> None:
        style = style_for(key)
        cursor = QTextCursor(block)
        cursor.beginEditBlock()
        cursor.mergeBlockFormat(block_format_for(style))
        cf = char_format_for(style)
        cursor.setBlockCharFormat(cf)
        if block.length() > 1:
            cursor.setPosition(block.position())
            cursor.setPosition(block.position() + block.length() - 1, QTextCursor.MoveMode.KeepAnchor)
            cursor.mergeCharFormat(cf)
        cursor.endEditBlock()

    def selected_blocks(self) -> list[QTextBlock]:
        cursor = self.textCursor()
        start = self.document().findBlock(cursor.selectionStart())
        end = self.document().findBlock(cursor.selectionEnd())
        out = [start]
        while start != end:
            start = start.next()
            out.append(start)
        return out

    def apply_style_to_selection(self, key: str) -> None:
        cursor = self.textCursor()
        cursor.beginEditBlock()
        for block in self.selected_blocks():
            self.apply_style(block, key)
        cursor.endEditBlock()

    # --- inline formatting -------------------------------------------------------

    def merge_format(self, fmt: QTextCharFormat) -> None:
        """Word behaviour: no selection + cursor inside a word -> format that word."""
        cursor = self.textCursor()
        if not cursor.hasSelection():
            probe = QTextCursor(cursor)
            probe.select(QTextCursor.SelectionType.WordUnderCursor)
            text = probe.selectedText()
            inside = (text.strip() and probe.selectionStart() < cursor.position() < probe.selectionEnd())
            if inside:
                probe.mergeCharFormat(fmt)
        cursor.mergeCharFormat(fmt)
        self.mergeCurrentCharFormat(fmt)

    def clear_inline_formatting(self) -> None:
        cursor = self.textCursor()
        cursor.beginEditBlock()
        for block in self.selected_blocks():
            self.apply_style(block, self.style_key(block))
        cursor.endEditBlock()

    # --- lists ---------------------------------------------------------------

    def list_kind(self, block: QTextBlock) -> str | None:
        lst = block.textList()
        if lst is None:
            return None
        style = lst.format().style()
        return next((k for k, s in LIST_STYLES.items() if s == style), "bullet")

    def leave_list(self, block: QTextBlock) -> None:
        lst = block.textList()
        if lst is not None:
            lst.remove(block)
        bf = block.blockFormat()
        bf.setIndent(0)
        bf.setObjectIndex(-1)
        QTextCursor(block).setBlockFormat(bf)

    def toggle_list(self, kind: str) -> None:
        cursor = self.textCursor()
        block = cursor.block()
        cursor.beginEditBlock()
        current = self.list_kind(block)
        if current == kind:
            for b in self.selected_blocks():
                if self.list_kind(b) == kind:
                    self.leave_list(b)
        else:
            fmt = QTextListFormat()
            fmt.setStyle(LIST_STYLES[kind])
            fmt.setIndent(1)
            cursor.createList(fmt)
        cursor.endEditBlock()

    # --- geometry ------------------------------------------------------------------

    def set_fit_width(self, on: bool) -> None:
        """Fit: the page stretches across the slot. Off: a fixed 8.5in page, centred."""
        self.fit_width = on
        self.setMaximumWidth(16777215 if on else PAGE_WIDTH)
        self.updateGeometry()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # keep 1in margins on a full page; shrink them proportionally when the slot is narrow
        margin = max(24, round(PAGE_MARGIN * min(1.0, self.viewport().width() / PAGE_WIDTH)))
        if self.document().documentMargin() != margin:
            self.document().setDocumentMargin(margin)

    # --- keys ------------------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (
                event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            cursor = self.textCursor()
            key = self.style_key(cursor.block())
            at_end = cursor.atBlockEnd() and not cursor.hasSelection()
            super().keyPressEvent(event)
            if at_end and key in HEADING_KEYS:
                self.apply_style(self.textCursor().block(), "p")     # Word: paragraph after a heading is Normal
            return
        super().keyPressEvent(event)

    # --- anchors -------------------------------------------------------------------

    def make_anchor(self, cursor: QTextCursor) -> dict | None:
        """Anchor for a cursor whose selection stays inside one paragraph (collapsed is fine)."""
        doc = self.document()
        start_block = doc.findBlock(cursor.selectionStart())
        end_block = doc.findBlock(cursor.selectionEnd())
        if start_block != end_block:
            return None
        start = cursor.selectionStart() - start_block.position()
        end = cursor.selectionEnd() - start_block.position()
        return {"para": self.para_id(start_block), "start": start, "end": end,
                "quote": start_block.text()[start:end]}

    def resolve_anchor(self, anchor: dict) -> dict | None:
        """Corrected anchor for the current text, or None if it's gone (orphaned)."""
        block = self.block_by_id(anchor.get("para", ""))
        quote = anchor.get("quote")
        if block is not None:
            text = block.text()
            start, end = anchor.get("start", 0), anchor.get("end", 0)
            if 0 <= start <= end <= len(text) and (quote is None or text[start:end] == quote):
                return {**anchor, "quote": text[start:end]}
            if quote:
                idx = text.find(quote)
                if idx >= 0:
                    return {**anchor, "start": idx, "end": idx + len(quote)}
        if quote:
            for b in self.blocks():           # paragraph id lost (e.g. recreated by undo)
                idx = b.text().find(quote)
                if idx >= 0:
                    return {**anchor, "para": self.para_id(b), "start": idx, "end": idx + len(quote)}
        return None

    def anchor_cursor(self, anchor: dict) -> QTextCursor | None:
        fixed = self.resolve_anchor(anchor)
        if fixed is None:
            return None
        block = self.block_by_id(fixed["para"])
        cursor = QTextCursor(block)
        cursor.setPosition(block.position() + fixed["start"])
        cursor.setPosition(block.position() + fixed["end"], QTextCursor.MoveMode.KeepAnchor)
        return cursor

    def replace_anchor(self, anchor: dict, text: str) -> bool:
        cursor = self.anchor_cursor(anchor)
        if cursor is None:
            return False
        cursor.beginEditBlock()
        cursor.insertText(text)
        cursor.endEditBlock()
        return True

    def scroll_to_block(self, block: QTextBlock) -> None:
        cursor = QTextCursor(block)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()
        self.setFocus()

    # --- highlights --------------------------------------------------------------

    def highlight(self, anchor: dict, color: str, tag: str) -> bool:
        cursor = self.anchor_cursor(anchor)
        if cursor is None:
            return False
        self._highlights.setdefault(tag, []).append((cursor, QColor(color)))
        self._refresh_highlights()
        return True

    def clear_highlights(self, tag: str) -> None:
        self._highlights.pop(tag, None)
        self._refresh_highlights()

    def _refresh_highlights(self) -> None:
        extras = []
        for entries in self._highlights.values():
            for cursor, color in entries:
                if cursor.isNull() or not cursor.hasSelection():
                    continue
                sel = QTextEdit.ExtraSelection()
                sel.cursor = cursor
                sel.format.setBackground(color)
                extras.append(sel)
        self.setExtraSelections(extras)

    # --- change tracking ---------------------------------------------------------

    def _on_contents_change(self, position: int, removed: int, added: int) -> None:
        if self.loading:
            return
        self.ensure_ids()
        doc = self.document()
        first = doc.findBlock(position)
        last = doc.findBlock(max(position, position + added - 1))
        ids = []
        block = first
        while block.isValid():
            ids.append(self.para_id(block))
            if block == last:
                break
            block = block.next()
        self.parasChanged.emit(ids)

    # --- stats ---------------------------------------------------------------------

    def word_count(self) -> int:
        return len(self.toPlainText().split())

    def headings(self) -> list[dict]:
        out = []
        for block in self.blocks():
            key = self.style_key(block)
            if key in HEADING_KEYS:
                out.append({"id": self.para_id(block), "level": int(key[1]), "text": block.text()})
        return out
