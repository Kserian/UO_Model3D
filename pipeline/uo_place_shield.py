# Put the SELECTED shield on the left forearm the way UO holds a shield (the bone shield.L: fitted frame by frame to the
# original UO shield, anim 582) and slide it towards the arm until its back touches the forearm. Run it from Blender's
# Text Editor.
# 1. Model / import the shield upright with its face towards the front view (Numpad 1), top up, point down.
# 2. Select it and run this script (the body is put in Rest Position while it works, as it was afterwards).
# 3. Then uo_bind_item.py with PART = "shield".
# Running it again places the shield again (any manual move is replaced).
import bpy, math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

GAP = 0.01            # m left between the back of the shield and the forearm skin
SHIFT = 0.0           # m, extra move along the shield's own axis after it touches (+ = further out, - = closer)

# calibration (forearm.L bone space): centre, face normal of the shield disc
CENTRE = Vector((-0.07, 0.21, -0.03))
NORMAL = Vector((-0.99622, -0.07987, 0.03415)).normalized()

rig = bpy.data.objects["UO_Rig"]
body = bpy.data.objects["UO_Body"]


def arm_skin_bvh():
    """left forearm skin in world space (Rest Position)"""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = body.evaluated_get(dg); me = ev.to_mesh()
    V = [ev.matrix_world @ v.co for v in me.vertices]
    names = [g.name for g in body.vertex_groups]
    fa = [i for i, n in enumerate(names) if n == "forearm.L"]
    W = np.zeros(len(me.vertices))
    for v in body.data.vertices:
        for g in v.groups:
            if g.group in fa:
                W[v.index] += g.weight
    me.calc_loop_triangles()
    tris = [t.vertices[:] for t in me.loop_triangles if np.mean(W[list(t.vertices)]) > 0.5]
    ev.to_mesh_clear()
    return BVHTree.FromPolygons(V, tris)


def place(ob):
    if "shield.L" in rig.data.bones:                                  # the shield bone: X width, Y height (top), Z face
        M = rig.matrix_world @ rig.data.bones["shield.L"].matrix_local; M3 = M.to_3x3().normalized()
        c = M.translation.copy(); n = M3.col[2].normalized(); up = M3.col[1].normalized()
    else:                                                             # older file: the calibrated disc on forearm.L
        b = rig.data.bones["forearm.L"]
        M = rig.matrix_world @ b.matrix_local; M3 = M.to_3x3()
        c = M @ CENTRE
        n = (M3 @ NORMAL).normalized()
        up = -(M3 @ NORMAL.cross(Vector((0, 1, 0)))).normalized()
    y = -n                                                            # model -Y (front) -> n
    x = y.cross(up).normalized(); z = x.cross(y).normalized()
    R = Matrix((x, y, z)).transposed().to_4x4()
    co = np.array([v.co[:] for v in ob.data.vertices])
    mid = Vector(((co.min(0) + co.max(0)) / 2).tolist())              # middle of the shield's bounds
    S = Matrix.Diagonal(ob.matrix_world.to_scale()).to_4x4()
    base = Matrix.Translation(c) @ R @ S @ Matrix.Translation(-mid)
    back = (R.to_3x3() @ Vector((0, 1, 0))).normalized()              # towards the arm
    bvh = arm_skin_bvh()
    P0 = [base @ Vector(p) for p in co]

    def closest(s):
        d = back * s
        return min(bvh.find_nearest(p + d)[3] for p in P0)

    s = -0.25                                                         # start well away from the arm
    while s < 0.25 and closest(s + 0.01) > GAP:
        s += 0.01
    for _ in range(10):                                               # refine to 1 mm
        if closest(s + 0.001) > GAP:
            s += 0.001
    s += SHIFT
    ob.rotation_mode = "XYZ"
    ob.matrix_world = Matrix.Translation(back * s) @ base
    print("uo_place_shield: %s on the left forearm, back %.0f mm from the skin" % (ob.name, closest(s) * 1000))


pose = rig.data.pose_position
rig.data.pose_position = "REST"
bpy.context.view_layer.update()
try:
    obs = [o for o in bpy.context.selected_objects if o.type == "MESH" and o != body]
    if not obs:
        raise RuntimeError("select the shield first")
    for ob in obs:
        place(ob)
finally:
    rig.data.pose_position = pose
