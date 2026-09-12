"""Notes: many small plain-text notes. List on top, the selected note below.

Provides TextSource over the selected note (paragraph = line), so comments or
an AI module can read a note without a special case.
"""

from __future__ import annotations

import secrets

from PySide6.QtCore import QRect, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QMessageBox, QPlainTextEdit, QSplitter, QStyle, QStyledItemDelegate,
                               QToolButton, QVBoxLayout, QWidget)

from app.core.module import Module
from app.core.shapes import TextSource

NOTE_ROLE = int(Qt.ItemDataRole.UserRole) + 1
DIRTY_DEBOUNCE_MS = 250

STYLE = """
QWidget#notesRoot { background: #1a191d; }
QListWidget#notesList { background: #1a191d; border: none; outline: none; }
QListWidget#notesList::item { border: none; }
QSplitter#notesSplit::handle { background: #26252b; height: 1px; }
QWidget#noteEditor { background: #16151a; }
QLineEdit#noteTitle {
    background: transparent; color: #cdb27b; border: none; border-bottom: 1px solid #26252b;
    font-size: 14px; font-weight: 600; padding: 6px 10px 4px 10px;
}
QPlainTextEdit#noteBody {
    background: transparent; color: #e0d6c4; border: none; padding: 4px 6px; font-size: 13px;
    selection-background-color: #3f3d47;
}
QLabel#notesEmpty { color: #6b6360; font-size: 12px; }
QWidget#notesHeader { background: transparent; }
QLineEdit#notesFilter {
    background: #34333a; color: #e0d6c4; border: 1px solid #4b4954; border-radius: 3px;
    padding: 0 6px; min-height: 20px; max-height: 20px; font-size: 11px;
}
QLineEdit#notesFilter:focus { border-color: #8b7d73; }
QToolButton#hdrBtn {
    color: #e0d6c4; background: transparent; border: 1px solid transparent; border-radius: 3px;
    min-width: 20px; max-width: 24px; min-height: 20px; max-height: 20px; font-size: 14px;
}
QToolButton#hdrBtn:hover { background: #5a5763; }
QToolButton#hdrBtn:disabled { color: #7d7469; }
"""


def new_note_id() -> str:
    return "n_" + secrets.token_hex(3)


class NoteDelegate(QStyledItemDelegate):
    """Two lines per note: title in the accent, first body line dimmed."""

    ROW_H = 40

    def sizeHint(self, option, index) -> QSize:
        return QSize(60, self.ROW_H)      # width is whatever the list gives; never forces a scrollbar

    def paint(self, painter: QPainter, option, index) -> None:
        note = index.data(NOTE_ROLE)
        r = option.rect
        painter.save()
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(r, QColor("#3f3d47"))
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(r, QColor("#232227"))
        painter.setPen(QPen(QColor("#26252b")))
        painter.drawLine(r.left() + 10, r.bottom(), r.right() - 10, r.bottom())

        title = note["title"].strip() or "untitled"
        preview = next((ln.strip() for ln in note["body"].splitlines() if ln.strip()), "")
        f = painter.font()
        f.setPointSize(12); f.setBold(True)
        painter.setFont(f)
        painter.setPen(QColor("#cdb27b"))
        fm = painter.fontMetrics()
        painter.drawText(QRect(r.left() + 12, r.top() + 5, r.width() - 24, fm.height()),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         fm.elidedText(title, Qt.TextElideMode.ElideRight, r.width() - 24))
        f.setPointSize(11); f.setBold(False)
        painter.setFont(f)
        painter.setPen(QColor("#8b7d73"))
        fm = painter.fontMetrics()
        painter.drawText(QRect(r.left() + 12, r.top() + 21, r.width() - 24, fm.height()),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         fm.elidedText(preview or "—", Qt.TextElideMode.ElideRight, r.width() - 24))
        painter.restore()


class NotesHeader(QWidget):
    """Title-bar controls: filter box, new, delete."""

    def __init__(self, module: NotesModule):
        super().__init__()
        self.setObjectName("notesHeader")
        self.setStyleSheet(STYLE)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        row = QHBoxLayout(self)
        row.setContentsMargins(6, 0, 0, 0)
        row.setSpacing(2)
        self.filter = QLineEdit()
        self.filter.setObjectName("notesFilter")
        self.filter.setPlaceholderText("filter…")
        self.filter.setClearButtonEnabled(True)
        self.filter.setMaximumWidth(160)
        self.filter.textChanged.connect(module.set_filter)
        self.add_btn = QToolButton()
        self.add_btn.setObjectName("hdrBtn")
        self.add_btn.setText("+")
        self.add_btn.setToolTip("new note")
        self.add_btn.setCursor(Qt.CursorShape.ArrowCursor)
        self.add_btn.clicked.connect(lambda: module.new_note())
        self.del_btn = QToolButton()
        self.del_btn.setObjectName("hdrBtn")
        self.del_btn.setText("−")
        self.del_btn.setToolTip("delete selected note")
        self.del_btn.setCursor(Qt.CursorShape.ArrowCursor)
        self.del_btn.clicked.connect(lambda: module.delete_selected())
        row.addWidget(self.filter, 1)
        row.addWidget(self.add_btn)
        row.addWidget(self.del_btn)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.filter.setVisible(event.size().width() > 120)


class NotesModule(Module):
    kind = "notes"
    title = "notes"
    description = "Scratch space. Many small notes, no structure imposed. List on top, editor below."
    provides = (TextSource,)
    events = ("changed",)
    min_size = (180, 160)

    def __init__(self, hub, module_id, config=None):
        self.notes: list[dict] = []
        self.selected: str | None = None
        self._filter = ""
        self._header: NotesHeader | None = None
        self._list: QListWidget | None = None
        self._title: QLineEdit | None = None
        self._body: QPlainTextEdit | None = None
        self._editor_box: QWidget | None = None
        self._empty: QLabel | None = None
        self._syncing = False
        self._dirty = QTimer()
        self._dirty.setSingleShot(True)
        self._dirty.setInterval(DIRTY_DEBOUNCE_MS)
        self._dirty.timeout.connect(self._flush_dirty)
        super().__init__(hub, module_id, config)

    # --- widgets ------------------------------------------------------------------

    def header_widget(self) -> QWidget:
        if self._header is None:
            self._header = NotesHeader(self)
        return self._header

    def build_widget(self) -> QWidget:
        root = QWidget()
        root.setObjectName("notesRoot")
        root.setStyleSheet(STYLE)
        col = QVBoxLayout(root)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)

        split = QSplitter(Qt.Orientation.Vertical)
        split.setObjectName("notesSplit")
        split.setChildrenCollapsible(False)

        self._list = QListWidget()
        self._list.setObjectName("notesList")
        self._list.setItemDelegate(NoteDelegate(self._list))
        self._list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self._list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._list.setMouseTracking(True)
        self._list.setUniformItemSizes(True)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setTextElideMode(Qt.TextElideMode.ElideRight)
        self._list.currentItemChanged.connect(self._on_current_changed)
        self._list.model().rowsMoved.connect(self._on_rows_moved)
        split.addWidget(self._list)

        self._editor_box = QWidget()
        self._editor_box.setObjectName("noteEditor")
        ecol = QVBoxLayout(self._editor_box)
        ecol.setContentsMargins(0, 0, 0, 0)
        ecol.setSpacing(0)
        self._title = QLineEdit()
        self._title.setObjectName("noteTitle")
        self._title.setPlaceholderText("title")
        self._title.textEdited.connect(self._on_title_edited)
        self._body = QPlainTextEdit()
        self._body.setObjectName("noteBody")
        self._body.setPlaceholderText("write…")
        self._body.setFrameShape(QPlainTextEdit.Shape.NoFrame)
        self._body.textChanged.connect(self._on_body_changed)
        self._empty = QLabel("no notes yet  ·  press + in the title bar")
        self._empty.setObjectName("notesEmpty")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ecol.addWidget(self._title)
        ecol.addWidget(self._body, 1)
        ecol.addWidget(self._empty, 1)
        split.addWidget(self._editor_box)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 2)
        col.addWidget(split, 1)

        self._rebuild_list()
        self._show_selected()
        return root

    # --- list <-> notes -------------------------------------------------------------

    def _visible_notes(self) -> list[dict]:
        q = self._filter.lower()
        if not q:
            return list(self.notes)
        return [n for n in self.notes if q in n["title"].lower() or q in n["body"].lower()]

    def _rebuild_list(self) -> None:
        if self._list is None:
            return
        self._syncing = True
        try:
            self._list.clear()
            current = None
            for note in self._visible_notes():
                item = QListWidgetItem()
                item.setData(NOTE_ROLE, note)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsDropEnabled)
                self._list.addItem(item)
                if note["id"] == self.selected:
                    current = item
            if current is not None:
                self._list.setCurrentItem(current)
        finally:
            self._syncing = False

    def _refresh_item(self, note: dict) -> None:
        if self._list is None:
            return
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.data(NOTE_ROLE)["id"] == note["id"]:
                item.setData(NOTE_ROLE, note)
                return

    def _on_current_changed(self, current: QListWidgetItem | None, _prev) -> None:
        if self._syncing:
            return
        self.selected = current.data(NOTE_ROLE)["id"] if current is not None else None
        self._show_selected()

    def _on_rows_moved(self, *_args) -> None:
        # the list is the truth for order among the visible notes; hidden ones keep their place
        visible_order = [self._list.item(i).data(NOTE_ROLE)["id"] for i in range(self._list.count())]
        by_id = {n["id"]: n for n in self.notes}
        visible_set = set(visible_order)
        it = iter(visible_order)
        self.notes = [by_id[next(it)] if n["id"] in visible_set else n for n in self.notes]
        self._touch()

    def _show_selected(self) -> None:
        if self._title is None:
            return
        note = self.note(self.selected) if self.selected else None
        has = note is not None
        self._title.setVisible(has)
        self._body.setVisible(has)
        self._empty.setVisible(not has)
        if self._header is not None:
            self._header.del_btn.setEnabled(has)
        if not has:
            return
        self._syncing = True
        try:
            self._title.setText(note["title"])
            if self._body.toPlainText() != note["body"]:
                self._body.setPlainText(note["body"])
        finally:
            self._syncing = False

    def _on_title_edited(self, text: str) -> None:
        note = self.note(self.selected)
        if note is None or self._syncing:
            return
        note["title"] = text
        self._refresh_item(note)
        self._touch()

    def _on_body_changed(self) -> None:
        note = self.note(self.selected)
        if note is None or self._syncing:
            return
        note["body"] = self._body.toPlainText()
        self._refresh_item(note)
        self._touch()

    def _touch(self) -> None:
        self._dirty.start()

    def _flush_dirty(self) -> None:
        self.mark_dirty()
        self.emit("changed", {"note": self.selected})

    # --- actions --------------------------------------------------------------------

    def note(self, note_id: str | None) -> dict | None:
        return next((n for n in self.notes if n["id"] == note_id), None)

    def new_note(self, title: str = "", body: str = "") -> dict:
        note = {"id": new_note_id(), "title": title, "body": body}
        self.notes.insert(0, note)
        self.selected = note["id"]
        self._filter_reset_if_hiding(note)
        self._rebuild_list()
        self._show_selected()
        if self._title is not None:
            self._title.setFocus()
        self._touch()
        return note

    def _filter_reset_if_hiding(self, note: dict) -> None:
        if self._filter and note not in self._visible_notes():
            self._filter = ""
            if self._header is not None:
                self._header.filter.blockSignals(True)
                self._header.filter.clear()
                self._header.filter.blockSignals(False)

    def delete_selected(self) -> str | None:
        note = self.note(self.selected)
        if note is None:
            return None
        parent = self._list.window() if self._list is not None else None
        label = note["title"].strip() or "this untitled note"
        answer = QMessageBox.question(parent, "delete note", f"Delete “{label}”? There is no undo.",
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                      QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return None
        idx = self.notes.index(note)
        self.notes.remove(note)
        rest = self.notes
        self.selected = rest[min(idx, len(rest) - 1)]["id"] if rest else None
        self._rebuild_list()
        self._show_selected()
        self._touch()
        return f"{self.id}: deleted “{label}”"

    def set_filter(self, text: str) -> None:
        self._filter = text.strip()
        self._rebuild_list()
        if self._list is not None and self._list.currentItem() is None and self._list.count():
            self._list.setCurrentRow(0)

    def menu_items(self):
        return [
            ("new note", lambda: (self.new_note(), f"{self.id}: new note")[1]),
            ("delete selected note", self.delete_selected),
            None,
            ("note count", lambda: f"{self.id}: {len(self.notes)} notes"),
        ]

    # --- TextSource over the selected note (paragraph = line) ----------------------

    def _lines(self) -> list[str]:
        note = self.note(self.selected)
        return note["body"].split("\n") if note else []

    def _para_id(self, i: int) -> str:
        return f"{self.selected}:{i}"

    def get_text(self) -> str:
        note = self.note(self.selected)
        return note["body"] if note else ""

    def get_paragraphs(self) -> list[dict]:
        return [{"id": self._para_id(i), "style": "p", "text": ln} for i, ln in enumerate(self._lines())]

    def _line_index(self, para: str) -> int | None:
        note_id, _, idx = para.rpartition(":")
        if note_id != self.selected or not idx.isdigit():
            return None
        i = int(idx)
        return i if i < len(self._lines()) else None

    def resolve_anchor(self, anchor: dict) -> dict | None:
        lines = self._lines()
        quote = anchor.get("quote")
        i = self._line_index(anchor.get("para", ""))
        if i is not None:
            text = lines[i]
            s, e = anchor.get("start", 0), anchor.get("end", 0)
            if 0 <= s <= e <= len(text) and (quote is None or text[s:e] == quote):
                return {**anchor, "quote": text[s:e]}
            if quote and (k := text.find(quote)) >= 0:
                return {**anchor, "start": k, "end": k + len(quote)}
        if quote:
            for j, text in enumerate(lines):
                if (k := text.find(quote)) >= 0:
                    return {**anchor, "para": self._para_id(j), "start": k, "end": k + len(quote)}
        return None

    def get_range(self, anchor: dict) -> str:
        fixed = self.resolve_anchor(anchor)
        if fixed is None:
            return ""
        return self._lines()[self._line_index(fixed["para"])][fixed["start"]:fixed["end"]]

    def replace_range(self, anchor: dict, text: str) -> bool:
        fixed = self.resolve_anchor(anchor)
        note = self.note(self.selected)
        if fixed is None or note is None:
            return False
        lines = self._lines()
        i = self._line_index(fixed["para"])
        lines[i] = lines[i][:fixed["start"]] + text + lines[i][fixed["end"]:]
        note["body"] = "\n".join(lines)
        self._refresh_item(note)
        self._show_selected()
        self._touch()
        return True

    # --- save / load ------------------------------------------------------------------

    def save(self) -> dict:
        data = {"notes": [dict(n) for n in self.notes]}
        if self.selected:
            data["selected"] = self.selected
        return data

    def load(self, data: dict) -> None:
        self.notes = [{"id": n.get("id") or new_note_id(), "title": n.get("title", ""), "body": n.get("body", "")}
                      for n in data.get("notes", [])]
        self.selected = data.get("selected") if self.note(data.get("selected")) else (
            self.notes[0]["id"] if self.notes else None)
        self._rebuild_list()
        self._show_selected()
