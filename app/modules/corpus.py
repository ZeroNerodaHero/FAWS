from app.core.shapes import Headings, Highlights, Selection, TextSource

from .placeholder import PlaceholderModule


class CorpusModule(PlaceholderModule):
    kind = "corpus"
    title = "corpus"
    description = ("The document. The thing you're actually writing.\n"
                   "Word-like editor: paragraphs, heading styles, selection, undo.")
    provides = (TextSource, Headings, Selection, Highlights)
    events = ("changed", "headings_changed", "selection_changed")
    min_size = (320, 200)

    def menu_items(self):
        return [
            ("word count", lambda: f"{self.id}: 0 words (placeholder)"),
            ("paragraph style ▸ (coming with the editor)", lambda: None),
        ]

    # TextSource
    def get_text(self) -> str: return ""
    def get_paragraphs(self) -> list: return []
    def get_range(self, anchor) -> str: return ""
    def replace_range(self, anchor, text) -> None: pass
    def resolve_anchor(self, anchor): return None

    # Headings
    def get_headings(self) -> list: return []
    def scroll_to(self, para_id) -> None: pass
    def set_style(self, para_id, style) -> None: pass

    # Selection
    def get_selection(self): return None

    # Highlights
    def highlight(self, anchor, color, tag) -> None: pass
    def clear_highlights(self, tag) -> None: pass
