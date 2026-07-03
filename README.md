# Edge Slide Grid Snap

A Blender add-on that slides edges along their rails — like the built-in Edge Slide —
but snaps the sliding vertices to the world grid, which the native tool can't do
(native snapping during edge slide only targets other geometry).

Packaged as a Blender extension (Blender 4.2+); tested on Blender 5.1.

## Install

1. Build or grab the zip from `dist/` (see Development below).
2. In Blender: **Edit > Preferences > Get Extensions >** dropdown arrow (top
   right) **> Install from Disk...** and pick
   `edge_slide_grid_snap-<version>.zip`.

Or drag and drop the zip into the Blender window.

## Use

1. In Edit Mode, select an edge loop (or any chain of edges).
2. Start the tool via **Edge menu > Edge Slide (Grid Snap)**, the Vertex menu,
   or the shortcut **Shift+Alt+V**.
3. Move the mouse to slide. While sliding:

   | Input | Action |
   |---|---|
   | Mouse move | Slide along the rails (factor 0 to 1, 0.5 = start) |
   | **Ctrl** (hold) | Temporarily invert grid snapping |
   | **Shift** (hold) | Precision (10× slower) movement |
   | **Mouse wheel** | Grid size down / up in linear steps (0.1 per click by default); switches to manual grid |
   | **A** | Toggle auto grid size (match the visible viewport grid) |
   | **LMB / Enter** | Confirm |
   | **RMB / Esc** | Cancel |

   The 3D Viewport header shows the current factor, snap state, and grid size.

4. After confirming, the redo panel (bottom-left) lets you tweak **Factor**,
   **Snap to Grid**, and **Auto Grid Size**; with auto off, **Grid Size** is
   editable directly (0.05 minimum). **Grid Wheel Step** sets how much one
   wheel click adds or removes during the modal, and is also the smallest
   grid size the wheel can reach (so it never decays toward zero).

## How snapping works

Each sliding vertex is constrained to its rail edge, so it generally can't land on
an exact 3D grid intersection. Instead, the add-on snaps the **dominant world axis**
of the rail: if a vertex slides along a mostly-X edge, its X coordinate lands
exactly on a grid line and the vertex stays on the rail. Each vertex snaps
independently, so a loop over irregular topology still lines up with the grid.

Snapping happens in world space, so it works correctly on objects that are moved,
rotated, or scaled.

With **Auto Grid Size** enabled (the default), the grid size matches the
finest grid lines currently visible in the viewport: like Blender's own
Absolute Grid Snap, the add-on picks the grid level whose lines are at least
12 pixels apart on screen at the current zoom. Zoom in and it snaps to the
fine subdivision lines; zoom out and it snaps to the coarser ones. Turn auto
off — by unchecking it, or by touching the mouse wheel while sliding — to use
a manual **Grid Size** instead; press **A** during the slide to jump back to
auto. (Imperial units use Blender's non-uniform grid steps in the viewport;
the add-on approximates them as powers of 10.)

The slide **Factor** runs from 0 to 1 across the whole slide span: 0.5 is the
starting position, 0 and 1 are the two rail endpoints.

## Limitations

- Rail detection is a simplified version of Blender's native edge slide: each vertex
  slides toward its best side edge. There is no *Even* or *Flipped* mode, and
  results on poles (vertices with many edges) may differ from the native tool.
- Boundary and wire edges fall back to sliding along a perpendicular direction.
- No numeric keyboard input during the modal (use the redo panel instead).

## Development

Layout: `edge_slide_grid_snap/` is the extension source (`__init__.py` +
`blender_manifest.toml`); metadata lives in the manifest, not `bl_info`.

Validate and build the distributable zip (from the repo root):

```
blender --command extension validate edge_slide_grid_snap
blender --command extension build --source-dir edge_slide_grid_snap --output-dir dist
```

Run the headless test suite:

```
blender -b --factory-startup --python smoke_test.py
```

## Publishing to extensions.blender.org

1. Bump `version` in `edge_slide_grid_snap/blender_manifest.toml`, then
   validate and build (above).
2. Sign in at <https://extensions.blender.org> with a Blender ID and upload
   `dist/edge_slide_grid_snap-<version>.zip`.
3. The site checks the manifest automatically; the extension goes live after
   moderation review. License is GPL-3.0-or-later, as required for add-ons.
