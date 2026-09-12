"""Corpus <-> JSON paragraphs.

{ "id": "p_8f3a", "style": "h1", "text": "Chapter 1" }
{ "id": "p_91c0", "style": "p",  "text": "It was dark.", "align": "center", "list": "bullet",
  "runs": [ {"t": "It was "}, {"t": "dark", "b": true}, {"t": "."} ] }

`text` is always written (greppable). `runs`, `align`, `list` only when needed.
Run keys: t text · b bold · i italic · u underline · s strike · font · size · color.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont, QTextBlock, QTextCharFormat, QTextCursor, QTextListFormat

from .editor import LIST_STYLES, PageEditor, new_para_id
from .styles import char_format_for, family_for, style_for

ALIGN_TO_KEY = {
    Qt.AlignmentFlag.AlignHCenter: "center",
    Qt.AlignmentFlag.AlignRight: "right",
    Qt.AlignmentFlag.AlignJustify: "justify",
}
KEY_TO_ALIGN = {v: k for k, v in ALIGN_TO_KEY.items()}
KEY_TO_ALIGN["left"] = Qt.AlignmentFlag.AlignLeft


def _run_for(fragment_text: str, cf: QTextCharFormat, style) -> dict:
    run: dict = {"t": fragment_text}
    if int(cf.fontWeight()) >= int(QFont.Weight.Bold) and not style.bold:
        run["b"] = True
    if cf.fontItalic() and not style.italic:
        run["i"] = True
    if cf.fontUnderline():
        run["u"] = True
    if cf.fontStrikeOut():
        run["s"] = True
    families = cf.fontFamilies()
    if families and families[0] != family_for(style):
        run["font"] = families[0]
    size = cf.fontPointSize()
    if size and size != style.size:
        run["size"] = int(size) if float(size).is_integer() else size
    if cf.hasProperty(QTextCharFormat.Property.ForegroundBrush):
        color = cf.foreground().color().name()
        if color != (style.color or "#000000"):
            run["color"] = color
    return run


def block_to_para(editor: PageEditor, block: QTextBlock) -> dict:
    key = editor.style_key(block)
    style = style_for(key)
    para: dict = {"id": editor.para_id(block), "style": key, "text": block.text()}

    align = block.blockFormat().alignment() & Qt.AlignmentFlag.AlignHorizontal_Mask
    if align in ALIGN_TO_KEY:
        para["align"] = ALIGN_TO_KEY[align]
    kind = editor.list_kind(block)
    if kind:
        para["list"] = kind

    runs = []
    it = block.begin()
    while not it.atEnd():
        frag = it.fragment()
        if frag.isValid():
            runs.append(_run_for(frag.text(), frag.charFormat(), style))
        it += 1
    if any(len(r) > 1 for r in runs):
        para["runs"] = runs
    return para


def save_paras(editor: PageEditor) -> list[dict]:
    return [block_to_para(editor, b) for b in editor.blocks()]


def _format_for_run(run: dict, base: QTextCharFormat) -> QTextCharFormat:
    cf = QTextCharFormat(base)
    if run.get("b"):
        cf.setFontWeight(QFont.Weight.Bold)
    if run.get("i"):
        cf.setFontItalic(True)
    if run.get("u"):
        cf.setFontUnderline(True)
    if run.get("s"):
        cf.setFontStrikeOut(True)
    if run.get("font"):
        cf.setFontFamilies([run["font"]])
    if run.get("size"):
        cf.setFontPointSize(float(run["size"]))
    if run.get("color"):
        cf.setForeground(QBrush(QColor(run["color"])))
    return cf


def load_paras(editor: PageEditor, paras: list[dict]) -> None:
    doc = editor.document()
    editor.loading = True
    try:
        doc.clear()
        cursor = QTextCursor(doc)
        cursor.beginEditBlock()
        current_list = None
        current_kind = None
        if not paras:
            paras = [{"style": "p", "text": ""}]
        for i, para in enumerate(paras):
            if i > 0:
                cursor.insertBlock()
            block = cursor.block()
            key = para.get("style", "p")
            editor.apply_style(block, key)
            editor.set_para_id(block, para.get("id") or new_para_id())
            base = char_format_for(style_for(key))

            align = KEY_TO_ALIGN.get(para.get("align", "left"), Qt.AlignmentFlag.AlignLeft)
            bf = block.blockFormat()
            bf.setAlignment(align)
            cursor.setBlockFormat(bf)

            kind = para.get("list")
            if kind in LIST_STYLES:
                if kind == current_kind and current_list is not None:
                    current_list.add(block)
                else:
                    fmt = QTextListFormat()
                    fmt.setStyle(LIST_STYLES[kind])
                    fmt.setIndent(1)
                    current_list = cursor.createList(fmt)
                    current_kind = kind
            else:
                # insertBlock() after a list item inherits the list; a non-list paragraph must leave it
                if block.textList() is not None:
                    editor.leave_list(block)
                current_list, current_kind = None, None

            runs = para.get("runs") or [{"t": para.get("text", "")}]
            for run in runs:
                cursor.insertText(run.get("t", ""), _format_for_run(run, base))
        cursor.endEditBlock()
    finally:
        editor.loading = False
    editor.ensure_ids()
    doc.clearUndoRedoStacks()
    doc.setModified(False)
    editor.moveCursor(QTextCursor.MoveOperation.Start)
