from app.core.shapes import Headings, Selection

from .placeholder import PlaceholderModule


class OutlineModule(PlaceholderModule):
    kind = "outline"
    title = "outline"
    description = ("Live table of contents for a corpus.\n"
                   "Click a heading to jump. Buttons promote/demote the current paragraph.")
    needs = {"source": (Headings, Selection)}
    min_size = (160, 120)

    def menu_items(self):
        return [
            ("collapse all", lambda: f"{self.id}: collapse all (placeholder)"),
            ("expand all", lambda: f"{self.id}: expand all (placeholder)"),
        ]
