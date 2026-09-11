# Layout

The window is a **1000 x 1000 grid**. Every slot is a rectangle on that grid.
The rectangles always tile the grid: no gaps, no overlaps, every point
belongs to exactly one slot.

Units aren't pixels. They're stretched to whatever the window is, so a slot
600 wide is always 60% of the window. Units aren't square either (1000 wide on
a 16:9 monitor is much more than 1000 tall), so don't reason about "square"
slots.

## Your example

```
     0            600           1000
   0 ┌─────────────┬─────────────┐
     │             │   notes     │
 333 │             ├─────────────┤
     │    main     │  comments   │
 666 │             ├─────────────┤
     │             │     ai      │
1000 └─────────────┴─────────────┘
```

```json
{
  "grid": [1000, 1000],
  "slots": [
    { "module": "main",     "rect": [0,   0,   600, 1000] },
    { "module": "notes",    "rect": [600, 0,   400, 333]  },
    { "module": "comments", "rect": [600, 333, 400, 333]  },
    { "module": "ai",       "rect": [600, 666, 400, 334]  }
  ]
}
```

- `rect` is `[x, y, w, h]` in grid units.
- `module` is an **instance id**, not a type. Type lives in the project's
  `modules` table (`03-save-format.md`). Two slots can hold two different
  corpus instances.
- `module` may be `null`: an **empty slot**. Renders as a box with a "pick a
  module" dropdown. This is what a fresh layout, a closed slot that couldn't
  be filled (see below), or a missing module kind all look like.

## Why a grid and not a split tree

A split tree (VS Code, i3) can only make layouts where some straight line
cuts a pane in two. The grid can make anything, including this:

```
┌──────────────┬──────┐   A: [0,   0,   700, 300]
│      A       │      │   B: [700, 0,   300, 700]
├──────┬───────┤  B   │   C: [300, 700, 700, 300]
│      │   E   │      │   D: [0,   300, 300, 700]
│  D   ├───────┴──────┤   E: [300, 300, 400, 400]
│      │      C       │
└──────┴──────────────┘   no full-length cut anywhere → not a tree.
```

Cost: we don't get `QSplitter` for free. We write one container widget that
positions children with `setGeometry` and draws handles on shared edges.
That's a few hundred lines and we own all the behaviour.

## The one invariant

> The slots always tile the 1000 x 1000 grid exactly.

Checked on load and after every edit:
`sum(w*h) == 1_000_000` and no two rects overlap. Together those mean full
coverage. If a layout file fails this, we refuse it and say which rects
collide or where the hole is.

Every operation below is designed so it can't break the invariant.

## The one operation: sweep an edge

Everything (resize, close, insert) is built from moving an edge.

```
   before                        sweep A's bottom edge down by 200
┌───────┬──────┐               ┌───────┬──────┐
│   A   │  B   │               │   A   │  B   │
├───────┤      │               │       │      │
│   C   ├──────┤    ───▶       ├───────┤      │
│       │  D   │               │   C   ├──────┤
└───────┴──────┘               └───────┴──────┘

  A grows, C shrinks. B and D don't touch that edge segment → untouched.
```

Rules:

- The edge segment is the full shared boundary: every rect whose edge lies on
  the line and overlaps the dragged segment is included, on both sides.
- Rects on the near side grow, rects on the far side shrink.
- A sweep is **refused** if any rect would drop below its minimum size (see
  below). The drag just stops there. Nothing is ever deleted by a sweep.
- Rects on the far side never get pushed out of the way sideways. This keeps
  the operation local and predictable.

## Resize

Drag a handle = sweep that edge. Neighbours follow automatically because they
share the edge. Snapping applies (below).

## Close a slot

Removing a slot leaves a hole. Fill it by sweeping one of the hole's four
edges across it:

```
remove C from the pinwheel above:

  C's top edge is covered exactly by E (300..700) and B (700..1000).
  Sweep it down to y=1000:  E → [300,300,400,700]   B → [700,0,300,1000]

┌──────────────┬──────┐
│      A       │      │
├──────┬───────┤  B   │
│      │       │      │
│  D   │   E   │      │
│      │       │      │
└──────┴───────┴──────┘
```

Some holes can't be filled by a neighbour just growing. The pinwheel centre
is the classic case: A, B, C, D all overhang E's edges. Sweeping still works
because sweeping pushes:

```
remove E:  sweep A's bottom edge (x 0..700) from y=300 to y=700.
           A grows to [0,0,700,700]. D is on that segment → shrinks to
           [0,700,300,300]. Still a tiling.

┌──────────────┬──────┐
│              │      │
│      A       │  B   │
│              │      │
├──────┬───────┴──────┤
│  D   │      C       │
└──────┴──────────────┘
```

Algorithm:

1. For each of the hole's 4 edges, simulate sweeping it across the hole.
2. Drop candidates that violate a min size.
3. Pick the one that changes the fewest rects; tie-break on longest shared
   edge. Hovering the close button previews the result.
4. If **none** are valid, the hole becomes an empty slot (`module: null`).
   Invariant holds, the user picks what goes there.

## Insert a slot

Drag a module (from a palette or another slot) and drop it on a slot:

```
        ┌─────────────────────────┐
        │           top           │   edge zones → split that slot in half,
        │  ┌───────────────────┐  │   new module takes the dropped side
        │  │                   │  │
        │ L│      center       │R │   center → swap the two modules
        │  │                   │  │             (or fill, if the slot is empty)
        │  └───────────────────┘  │
        │          bottom         │
        └─────────────────────────┘
```

Splitting one rect into two is always a valid tiling. Dragging a module out of
its slot leaves that slot empty (not a hole), so the source side is safe too.

## Snapping

While sweeping an edge, snap to:

- grid lines every **25 units** (so 40 x 40 tidy positions), and
- any other rect's edge on the same axis, so things line up across the screen.

Within 8 px → jump. Hold `Alt` to drag freely.

```
 dragging this edge ──┐
                      │
   ┌──────┬───────────┼──┬──────┐
   │      │           │  │      │   ▏ snap targets: grid lines +
   │      │  ▏   ▏    │▏ │      │     edges of rects above/below
   │      │           │  │      │
   └──────┴───────────┴──┴──────┘
```

## Minimum sizes and small screens

Each module declares a minimum size **in pixels** (a comments list under
180 px wide is useless). Units → pixels depends on the window, so:

- Sweeps are refused if they'd push a rect under its pixel minimum at the
  current window size.
- If the window shrinks so far that the layout can't satisfy every minimum,
  we don't move anything. The too-small slots show a collapsed title bar
  with a "too narrow" hint. Growing the window back restores them. Layout
  data never changes because of a window resize.

## Pixel rounding

Convert edge coordinates, not widths: `px = round(x * W / 1000)`. Two rects
that share an edge in units then share the exact same pixel, so there are no
1 px cracks or overlaps from rounding.

## Layout presets

A layout can live on its own in `layouts/*.json` (`default`, `focus`,
`review`). Switching presets keeps your modules and only changes the slots.
Slots that reference a module id the project doesn't have become empty slots.
