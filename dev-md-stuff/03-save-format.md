# Save Format

One project = one JSON file (`mynovel.faws.json`, or `.faws` later). It holds
the layout, the module list, the wiring, and each module's data.

```json
{
  "faws": 1,
  "title": "My Novel",

  "layout": { "...": "see 01-layout.md" },

  "modules": {
    "main": {
      "kind": "corpus",
      "data": {
        "paras": [
          { "id": "p_8f3a", "style": "h1", "text": "Chapter 1" },
          { "id": "p_91c0", "style": "p",  "text": "It was a dark and stormy night." },
          { "id": "p_2be4", "style": "h2", "text": "The Storm" }
        ]
      }
    },

    "notes": {
      "kind": "notes",
      "data": {
        "notes": [
          { "id": "n1", "title": "Names", "body": "Protagonist: Mara. Village: Holt." }
        ]
      }
    },

    "outline": {
      "kind": "outline",
      "wire": { "source": "main" },
      "data": { "collapsed": [] }
    },

    "comments": {
      "kind": "comments",
      "wire": { "target": "main" },
      "data": {
        "comments": [
          {
            "id": "c1",
            "anchor": { "para": "p_91c0", "start": 0, "end": 31,
                        "quote": "It was a dark and stormy night." },
            "text": "cliché opener",
            "suggest": "The storm came in at dusk.",
            "resolved": false,
            "created": "2026-09-10T15:40:00"
          }
        ]
      }
    }
  }
}
```

## Rules

- **Each module owns its `data`.** The app never looks inside it. It calls
  `module.save()` to fill it and `module.load(data)` to restore it.
- **Unknown kinds are kept, not dropped.** If you open a project that has an
  `ai` module and this build doesn't ship one, the slot shows "module `ai` not
  available" and its `data` is written back untouched on save. Nothing is
  lost by opening a file in a smaller build.
- **Adding a module = adding a key.** That's the "mount more stuff over time"
  requirement. There is no schema migration for adding modules.
- **`faws` is the format version** for the outer envelope only. Module data
  versions are the module's own problem (put a `"v": 1` inside `data` if you
  need it).
- **Text is stored as paragraphs, not HTML.** Diffable, greppable, editable by
  hand, git-friendly. Paragraph `style` is one of `p h1 h2 h3 quote code`.
- **Inline formatting is a list of `runs`**, only written when a paragraph has
  any. `text` is always there too, so grep still works:

```json
{ "id": "p_91c0", "style": "p", "align": "center", "list": "bullet",
  "text": "It was dark.",
  "runs": [ { "t": "It was " }, { "t": "dark", "b": true }, { "t": "." } ] }
```

  Run keys: `t` text · `b` bold · `i` italic · `u` underline · `s` strike ·
  `font` · `size` · `color`. Only deviations from the paragraph style are
  written (a heading is bold by its style, so its runs don't say `b`).
  `align` is `center | right | justify` (left is the default and omitted).
  `list` is `bullet | number`; consecutive list paragraphs form one list.

## Multiple works in one project

Nothing special needed. Two corpus instances:

```json
"modules": {
  "ch1": { "kind": "corpus", "data": { "paras": [ ... ] } },
  "ch2": { "kind": "corpus", "data": { "paras": [ ... ] } },
  "comments": { "kind": "comments", "wire": { "target": "ch1" } }
}
```

Which of them is on screen is the layout's business, not the data's. A
project can have ten corpuses and show one.

## File vs folder

v1 is a single file because it's simplest to open/save/share. If files get big
(images, many chapters), the same structure moves to a folder or zip:

```
mynovel.faws/
  project.json        # envelope, layout, modules (kind + wire), no data
  main.json           # one file per module's data
  notes.json
  comments.json
```

The in-memory model is identical, so this is a loader change, not a redesign.

## Saving behaviour

- **Autosave**: every change restarts a 1 s timer; when it fires, the whole
  project is written to its own path. "Every change" means layout (resize a
  slot, split, close, drop, swap, preset, add/remove a module) *and* module
  content — a module calls `mark_dirty()` when its text or config changes, so
  typing in the corpus or a note saves 1 s after the last keystroke. Window
  resizes don't count. Quitting or opening another project flushes a pending
  autosave first. The status bar shows `autosaved HH:MM:SS`.
- Save writes to a temp file then renames. Never half-written projects.
- Ctrl+S still exists for people who like pressing it; it just saves now.
- Autosave can be turned off in settings → Preferences. Snapshot history (walk
  a bad edit back) is still to do.
