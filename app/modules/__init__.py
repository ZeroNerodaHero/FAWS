"""kind -> module class. Adding a module = adding a line here."""

from .comments import CommentsModule
from .corpus import CorpusModule
from .notes import NotesModule
from .outline import OutlineModule

REGISTRY = {cls.kind: cls for cls in (CorpusModule, NotesModule, OutlineModule, CommentsModule)}
