# A worn item that wraps the trunk (a vest, a waistcoat, a corset) as a SHELL OF THE BODY SKIN. A foreign model of such an item, made on another mannequin, never fits the UO torso: pushing its vertices out of the body
# (uo_fit_item.py) and out of the arms in the poses (uo_pose_clear.py) tears it into spikes and ragged edges, and whatever is left in the body shows as skin through the cloth. Here the item is rebuilt from the skin:
#   1. the footprint: the skin vertices of the torso (groups GROUPS, below ZMAX) that lie within D of the fitted item (the item you made with uo_fit_item.py: it gives the outline, the length, the neckline, the armholes);
#   2. the skin faces inside that footprint (a V of the neckline is cut out of the front, VNECK), copied, moved out along the normals by GAP, subdivided once (Catmull-Clark) and smoothed (the cloth is flatter than muscle),
#      the border (neckline, armholes, hem) is smoothed too;
#   3. the item's mesh is replaced by this shell (material slots stay); run uo_bind_item.py again: every vertex follows the skin under it, so the shell can not poke through the body or tear.
# Run on the SELECTED, fitted and bound item (from Blender's Text Editor or from uo_make_item.py: "skin_shell" in a part of a recipe), then bind it again (uo_make_item.py does).
import bpy
import bmesh
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

GROUPS = ("pelvis", "spine", "chest", "clavicle")   # body groups (names start with) the shell may cover: a vertex counts when most of its weight is in them
INSIDE = 0.8          # the skin vertex counts when at least this share of its weight is in GROUPS (lower: reaches the shoulders, where the weights are shared with the arms)
D = 0.075             # m: skin farther than this from the fitted item is not covered
ZMAX = 1.56           # m: the shell does not go above this height
NECK_RADIUS = 0.0     # m: > 0: the neck stays free: skin within this horizontal distance of the neck axis (the head of the bone "neck") and above its base is not covered (the shoulder straps lie outside it)
ZMIN = -1.0           # m: nor below this
VNECK = None          # (z of the apex, z of the top, half width at the top) in m: a V cut out of the front of the shell (a vest); None = none
GAP = 0.03            # m: the shell stands this far off the skin
MIN_GAP = 0.0         # m: > 0: after the smoothing (it flattens the muscle into the skin) nothing stays closer to the skin than this: pushed out along the skin normal, smoothed, 4 rounds
SUBDIV = 1            # Catmull-Clark levels
SMOOTH = 6            # Laplacian passes of the inner vertices (the cloth is flatter than the muscle under it)
BORDER_SMOOTH = 8     # Laplacian passes along the border (neckline, armholes, hem)
MIN_PIECE = 30        # faces: islands smaller than this are dropped
REPORT = True
GROUPS = tuple(GROUPS)   # a recipe gives a list

body = bpy.data.objects["UO_Body"]
rig = bpy.data.objects["UO_Rig"]


def build(item):
    saved = rig.data.pose_position
    rig.data.pose_position = "REST"; bpy.context.view_layer.update()
    names = {g.index: g.name for g in body.vertex_groups}
    nb = len(body.data.vertices); inside = np.zeros(nb)
    for vt in body.data.vertices:
        w = {}
        for g in vt.groups:
            w[names[g.group]] = w.get(names[g.group], 0.0) + g.weight
        inside[vt.index] = sum(x for k, x in w.items() if k.startswith(GROUPS)) / max(sum(w.values()), 1e-9)
    # footprint: skin vertices near the fitted item
    bm = bmesh.new(); bm.from_mesh(item.data); bm.transform(item.matrix_world); bmesh.ops.triangulate(bm, faces=bm.faces)
    co = [v.co.copy() for v in bm.verts]; tri = [[v.index for v in f.verts] for f in bm.faces]; bm.free()
    bvh = BVHTree.FromPolygons(co, tri)
    P = [body.matrix_world @ v.co for v in body.data.vertices]
    nk = rig.matrix_world @ rig.data.bones["neck"].head_local if "neck" in rig.data.bones else Vector((0, 0, 9))
    cov = np.zeros(nb, bool)
    for i, p in enumerate(P):
        if not (ZMIN <= p.z <= ZMAX) or inside[i] < INSIDE:
            continue
        if NECK_RADIUS > 0 and p.z > nk.z - 0.02 and (p.x - nk.x) ** 2 + (p.y - nk.y) ** 2 < NECK_RADIUS ** 2:
            continue
        loc, nrm, fi, d = bvh.find_nearest(p, D * 1.5)
        cov[i] = loc is not None and d < D
        if cov[i] and VNECK is not None and p.y < 0.0:                    # the V of the neckline (the front is -Y)
            zv, zt, hw = VNECK
            if p.z >= zv and abs(p.x) < hw * min((p.z - zv) / max(zt - zv, 1e-6), 1.0):
                cov[i] = False
    sh = bmesh.new(); sh.from_mesh(body.data); sh.verts.ensure_lookup_table(); sh.faces.ensure_lookup_table()
    drop = [f for f in sh.faces if not all(cov[v.index] for v in f.verts)]
    bmesh.ops.delete(sh, geom=drop, context="FACES")
    bmesh.ops.delete(sh, geom=[v for v in sh.verts if not v.link_faces], context="VERTS")
    # drop small islands
    seen, kill = set(), []
    for f in sh.faces:
        if f in seen:
            continue
        comp, stack = [f], [f]; seen.add(f)
        while stack:
            u = stack.pop()
            for e in u.edges:
                for g in e.link_faces:
                    if g not in seen:
                        seen.add(g); comp.append(g); stack.append(g)
        if len(comp) < MIN_PIECE:
            kill += comp
    if kill:
        bmesh.ops.delete(sh, geom=kill, context="FACES")
        bmesh.ops.delete(sh, geom=[v for v in sh.verts if not v.link_faces], context="VERTS")
    sh.normal_update()
    for v in sh.verts:
        v.co = v.co + v.normal * GAP                                      # in the body's own space
    me = bpy.data.meshes.new("uo_shell"); sh.to_mesh(me); sh.free()
    tmp = bpy.data.objects.new("uo_shell_tmp", me); tmp.matrix_world = body.matrix_world; bpy.context.scene.collection.objects.link(tmp)
    if SUBDIV > 0:
        md = tmp.modifiers.new("sub", "SUBSURF"); md.levels = SUBDIV; md.render_levels = SUBDIV; md.subdivision_type = "CATMULL_CLARK"
        bpy.context.view_layer.update()
        me2 = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get())); tmp.modifiers.clear(); tmp.data = me2; bpy.data.meshes.remove(me)
    out = bmesh.new(); out.from_mesh(tmp.data)
    for _ in range(SMOOTH):
        bmesh.ops.smooth_vert(out, verts=[v for v in out.verts if not v.is_boundary], factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    for _ in range(BORDER_SMOOTH):
        new = {}
        for v in [v for v in out.verts if v.is_boundary]:
            nb2 = [e.other_vert(v) for e in v.link_edges if e.is_boundary]
            if len(nb2) == 2:
                new[v] = (nb2[0].co + nb2[1].co) * 0.5
        for v, c in new.items():
            v.co = v.co * 0.4 + c * 0.6
    if MIN_GAP > 0:
        sk = bmesh.new(); sk.from_mesh(body.data); bmesh.ops.triangulate(sk, faces=sk.faces); sk.transform(body.matrix_world)
        skbvh = BVHTree.FromPolygons([v.co.copy() for v in sk.verts], [[v.index for v in f.verts] for f in sk.faces]); sk.free()
        Mw = body.matrix_world; Mi = Mw.inverted()
        for _ in range(4):
            moved = 0
            for v in out.verts:
                p = Mw @ v.co
                loc, nrm, fi, d = skbvh.find_nearest(p, 0.2)
                if loc is None:
                    continue
                sd = (p - loc).dot(nrm)
                if sd < MIN_GAP:
                    v.co = Mi @ (p + nrm * (MIN_GAP - sd)); moved += 1
            if not moved:
                break
            bmesh.ops.smooth_vert(out, verts=[v for v in out.verts if not v.is_boundary], factor=0.3, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    out.transform(body.matrix_world); out.transform(item.matrix_world.inverted())        # into the item's own space
    for lay in list(out.verts.layers.deform):                                              # the weights of the BODY's groups came with the copied faces: they mean nothing on the item (uo_bind_item.py makes its own)
        out.verts.layers.deform.remove(lay)
    for lay in list(out.verts.layers.shape):
        out.verts.layers.shape.remove(lay)
    item.data.clear_geometry()
    out.to_mesh(item.data); nv, nf = len(out.verts), len(out.faces); out.free()
    for p in item.data.polygons:
        p.use_smooth = True
    item.data.update()
    tmp_mesh = tmp.data
    bpy.data.objects.remove(tmp, do_unlink=True)
    if tmp_mesh.users == 0:
        bpy.data.meshes.remove(tmp_mesh)
    rig.data.pose_position = saved
    if REPORT:
        print("uo_skin_shell: %s | footprint %d skin vertices, shell %d vertices / %d faces, %.1f cm off the skin, up to z %.2f m" % (item.name, int(cov.sum()), nv, nf, 100 * GAP, ZMAX))


for ob in [o for o in bpy.context.selected_objects if o.type == "MESH" and o != body]:
    build(ob)
