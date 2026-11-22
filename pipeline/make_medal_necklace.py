"""A ribbon medal (glTF: a flat loop of ribbon + a medal on a ring) -> a necklace lying on the UO body, as a new glTF in body coordinates (m, rest pose).

    python make_medal_necklace.py MEDAL.glb OUT.glb [--base ../model/UO_Body_0x190.blend] [--medal-d 0.13] [--ribbon-w 0.06] [--ring-z 1.385]

The medal (disc + rim + ring, the faces of the file that are not red) is kept as it is, scaled to --medal-d and put on the sternum between the breasts,
tilted to the slope of the chest and set on the skin (touching, not through). The ribbon of the file hangs as a long flat loop that does not fit a body, so
it is rebuilt: a closed strip of --ribbon-w width and 3 mm thickness, in the same red texture, that leaves the ring in a V up the chest, goes over the
collar bones and the sides of the neck and round the nape; every point of it is snapped to the skin (the body without the head, rest pose), so it lies on the
skin. The result is static: bind it rigid on the chest (recipe prepare PART "quiver", AUTOFIT / FIT / DENSIFY off, see model/items/medal/).
"""
import argparse, math, os, sys
import bpy, bmesh
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

ap = argparse.ArgumentParser()
ap.add_argument("medal"); ap.add_argument("out")
ap.add_argument("--base", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model", "UO_Body_0x190.blend"))
ap.add_argument("--medal-d", type=float, default=0.13)       # m, diameter of the medal disc (the file: 0.31)
ap.add_argument("--ribbon-w", type=float, default=0.06)       # m, width of the ribbon (at 36 px/m 3.2 cm was 1 px: a broken line)
ap.add_argument("--ring-z", type=float, default=1.385)        # m, height of the ring the ribbon passes through (the medal hangs below it)
ap.add_argument("--gap", type=float, default=0.006)           # m, medal off the skin
ap.add_argument("--ribbon-gap", type=float, default=0.012)    # m, ribbon off the skin (the posed skin of the neck / shoulders pokes through a ribbon that lies on it)
ap.add_argument("--thick", type=float, default=0.003)         # m, thickness of the ribbon
ap.add_argument("--ribbon-rgb", type=float, nargs=3, default=(0.45, 0.03, 0.06))   # sRGB 0..1 of the ribbon (the file: a bright red 0.95 0.2 0.15)
a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])

# ---- the body (rest pose), without the head: the skin the necklace lies on -------------------------------------------------------------------------
bpy.ops.wm.open_mainfile(filepath=os.path.abspath(a.base))
rig = bpy.data.objects["UO_Rig"]; rig.data.pose_position = "REST"; bpy.context.view_layer.update()
body = bpy.data.objects["UO_Body"]
me = body.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
head = np.zeros(len(me.vertices), bool)
for i, v in enumerate(body.data.vertices):
    head[i] = sum(g.weight for g in v.groups if body.vertex_groups[g.group].name == "head") > 0.5
BV = [tuple((body.matrix_world @ v.co)[:]) for v in me.vertices]
tris = [(f[0], f[k], f[k + 1]) for f in (tuple(p.vertices) for p in me.polygons if not head[list(p.vertices)].any()) for k in range(1, len(f) - 1)]
bvh = BVHTree.FromPolygons(BV, tris)


def front_y(x, z):
    """the skin at the front: a ray from inside the trunk towards -Y"""
    h = bvh.ray_cast(Vector((x, 0.0, z)), Vector((0, -1, 0)))
    return h[0].y if h[0] else None


def snap(p, gap=0.0):
    loc, n, _, _ = bvh.find_nearest(Vector(p))
    return np.array(loc + n * gap), np.array(n)


# ---- the medal of the file ------------------------------------------------------------------------------------------------------------------------
bpy.ops.import_scene.gltf(filepath=os.path.abspath(a.medal))
src = [o for o in bpy.context.selected_objects if o.type == "MESH"][0]
mat = src.data.materials[0]
img = next(n.image for n in mat.node_tree.nodes if n.type == "TEX_IMAGE" and n.image.name == "texture_0")
W, H = img.size; px = np.array(img.pixels[:], np.float32).reshape(H, W, 4)[::-1]           # row 0 = top


def color_at(u, v):
    return px[min(H - 1, max(0, int((1 - v) * H))), min(W - 1, max(0, int(u * W)))][:3]


def is_red(c):
    return c[0] > 2.0 * c[1] and c[0] > 2.0 * c[2]


bm = bmesh.new(); bm.from_mesh(src.data); uvl = bm.loops.layers.uv.active
red = []
for f in bm.faces:
    u = np.mean([l[uvl].uv[0] for l in f.loops]); v = np.mean([l[uvl].uv[1] for l in f.loops])
    if is_red(color_at(u, v)) or max(l.vert.co.z for l in f.loops) > -0.50 or abs(np.mean([l.vert.co.x for l in f.loops])) > 0.2:      # the ribbon (red), anything above the ring
        red.append(f)
bmesh.ops.delete(bm, geom=red, context="FACES")
bm.verts.ensure_lookup_table()
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
medal_n = len(bm.faces)

# a spot of the atlas that is plain red, for the UV of the ribbon
bm2 = bmesh.new(); bm2.from_mesh(src.data)
best, best_uv = -1, None
rng = np.random.default_rng(1)
for _ in range(4000):
    iu, iv = int(rng.integers(12, W - 12)), int(rng.integers(12, H - 12))
    blk = px[iv - 8:iv + 9, iu - 8:iu + 9, :3]
    if (blk[..., 0] > 2 * blk[..., 1]).all() and (blk[..., 0] > 2 * blk[..., 2]).all():
        sc_ = blk[..., 0].mean() - blk.std()
        if sc_ > best:
            best, best_uv = sc_, (iu / W, 1 - iv / H)
bm2.free()
iu, iv = int(best_uv[0] * W), int((1 - best_uv[1]) * H)         # the patch the ribbon uses is painted the ribbon colour (no medal face uses it: they are not red)
px_ = np.array(img.pixels[:], np.float32).reshape(H, W, 4)
px_[H - 1 - iv - 8:H - 1 - iv + 9, iu - 8:iu + 9, :3] = np.array(a.ribbon_rgb, np.float32)
img.pixels.foreach_set(px_.ravel()); img.update()
print("medal faces %d (of %d), red uv %s" % (medal_n, len(src.data.polygons), best_uv))

M = np.array([v.co[:] for v in bm.verts])
RING_C = np.array([0.0, 0.006, -0.604])                  # the ring hole of the file (measured on a zoomed render)
k = a.medal_d / 0.306
M = (M - RING_C) * k                                      # ring centre at the origin, medal hangs along -z (glTF Z-up after import)
print("medal after scale: x %.3f..%.3f  z %.3f..%.3f  y %.4f..%.4f" % (M[:, 0].min(), M[:, 0].max(), M[:, 2].min(), M[:, 2].max(), M[:, 1].min(), M[:, 1].max()))

# drape the medal over the skin: every vertex keeps its x and height and its thickness, and lies GAP in front of the skin under it (a flat disc over the sternum and the breasts
# touches only the middle of the chest, the skin under its lower half falls away); the skin line is smoothed over the mesh so that the pecs do not wrinkle the disc
Mr = M.copy(); Mr[:, 2] += a.ring_z
t_ = Mr[:, 1].max() - Mr[:, 1]                                  # thickness in front of the back plane (the front is -Y)
bm.verts.ensure_lookup_table()
fy = np.array([front_y(p[0], p[2]) for p in Mr], dtype=float)
bad = np.isnan(fy); fy[bad] = np.nanmean(fy)
b = fy - a.gap
edges = np.array([[e.verts[0].index, e.verts[1].index] for e in bm.edges])
for _ in range(6):
    acc = np.zeros_like(b); cnt = np.zeros_like(b)
    np.add.at(acc, edges[:, 0], b[edges[:, 1]]); np.add.at(acc, edges[:, 1], b[edges[:, 0]])
    np.add.at(cnt, edges[:, 0], 1); np.add.at(cnt, edges[:, 1], 1)
    b = np.where(cnt > 0, 0.5 * b + 0.5 * acc / np.maximum(cnt, 1), b)
b = np.minimum(b, fy - a.gap)                      # never behind the skin line (smoothing may push a vertex into a breast)
Mr[:, 1] = b - t_
ring_y = front_y(0.0, a.ring_z)
print("medal: draped on the skin, back %.1f mm from it on average, ring y %.3f (skin %.3f)" % (1000 * np.mean(fy - Mr[:, 1] - t_), Mr[:, 1].mean(), ring_y))
for v, p in zip(bm.verts, Mr):
    v.co = p

# ---- the ribbon: a closed strip, snapped to the skin -----------------------------------------------------------------------------------------------
ctrl = [(0.0, None, a.ring_z + 0.004), (0.0, None, a.ring_z + 0.022), (0.012, None, a.ring_z + 0.042), (0.034, None, a.ring_z + 0.078),
        (0.058, None, a.ring_z + 0.115), (0.085, -0.118, 1.525), (0.113, -0.07, 1.55), (0.120, -0.02, 1.575), (0.103, 0.036, 1.565), (0.062, 0.062, 1.552), (0.0, 0.068, 1.548)]
pts = []
for x, y, z in ctrl:
    if y is None:
        y = front_y(x, z) - 0.01
    pts.append((x, y, z))
pts = np.array(pts)
half = np.array([[-p[0], p[1], p[2]] for p in pts[::-1]][1:])     # mirror (the nape point is shared)
path = np.vstack([pts, half])                                     # tip (right) -> nape -> tip (left)


def catmull(P, n_per=14):
    P = np.vstack([P[0] - (P[1] - P[0]), P, P[-1] + (P[-1] - P[-2])])
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for t in np.linspace(0, 1, n_per, endpoint=False):
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(P[-2])
    return np.array(out)


C = catmull(path)
for it in range(4):                                               # snap to the skin, smooth along the path, snap again
    S = np.array([snap(p)[0] for p in C])
    Sm = S.copy(); Sm[1:-1] = 0.25 * S[:-2] + 0.5 * S[1:-1] + 0.25 * S[2:]
    C = Sm
cen, nor = zip(*[snap(p, 0.0) for p in C]); cen = np.array(cen); nor = np.array(nor)
tan = np.gradient(cen, axis=0); tan /= np.linalg.norm(tan, axis=1)[:, None] + 1e-12
NW = 7                                                            # points across the width
u = np.linspace(-0.5, 0.5, NW) * a.ribbon_w
rows_in, rows_out = [], []
for i in range(len(cen)):
    n_i = nor[i]; b = np.cross(n_i, tan[i]); b /= np.linalg.norm(b) + 1e-12
    r_in, r_out = [], []
    for uu in u:
        q, nq = snap(cen[i] + b * uu, 0.0)
        r_in.append(q + nq * a.ribbon_gap); r_out.append(q + nq * (a.ribbon_gap + a.thick))
    rows_in.append(r_in); rows_out.append(r_out)
rows_in = np.array(rows_in); rows_out = np.array(rows_out)
# the left strand lies on top of the right one at the ring: lift the second half of the last 4 cm by one thickness
for i in range(len(cen)):
    if i > len(cen) // 2 and np.linalg.norm(cen[i] - cen[-1]) < 0.045:
        rows_in[i] += nor[i] * a.thick; rows_out[i] += nor[i] * a.thick

nv = len(cen)
uv_red = best_uv
rv = []
for layer in (rows_out, rows_in):
    ids = [[bm.verts.new(Vector(layer[i][j])) for j in range(NW)] for i in range(nv)]
    rv.append(ids)
out_ids, in_ids = rv
uvl = bm.loops.layers.uv.verify()


def add(vs, flip=False):
    vs = list(reversed(vs)) if flip else vs
    f = bm.faces.new(vs)
    for l in f.loops:
        l[uvl].uv = uv_red
    return f


for i in range(nv - 1):
    for j in range(NW - 1):
        add([out_ids[i][j], out_ids[i + 1][j], out_ids[i + 1][j + 1], out_ids[i][j + 1]], flip=True)      # outer face (away from the skin)
        add([in_ids[i][j], in_ids[i + 1][j], in_ids[i + 1][j + 1], in_ids[i][j + 1]])                    # inner face (towards the skin)
for i in range(nv - 1):                                                                                    # the two long edges
    add([out_ids[i][0], out_ids[i + 1][0], in_ids[i + 1][0], in_ids[i][0]])
    add([out_ids[i][NW - 1], in_ids[i][NW - 1], in_ids[i + 1][NW - 1], out_ids[i + 1][NW - 1]])
for end in (0, nv - 1):                                                                                    # the two ends (at the ring)
    for j in range(NW - 1):
        add([out_ids[end][j], in_ids[end][j], in_ids[end][j + 1], out_ids[end][j + 1]], flip=(end == 0))
bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))

res = bpy.data.meshes.new("medal_necklace"); bm.to_mesh(res); bm.free()
res.materials.append(mat)
ob = bpy.data.objects.new("medal_necklace", res); bpy.context.scene.collection.objects.link(ob)
for o in list(bpy.data.objects):
    if o is not ob:
        bpy.data.objects.remove(o, do_unlink=True)
Pn = np.array([v.co[:] for v in res.vertices])
print("necklace: %d vertices, x %.3f..%.3f, y %.3f..%.3f, z %.3f..%.3f" % (len(Pn), *[f(Pn[:, i]) for i in range(3) for f in (np.min, np.max)]))
bpy.ops.object.select_all(action="DESELECT"); ob.select_set(True); bpy.context.view_layer.objects.active = ob
bpy.ops.export_scene.gltf(filepath=os.path.abspath(a.out), export_format="GLB", use_selection=True, export_apply=True)
print("wrote", a.out)
