# Size and place the SELECTED item on the UO body by what the item has to do: wrap the skin it covers, at a small distance, without the skin poking out.
# uo_import_item.py scales an item from ONE number per KIND (the height of a typical original), which is only right for items shaped like that original: a chest piece
# that stops at the ribs, a cuirass with huge pauldrons or a short jacket came out too big or too small (docs/qa/autofit.md). This script instead looks at the
# skin of the slot's body parts (PARTS_BY_KIND) and finds the uniform scale and the move (3 numbers, optionally a half turn) for which
#   - the item's inner surface lies about `GAP` from the skin where it covers it (distance from every skin point to the nearest item surface point), and
#   - no skin point lies on the outer side of the surface it is nearest to (the skin pokes through): that costs 3x more than a gap that is too large,
#   - where the item does not cover the skin at all (the item is short, the neck / arm holes) nothing is asked, so a short item is not stretched to cover everything.
# The vertical place of an item that fits equally well anywhere on the torso (a short cuirass) is settled by the edge of the slot that is stable in the original items
# (EDGE_BY_KIND: top of shirts, trousers, hair, bottom of boots, gloves, arm guards; docs/AUDYT_2026-10-03.md, point 5), a weak pull of the same weight as ~5 cm of misfit.
# The size units are found first (a file in cm, mm): the unit that puts the longest side of the item in 0.15..3 m (UNIT = 0 -> automatic).
# Run it with the item(s) selected, after uo_import_item.py with FIT = "wrap" (which only converts units and puts the item near the body), before uo_fit_item.py
# (that one pushes whatever is still in the skin out). Rest Position. Prints the result and the alternatives that were nearly as good ("AMBIGUOUS").
import bpy
import numpy as np
from mathutils import Matrix
from scipy import optimize, spatial

KIND = "shirt"        # slot, see PARTS_BY_KIND ("" = every body part)
GAP = -1.0            # m, wanted distance from the skin to the item's inner surface; < 0 = by KIND (as MIN_GAP of uo_fit_item.py)
UNIT = 0.0            # > 0: multiply the size by this (0.01: the file is in cm) instead of finding the unit; 0 = automatic
SCALE_RANGE = (0.55, 1.8)   # the scale after the units may be this far from 1 (relative to the item as it is now)
TURN_BACK = True      # also try the item turned by 180 deg around the vertical axis (a model that came in back to front); the better one wins
TURN_PENALTY = 0.0004 # cost added to the item turned by 180 deg: it must be clearly better to win (front and back of a torso differ little)
USE_EDGE = True       # the pull of EDGE_BY_KIND on the vertical place (off: only the wrap decides)
SAMPLES = 3500        # skin points used
ITEM_POINTS = 60000   # item surface points used at most
APPLY = True          # False: only report
REPORT = True

PARTS_BY_KIND = {"shirt": ("pelvis", "spine", "chest", "neck"), "plate": ("pelvis", "spine", "chest", "neck"), "harness": ("pelvis", "spine", "chest", "neck"),
                 "arms": ("upper_arm", "forearm"), "pants": ("pelvis", "thigh", "shin"), "legs": ("pelvis", "thigh", "shin"), "boots": ("shin", "foot"),
                 "gloves": ("forearm", "hand"), "helm": ("head",), "hat": ("head",), "hair": ("head",), "beard": ("head",), "neck": ("neck", "chest", "head")}
# the edge of the slot that is the same in most original items, and where it is (m, from uo_import_item.py EXTENTS, measured on the original sprites)
EDGE_BY_KIND = {"shirt": ("top", 1.656), "plate": ("top", 1.643), "harness": ("top", 1.55), "pants": ("top", 1.170), "legs": ("top", 1.138), "boots": ("bottom", -0.069),
                "gloves": ("bottom", 0.797), "arms": ("bottom", 0.929), "helm": ("top", 1.903), "hat": ("top", 1.92), "hair": ("top", 1.89), "beard": ("top", 1.72),
                "neck": ("top", 1.64)}
GAP_BY_KIND = {"shirt": 0.015, "pants": 0.015, "boots": 0.015, "gloves": 0.015, "plate": 0.03, "legs": 0.03, "arms": 0.03, "helm": 0.03, "neck": 0.03, "harness": 0.015}
# where the slot lives on the body (m, z of the lowest / highest point of the typical original item, uo_import_item.py EXTENTS): the item may not drift out of this zone
# (by more than ZONE_MARGIN), and its height may differ from the typical one only by HEIGHT_RATIO - far-away "solutions" fit nothing and cost nothing
ZONE_BY_KIND = {"shirt": (0.999, 1.656), "plate": (0.651, 1.643), "harness": (0.9, 1.65), "arms": (0.929, 1.694), "pants": (0.057, 1.170), "legs": (-0.107, 1.138),
                "boots": (-0.069, 0.563), "gloves": (0.797, 1.245), "helm": (1.504, 1.903), "hair": (1.52, 1.89), "beard": (1.52, 1.72), "hat": (1.52, 1.92), "neck": (1.48, 1.64)}
ZONE_MARGIN = 0.15
HEIGHT_RATIO = (0.4, 1.8)
ZONE_WEIGHT = 4.0     # residual per metre outside the zone / the ratio
PLAUSIBLE = (0.15, 3.0)   # m, longest side of an item
CAP = 0.10            # m, skin farther than this from the item is "not covered"
CAP_WIDE = 0.40       # the same for the first, coarse stage
EDGE_WEIGHT = 0.05    # 1/m^2: tie-breaker only (10 cm off costs as much as a 2 cm misfit): the wrap itself fixes the height of every item that has any structure
SCALE_PRIOR = 0.01    # tie-breaker only: a tiny pull towards the size the model was made in (after the units)
# how far from the skin an item may stand (m) before it counts as too thick: the p90 of the distance of the item's pixels from the body silhouette in the original
# items of the slot (docs/qa/layer_analysis.md: plate / InnerTorso 5.6-8.1 cm, shirt 5.6, pants 3.9-5.6, arms 4.7-10, helm 8.3, hair 5.6-7.9, boots 3.3) with a margin;
# beyond it the part is pulled back by a smaller scale (OUT_WEIGHT) - big pauldrons and flares are what makes an item "too thick"
OUT_BY_KIND = {"shirt": 0.09, "plate": 0.12, "harness": 0.09, "pants": 0.08, "legs": 0.09, "arms": 0.10, "boots": 0.07, "gloves": 0.07, "helm": 0.12, "hat": 0.12,
               "hair": 0.12, "beard": 0.08, "neck": 0.08}
OUT_WEIGHT = 3.0      # weight of the "too thick" term: 5 cm too far, over the whole surface, costs like 2.5 cm of misfit of the wrap
OUT_POINTS = 5000     # item points used for it
PIERCE = 3.0          # a skin point poking out of the item costs this much more than the same gap too large
BAND_LOW, BAND_HIGH = 0.003, 0.003   # m: the item may stand from GAP - 3 mm to GAP + 3 mm from the skin at no cost (wider: the size drifts, measured with test_autofit.py)
BAND_PULL = 0.6       # weight of the pull to GAP inside the band

import os
for _k in ("BAND_LOW", "BAND_HIGH", "BAND_PULL", "SCALE_PRIOR", "EDGE_WEIGHT", "OUT_WEIGHT", "PIERCE", "ZONE_WEIGHT", "TURN_PENALTY"):    # tuning from the environment (test_autofit.py --env)
    if "UO_AUTOFIT_" + _k in os.environ:
        globals()[_k] = float(os.environ["UO_AUTOFIT_" + _k])

body = bpy.data.objects["UO_Body"]
rig = bpy.data.objects["UO_Rig"]
rng = np.random.default_rng(12345)


def base_of(name):
    s = name[-2:] if name.endswith((".L", ".R")) else ""
    b = name[:-2] if s else name
    return "hand" if b.startswith("finger") else b


def body_points(whole=False):
    """SAMPLES skin points (world space) with their normals, from the triangles of the slot's body parts (rest shape)"""
    me = body.data
    kb = me.shape_keys.key_blocks["Basis"] if me.shape_keys else None
    co = np.empty(len(me.vertices) * 3, np.float32)
    (kb.data if kb else me.vertices).foreach_get("co", co)
    M = np.array(body.matrix_world)
    co = co.reshape(-1, 3).astype(np.float64) @ M[:3, :3].T + M[:3, 3]
    parts = None if whole else PARTS_BY_KIND.get(KIND)
    names = {g.index: base_of(g.name) for g in body.vertex_groups}
    keep = np.array([bool(v.groups) and (parts is None or names[max(v.groups, key=lambda g: g.weight).group] in parts) for v in me.vertices])
    me.calc_loop_triangles()
    tri = np.array([t.vertices[:] for t in me.loop_triangles])
    tri = tri[keep[tri].sum(1) >= 2]
    a, b, c = co[tri[:, 0]], co[tri[:, 1]], co[tri[:, 2]]
    cr = np.cross(b - a, c - a); area = np.linalg.norm(cr, axis=1)
    k = rng.choice(len(tri), SAMPLES, p=area / area.sum())
    u, v = rng.random(SAMPLES), rng.random(SAMPLES)
    f = u + v > 1; u[f], v[f] = 1 - u[f], 1 - v[f]
    P = a[k] + u[:, None] * (b[k] - a[k]) + v[:, None] * (c[k] - a[k])
    N = cr[k] / np.maximum(area[k], 1e-12)[:, None]
    # the winding of the body mesh tells the outside: decided once for the whole body (a part such as a pair of legs has no usable middle point)
    allt = np.array([t.vertices[:] for t in me.loop_triangles])
    ca, cb, cc = co[allt[:, 0]], co[allt[:, 1]], co[allt[:, 2]]
    flip = np.sum(np.cross(cb - ca, cc - ca) * ((ca + cb + cc) / 3 - co.mean(0)), axis=1).sum() < 0
    return P, (-N if flip else N)


def item_points(obs):
    """surface points (vertices, edge middles, face centres: low-poly items need them) and outward normals of the items, world space"""
    P, N = [], []
    for ob in obs:
        me = ob.data
        M = np.array(ob.matrix_world)
        co = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3).astype(np.float64)
        me.calc_loop_triangles()
        tri = np.empty(len(me.loop_triangles) * 3, np.int32); me.loop_triangles.foreach_get("vertices", tri); tri = tri.reshape(-1, 3)
        vn = np.zeros_like(co)
        fn = np.cross(co[tri[:, 1]] - co[tri[:, 0]], co[tri[:, 2]] - co[tri[:, 0]])
        for j in range(3):
            np.add.at(vn, tri[:, j], fn)
        vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-12)
        fa = np.linalg.norm(fn, axis=1); fnn = fn / np.maximum(fa, 1e-12)[:, None]
        pts = [co, co[tri].mean(1), (co[tri[:, 0]] + co[tri[:, 1]]) / 2]
        nrm = [vn, fnn, fnn]
        p = np.concatenate(pts) @ M[:3, :3].T + M[:3, 3]
        n = np.concatenate(nrm) @ np.linalg.inv(M[:3, :3]).T
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
        P.append(p); N.append(n)
    P, N = np.concatenate(P), np.concatenate(N)
    if len(P) > ITEM_POINTS:
        k = rng.choice(len(P), ITEM_POINTS, replace=False); P, N = P[k], N[k]
    return P, N


def find_unit(P):
    size = (P.max(0) - P.min(0)).max()
    if UNIT > 0:
        return UNIT
    for f in (1.0, 0.01, 0.001, 0.1, 0.0254, 10.0, 100.0):
        if PLAUSIBLE[0] <= size * f <= PLAUSIBLE[1]:
            return f
    return 1.0


class Fit:
    def __init__(self, BP, BN, IP, gap):
        self.BP, self.BN, self.IP, self.gap = BP, BN, IP, gap
        self.tree = spatial.cKDTree(IP)
        self.edge = EDGE_BY_KIND.get(KIND) if USE_EDGE else None
        self.cap = CAP
        self.zlo, self.zhi = np.percentile(IP[:, 2], 0.5), np.percentile(IP[:, 2], 99.5)
        self.unit = 1.0
        self.out_limit = OUT_BY_KIND.get(KIND)
        if self.out_limit is not None and OUT_WEIGHT > 0:
            self.sub = IP[rng.choice(len(IP), min(OUT_POINTS, len(IP)), replace=False)]
            self.btree = spatial.cKDTree(body_points(whole=True)[0])

    def eval(self, x, detail=False):
        """x = log scale, tx, ty, tz, yaw: the item is x -> s R x + t; the skin points are brought into item space instead (the tree is built once)"""
        s = np.exp(x[0]); t = np.array(x[1:4]); yaw = x[4]
        c, sn = np.cos(yaw), np.sin(yaw)
        R = np.array([[c, -sn, 0], [sn, c, 0], [0, 0, 1.0]])
        Q = (self.BP - t) @ R / s                                    # skin points in item space: R^T (p - t) / s
        d, j = self.tree.query(Q, k=1)
        w = (self.IP[j] - Q) @ R.T * s                               # skin point -> nearest item point, world axes
        e = (w * self.BN).sum(1)                                     # > 0: the item lies on the outer side of the skin there, < 0: the skin pokes out
        d = d * s
        cap = self.cap
        near = d < cap
        glo, ghi = max(0.0, self.gap - BAND_LOW), self.gap + BAND_HIGH
        # no cost while the item stands between glo and ghi from the skin (a model that fits snugly is left at its size), the skin poking out costs PIERCE x, a gap that
        # is too large costs 1 x; a small pull to GAP inside the band keeps the solver moving
        r = np.where(e < glo, PIERCE * (e - glo), np.where(e > ghi, e - ghi, BAND_PULL * (e - self.gap)))
        r = np.where(near, np.clip(r, -cap, cap), cap)
        # only the skin at the heights the item occupies is asked about (smooth edges), averaged over those points: a bigger item does not win by covering more skin
        zlo, zhi = s * self.zlo + t[2], s * self.zhi + t[2]
        wz = 1 / (1 + np.exp(-(self.BP[:, 2] - zlo) / 0.012)) / (1 + np.exp(-(zhi - self.BP[:, 2]) / 0.012))
        wsum = max(wz.sum(), 1.0)
        out = [r * np.sqrt(wz / wsum)]
        out.append(np.array([np.sqrt(SCALE_PRIOR) * x[0]]))     # x[0]: the scale on top of the units already converted
        zone = ZONE_BY_KIND.get(KIND)
        if zone is not None:
            lo, hi = zone
            h = (zhi - zlo) / max(hi - lo, 1e-9)
            out.append(ZONE_WEIGHT * np.array([max(0.0, lo - ZONE_MARGIN - zlo), max(0.0, zhi - hi - ZONE_MARGIN), max(0.0, HEIGHT_RATIO[0] - h) * (hi - lo), max(0.0, h - HEIGHT_RATIO[1]) * (hi - lo)]))
        if self.out_limit is not None and OUT_WEIGHT > 0:
            dsk = self.btree.query(s * (self.sub @ R.T) + t)[0]
            out.append(np.sqrt(OUT_WEIGHT / len(dsk)) * np.clip(dsk - self.out_limit, 0, None))
        if self.edge is not None:
            which, ref = self.edge
            z = s * (self.zhi if which == "top" else self.zlo) + t[2]
            out.append(np.array([np.sqrt(EDGE_WEIGHT) * (z - ref)]))
        if detail:
            m = wz > 0.5
            return np.concatenate(out), dict(covered=float(near[m].mean()) if m.any() else 0.0, pierced=float(((e < -0.005) & near)[m].mean()) if m.any() else 0.0,
                                           gap=float(np.median(e[near & m])) if (near & m).any() else 0.0)
        return np.concatenate(out)


def solve(BP, BN, IP, gap, yaws, unit=1.0):
    ctr = np.array([np.median(BP[:, 0]), (BP[:, 1].min() + BP[:, 1].max()) / 2, 0.0])
    ictr = np.array([(IP[:, 0].min() + IP[:, 0].max()) / 2, (IP[:, 1].min() + IP[:, 1].max()) / 2, 0.0])
    fit = Fit(BP, BN, IP, gap)
    fit.unit = unit
    zb = np.percentile(BP[:, 2], [5, 95]); zi = np.percentile(IP[:, 2], [5, 95])
    # 1. coarse grid over scale, height and the item's turn, 2. refine the best few starts: first with a wide CAP (the skin far from the item still pulls it: a pair of
    # gloves or a helmet that starts a hand's width away finds its way), then with the real one
    fit.cap = CAP_WIDE
    grid = []
    for yaw in yaws:
        c, sn = np.cos(yaw), np.sin(yaw)
        R = np.array([[c, -sn, 0], [sn, c, 0], [0, 0, 1.0]])
        for sc in np.geomspace(SCALE_RANGE[0], SCALE_RANGE[1], 14):
            for dz in np.arange(-0.3, 0.31, 0.05):
                t0 = ctr - sc * R @ ictr
                x0 = np.array([np.log(sc), t0[0], t0[1], (zb.mean() - sc * zi.mean()) + dz, yaw])
                grid.append((float(np.sum(fit.eval(x0) ** 2)), 1.0, yaw, x0))
    grid.sort(key=lambda g: g[0])
    starts, best = [], []
    for g in grid:                                                   # distinct starts: another turn / orientation, or scale and height not close to a chosen one
        if all(g[1] != h[1] or g[2] != h[2] or abs(g[3][0] - h[3][0]) > 0.06 or abs(g[3][3] - h[3][3]) > 0.06 for h in starts):
            starts.append(g)
        if len(starts) >= 8:
            break
    lo, hi = [np.log(SCALE_RANGE[0]), -2, -2, -3], [np.log(SCALE_RANGE[1]), 2, 2, 3]
    for c0, sg, yaw, x0 in starts:
        x = np.clip(x0[:4], np.array(lo) + 1e-9, np.array(hi) - 1e-9)
        for cap, nfev in ((CAP_WIDE, 25), (CAP, 30)):
            fit.cap = cap
            r = optimize.least_squares(lambda y: fit.eval(np.r_[y, yaw]), x, bounds=(lo, hi), x_scale=[0.1, 0.05, 0.05, 0.05], max_nfev=nfev)
            x = r.x
        best.append((float(2 * r.cost) + (TURN_PENALTY if yaw else 0.0), sg, yaw, np.r_[r.x, yaw]))
    fit.cap = CAP
    best.sort(key=lambda b: b[0])
    return fit, best


def run():
    obs = [o for o in bpy.context.selected_objects if o.type == "MESH" and o.name not in ("UO_Body",)]
    if not obs:
        raise RuntimeError("select the item(s) first")
    gap = GAP if GAP >= 0 else GAP_BY_KIND.get(KIND, 0.015)
    IP, _ = item_points(obs)
    f = find_unit(IP)
    if f != 1.0:
        IP = IP * f
    BP, BN = body_points()
    fit, best = solve(BP, BN, IP, gap, (0.0, np.pi) if TURN_BACK else (0.0,), f)
    c0, sg, yaw, x = best[0]
    r, info = fit.eval(x, detail=True)
    # alternatives with a clearly different scale or turn that are nearly as good
    amb = [b for b in best[1:] if b[0] < c0 * 1.15 + 1e-6 and (abs(b[3][0] - x[0]) > 0.08 or abs(b[3][4] - x[4]) > 1)]
    s = np.exp(x[0]) * f
    msg = "uo_autofit_item: KIND %s | units x%g | scale %.3f (x%.3f of the file) | turn %d deg | move %.3f %.3f %.3f m | skin covered %.0f%%, poking out %.1f%%, median gap %.1f mm (wanted %.0f)" % (
        KIND, f, s, np.exp(x[0]), round(np.degrees(yaw)), *x[1:4], 100 * info["covered"], 100 * info["pierced"], 1000 * info["gap"], 1000 * gap)
    if amb:
        b = amb[0]
        msg += "\n  AMBIGUOUS: scale %.3f / turn %d deg fits nearly as well (cost %.4g vs %.4g): check the preview, or give UNIT / TURN_BACK / SCALE_RANGE" % (
            np.exp(b[3][0]) * f, round(np.degrees(b[3][4])), b[0], c0)
    if REPORT:
        print(msg)
    if not APPLY:
        return x, f, info
    c, sn = np.cos(yaw), np.sin(yaw)
    R3 = np.array([[c, -sn, 0], [sn, c, 0], [0, 0, 1.0]])
    T = np.eye(4); T[:3, :3] = np.exp(x[0]) * R3; T[:3, 3] = x[1:4]
    U = np.diag([f, f, f, 1.0])
    for ob in obs:
        ob.data.transform(Matrix(T @ U) @ ob.matrix_world)       # into the mesh: world coordinates, the object's own transform becomes identity
        ob.matrix_world = Matrix.Identity(4)
    bpy.context.view_layer.update()
    return x, f, info


_result = run()
