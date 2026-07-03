"""Headless smoke test for edge_slide_grid_snap. Run: blender -b --python smoke_test.py"""
import os
import sys
import bpy
import bmesh

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import edge_slide_grid_snap as addon

failures = []


def check(label, cond):
    print(("PASS  " if cond else "FAIL  ") + label)
    if not cond:
        failures.append(label)


addon.register()
check("operator registered", hasattr(bpy.ops.mesh, "edge_slide_grid_snap"))

# Adaptive grid step selection: smallest base*subdiv**i step spanning >= 12 px.
check("step 0.1 at 500 px/unit", abs(addon._pick_grid_step(1.0, 10, 500) - 0.1) < 1e-9)
check("step 1.0 at 50 px/unit", abs(addon._pick_grid_step(1.0, 10, 50) - 1.0) < 1e-9)
check("step 1.0 at 13 px/unit", abs(addon._pick_grid_step(1.0, 10, 13) - 1.0) < 1e-9)
check("step 0.01 at 5000 px/unit", abs(addon._pick_grid_step(1.0, 10, 5000) - 0.01) < 1e-9)
check("step 0.5 subdiv 2 at 30 px/unit", abs(addon._pick_grid_step(1.0, 2, 30) - 0.5) < 1e-9)

# Build a 4x4-quad plane: vertex rows/columns at -1, -0.5, 0, 0.5, 1.
bpy.ops.wm.read_homefile(use_empty=True)
bpy.ops.mesh.primitive_plane_add(size=2)
obj = bpy.context.active_object
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.subdivide(number_cuts=3)
bpy.ops.mesh.select_all(action='DESELECT')

# Select the vertical edge loop at x = 0.
bm = bmesh.from_edit_mesh(obj.data)
eps = 1e-5
for e in bm.edges:
    if all(abs(v.co.x) < eps for v in e.verts):
        e.select = True
bm.select_flush(True)
bmesh.update_edit_mesh(obj.data)
sel_count = sum(1 for e in bm.edges if e.select)
check("selected 4 loop edges", sel_count == 4)

# Slide with snapping: factor runs 0..1 with 0.5 = original position, so
# 0.85 puts verts at x=0.35 unsnapped, which must snap to the nearest
# 0.2 grid line (0.4), same sign for all.
result = bpy.ops.mesh.edge_slide_grid_snap(
    factor=0.85, use_snap=True, auto_grid=False, grid_size=0.2)
check("operator ran", result == {'FINISHED'})

bm = bmesh.from_edit_mesh(obj.data)
moved = [v for v in bm.verts if v.select]
check("5 verts moved", len(moved) == 5)
xs = sorted({round(v.co.x, 6) for v in moved})
check("all verts share one x (%s)" % xs, len(xs) == 1)
x = xs[0]
check("x on 0.2 grid, snapped to +/-0.4 (got %s)" % x, abs(abs(x) - 0.4) < 1e-6)
ys = sorted(round(v.co.y, 6) for v in moved)
check("y coords untouched %s" % ys, ys == [-1.0, -0.5, 0.0, 0.5, 1.0])

# Reset and slide without snapping: factor 0.85 -> x = +/-0.35 exactly.
for v in moved:
    v.co.x = 0.0
bmesh.update_edit_mesh(obj.data)
result = bpy.ops.mesh.edge_slide_grid_snap(factor=0.85, use_snap=False)
check("unsnapped run", result == {'FINISHED'})
bm = bmesh.from_edit_mesh(obj.data)
xs = sorted({round(abs(v.co.x), 6) for v in bm.verts if v.select})
check("unsnapped |x| == 0.35 (got %s)" % xs, xs == [0.35])

# Factor 0.5 is the original position: nothing may move, even with snap on.
for v in bm.verts:
    if v.select:
        v.co.x = 0.0
bmesh.update_edit_mesh(obj.data)
result = bpy.ops.mesh.edge_slide_grid_snap(
    factor=0.5, use_snap=True, auto_grid=False, grid_size=0.2)
check("midpoint run", result == {'FINISHED'})
bm = bmesh.from_edit_mesh(obj.data)
xs = sorted({round(v.co.x, 6) for v in bm.verts if v.select})
check("factor 0.5 leaves verts in place (got %s)" % xs, xs == [0.0])

# Auto grid without a 3D view falls back to grid scale 1.0: from x=0,
# factor 0.85 (0.35 unsnapped) snaps back to the nearest 1.0 line at 0.
result = bpy.ops.mesh.edge_slide_grid_snap(factor=0.85, use_snap=True, auto_grid=True)
check("auto-grid run", result == {'FINISHED'})
bm = bmesh.from_edit_mesh(obj.data)
xs = sorted({round(v.co.x, 6) for v in bm.verts if v.select})
check("auto-grid fallback snaps to 1.0 lines (got %s)" % xs, xs == [0.0])

# Object transform: offset the object so world snapping differs from local.
for v in bm.verts:
    if v.select:
        v.co.x = 0.0
bmesh.update_edit_mesh(obj.data)
bpy.ops.object.mode_set(mode='OBJECT')
obj.location.x = 0.13
bpy.ops.object.mode_set(mode='EDIT')
result = bpy.ops.mesh.edge_slide_grid_snap(
    factor=0.85, use_snap=True, auto_grid=False, grid_size=0.2)
check("offset-object run", result == {'FINISHED'})
bm = bmesh.from_edit_mesh(obj.data)
wxs = sorted({round((obj.matrix_world @ v.co).x, 6) for v in bm.verts if v.select})
check("world x on 0.2 grid with offset object (got %s)" % wxs,
      len(wxs) == 1 and abs(wxs[0] / 0.2 - round(wxs[0] / 0.2)) < 1e-5)

# No selection -> clean cancel.
bpy.ops.mesh.select_all(action='DESELECT')
result = bpy.ops.mesh.edge_slide_grid_snap(factor=0.85)
check("no selection cancels", result == {'CANCELLED'})

addon.unregister()
try:
    bpy.ops.mesh.edge_slide_grid_snap.poll()
    check("unregister clean", False)
except AttributeError:
    check("unregister clean", True)

print("RESULT:", "FAILED: %s" % failures if failures else "ALL OK")
sys.exit(1 if failures else 0)
