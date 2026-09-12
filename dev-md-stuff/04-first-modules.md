# The First Four Modules

```
             ┌──────────────┐
             │   corpus     │ provides: TextSource, Headings, Selection, Highlights
             └──────┬───────┘ needs:    nothing
        ┌───────────┼──────────────┐
        │           │              │
  ┌─────┴─────┐ ┌───┴──────┐  ┌────┴─────┐
  │  outline  │ │ comments │  │  notes   │ (not wired to anyone;
  │ needs:    │ │ needs:   │  │ provides:│  stands alone, but offers
  │ Headings  │ │TextSource│  │TextSource│  TextSource so it *could*
  │ Selection │ │Highlights│  │          │  be a comments target later)
  └───────────┘ │Selection │  └──────────┘
                │ provides:│
                │ Comments │
                └──────────┘
```

---

## 1. Corpus (`kind: "corpus"`)

The document. The thing you're actually writing.

**UI**: a `QTextEdit` with a small toolbar (paragraph style dropdown, later
bold/italic). Word-processor feel: page-ish margins, decent font, no chrome.

**Provides**

| Shape | Function | Does |
|---|---|---|
| TextSource | `get_text()` | whole doc as plain text |
| | `get_paragraphs()` | `[{id, style, text}, ...]` |
| | `get_range(anchor)` | text inside the anchor |
| | `replace_range(anchor, text)` | edit, as one undo step |
| | `resolve_anchor(anchor)` | returns a live/corrected anchor, or `None` if orphaned |
| Headings | `get_headings()` | `[{id, level, text}, ...]` in document order |
| | `scroll_to(para_id)` | scroll + put the cursor there |
| | `set_style(para_id, style)` | make a paragraph `h1`, `p`, etc. |
| Selection | `get_selection()` | anchor of the selection; collapsed (`start == end`) when nothing is selected, so listeners always know the current paragraph. `None` only if the selection spans paragraphs |
| Highlights | `highlight(anchor, color, tag)` | colored underline/background |
| | `clear_highlights(tag)` | remove all with that tag |

**Events**: `changed {paras: [ids]}`, `headings_changed`, `selection_changed`.

**Data**: `paras: [{id, style, text, runs?, align?, list?}]` (see `03-save-format.md`).

**Status: built.** `app/modules/corpus/`: `editor.py` (page, ids, styles,
anchors, highlights, lists), `formatbar.py` (the writing bar that lives in the
slot's title bar, synced to the cursor), `serialize.py`, `module.py` (the four
shapes + events).

**Config**: `fit_width: bool` — page stretches to the slot (on) or is a fixed,
centred 8.5in page (off, default). Toggle with `⇔` in the title bar or the `▾`
menu; saved per corpus instance in the project file.

**Notes for the build**

- Paragraph ids live in `QTextBlockUserData`. New paragraph (Enter) → new id.
  Split a paragraph → the second half gets a new id. Merge → keep the first.
  Undo can recreate a block without its id; `resolve_anchor` falls back to
  searching for the anchor's `quote`, so comments survive that too.
- Enter at the end of a heading gives a Normal paragraph (Word behaviour).
  Bold/italic with no selection applies to the word under the cursor.
- The paragraph style lives on the block format (undo-safe); the id does not
  (would be duplicated on Enter). That split is deliberate.
- `headings_changed` fires only when a heading's text/level/order actually
  changed, not on every keystroke. Debounce ~150 ms.
- Highlights are `QTextEdit.ExtraSelection`s, not real formatting, so they
  never end up in the saved text.

---

## 2. Notes (`kind: "notes"`)

Scratch space. Many small notes, no structure imposed.

**UI**: list of notes on top (title + first line), editor for the selected
note below. `+` adds one. Drag to reorder.

```
┌──────────────────┐
│ + Names          │
│   Timeline       │
│   Things to fix  │
├──────────────────┤
│ Protagonist: Mara│
│ Village: Holt    │
│                  │
└──────────────────┘
```

**Provides**: `TextSource` (over the currently selected note). Not needed by
anything in v1; it's there so a comments module could target a note and so
the AI module can read notes without a special case.

**Needs**: nothing.

**Data**: `notes: [{id, title, body}]`, plus `selected` (id of the open note).

**Status: built** (`app/modules/notes.py`). Title bar holds a filter box, `+`
and `−`. Notes are plain text; a paragraph is a line, with ids like
`n_1a2b3c:2` (note id : line index). Reorder by dragging in the list. Delete
asks first — there is no undo for it.

---

## 3. Outline (`kind: "outline"`)

"Header and stuff." A live table of contents for a corpus, and a way to
promote/demote headings.

**UI**

```
┌──────────────────────┐
│ Chapter 1            │  ← h1
│   The Storm          │  ← h2, click = jump
│   The Morning After  │
│ Chapter 2            │
│                      │
│ [H1] [H2] [H3] [P]   │  ← applies to the paragraph the cursor is in
└──────────────────────┘
```

- Click a heading → `source.scroll_to(id)`.
- Current paragraph is bolded in the list (from `selection_changed`).
- Buttons call `source.set_style(current_para, "h2")`.

**Needs**: `source: Headings + Selection` (one role, two shapes; the hub checks
both).

**Provides**: nothing.

**Data**: `collapsed: [para_ids]` (which subtrees are folded).

---

## 4. Comments (`kind: "comments"`)

Margin comments on a target text, with optional suggested edits you can
accept.

**UI**

```
┌──────────────────────────────┐
│ "It was a dark and stormy…"  │  ← quote from the anchor
│ cliché opener                │  ← comment text
│ ⇢ The storm came in at dusk. │  ← suggestion, if any
│ [accept] [reject] [resolve]  │
├──────────────────────────────┤
│ "Mara"                       │
│ is this spelling final?      │
│ [resolve]                    │
├──────────────────────────────┤
│ + comment on selection       │  ← enabled when target has a selection
└──────────────────────────────┘
```

**Flows**

- **Add**: `target.get_selection()` → build anchor → store → `target.highlight(anchor, yellow, "comment:<id>")`.
- **Click a comment**: `target.scroll_to(anchor.para)`.
- **Accept**: `target.replace_range(anchor, suggest)` → mark resolved → clear its highlight.
- **Reject**: drop the suggestion, keep the comment.
- **On `target.changed`**: for each comment, `target.resolve_anchor(anchor)`;
  update the quote; if `None`, show it greyed as orphaned.
- Resolved comments collapse into a "show resolved (3)" line at the bottom.

**Needs**: `target: TextSource + Highlights + Selection`.

**Provides**: `Comments` → `get_comments()`, `add_comment(anchor, text, suggest=None)`,
`resolve_comment(id)`. This is what lets an AI module leave comments later
with zero changes here.

**Events**: `comments_changed`.

**Data**: `comments: [{id, anchor, text, suggest?, resolved, created}]`.

---

## What "later: AI agent" looks like against this

```
ai needs:  source: TextSource        (read the draft)
           comments: Comments        (leave suggestions)
           notes: TextSource         (read your notes for context)   ← optional wire
ai provides: nothing
```

Every one of those is already provided. The AI module is UI + prompt
plumbing; the rest of the app doesn't change. That's the test of whether the
module design is right.
