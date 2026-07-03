# Edge Slide Grid Snap — Blender extension.
# Metadata lives in blender_manifest.toml; there is deliberately no bl_info.

import bpy
import bmesh
from collections import defaultdict
from mathutils import Vector
from bpy.props import BoolProperty, FloatProperty
from bpy_extras.view3d_utils import location_3d_to_region_2d


# ------------------------------------------------------------------
# Slide data
# ------------------------------------------------------------------

def _orient_edges(sel_edges):
    """Give every selected edge a consistent direction along its chain(s).

    Returns {edge: (v_from, v_to)}.
    """
    orient = {}
    vert_map = defaultdict(list)
    for e in sel_edges:
        for v in e.verts:
            vert_map[v].append(e)

    for start in sel_edges:
        if start in orient:
            continue
        orient[start] = (start.verts[0], start.verts[1])
        stack = [start]
        while stack:
            cur = stack.pop()
            a, b = orient[cur]
            for v, forward in ((b, True), (a, False)):
                for ne in vert_map[v]:
                    if ne in orient:
                        continue
                    ov = ne.other_vert(v)
                    orient[ne] = (v, ov) if forward else (ov, v)
                    stack.append(ne)
    return orient


def _build_slide_items(bm):
    """For every vertex touched by a selected edge, work out the two rail
    targets it can slide toward (side A for factor > 0, side B for < 0).

    Returns a list of (vert, co_orig, target_a, target_b), or None if there
    is nothing to slide.
    """
    sel_edges = [e for e in bm.edges if e.select and not e.hide]
    if not sel_edges:
        return None
    sel_set = set(sel_edges)
    orient = _orient_edges(sel_edges)

    vert_edges = defaultdict(list)
    for e in sel_edges:
        for v in e.verts:
            vert_edges[v].append(e)

    items = []
    for v, edges in vert_edges.items():
        # Consistent along-loop direction at this vertex.
        loop_dir = Vector()
        for e in edges:
            a, b = orient[e]
            d = b.co - a.co
            if d.length_squared > 1e-12:
                loop_dir += d.normalized()
        if loop_dir.length_squared < 1e-12:
            loop_dir = Vector((1.0, 0.0, 0.0))
        loop_dir.normalize()

        normal = v.normal if v.normal.length_squared > 1e-12 else Vector((0.0, 0.0, 1.0))
        perp = loop_dir.cross(normal)
        if perp.length_squared < 1e-12:
            perp = loop_dir.orthogonal()
        perp.normalize()

        # Candidate rails: unselected edges at this vertex; prefer the ones
        # that share a face with the selected loop, like native edge slide.
        sel_faces = {f for e in edges for f in e.link_faces}
        cands = []
        for e in v.link_edges:
            if e in sel_set:
                continue
            d = e.other_vert(v).co - v.co
            if d.length_squared < 1e-12:
                continue
            shares_face = any(f in sel_faces for f in e.link_faces)
            cands.append((d, d.normalized().dot(perp), shares_face))
        if any(c[2] for c in cands):
            cands = [c for c in cands if c[2]]

        best_a = best_b = None
        for d, side, _ in cands:
            if side >= 0.0:
                if best_a is None or side > best_a[1]:
                    best_a = (d, side)
            else:
                if best_b is None or side < best_b[1]:
                    best_b = (d, side)

        if best_a is None and best_b is None:
            # Wire edge or boundary with no rails: slide along the
            # perpendicular, scaled by the local edge length.
            avg_len = sum(e.calc_length() for e in edges) / len(edges)
            vec_a = perp * avg_len
            vec_b = -vec_a
        elif best_a is None:
            vec_b = best_b[0]
            vec_a = -vec_b
        elif best_b is None:
            vec_a = best_a[0]
            vec_b = -vec_a
        else:
            vec_a = best_a[0]
            vec_b = best_b[0]

        items.append((v, v.co.copy(), v.co + vec_a, v.co + vec_b))
    return items


def _apply_factor(items, mw, mw_inv, factor, snap, grid):
    """Move every vertex along its rail. Factor runs 0..1 across the whole
    slide span: 0 = side B target, 0.5 = original position, 1 = side A
    target. With snapping on, each vertex picks the rail position whose
    dominant world axis lands on a grid line."""
    f = max(0.0, min(1.0, factor)) * 2.0 - 1.0
    for v, co, target_a, target_b in items:
        if f >= 0.0:
            target, ff = target_a, f
        else:
            target, ff = target_b, -f

        if snap and grid > 0.0:
            ow = mw @ co
            vec = (mw @ target) - ow
            axis = max(range(3), key=lambda i: abs(vec[i]))
            if abs(vec[axis]) > 1e-9:
                p = ow[axis] + ff * vec[axis]
                snapped = round(p / grid) * grid
                ff = (snapped - ow[axis]) / vec[axis]
                ff = max(0.0, min(1.0, ff))
            v.co = mw_inv @ (ow + vec * ff)
        else:
            v.co = co.lerp(target, ff)


def _pick_grid_step(base, subdiv, px_per_unit):
    """Smallest grid step from base * subdiv**i that spans at least 12 px on
    screen — the same threshold Blender's adaptive viewport grid uses."""
    for i in range(-8, 9):
        step = base * subdiv ** i
        if step * px_per_unit >= 12.0:
            return step
    return base


def _view_grid(context, center):
    """Spacing of the finest grid lines visible at the current zoom,
    mirroring Blender's adaptive viewport grid (ED_view3d_grid_view_scale)."""
    sp = context.space_data
    if sp is None or sp.type != 'VIEW_3D':
        return 1.0
    base = sp.overlay.grid_scale
    unit = context.scene.unit_settings
    if unit.system == 'NONE':
        subdiv = max(sp.overlay.grid_subdivisions, 2)
    else:
        # Metric grid steps are powers of 10; imperial is approximated the same.
        subdiv = 10
        base *= unit.scale_length
    region = context.region
    rv3d = context.region_data
    if region is None or rv3d is None:
        return base
    # Pixels covered by one world unit in the view plane at the center's depth.
    offset = rv3d.view_rotation @ Vector((1.0, 0.0, 0.0))
    p0 = location_3d_to_region_2d(region, rv3d, center)
    p1 = location_3d_to_region_2d(region, rv3d, center + offset)
    if p0 is None or p1 is None:
        return base
    px_per_unit = (p1 - p0).length
    if px_per_unit <= 0.0:
        return base
    return _pick_grid_step(base, subdiv, px_per_unit)


# ------------------------------------------------------------------
# Operator
# ------------------------------------------------------------------

class MESH_OT_edge_slide_grid_snap(bpy.types.Operator):
    """Slide edges along their rails, snapping vertices to the world grid"""
    bl_idname = "mesh.edge_slide_grid_snap"
    bl_label = "Edge Slide (Grid Snap)"
    bl_options = {'REGISTER', 'UNDO', 'GRAB_CURSOR', 'BLOCKING'}

    factor: FloatProperty(
        name="Factor",
        default=0.5, min=0.0, max=1.0,
        description="Position across the slide span (0.5 = original position)",
    )
    use_snap: BoolProperty(
        name="Snap to Grid",
        default=True,
        description="Snap sliding vertices to the world grid (hold Ctrl to invert while sliding)",
    )
    auto_grid: BoolProperty(
        name="Auto Grid Size",
        default=True,
        description="Use the finest grid lines visible in the viewport (press A to toggle while sliding)",
    )
    grid_size: FloatProperty(
        name="Grid Size",
        default=0.1, min=0.05,
        description="Grid spacing in world units (used when Auto Grid Size is off)",
    )
    grid_step: FloatProperty(
        name="Grid Wheel Step",
        default=0.1, min=0.001,
        description="How much one mouse wheel click changes the grid size, and the smallest grid size the wheel can reach",
    )

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    # -- shared ----------------------------------------------------

    def _gather(self, context):
        """Collect (object, bmesh, items, matrix, matrix_inv) per edit object."""
        objs = []
        for obj in context.objects_in_mode_unique_data:
            if obj.type != 'MESH':
                continue
            bm = bmesh.from_edit_mesh(obj.data)
            items = _build_slide_items(bm)
            if items:
                mw = obj.matrix_world.copy()
                objs.append((obj, bm, items, mw, mw.inverted()))
        return objs

    def _apply(self, context):
        for obj, bm, items, mw, mw_inv in self._objs:
            _apply_factor(items, mw, mw_inv, self.factor, self._snap, self._grid)
            bmesh.update_edit_mesh(obj.data)

    def _items_center(self):
        center = Vector()
        count = 0
        for obj, bm, items, mw, mw_inv in self._objs:
            for v, co, target_a, target_b in items:
                center += mw @ co
                count += 1
        return center / count

    # -- non-interactive (redo panel / scripts) --------------------

    def execute(self, context):
        self._objs = self._gather(context)
        if not self._objs:
            self.report({'WARNING'}, "No edges selected")
            return {'CANCELLED'}
        self._snap = self.use_snap
        if self.auto_grid:
            self._grid = _view_grid(context, self._items_center())
        else:
            self._grid = self.grid_size
        self._apply(context)
        return {'FINISHED'}

    # -- interactive ------------------------------------------------

    def invoke(self, context, event):
        if context.area is None or context.area.type != 'VIEW_3D':
            self.report({'WARNING'}, "Must run in a 3D Viewport")
            return {'CANCELLED'}

        self._objs = self._gather(context)
        if not self._objs:
            self.report({'WARNING'}, "No edges selected")
            return {'CANCELLED'}

        # World-space anchor for mapping mouse movement to a slide factor.
        count = 0
        dir_a = Vector()
        for obj, bm, items, mw, mw_inv in self._objs:
            for v, co, target_a, target_b in items:
                dir_a += (mw @ target_a) - (mw @ co)
                count += 1
        self._center = self._items_center()
        dir_a /= count
        if dir_a.length_squared < 1e-12:
            # Symmetric rails cancel out; fall back to one vertex's rail.
            obj, bm, items, mw, mw_inv = self._objs[0]
            v, co, target_a, target_b = items[0]
            dir_a = (mw @ target_a) - (mw @ co)
        self._dir_a = dir_a

        self._snap = self.use_snap
        self._auto = self.auto_grid
        self._grid = _view_grid(context, self._center) if self._auto else self.grid_size
        self.factor = 0.5

        context.window_manager.modal_handler_add(self)
        self._update_header(context)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
            s = self._screen_dir(context)
            if s is not None:
                dm = Vector((event.mouse_x - event.mouse_prev_x,
                             event.mouse_y - event.mouse_prev_y))
                dt = dm.dot(s) / s.length_squared
                if event.shift:
                    dt *= 0.1
                # dt is in rail lengths; factor spans two rails (0..1).
                self.factor = max(0.0, min(1.0, self.factor + dt * 0.5))
            self._snap = self.use_snap != event.ctrl
            self._apply(context)
            self._update_header(context)

        elif event.type in {'LEFT_CTRL', 'RIGHT_CTRL'}:
            self._snap = self.use_snap != event.ctrl
            self._apply(context)
            self._update_header(context)

        elif event.type == 'WHEELUPMOUSE':
            self._auto = False
            self._grid = max(round(self._grid - self.grid_step, 6), self.grid_step)
            self._apply(context)
            self._update_header(context)

        elif event.type == 'WHEELDOWNMOUSE':
            self._auto = False
            self._grid = round(self._grid + self.grid_step, 6)
            self._apply(context)
            self._update_header(context)

        elif event.type == 'A' and event.value == 'PRESS':
            self._auto = not self._auto
            if self._auto:
                self._grid = _view_grid(context, self._center)
            self._apply(context)
            self._update_header(context)

        elif event.type in {'LEFTMOUSE', 'RET', 'NUMPAD_ENTER'} and event.value == 'PRESS':
            # Bake the live state into the properties so the redo panel matches.
            self.use_snap = self._snap
            self.auto_grid = self._auto
            self.grid_size = self._grid
            self._finish(context)
            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            for obj, bm, items, mw, mw_inv in self._objs:
                for v, co, target_a, target_b in items:
                    v.co = co
                bmesh.update_edit_mesh(obj.data)
            self._finish(context)
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def _screen_dir(self, context):
        region = context.region
        rv3d = context.region_data
        if region is None or rv3d is None:
            return None
        p0 = location_3d_to_region_2d(region, rv3d, self._center)
        p1 = location_3d_to_region_2d(region, rv3d, self._center + self._dir_a)
        if p0 is None or p1 is None:
            return None
        s = p1 - p0
        if s.length_squared < 1e-6:
            return None
        return s

    def _update_header(self, context):
        context.area.header_text_set(
            "Edge Slide: {:.4f} | Snap: {} (Ctrl toggles) | Grid: {:.4g} {} (A: auto, Wheel: ±{:g}) | "
            "Shift: precision | LMB/Enter: confirm, RMB/Esc: cancel".format(
                self.factor, "ON" if self._snap else "OFF", self._grid,
                "[Auto]" if self._auto else "[Manual]", self.grid_step,
            )
        )

    def _finish(self, context):
        context.area.header_text_set(None)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "factor")
        layout.prop(self, "use_snap")
        layout.prop(self, "auto_grid")
        row = layout.row()
        row.enabled = not self.auto_grid
        row.prop(self, "grid_size")
        layout.prop(self, "grid_step")


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------

def menu_func(self, context):
    self.layout.operator(MESH_OT_edge_slide_grid_snap.bl_idname)


addon_keymaps = []


def register():
    bpy.utils.register_class(MESH_OT_edge_slide_grid_snap)
    bpy.types.VIEW3D_MT_edit_mesh_edges.append(menu_func)
    bpy.types.VIEW3D_MT_edit_mesh_vertices.append(menu_func)

    kc = bpy.context.window_manager.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name='Mesh', space_type='EMPTY')
        kmi = km.keymap_items.new(
            MESH_OT_edge_slide_grid_snap.bl_idname,
            'V', 'PRESS', shift=True, alt=True,
        )
        addon_keymaps.append((km, kmi))


def unregister():
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()

    bpy.types.VIEW3D_MT_edit_mesh_vertices.remove(menu_func)
    bpy.types.VIEW3D_MT_edit_mesh_edges.remove(menu_func)
    bpy.utils.unregister_class(MESH_OT_edge_slide_grid_snap)
