# A cape from a free model -> ONE regular cloth sheet for the simulation (uo_cape_sim.py), with the folds of the model as its rest shape.
#
# A cape sculpted as a closed solid ~1-2 cm thick (two layers that touch in the deep pleats under the clasps) cannot be cut into an outer layer without tearing the pleats open, and its
# triangles are as different as 5 mm and 20 cm (Blender's cloth needs even edges). So the sheet is rebuilt from the model: a triangular lattice of EDGE (file units) spacing in the plane of
# the cape (rows shifted by half a cell: equilateral triangles, no preferred direction), every lattice point lifted to where a ray from the OUTER side (DIR) first meets the model: a height field,
# the folds stay (the overhang of the deepest pleats is lost, they are shallow enough), the clasp reliefs and the cloth colour are baked from the model into the texture afterwards
# (uo_import_item.py bake_texture, BAKE_UV = one planar projection along DIR).
#
# Run after uo_import_item.py imported the model whole (KIND = "", DECIMATE_TO = 0, NAME = "Cape_original") with the model selected, in the file's own axes.
import os
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE = os.environ.get("UO_SCRIPTS") or os.path.dirname(os.path.abspath(globals().get("__file__", "x")))
DIR = (0.0, -1.0, 0.0)  # file axes: OUTWARD = the side of the clasps and folds (the rays come from there and go the other way); the cape plane is x, z (up)
EDGE = 0.015            # file units (m before the scale): lattice spacing (0.017 -> ~1 cm at the scale the cape gets on the body: ~8k vertices)
BAKE = 2048             # px of the baked colour / normal map
NORMAL = 0.0            # m: blur of the normal map of the model's geometry (uo_import_item.py BAKE_NORMAL)
MAX_JUMP = 100.0         # a triangle with an edge longer than this x EDGE (a ray that hit another fold behind) is left out
SMOOTH = 8             # Taubin passes over the sheet (0 = off)
MIN_PIECE = 80          # faces: smaller loose pieces are removed
NAME = "Cape"

orig = next(o for o in bpy.context.selected_objects if o.type == "MESH")
orig.name = NAME + "_original"
bpy.context.view_layer.update()
M = np.array(orig.matrix_world)
me = orig.data
co = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", co); V = co.reshape(-1, 3).astype(np.float64) @ M[:3, :3].T + M[:3, 3]
me.calc_loop_triangles(); tri = np.empty(len(me.loop_triangles) * 3, np.int32); me.loop_triangles.foreach_get("vertices", tri); tri = tri.reshape(-1, 3)
bvh = BVHTree.FromPolygons([Vector(p) for p in V], tri.tolist())

d = np.array(DIR, float); d /= np.linalg.norm(d)                                  # outward
up = np.array([0.0, 0.0, 1.0]); ux = np.cross(up, d); ux /= np.linalg.norm(ux)       # across the cape (the cape plane is spanned by ux and up)
dd = V @ d; U = V @ ux
U0, U1 = U.min(), U.max(); Z0, Z1 = V[:, 2].min(), V[:, 2].max()
dz = EDGE * np.sqrt(3) / 2
nj = int(np.ceil((Z1 - Z0) / dz)) + 1; ni = int(np.ceil((U1 - U0) / EDGE)) + 2
pts = -np.ones((nj, ni), int); P = []
for j in range(nj):
    for i in range(ni):
        u = U0 + (i + 0.5 * (j % 2) - 0.5) * EDGE; z = Z0 + j * dz                        # odd rows are shifted by half a cell
        hit = bvh.ray_cast(Vector(ux * u + up * z + d * (dd.max() + 0.5)), Vector(-d), float(np.ptp(dd)) + 1.0)     # from outside, first surface met
        if hit[0] is not None:
            pts[j, i] = len(P); P.append(np.array(hit[0][:]))
P = np.array(P)
faces = []
for j in range(nj - 1):
    for i in range(ni - 1):
        a = pts[j, i]                                                                 # even row: vertex i at i, the row above at i - 1/2 and i + 1/2; odd row: vertex i at i + 1/2, above at i and i + 1
        if j % 2 == 0:
            tris = [(a, pts[j, i + 1], pts[j + 1, i]), (a, pts[j + 1, i], pts[j + 1, i - 1] if i > 0 else -1)]
        else:
            tris = [(a, pts[j, i + 1], pts[j + 1, i + 1]), (a, pts[j + 1, i + 1], pts[j + 1, i])]
        for t in tris:
            if min(t) < 0:
                continue
            q = P[list(t)]; el = max(np.linalg.norm(q[0] - q[1]), np.linalg.norm(q[1] - q[2]), np.linalg.norm(q[2] - q[0]))
            if el <= MAX_JUMP * EDGE:
                faces.append(t)
faces = np.array(faces)
# loose pieces
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
nv = len(P); A = coo_matrix((np.ones(len(faces) * 3), (faces[:, [0, 1, 2]].ravel(), faces[:, [1, 2, 0]].ravel())), shape=(nv, nv))
nc, lab = connected_components(A, directed=False)
cnt = np.bincount(lab[faces[:, 0]], minlength=nc); keepf = cnt[lab[faces[:, 0]]] >= MIN_PIECE
faces = faces[keepf]; used = np.unique(faces); remap = -np.ones(nv, int); remap[used] = np.arange(len(used)); P = P[used]; faces = remap[faces]
# the faces look outward (along d)
n0 = np.cross(P[faces[:, 1]] - P[faces[:, 0]], P[faces[:, 2]] - P[faces[:, 0]])
flip = (n0 @ d) < 0
faces[flip] = faces[flip][:, ::-1]
sheet_me = bpy.data.meshes.new(NAME)
sheet_me.from_pydata([tuple(p) for p in P], [], [tuple(f) for f in faces]); sheet_me.update()
# the beads along the pleats (a height field jumps from ridge to valley there): Taubin smoothing (a shrink step and an inflate step, the size stays), the folds are wider than this
if SMOOTH > 0:
    from scipy.sparse import csr_matrix
    ed = np.vstack([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]); ed = np.unique(np.sort(ed, axis=1), axis=0)
    Aj = csr_matrix((np.ones(len(ed) * 2), (np.r_[ed[:, 0], ed[:, 1]], np.r_[ed[:, 1], ed[:, 0]])), shape=(len(P), len(P))); dg_ = np.asarray(Aj.sum(1)).ravel()
    for _ in range(SMOOTH):
        for k in (0.5, -0.53):
            P = P + k * ((Aj @ P) / np.maximum(dg_, 1)[:, None] - P)
    sheet_me.vertices.foreach_set("co", P.astype(np.float32).ravel()); sheet_me.update()
# holes inside the sheet (a ray that missed an overhang of a pleat): closed; the longest boundary loop is the rim of the cape and stays open
import bmesh, collections
bm = bmesh.new(); bm.from_mesh(sheet_me); bm.edges.ensure_lookup_table()
adj = collections.defaultdict(list); be = [e for e in bm.edges if e.is_boundary]
for e in be:
    a_, b_ = e.verts; adj[a_.index].append(e); adj[b_.index].append(e)
seen = set(); loops = []
for e0 in be:
    if e0.index in seen:
        continue
    st = [e0]; seen.add(e0.index); comp = [e0]
    while st:
        e = st.pop()
        for v in e.verts:
            for f in adj[v.index]:
                if f.index not in seen:
                    seen.add(f.index); st.append(f); comp.append(f)
    loops.append(comp)
loops.sort(key=len, reverse=True)
inner = [e for lp in loops[1:] for e in lp]
if inner:
    r = bmesh.ops.holes_fill(bm, edges=inner, sides=0)
    tris = [f for f in r["faces"]]
    bmesh.ops.triangulate(bm, faces=tris)
    bm.to_mesh(sheet_me); sheet_me.update()
    print("uo_cape_sheet: %d holes closed (%d boundary edges)" % (len(loops) - 1, len(inner)))
bm.free()
sheet = bpy.data.objects.new(NAME, sheet_me)
for c in orig.users_collection:
    c.objects.link(sheet)
sheet_me.polygons.foreach_set("use_smooth", [True] * len(sheet_me.polygons)); sheet_me.update()
print("uo_cape_sheet: lattice %d x %d (%.1f mm), %d vertices, %d faces, %d loose pieces dropped" % (ni, nj, 1000 * EDGE, len(P), len(faces), nc - len(np.unique(lab[faces[:, 0]]))))

# colour and the model's geometry baked into the sheet (the functions of uo_import_item.py, settings given here)
import re
src = open(os.path.join(HERE, "uo_import_item.py"), encoding="utf-8").read().split("\ndef run():")[0]
for k, v in dict(BAKE_NORMAL=NORMAL, BAKE_UV=tuple(DIR), BAKE_RAY=0.15, FILE="", KIND="").items():
    src, n = re.subn(r"^%s\s*=.*$" % re.escape(k), "%s = %r" % (k, v), src, count=1, flags=re.M)
    assert n == 1, k
ns = {"__name__": "uo_import_item_funcs"}
exec(compile(src, "uo_import_item.py", "exec"), ns)
ns["bake_texture"](sheet, orig, BAKE)
img = bpy.data.images["uo_baked_" + sheet.name]                        # texels no ray reached (the valleys of the deepest pleats, where the sheet leaves the model): the colour of the nearest baked texel
w_, h_ = img.size; C = np.array(img.pixels[:], np.float32).reshape(h_, w_, 4)
miss = C[..., :3].sum(2) < 1e-4
if miss.any() and not miss.all():
    from scipy import ndimage
    ii = ndimage.distance_transform_edt(miss, return_distances=False, return_indices=True)
    C[..., :3] = C[ii[0], ii[1], :3]; img.pixels[:] = C.ravel(); img.update(); img.pack()
    print("uo_cape_sheet: %.1f %% of the texels filled from their neighbours (no ray reached the model)" % (100 * miss.mean()))
bpy.data.objects.remove(orig, do_unlink=True)
bpy.ops.object.select_all(action="DESELECT")
sheet.select_set(True)
bpy.context.view_layer.objects.active = sheet
print("uo_cape_sheet: done")
