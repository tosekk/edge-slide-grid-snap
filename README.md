# Edge Slide Grid Snap
Edge slide, but it snaps vertices to the world grid while you drag. Native edge slide (double G) only snaps to other geometry. This extension somewhat fills that gap.

Packaged as a Blender extension (Blender 4.2+), tested on Blender 5.1.

## Install
1. Grab the zip from the [releases page](https://github.com/tosekk/edge-slide-grid-snap/releases).
2. In Blender: **Edit > Preferences > Get Extensions > dropdown arrow (top right) > Install from Disk...** and pick the zip.
3. Or drag and drop the zip into the Blender window.

## Use
1. In Edit Mode, select an edge loop (or any chain of edges).
2. Start the tool via **Edge menu > Edge Slide (Grid Snap)**, the Vertex menu or **Shift+Alt+V**.
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

4. After confirming, the redo panel (bottom-left) lets you change values for **Factor**, **Snap to Grid**, and **Auto Grid Size** with auto off. **Grid Size** is editable directly (0.05 minimum). **Grid Wheel Step** is how much one wheel click adds/removes to the grid size. Also the smallest grid size the wheel can hit, never decays to zero.

## How snapping works
A vertex is stuck on its rail edge so it can't land on an exact grid intersection. Instead we snap its **dominant axis** (mostly-X edge → X lands on a grid line). Each vertex snaps independently, keeps irregular loops lined up. Works in world space, works fine on moved/rotated/scaled objects too.

**Auto Grid Size** (default on) matches whatever grid lines are visible in the viewport. The same 12px-apart rule Blender's own Absolute Grid Snap uses, gets finer as you zoom in. Wheel or uncheck it to go manual, **A** to turn auto back on.

**Factor** is 0–1, 0.5 = start, 0/1 = the two rail ends.

## Limitations
- Rail detection is a simplified version of Blender's native edge slide so each
  vertex just slides toward its best side edge. No *Even* or *Flipped* mode,
  and poles (vertices with lots of edges) may behave differently than native.
- Boundary and wire edges fall back to sliding along a perpendicular direction.
- No numeric keyboard input during the modal. That's why you need to use the redo panel instead.
