# Fit a strap that came with a model (a drum on a baldric strap) to the body: the strap's centre line is found, laid on a path over the skin, and the strap is bent along it.
# Run on the SELECTED strap object (placed in the rest pose, world coordinates, e.g. by uo_make_item.py "rigid" + "strap"), before uo_bind_item.py.
#   1. The centre line of the strap: the vertices are put on a nearest-neighbour graph, the geodesic distance from one END of the strap gives every vertex its position s along it (the ends are found by two
#      sweeps: the farthest vertex from anywhere, then the farthest from that one); the vertices of every SEG m of s give a centre point; the cross-section of the strap there (principal axes of the
#      vertices) gives the frame: T along the strap, N across its thickness (outward = up at the highest point, the apex of the V, continuous from there), B = N x T across its width.
#   2. Every vertex is written in that frame: (s, a, b, c) = position along the line and offsets along T, B, N from the centre point.
#   3. The path: the two ends stay where they are (the hooks hang on the lugs of the drum); in between the strap runs over the skin: WAYPOINTS are skin targets (x, y, z, rest pose, world; the nearest point of the body
#      is taken and lifted by OFFSET - lowest c of the cross-section, so that the lowest vertex of the strap is OFFSET above the skin, whatever the padding is). The curve through them (Catmull-Rom) is
#      sampled; every sample gets the normal of the skin under it as N' (samples farther than FREE from the skin: the one of the nearest sample that touches it), T' along the curve, B' = N' x T'.
#   4. A vertex goes to  P'(s * length of the path / length of the strap) + a T' + WIDEN b B' + c N': the strap keeps its width, thickness, stitching and hardware, and is stretched / shortened along its length
#      by the one factor that makes it fit the path (reported).
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra, connected_components

# skin targets of the middle of the path from the END A to the END B: x, y, z in m (rest pose, world); the nearest skin point is used. The default: a baldric strap that runs from the lug on the
# right head of a drum on the chest over the right shoulder, across the nape, over the left shoulder to the left lug.
WAYPOINTS = [(-0.10, -0.14, 1.46), (-0.13, 0.0, 1.50), (-0.05, 0.075, 1.47), (0.05, 0.075, 1.47), (0.13, 0.0, 1.50), (0.10, -0.14, 1.46)]
OFFSET = 0.008        # m: lowest point of the strap above the skin
FREE = 0.06           # m: a sample of the path farther from the skin than this is free (between the drum and the shoulder): it keeps the line, its normal comes from the nearest sample on the skin
SEG = 0.01            # m: spacing of the centre points
KNN = 12              # neighbours in the graph of the vertices
SMOOTH = 3            # passes of the smoothing of the path after the projection onto the skin
WIDEN = 1.0          # factor on the width of the strap (a 3.6 cm strap is 1.3 px at 36 px/m: 1.7-1.8 makes it read), thickness and length stay
APEX_UP = True        # the outer face of the strap is the one that looks up at its highest point (the apex of the V); False: down
ALIGN_ENDS = True     # the end A of the path is the end of the strap that is nearer to the first waypoint's side (x < 0 for the first waypoint of the right shoulder)

obs = [o for o in bpy.context.selected_objects if o.type == "MESH"]
assert len(obs) == 1, "uo_fit_strap: select the strap object only"
ob = obs[0]
M = np.array(ob.matrix_world)
n = len(ob.data.vertices)
co = np.empty(n * 3, np.float32); ob.data.vertices.foreach_get("co", co)
P = co.reshape(-1, 3).astype(np.float64) @ M[:3, :3].T + M[:3, 3]

body = bpy.data.objects["UO_Body"]
bpy.context.view_layer.update()
eb = body.evaluated_get(bpy.context.evaluated_depsgraph_get()); mb = eb.to_mesh(); mb.calc_loop_triangles()
bv = BVHTree.FromPolygons([eb.matrix_world @ v.co for v in mb.vertices], [t.vertices[:] for t in mb.loop_triangles]); eb.to_mesh_clear()


def skin(p):
    loc, nrm, fi, d = bv.find_nearest(Vector(p), 0.5)
    return np.array(loc), np.array(nrm), d


# 1. the centre line
tree = cKDTree(P)
dist, nb = tree.query(P, k=KNN + 1)
rows = np.repeat(np.arange(n), KNN); cols = nb[:, 1:].ravel(); w = dist[:, 1:].ravel()
G = coo_matrix((w, (rows, cols)), shape=(n, n)); G = G.maximum(G.T).tocsr()
ncomp, lab = connected_components(G, directed=False)
if ncomp > 1:                                                     # pieces the graph does not connect: tied to the nearest vertex of the main piece
    main = np.bincount(lab).argmax(); mi = np.nonzero(lab == main)[0]; mt = cKDTree(P[mi])
    extra = [(i, mi[mt.query(P[i])[1]], mt.query(P[i])[0]) for i in range(n) if lab[i] != main]
    ex = np.array(extra)
    G = (G + coo_matrix((ex[:, 2], (ex[:, 0].astype(int), ex[:, 1].astype(int))), shape=(n, n)).maximum(coo_matrix((ex[:, 2], (ex[:, 1].astype(int), ex[:, 0].astype(int))), shape=(n, n)))).tocsr()
d0 = dijkstra(G, indices=int(np.argmax(P[:, 2])), directed=False)
e1 = int(np.argmax(np.where(np.isfinite(d0), d0, -1)))
d1 = dijkstra(G, indices=e1, directed=False)
e2 = int(np.argmax(np.where(np.isfinite(d1), d1, -1)))
d2 = dijkstra(G, indices=e2, directed=False)
if ALIGN_ENDS:                                                    # end A = the end on the side of the first waypoint (x)
    if (P[e1, 0] - P[e2, 0]) * (WAYPOINTS[0][0] - WAYPOINTS[-1][0]) < 0:
        e1, e2, d1, d2 = e2, e1, d2, d1
s = np.where(np.isfinite(d1), d1, 0.0); L = float(s.max())
nbin = max(8, int(L / SEG)); edges = np.linspace(0, L, nbin + 1)
bi = np.clip(np.digitize(s, edges) - 1, 0, nbin - 1)
C = np.array([P[bi == k].mean(0) if (bi == k).any() else np.full(3, np.nan) for k in range(nbin)])
ok = ~np.isnan(C[:, 0])
for c in range(3):
    C[:, c] = np.interp(np.arange(nbin), np.nonzero(ok)[0], C[ok, c])
for _ in range(2):
    C[1:-1] = 0.25 * C[:-2] + 0.5 * C[1:-1] + 0.25 * C[2:]
T = np.gradient(C, axis=0); T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-9)
Nn = np.zeros_like(C)
for k in range(nbin):
    q = P[bi == k] - C[k]
    if len(q) < 4:
        Nn[k] = np.nan; continue
    q = q - np.outer(q @ T[k], T[k])
    ev, evec = np.linalg.eigh(q.T @ q)
    Nn[k] = evec[:, 0]                                            # least variance: across the thickness
good = ~np.isnan(Nn[:, 0])
for c in range(3):
    Nn[:, c] = np.interp(np.arange(nbin), np.nonzero(good)[0], Nn[good, c])
Nn -= np.einsum("ij,ij->i", Nn, T)[:, None] * T; Nn /= np.maximum(np.linalg.norm(Nn, axis=1, keepdims=True), 1e-9)
apex = int(np.argmax(C[:, 2]))
if (Nn[apex, 2] < 0) == APEX_UP:
    Nn[apex] *= -1
for k in range(apex + 1, nbin):
    if Nn[k] @ Nn[k - 1] < 0:
        Nn[k] *= -1
for k in range(apex - 1, -1, -1):
    if Nn[k] @ Nn[k + 1] < 0:
        Nn[k] *= -1
for _ in range(2):
    Nn[1:-1] = 0.25 * Nn[:-2] + 0.5 * Nn[1:-1] + 0.25 * Nn[2:]
Nn -= np.einsum("ij,ij->i", Nn, T)[:, None] * T; Nn /= np.maximum(np.linalg.norm(Nn, axis=1, keepdims=True), 1e-9)
Bn = np.cross(Nn, T)

# 2. vertices in the frame
fk = np.clip(s / L * nbin - 0.5, 0, nbin - 1.001); k0 = fk.astype(int); fr = (fk - k0)[:, None]
def lerp(A):
    return A[k0] * (1 - fr) + A[k0 + 1] * fr
Cv, Tv, Bv, Nv = lerp(C), lerp(T), lerp(Bn), lerp(Nn)
off = P - Cv
a_, b_, c_ = np.einsum("ij,ij->i", off, Tv), np.einsum("ij,ij->i", off, Bv), np.einsum("ij,ij->i", off, Nv)
cmin = np.array([c_[bi == k].min() if (bi == k).any() else 0.0 for k in range(nbin)])
width = float(np.percentile(np.abs(b_), 97) * 2); thick = float(np.percentile(c_, 97) - np.percentile(c_, 3))

# 3. the path
way = [C[0]]
for tgt in WAYPOINTS:
    q, nr, d = skin(tgt); way.append(q + nr * (OFFSET + 0.004))
way.append(C[-1]); way = np.array(way)


def catmull(Pw, step):
    Pw = np.vstack([2 * Pw[0] - Pw[1], Pw, 2 * Pw[-1] - Pw[-2]]); out = []
    for i in range(1, len(Pw) - 2):
        p0, p1, p2, p3 = Pw[i - 1], Pw[i], Pw[i + 1], Pw[i + 2]
        m = max(2, int(np.linalg.norm(p2 - p1) / step))
        for t in np.linspace(0, 1, m, endpoint=False):
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(Pw[-2])
    return np.array(out)


path = catmull(way, SEG)
seg = np.linalg.norm(np.diff(path, axis=0), axis=1); sp = np.r_[0, np.cumsum(seg)]; Lt = float(sp[-1])
# resample to equal arc length (nbin points)
t_new = np.linspace(0, Lt, nbin)
path = np.stack([np.interp(t_new, sp, path[:, c]) for c in range(3)], 1)
tp = np.gradient(path, axis=0); tp /= np.maximum(np.linalg.norm(tp, axis=1, keepdims=True), 1e-9)
contact = np.zeros(nbin, bool); npath = np.zeros_like(path)
for k in range(nbin):
    q, nr, d = skin(path[k])
    if d < FREE:
        contact[k] = True; npath[k] = nr
idx = np.nonzero(contact)[0]
if len(idx) == 0:
    raise RuntimeError("uo_fit_strap: the path does not touch the skin: check WAYPOINTS")
for k in range(nbin):
    if not contact[k]:
        j = idx[np.argmin(np.abs(idx - k))]; npath[k] = npath[j]
for _ in range(SMOOTH):
    npath[1:-1] = 0.25 * npath[:-2] + 0.5 * npath[1:-1] + 0.25 * npath[2:]
npath /= np.maximum(np.linalg.norm(npath, axis=1, keepdims=True), 1e-9)
npath -= np.einsum("ij,ij->i", npath, tp)[:, None] * tp; npath /= np.maximum(np.linalg.norm(npath, axis=1, keepdims=True), 1e-9)
# lay the contact part on the skin: the centre point at the skin + normal * (OFFSET - lowest c of the cross-section there)
for k in range(nbin):
    if contact[k]:
        q, nr, d = skin(path[k]); path[k] = q + npath[k] * (OFFSET - cmin[k])
for _ in range(SMOOTH):
    path[1:-1] = 0.25 * path[:-2] + 0.5 * path[1:-1] + 0.25 * path[2:]
path[0] = C[0]; path[-1] = C[-1]
bp = np.cross(npath, tp)

# 4. the vertices onto the path
fk2 = np.clip(s / L * (nbin - 1), 0, nbin - 1.001); j0 = fk2.astype(int); fr2 = (fk2 - j0)[:, None]
def lerp2(A):
    return A[j0] * (1 - fr2) + A[j0 + 1] * fr2
Pn = lerp2(path) + a_[:, None] * lerp2(tp) + (WIDEN * b_)[:, None] * lerp2(bp) + c_[:, None] * lerp2(npath)
# whatever stays under the skin of the contact part (a corner of the hardware): out along the normal
pushed = 0
for i in np.nonzero(contact[np.clip(np.round(fk2).astype(int), 0, nbin - 1)])[0]:
    q, nr, d = skin(Pn[i])
    sd = float((Pn[i] - q) @ nr)
    if d < 0.03 and sd < 0.004:
        Pn[i] += nr * (0.004 - sd); pushed += 1
loc = (np.linalg.inv(M) @ np.c_[Pn, np.ones(n)].T).T[:, :3]
ob.data.vertices.foreach_set("co", loc.astype(np.float32).ravel()); ob.data.update()
print("uo_fit_strap: %s: strap %.3f m long, %.1f cm wide (x%.2f), %.1f mm thick; path %.3f m (stretch x%.2f), contact %d of %d samples, %d vertices pushed off the skin" % (ob.name, L, 100 * width * WIDEN, WIDEN, 1000 * thick, Lt, Lt / L, contact.sum(), nbin, pushed))
