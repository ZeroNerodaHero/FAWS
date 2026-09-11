# Roadmap

Each phase ends with something you can run. No phase depends on a later one.

```
 0 skeleton ──▶ 1 corpus+outline ──▶ 2 notes+save ──▶ 3 comments ──▶ 4 snapping/drag ──▶ 5 ai
 (empty boxes    (you can write)      (it persists)    (it talks)     (it rearranges)     (bonus)
  on screen)
```

Status: phase 0 done, phase 4 done (except hover preview on close), phase 2's
save/open done. Phases 1, 3, 5 (the actual modules) are next.

## Phase 0: skeleton — done

- `main.py`, `core/hub.py`, `core/shapes.py`, `core/layout.py`, `core/module.py`
- Layout JSON → grid container widget. Validates the tiling invariant,
  positions placeholder modules that just show their id, re-lays out on
  window resize with edge-based pixel rounding.
- Hub: register, `get`, `on`, `emit`, wire + shape check with the error
  message from `02-modules-and-shapes.md`.
- Done when: `python main.py` shows your left/right-with-3-rows layout from
  `layouts/default.json`, and a layout file with a hole or overlap is
  rejected with a useful message.

## Phase 1: corpus + outline

- Corpus module on `QTextEdit`: paragraph ids, styles, all four shapes.
- Outline module wired to it.
- Done when: type headings on the left, they appear on the right, click one
  to jump.

## Phase 2: notes + save/load

- Notes module.
- `core/project.py`: save/load the envelope, call each module's
  `save()`/`load()`, preserve unknown kinds, atomic write. **done**
- File menu: Open / Save / Save As. **done** (top bar → file).
- Autosave: debounced 1.5 s after any layout/module change, flush on quit.
  **done**. Still to do: New project.
- Done when: quit, reopen, everything is where you left it.

## Phase 3: comments

- Anchors + `resolve_anchor` in corpus. Highlights via extra selections.
- Comments module: add / jump / accept / reject / resolve / orphan handling.
- Done when: comment on a sentence, suggest a rewrite, accept it, undo it,
  and the comment behaves sensibly throughout.

## Phase 4: edge sweep, snapping, rearranging — done

- Edge sweep: the one operation from `01-layout.md`. Drag handles on shared
  edges, neighbours follow, min sizes block.
- Snap to 25-unit grid lines and to other rects' edges (`Alt` to bypass).
- Close slot (`×`) → fill by sweep, fall back to empty slot. Hover preview
  not done yet.
- Every slot has a title bar with `▾` (module items + split / wiring /
  remove / close) and `×`. Modules add their own items via
  `Module.menu_items()`.
- Drag a title bar or a top-bar `+ kind` button onto a slot: edge → split,
  centre → swap (or fill, if empty). New modules with `needs` get a wiring
  dialog listing only compatible targets.
- Closing hides a module; it stays in the project under top bar → existing.
  "remove from project" is refused while anything is wired to it.
- Layout presets menu (`layouts/*.json`) + save current as preset.
- Done when: you can go from the default layout to "corpus only" and back
  without touching JSON by hand, and the pinwheel layout survives closing
  its centre.

## Phase 5: AI module

- Needs `source: TextSource`, `comments: Comments`, optional `notes`.
- Chat pane; "review selection" and "review document" buttons that leave
  comments with suggestions.
- Provider behind a tiny interface so local models and APIs both work.

## Later / maybe

- Inline bold/italic (markdown-ish markers in `text`).
- Export: markdown, docx, pdf.
- Folder/zip project format when single-file gets heavy.
- Word count / goals module (needs `TextSource`, provides nothing; a nice
  10-minute proof that modules are cheap).
- Themes via a `theme.json` → Qt stylesheet.

## Code layout

```
FAWS/
  run.sh                    # ./run.sh [project]  — makes the venv on first run
  requirements.txt          # PySide6
  app/                      # the Python package; run as `python -m app.main`
    main.py                 # window, top bar wiring, stylesheet
    core/
      hub.py                # registry, events, wiring + shape check
      shapes.py             # Shape class + the built-in shapes
      module.py             # Module base class
      layout.py             # slots on the 1000x1000 grid, tiling check, sweep, split, fill
      grid.py               # Qt: SlotFrame, GridContainer, ghost drag, overlay
      workspace.py          # one project on one grid: close/split/drop/menus/autosave
      toolbar.py            # top bar
      project.py            # load/save, MissingModule
    modules/
      placeholder.py        # base for the four stubs below
      corpus.py  notes.py  outline.py  comments.py
  layouts/                  # presets: default, focus, review
  examples/                 # example projects (default one opens with ./run.sh)
  dev-md-stuff/             # these docs
```

## Decisions I made that you should sanity-check

1. **Python + PySide6** over web or staying in LÖVE. Biggest call in here.
2. **Modules call each other directly** after wiring; the hub is just a
   registry + event bus. Simpler than routing every call through the hub, at
   the cost of a bit less introspection.
3. **Shapes are checked by function names only**, at load time. No runtime
   type checking of arguments.
4. **Paragraph-level styles only in v1**, no inline bold/italic. Gets the
   architecture right before the editor gets complicated.
5. **Single JSON file** for the project. Folder/zip is a loader change later.
6. **Anchors = paragraph id + offsets + quote.** Not character offsets into
   the whole document (those break on every edit above the anchor).
7. **Layout is a 1000 x 1000 grid of rectangles that must tile exactly**, not
   a split tree. More layouts possible (pinwheel), one operation (edge sweep)
   does resize/close/insert, and we write the container ourselves instead of
   using `QSplitter`.
8. **Closing a slot fills the hole by sweeping a neighbour's edge**; if no
   sweep is valid under min sizes, the hole becomes an empty slot rather than
   a gap.

## Open questions for you

- Should notes be one big freeform text, or a list of small notes as specced?
- Do comments need threads (replies), or is one comment + resolve enough for v1?
- Should the layout be stored in the project file (opens as you left it) or
  separately (same layout across all projects)? Docs currently say: in the
  project, with optional standalone presets.
- Any hard requirement on what the corpus must export to eventually (docx?
  markdown?). It affects how much of Qt's rich text we lean on.
- What to do with `app/` (the Lua prototype): delete, or keep as reference?
