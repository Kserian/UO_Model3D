# A carrying sash / strap for an item hung in front of the body (a drum): a ribbon that starts on the top of the item at two points, runs back over the shoulders, lies on the skin of the
# upper back and joins there in a U (the two straps of a baldric). Built in the rest pose, in world coordinates, from waypoints:
#   - the two ends sit on the item (ATTACH: the centre of the first point in m, x mirrored about ATTACH_X0 +- ATTACH_DX),
#   - the points of the shoulder and the back (SHOULDER, BACK, JOIN: x, y, z targets of the left side, mirrored for the right) are pulled onto the skin (nearest point of the body) and lifted by OFFSET + THICK/2
#     along its normal, so the ribbon lies on the skin and never in it; the span from the item to the first skin point is free.
# The ribbon is a closed solid WIDTH wide and THICK thick (a 4 cm strap is 1.5 px at 36 px/m: WIDTH 0.06), one object named NAME with its own material, selected after the run (with whatever was selected before).
# Run from uo_make_item.py (recipe "rigid": {"sash": {...}}) before uo_bind_item.py; its settings are overridden by name.
import bpy
import bmesh
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

NAME = "sash"
ATTACH = (-0.02, -0.32, 1.46)   # centre of the top of the item where the straps start (m, rest pose); x of the two ends = ATTACH[0] +- ATTACH_DX
ATTACH_DX = 0.07
SHOULDER = (0.10, -0.14, 1.47)  # skin target (left side, +x): the front of the shoulder where the strap leaves the chest
BACK = [(0.13, 0.0, 1.50), (0.11, 0.12, 1.40), (0.06, 0.14, 1.28)]   # skin targets over the shoulder and down the upper back (left side); the next point is the JOIN
JOIN = (0.0, 0.14, 1.22)        # the two straps meet here (x = 0)
WIDTH = 0.06
THICK = 0.012
OFFSET = 0.008                  # m: gap between the skin and the underside of the strap
STEP = 0.01                     # m: spacing of the path samples
COLOR = (0.30, 0.16, 0.08)
SELECT = True

body = bpy.data.objects["UO_Body"]


def skin_bvh():
    bpy.context.view_layer.update()
    eb = body.evaluated_get(bpy.context.evaluated_depsgraph_get()); mb = eb.to_mesh(); mb.calc_loop_triangles()
    bv = BVHTree.FromPolygons([eb.matrix_world @ v.co for v in mb.vertices], [t.vertices[:] for t in mb.loop_triangles]); eb.to_mesh_clear()
    return bv


def on_skin(bv, p, lift):
    loc, nrm, fi, d = bv.find_nearest(Vector(p), 0.5)
    return np.array(loc + nrm * lift), np.array(nrm)


def catmull(P, step):
    """Catmull-Rom curve through the points P (n, 3), samples about `step` apart"""
    P = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]]); out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        n = max(2, int(np.linalg.norm(p2 - p1) / step))
        for t in np.linspace(0, 1, n, endpoint=False):
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(P[-2])
    return np.array(out)


bv = skin_bvh()
lift = OFFSET + THICK / 2
way = []                                                          # left side: attach -> shoulder -> back ... -> join; the right side mirrored
for tgt in [SHOULDER] + list(BACK) + [JOIN]:
    p, n = on_skin(bv, tgt, lift); way.append(p)
way = np.array(way); way[-1][0] = 0.0
a_l = np.array([ATTACH[0] + ATTACH_DX, ATTACH[1], ATTACH[2]]); a_r = np.array([ATTACH[0] - ATTACH_DX, ATTACH[1], ATTACH[2]])
left = np.vstack([a_l, way])
right = left[::-1].copy(); right[:, 0] *= -1; right[-1] = a_r; right = right[:-1] if False else right
right = np.vstack([way[::-1][1:] * np.array([-1, 1, 1]), a_r])
path = np.vstack([left, right])
curve = catmull(path, STEP)
# lay every sample on the skin (the free span between the item and the shoulder keeps its straight line: only samples nearer than 6 cm to the skin are moved onto it)
pts, nrm = [], []
for p in curve:
    q, n = on_skin(bv, p, lift)
    d = np.linalg.norm(p - (q - n * lift))
    if d < 0.06:
        pts.append(q); nrm.append(n)
    else:
        pts.append(p); nrm.append(None)
pts = np.array(pts)
for i, n in enumerate(nrm):                                       # free samples take the normal of the nearest skin sample (up for the span over the chest)
    if n is None:
        j = next((k for k in range(len(nrm)) if nrm[k] is not None and k > i), None) if i < len(nrm) // 2 else next((k for k in range(i, -1, -1) if nrm[k] is not None), None)
        nrm[i] = nrm[j] if j is not None else np.array([0.0, 0.0, 1.0])
nrm = np.array(nrm)
for _ in range(3):                                                # smooth the path a little (the nearest-point projection jitters on the muscle), then keep it off the skin
    pts[1:-1] = 0.25 * pts[:-2] + 0.5 * pts[1:-1] + 0.25 * pts[2:]
    nrm[1:-1] = 0.25 * nrm[:-2] + 0.5 * nrm[1:-1] + 0.25 * nrm[2:]
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-9)
for i in range(len(pts)):
    q, n = on_skin(bv, pts[i], 0.0)
    if np.linalg.norm(pts[i] - q) < 0.06:
        d = float((pts[i] - q) @ n)
        if d < lift:
            pts[i] = pts[i] + n * (lift - d)
tan = np.gradient(pts, axis=0); tan /= np.maximum(np.linalg.norm(tan, axis=1, keepdims=True), 1e-9)
bin_ = np.cross(nrm, tan); bin_ /= np.maximum(np.linalg.norm(bin_, axis=1, keepdims=True), 1e-9)
n_s = len(pts)
bm = bmesh.new()
rows = []
for i in range(n_s):                                              # four corners per cross-section: top-left, top-right, bottom-right, bottom-left
    c = [pts[i] + nrm[i] * THICK / 2 - bin_[i] * WIDTH / 2, pts[i] + nrm[i] * THICK / 2 + bin_[i] * WIDTH / 2, pts[i] - nrm[i] * THICK / 2 + bin_[i] * WIDTH / 2, pts[i] - nrm[i] * THICK / 2 - bin_[i] * WIDTH / 2]
    rows.append([bm.verts.new(tuple(x)) for x in c])
for i in range(n_s - 1):
    for k in range(4):
        bm.faces.new([rows[i][k], rows[i][(k + 1) % 4], rows[i + 1][(k + 1) % 4], rows[i + 1][k]])
bm.faces.new(rows[0][::-1]); bm.faces.new(rows[-1])
bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
me = bpy.data.meshes.new(NAME); bm.to_mesh(me); bm.free()
for p in me.polygons:
    p.use_smooth = False
mat = bpy.data.materials.new(NAME); mat.use_nodes = True
b = mat.node_tree.nodes["Principled BSDF"]; b.inputs["Base Color"].default_value = (*COLOR, 1.0); b.inputs["Roughness"].default_value = 0.7
me.materials.append(mat)
ob = bpy.data.objects.new(NAME, me)
(bpy.data.collections.get("Clothing") or bpy.context.scene.collection).objects.link(ob)
if SELECT:
    ob.select_set(True)
# report: how close the sash comes to the skin along the strap (min gap over the contact part), the length
gaps = []
for p in pts:
    q, n = on_skin(bv, p, 0.0)
    dd = float((p - q) @ n)
    if np.linalg.norm(p - q) < 0.06:
        gaps.append(dd - THICK / 2)
print("uo_make_sash: %s: %d samples, length %.2f m, %d vertices, gap to the skin min %.1f mm median %.1f mm" % (NAME, n_s, float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum()), len(me.vertices), 1000 * min(gaps), 1000 * float(np.median(gaps))))
