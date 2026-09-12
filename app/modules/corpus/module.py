"""CorpusModule: the document. Provides TextSource, Headings, Selection, Highlights."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.core.module import Module
from app.core.shapes import Headings, Highlights, Selection, TextSource

from .editor import PageEditor
from .formatbar import FormatBar
from .serialize import load_paras, save_paras
from .styles import STYLES

CHANGED_DEBOUNCE_MS = 150

# the corpus is the one light island in a dark app, on purpose: it's the page
STYLE = """
QWidget#corpusRoot { background: #e9e9ec; }
QTextEdit#corpusPage { background: #ffffff; color: #000000; border: none; selection-background-color: #b4d5fe; }
QLabel#corpusStatus { color: #666; font-size: 11px; padding: 2px 10px; background: #f3f3f3; border-top: 1px solid #d0d0d0; }
"""


class CorpusModule(Module):
    kind = "corpus"
    title = "corpus"
    description = ("The document. A Word-like page: styles, headings, inline formatting, lists. "
                   "Writing controls sit in the slot's title bar.")
    provides = (TextSource, Headings, Selection, Highlights)
    events = ("changed", "headings_changed", "selection_changed")
    min_size = (420, 260)

    def __init__(self, hub, module_id, config=None):
        # the editor exists before the widget so the API works as soon as the module is wired
        self.editor = PageEditor()
        self._pending: set[str] = set()
        self._last_headings: list[dict] | None = None
        self._changed_timer = QTimer()
        self._changed_timer.setSingleShot(True)
        self._changed_timer.setInterval(CHANGED_DEBOUNCE_MS)
        self._changed_timer.timeout.connect(self._flush_changed)
        self.editor.parasChanged.connect(self._on_paras_changed)
        self.editor.cursorPositionChanged.connect(self._on_selection)
        self.editor.selectionChanged.connect(self._on_selection)
        self._status: QLabel | None = None
        self._header: FormatBar | None = None
        super().__init__(hub, module_id, config)
        self.editor.set_fit_width(bool(self.config.get("fit_width", False)))

    # --- widgets ---------------------------------------------------------------------

    def header_widget(self) -> QWidget:
        if self._header is None:
            self._header = FormatBar(self.editor, self.set_fit_width)
            self._header.set_fit_width(self.editor.fit_width)
        return self._header

    def build_widget(self) -> QWidget:
        root = QWidget()
        root.setObjectName("corpusRoot")
        root.setStyleSheet(STYLE)
        col = QVBoxLayout(root)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)

        page_area = QWidget()
        self._page_row = QHBoxLayout(page_area)
        self._page_row.setContentsMargins(0, 0, 0, 0)
        self._page_row.addStretch(1)
        self._page_row.addWidget(self.editor, 0)
        self._page_row.addStretch(1)
        self._apply_page_margins()
        col.addWidget(page_area, 1)

        self._status = QLabel()
        self._status.setObjectName("corpusStatus")
        col.addWidget(self._status)
        self._update_status()
        return root

    def _update_status(self) -> None:
        if self._status is not None:
            paras = self.editor.document().blockCount()
            self._status.setText(f"{self.editor.word_count()} words  ·  {paras} paragraphs  ·  {self.id}")

    def _apply_page_margins(self) -> None:
        # a fixed page floats centred on the grey desk; a fitted page is flush with the slot
        row = getattr(self, "_page_row", None)
        if row is None:
            return
        fit = self.editor.fit_width
        row.setContentsMargins(0, 0 if fit else 12, 0, 0)
        row.setStretch(0, 0 if fit else 1)
        row.setStretch(1, 1 if fit else 0)
        row.setStretch(2, 0 if fit else 1)

    def set_fit_width(self, on: bool) -> str:
        on = bool(on)
        self.editor.set_fit_width(on)
        self.config["fit_width"] = on
        if self._header is not None:
            self._header.set_fit_width(on)
        self._apply_page_margins()
        self.mark_dirty()
        return f"{self.id}: page {'fits the slot width' if on else 'is a fixed 8.5in page'}"

    def menu_items(self):
        fit = self.editor.fit_width
        return [
            (("✓ " if fit else "    ") + "fit page to slot width", lambda: self.set_fit_width(not fit)),
            None,
            ("word count", lambda: f"{self.id}: {self.editor.word_count()} words, "
                                   f"{self.editor.document().blockCount()} paragraphs"),
            ("select all", lambda: self.editor.selectAll()),
            ("clear formatting in selection", lambda: self.editor.clear_inline_formatting()),
        ]

    # --- events -----------------------------------------------------------------------

    def _on_paras_changed(self, ids: list[str]) -> None:
        self._pending.update(i for i in ids if i)
        self._changed_timer.start()

    def _flush_changed(self) -> None:
        ids = sorted(self._pending)
        self._pending.clear()
        self._update_status()
        self.mark_dirty()
        self.emit("changed", {"paras": ids})
        headings = self.editor.headings()
        if headings != self._last_headings:
            self._last_headings = headings
            self.emit("headings_changed", headings)

    def _on_selection(self) -> None:
        self.emit("selection_changed", self.get_selection())

    # --- TextSource -----------------------------------------------------------------

    def get_text(self) -> str:
        return self.editor.toPlainText()

    def get_paragraphs(self) -> list[dict]:
        return [{"id": self.editor.para_id(b), "style": self.editor.style_key(b), "text": b.text()}
                for b in self.editor.blocks()]

    def get_range(self, anchor: dict) -> str:
        cursor = self.editor.anchor_cursor(anchor)
        return cursor.selectedText() if cursor is not None else ""

    def replace_range(self, anchor: dict, text: str) -> bool:
        return self.editor.replace_anchor(anchor, text)

    def resolve_anchor(self, anchor: dict) -> dict | None:
        return self.editor.resolve_anchor(anchor)

    # --- Headings ---------------------------------------------------------------------

    def get_headings(self) -> list[dict]:
        return self.editor.headings()

    def scroll_to(self, para_id: str) -> bool:
        block = self.editor.block_by_id(para_id)
        if block is None:
            return False
        self.editor.scroll_to_block(block)
        return True

    def set_style(self, para_id: str, style: str) -> bool:
        block = self.editor.block_by_id(para_id)
        if block is None or style not in STYLES:
            return False
        self.editor.apply_style(block, style)
        return True

    # --- Selection ----------------------------------------------------------------------

    def get_selection(self) -> dict | None:
        """Anchor of the selection; collapsed (start == end) when nothing is selected.
        None if the selection spans several paragraphs."""
        return self.editor.make_anchor(self.editor.textCursor())

    # --- Highlights -----------------------------------------------------------------------

    def highlight(self, anchor: dict, color: str, tag: str) -> bool:
        return self.editor.highlight(anchor, color, tag)

    def clear_highlights(self, tag: str) -> None:
        self.editor.clear_highlights(tag)

    # --- save / load ------------------------------------------------------------------------

    def save(self) -> dict:
        return {"paras": save_paras(self.editor)}

    def load(self, data: dict) -> None:
        load_paras(self.editor, data.get("paras", []))
        self._last_headings = self.editor.headings()
        self._update_status()
