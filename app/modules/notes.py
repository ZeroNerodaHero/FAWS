from app.core.shapes import TextSource

from .placeholder import PlaceholderModule


class NotesModule(PlaceholderModule):
    kind = "notes"
    title = "notes"
    description = ("Scratch space. Many small notes, no structure imposed.\n"
                   "List on top, editor for the selected note below.")
    provides = (TextSource,)
    events = ("changed",)
    min_size = (180, 120)

    def menu_items(self):
        return [("new note", lambda: f"{self.id}: new note (placeholder)")]

    # TextSource (over the selected note)
    def get_text(self) -> str: return ""
    def get_paragraphs(self) -> list: return []
    def get_range(self, anchor) -> str: return ""
    def replace_range(self, anchor, text) -> None: pass
    def resolve_anchor(self, anchor): return None
