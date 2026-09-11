# FAWS — Overview

A writing app that looks like Word/Docs in the middle, but every part of the
screen is a swappable **module**, and modules can talk to each other.

Read these in order:

| File | What it covers |
|---|---|
| `00-overview.md` | this file: the idea, tech choice, vocabulary |
| `01-layout.md` | how the screen is split, the layout JSON, snapping |
| `02-modules-and-shapes.md` | what a module is, how they talk, "shapes" |
| `03-save-format.md` | the project file |
| `04-first-modules.md` | specs for corpus, notes, outline, comments |
| `05-roadmap.md` | build order + open questions |

## The idea in one picture

```
┌──────────────────────────────┬──────────────────────┐
│                              │  notes               │
│                              ├──────────────────────┤
│  main corpus                 │  comments            │
│  (the thing you're writing)  │   ↕ talks to corpus  │
│                              ├──────────────────────┤
│                              │  ai agent            │
│                              │   ↕ talks to both    │
└──────────────────────────────┴──────────────────────┘
```

- The screen is a 1000 x 1000 grid, fully tiled by rectangles. Every
  rectangle is a slot holding one module. No gaps, ever.
- Modules don't know about each other's internals. They only see each other's
  **API** (a few functions + a few events).
- A module says what it **provides** and what it **needs**. If A provides what
  B needs, you can wire B to A. That's the whole compatibility rule.
- A project file is one JSON. Each module owns its own chunk of it, so adding a
  module never breaks the file.

## Tech choice: Python + Qt (PySide6)

Why not keep the Lua/LÖVE prototype: LÖVE is a game framework. It has no text
widget, so we'd be writing selection, wrapping, clipboard, undo, scrolling,
fonts, IME... by hand. `app/inputbox.lua` is already showing that pain.

Why Python + PySide6:

| Need | What Qt gives us for free |
|---|---|
| Word-like editor | `QTextEdit` / `QTextDocument`: paragraphs, heading styles, cursor, selection, undo, clipboard |
| Grid of slots | one custom container widget placing children with `setGeometry`; Qt handles paint, input, resize events |
| Snapping / dragging | we own the edge handles, so snapping and drag-to-rearrange are our code, not fought out of a framework |
| Easy to run | `pip install -r requirements.txt` then `python main.py`. No build step. Mac/Win/Linux |
| Custom look | stylesheets (CSS-ish), so it doesn't have to look like 2005 |

Cost: PySide6 is a big install (~150 MB) and Qt has its own way of doing
things. Worth it: the editor is the hard part of this app and we get it on
day one.

Alternatives considered and passed on:

- **Web (Electron/Tauri + ProseMirror)**: best editors on earth, but "easy to
  run" gets worse (node, bundler, two languages).
- **Tkinter**: ships with Python, but the text widget and layout are too weak
  for this.
- **Keep LÖVE**: see above.

## Vocabulary (used everywhere else in these docs)

| Word | Meaning |
|---|---|
| **Module** | One self-contained thing you can put on screen: corpus, notes, comments, outline, AI... Has a widget, an API, and its own save data. |
| **Slot** | A rectangle on the 1000 x 1000 grid. Holds one module, or is empty. |
| **Layout** | The list of slots. Always tiles the grid exactly. JSON. |
| **Hub** | The one object every module gets a handle to. Looks up other modules, routes events, checks wiring. |
| **Shape** | A named list of functions (and events). "Provides shape X" = has all those functions. |
| **Wire** | "Module B's `target` is module A." Stored in JSON. Checked against shapes at load. |
| **Anchor** | A pointer into some text: paragraph id + start/end offsets. Used by comments, highlights, suggestions. |
| **Project** | One JSON file: layout + every module's data. |
