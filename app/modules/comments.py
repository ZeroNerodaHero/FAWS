from app.core.shapes import Comments, Highlights, Selection, TextSource

from .placeholder import PlaceholderModule


class CommentsModule(PlaceholderModule):
    kind = "comments"
    title = "comments"
    description = ("Margin comments anchored to a target text,\n"
                   "with suggested edits you can accept or reject.")
    provides = (Comments,)
    needs = {"target": (TextSource, Highlights, Selection)}
    events = ("comments_changed",)
    min_size = (200, 120)

    def menu_items(self):
        return [
            ("show resolved", lambda: f"{self.id}: show resolved (placeholder)"),
            None,
            ("comment on selection", lambda: f"{self.id}: needs the corpus editor first"),
        ]

    # Comments
    def get_comments(self) -> list: return []
    def add_comment(self, anchor, text, suggest=None) -> str: return ""
    def resolve_comment(self, comment_id) -> None: pass
