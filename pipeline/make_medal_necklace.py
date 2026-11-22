"""A ribbon medal (glTF: a flat loop of ribbon + a medal on a ring) -> a necklace lying on the UO body, as a new glTF in body coordinates (m, rest pose).

    python make_medal_necklace.py MEDAL.glb OUT.glb [--base ../model/UO_Body_0x190.blend] [--medal-d 0.17] [--ribbon-w 0.06] [--ring-z 1.385]

The medal (disc, rim, recessed face, ring: built here, plain colours painted into flat spots of the normal map of the file) is --medal-d wide and put on the sternum between the breasts,
tilted to the slope of the chest and set on the skin (touching, not through). The ribbon of the file hangs as a long flat loop that does not fit a body, so
it is rebuilt: a closed round cord of --ribbon-w diameter, in the same red texture, that leaves the ring in a V up the chest, goes over the
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
ap.add_argument("--medal-d", type=float, default=0.17)       # m, diameter of the medal disc (the file: 0.31)
ap.add_argument("--ribbon-w", type=float, default=0.045)      # m, DIAMETER of the cord the ribbon is modelled as (a flat strip changes its width with the angle it is seen at: edge-on on the shoulders it was a broken 1-px line; a round cord is the same width from every side)
ap.add_argument("--ring-z", type=float, default=1.385)        # m, height of the ring the ribbon passes through (the medal hangs below it)
ap.add_argument("--gap", type=float, default=0.014)           # m, medal off the skin (in front of the end of the ribbon)
ap.add_argument("--paths", default="")                        # JSON: the cord axis and the medal disc (rest pose) for medal_sprite.py (the 2D drawing of the necklace)
ap.add_argument("--rim-rgb", type=float, nargs=3, default=(0.42, 0.42, 0.45))     # sRGB of the rim and the ring of the medal
ap.add_argument("--face-rgb", type=float, nargs=3, default=(0.74, 0.74, 0.76))    # sRGB of the face of the medal
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


# ---- the texture of the file: three flat patches (ribbon, medal rim, medal face) painted with plain colours ------------------------------------------------
bpy.ops.import_scene.gltf(filepath=os.path.abspath(a.medal))
src = [o for o in bpy.context.selected_objects if o.type == "MESH"][0]
mat = src.data.materials[0]
img = next(n.image for n in mat.node_tree.nodes if n.type == "TEX_IMAGE" and n.image.name == "texture_0")
nimg = bpy.data.images["normal"]
W, H = img.size
nrm_px = np.array(nimg.pixels[:], np.float32).reshape(nimg.size[1], nimg.size[0], 4)
px_ = np.array(img.pixels[:], np.float32).reshape(H, W, 4)
# the file's texture is an atlas of 2048 px with a bumpy normal map: take 17 x 17 px blocks where the normal map is flat (no relief on the faces that use them)
flat = []
rng = np.random.default_rng(3)
for _ in range(6000):
    iu, iv = int(rng.integers(12, W - 12)), int(rng.integers(12, H - 12))
    blk = nrm_px[iv - 8:iv + 9, iu - 8:iu + 9, :3]
    dev = np.abs(blk - np.array([0.5, 0.5, 1.0])).max()
    if dev < 0.06 and all(abs(iu - u) + abs(iv - v) > 40 for u, v in flat):
        flat.append((iu, iv))
    if len(flat) == 3:
        break
assert len(flat) == 3, "no flat patch of the normal map found"
UV = {}
for name, (iu, iv), rgb in zip(("ribbon", "rim", "face"), flat, (a.ribbon_rgb, a.rim_rgb, a.face_rgb)):
    px_[iv - 8:iv + 9, iu - 8:iu + 9, :3] = np.array(rgb, np.float32)
    px_[iv - 8:iv + 9, iu - 8:iu + 9, 3] = 1.0
    UV[name] = (iu / W, iv / H)                                   # bpy pixels: row 0 is the BOTTOM of the image, so v = row / H
img.pixels.foreach_set(px_.ravel()); img.update()
print("patches (u, v):", {k: (round(v[0], 3), round(v[1], 3)) for k, v in UV.items()})

# ---- the medal: a disc with a raised rim, a recessed face and a hanging ring, built flat (x right, z up, the face towards -Y), 1 = the disc diameter ---------
D = a.medal_d
bm = bmesh.new()
uvl = bm.loops.layers.uv.verify()
NS = 40


def prism_ring(r_out, r_in, y_back, y_front, zc, uv):
    """a flat ring (annulus) of thickness y_back..y_front (y_front < y_back: the front is -Y): outer wall, front, inner wall, back; own vertices per face group (hard edges)"""
    ang = np.linspace(0, 2 * np.pi, NS, endpoint=False)
    P = lambda r, y: [bm.verts.new((r * np.sin(t), y, zc + r * np.cos(t))) for t in ang]
    def quad(ring_a, ring_b, flip=False):
        for i in range(NS):
            j = (i + 1) % NS
            vs = [ring_a[i], ring_a[j], ring_b[j], ring_b[i]]
            f = bm.faces.new(vs[::-1] if flip else vs)
            for l in f.loops:
                l[uvl].uv = uv
    quad(P(r_out, y_back), P(r_out, y_front), flip=False)           # outer wall
    quad(P(r_out, y_front), P(r_in, y_front), flip=False)           # front
    quad(P(r_in, y_front), P(r_in, y_back), flip=False)             # inner wall
    quad(P(r_in, y_back), P(r_out, y_back), flip=False)             # back


def disc(r, y, zc, uv, front=True):
    ang = np.linspace(0, 2 * np.pi, NS, endpoint=False)
    c = bm.verts.new((0, y, zc)); ring = [bm.verts.new((r * np.sin(t), y, zc + r * np.cos(t))) for t in ang]
    for i in range(NS):
        f = bm.faces.new([c, ring[i], ring[(i + 1) % NS]] if front else [c, ring[(i + 1) % NS], ring[i]])
        for l in f.loops:
            l[uvl].uv = uv


R = 0.5 * D; rw = 0.07 * D; th = 0.08 * D; zd = -0.62 * D              # disc radius, rim width, thickness, disc centre below the ring centre
prism_ring(R, R - rw, 0.0, -th, zd, UV["rim"])                      # rim, full thickness
disc(R - rw, -0.45 * th, zd, UV["face"], front=True)               # recessed face
disc(R, 0.0, zd, UV["rim"], front=False)                           # back
prism_ring(0.195 * D, 0.11 * D, 0.0, -0.5 * th, 0.0, UV["rim"])    # the ring the ribbon passes through (flat, thinner than the disc)
bm.verts.ensure_lookup_table()
bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
M = np.array([v.co[:] for v in bm.verts]); M[:, 1] += 0.5 * th      # the disc centred on y = 0
print("medal: %d vertices, x %.3f..%.3f  z %.3f..%.3f" % (len(M), M[:, 0].min(), M[:, 0].max(), M[:, 2].min(), M[:, 2].max()))

# drape the medal over the skin: every vertex keeps its x and height and its thickness, and lies GAP in front of the skin under it (a flat disc over the sternum and the breasts
# touches only the middle of the chest, the skin under its lower half falls away); the skin line is averaged over 1.5 cm round the vertex so that the pecs do not wrinkle the disc
Mr = M.copy(); Mr[:, 2] += a.ring_z
t_ = Mr[:, 1].max() - Mr[:, 1]                                  # thickness in front of the back plane (the front is -Y)
rr = 0.025


def skin_line(x, z):
    ys = [front_y(x + dx, z + dz) for dx in (-rr, 0, rr) for dz in (-rr, 0, rr)]
    ys = [v for v in ys if v is not None]
    return (np.mean(ys), min(ys)) if ys else (np.nan, np.nan)


sl = np.array([skin_line(p[0], p[2]) for p in Mr])
sl[np.isnan(sl[:, 0])] = np.nanmean(sl, axis=0)
b = np.minimum(sl[:, 0], sl[:, 1] + 0.004) - a.gap               # the averaged skin line, but at most 4 mm behind the most forward skin round the vertex
Mr[:, 1] = b - t_
ring_y = front_y(0.0, a.ring_z)
print("medal: draped on the skin, ring y %.3f (skin %.3f), lowest vertex y %.3f" % (Mr[:, 1].mean(), ring_y, Mr[np.argmin(Mr[:, 2])][1]))
for v, p in zip(bm.verts, Mr):
    v.co = p
MED = Mr.copy()

# ---- the ribbon: a closed strip, snapped to the skin -----------------------------------------------------------------------------------------------
ctrl = [(0.0, None, a.ring_z + 0.026), (0.0, None, a.ring_z + 0.04), (0.012, None, a.ring_z + 0.042), (0.034, None, a.ring_z + 0.078),
        (0.058, None, a.ring_z + 0.115), (0.068, -0.118, 1.495), (0.086, -0.07, 1.515), (0.09, -0.02, 1.525), (0.078, 0.036, 1.52), (0.048, 0.058, 1.505), (0.0, 0.062, 1.50)]
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
NC = 8                                                            # points round the cord
r_c = 0.5 * a.ribbon_w
rings = []
for i in range(len(cen)):
    n_i = nor[i]; b = np.cross(n_i, tan[i]); b /= np.linalg.norm(b) + 1e-12
    d_tip = min(np.linalg.norm(cen[i] - cen[0]), np.linalg.norm(cen[i] - cen[-1]))
    gap_i = 0.003 + (a.ribbon_gap - 0.003) * min(d_tip / 0.07, 1.0)      # near the ring the cord lies low, under the medal (the medal covers it, not the other way round)
    c0, _ = snap(cen[i], 0.0)
    ctr = c0 + n_i * (gap_i + r_c)                                    # the cord rests GAP above the skin: its axis one radius higher
    rings.append([ctr + r_c * (np.cos(ph) * n_i + np.sin(ph) * b) for ph in np.linspace(0, 2 * np.pi, NC, endpoint=False)])
rings = np.array(rings)

axis_pts = np.array([r.mean(0) for r in rings])
nv = len(cen)
uv_red = UV['ribbon']
ids = [[bm.verts.new(Vector(rings[i][j])) for j in range(NC)] for i in range(nv)]
uvl = bm.loops.layers.uv.verify()


def add(vs):
    f = bm.faces.new(vs)
    for l in f.loops:
        l[uvl].uv = uv_red
    return f


for i in range(nv - 1):
    for j in range(NC):
        k = (j + 1) % NC
        add([ids[i][j], ids[i][k], ids[i + 1][k], ids[i + 1][j]])
for end in (0, nv - 1):                                                                                    # the two ends (at the ring): a cap
    c = bm.verts.new(Vector(rings[end].mean(0)))
    for j in range(NC):
        k = (j + 1) % NC
        add([c, ids[end][k], ids[end][j]] if end == 0 else [c, ids[end][j], ids[end][k]])
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

if a.paths:
    import json
    disc_v = MED[MED[:, 2] < a.ring_z - 0.3 * D]                     # the disc (not the ring)
    c0 = disc_v.mean(0)
    u_, s_, vt = np.linalg.svd(disc_v - c0, full_matrices=False)
    nrm = vt[2] * (1 if vt[2][1] < 0 else -1)                         # towards the front (-Y)
    up = np.array([0, 0, 1.0]) - nrm * nrm[2]; up /= np.linalg.norm(up)
    right = np.cross(up, nrm); right /= np.linalg.norm(right)
    json.dump(dict(axis=axis_pts.round(5).tolist(), cord_radius=r_c, medal=dict(centre=c0.round(5).tolist(), normal=nrm.round(5).tolist(), up=up.round(5).tolist(), right=right.round(5).tolist(), radius=0.5 * D,
                                                                                 ring=(c0 + up * (0.62 * D)).round(5).tolist())), open(a.paths, "w"))
    print("paths ->", a.paths)
