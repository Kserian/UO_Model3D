"""Conform a worn item (shirt, tunic, coat) to the UO body: a shell of the skin at a small, steady distance, so that the skin does not come through it in the actions
and it does not slide or tear when the arms move.

    python uo_conform_item.py ITEM.blend [OUT.blend] [--set NAME=VALUE ...]      # e.g. --set MOVE=0,0,-0.07 --set GAP=0.02 --set SKIRT=False

ITEM.blend is the output of uo_make_item.py (the item in the collection Clothing, placed and sized by uo_autofit_item.py, "prepare": {"FIT": false, "DENSIFY": false};
uo_make_item.py "conform" does that and runs this script). Its fit and weights are replaced. Why: a model made on another mannequin (the Jedi tunic: sleeves 9-18 cm
above the UO arms, the chest of the UO body through its front and back) cannot be pushed into place in the rest pose: the push of uo_fit_item.py moved parts up to
21 cm, the sleeves stayed off the arms and in the actions the arms came out of them (docs/qa/jedi_tunic.md). Here:
  1. sleeves onto the arms: per side the centre line of the sleeve (centroids of slices) is turned and moved onto the line of the UO arm (shoulder -> wrist); the move
     fades in over BLEND from the root of the sleeve and out beyond the radius of the sleeve tube, so the torso part stays where it is;
  2. wrap: the item is pulled onto the body like a membrane, to h = GAP + a little of the model's looseness (LOOSE_K, at most LOOSE_MAX) and folds (FOLD_MAX):
     pulled along its own normal (the stand-off is continuous, so nothing tears), kept out of the skin along the skin normal (inside an arm: away from its bone),
     at most WRAP_STEP a pass, smoothed (even vertices, hollows like the armpit bridged) and no edge stretched more than STRETCH x; the outline (hem, neck, cuffs)
     and the UVs stay those of the model. SKIRT: below the crotch the model keeps its shape (out of the legs by GAP): the skirt of a tunic hangs, it does not wrap the legs;
  3. weights: those of the skin point under the vertex (SMOOTH passes; hands -> forearm), except that the torso part keeps only TORSO_ARM of the arm's weight (the skin of
     the upper chest and shoulder carries 30-90 % of the arm: the item slid after a raised arm); within TORSO_ARM_NEAR of the arm's skin it keeps all of it. SKIRT: what
     lies over the thighs follows the pelvis and the legs push it per frame (render_uo_layer.py, custom property uo_cloth, like a robe);
  4. the render keeps it POSE_GAP off the skin in every frame (custom property uo_conform, point attribute uo_region: cloth_lib.conform_push): the torso part off the
     torso, legs, head and arms, a sleeve off its arm, the root of a sleeve off its arm and the torso. (A static version, moving the rest shape out for all the poses,
     made the tunic lumpy: 6000 vertices moved by up to 9 cm.)
Measure it with item_clearance.py (skin through the item after the render's push, stretch) and look at it with uo_make_item.py --preview.
"""
import sys, os, json
import numpy as np
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

GAP = 0.015           # m: distance of the shell from the skin (uo_fit_item.py GAP_BY_KIND shirt; the original shirts stand ~1 px = 2.8 cm off the body silhouette)
LOOSE_K = 0.25        # share of the model's smooth stand-off kept on top of GAP (0 = skin-tight, 1 = as loose as the model)
LOOSE_MAX = 0.03      # m: at most this much of it
FOLD_MAX = 0.02       # m: folds of the model (stand-off minus its smooth part) kept up to this much outwards (and half of it inwards)
FOLD_SMOOTH = 12      # passes that make the smooth part of the stand-off (bigger = broader things count as folds)
MOVE = (0.0, 0.0, 0.0) # m: the whole item is moved by this first
SLEEVES = True        # step 1
SLEEVE_END = -1.0     # m: >= 0 = each sleeve is shortened along its arm (only its last SLEEVE_SPAN before the end is squeezed, the cuff keeps its shape) so that it ends this far past the
                      # wrist (the head of the hand bone): a bell sleeve of a longer-armed mannequin hid the hands (docs/qa/robe_black.md: 9 cm past the wrist -> 0.02). < 0 = as the model
SLEEVE_SPAN = 0.25    # m
BLEND = 0.10          # m: along the sleeve from its root, over which it goes from where the model has it to the UO arm
TUBE_MARGIN = 0.05    # m: beyond the radius of the sleeve tube the move fades out over this (the side of the torso under the arm stays)
SKIRT = True          # below the crotch: hangs (the model's shape, pushed out of the legs), follows the pelvis, the legs push it in the render
SKIRT_TOP = 0.05      # m above the crotch where the shell starts to give way to the hanging skirt (over SKIRT_BAND)
SKIRT_BAND = 0.08
POSE_GAP = 0.008      # m: in every frame of every action nothing of the item closer than this to the skin of its own region (render_uo_layer.py BODY_GAP is 0.006)
TORSO_ARM = 0.35      # share of the arm's weight the torso part of the item keeps (front, back, sides, the cap of the shoulder); the rest goes to the chest; the sleeves keep all of it. 1 = as the skin
TORSO_ARM_NEAR = 0.02 # m from the skin of the arm (upper arm, forearm) within which the item keeps all of the arm's weight
TORSO_ARM_FADE = 0.06 # m beyond that over which it fades to TORSO_ARM (a sharp change tears the shoulder seam open when the arm moves)
ROOT_SHARE = 0.1      # a sleeve vertex with at least this share of torso weight is the root of the sleeve: the render keeps it off the torso too (the side of the chest under a raised arm)
SMOOTH = 4            # passes of weight smoothing over the item
RELAX = 3             # passes of smoothing of the shell offset (h) over the item
WRAP_ITERS = 150      # passes of pulling the item onto the body as a membrane
WRAP_PULL = 0.3       # share of the excess stand-off removed per pass (along the item's own normal)
WRAP_SMOOTH = 0.3     # membrane smoothing per pass (spreads the vertices, bridges hollows)
LIMB_R = 0.07         # m: a vertex inside an arm closer than this to its bone is pushed out straight away from the bone
SETTLE_ITERS = 200    # passes after the wrap that only keep the item out of the skin
STRETCH = 1.25        # the most an edge may be stretched against the model while it is wrapped
WRAP_FLATTEN = 0.2    # share of the smoothing across the surface (0 = only along it)
WRAP_STEP = 0.01      # m: the most a vertex moves in one pass (the smoothing keeps up: no vertex flies off on its own)
SPACE_SMOOTH = 0.0    # m: > 0 = the move of the wrap is averaged over everything within this distance in SPACE (not along the mesh): a model of separate overlapping panels (a closure of two
                      # flaps, knots on it, a stand-up collar: the robe of docs/qa/robe_black.md) moves as one piece, its panels do not cut through each other and open holes
SPACE_PASSES = 2      # passes of that averaging
FINAL_ITERS = 40      # passes of the last push out of the skin (to 0.9 GAP; inside an arm away from its bone)
REGIONS = ("torso", "arm.L", "arm.R", "leg.L", "leg.R")
CLOTH_MARGIN_SHORT, CLOTH_KAPPA_SHORT, CLOTH_MARGIN, CLOTH_KAPPA, CLOTH_DROP = 0.02, 0.5, 0.05, 0.8, 1.0   # uo_bind_item.py mark_cloth


def bone_region(name):
    n = name.split(".")[0]
    side = name[-2:] if name[-2:] in (".L", ".R") else ""
    if n in ("upper_arm", "forearm", "hand") or n.startswith("finger"):
        return "arm" + side
    if n in ("thigh", "shin", "foot"):
        return "leg" + side
    if n in ("polearm", "axe2h", "bow", "shield", "weapon1h"):
        return "arm" + side
    return "torso"


def rest_co(ob):
    co = np.empty(len(ob.data.vertices) * 3, np.float32); ob.data.vertices.foreach_get("co", co)
    M = np.array(ob.matrix_world)
    return co.reshape(-1, 3).astype(np.float64) @ M[:3, :3].T + M[:3, 3]


def weights(ob, bones):
    W = np.zeros((len(ob.data.vertices), len(bones)))
    gi = {g.index: bones.index(g.name) for g in ob.vertex_groups if g.name in bones}
    for v in ob.data.vertices:
        for g in v.groups:
            if g.group in gi:
                W[v.index, gi[g.group]] += g.weight
    s = W.sum(1, keepdims=True)
    return np.where(s > 0, W / np.maximum(s, 1e-12), 0.0)


class Graph:
    def __init__(self, n, E):
        self.E = E; self.deg = np.bincount(E.ravel(), minlength=n).astype(float)

    def nsum(self, x):
        acc = np.zeros_like(x)
        np.add.at(acc, self.E[:, 0], x[self.E[:, 1]]); np.add.at(acc, self.E[:, 1], x[self.E[:, 0]])
        return acc

    def smooth(self, x, passes, fixed=None):
        d = self.deg.reshape((-1,) + (1,) * (x.ndim - 1))
        for _ in range(passes):
            y = np.where(d > 0, 0.5 * x + 0.5 * self.nsum(x) / np.maximum(d, 1), x)
            x = y if fixed is None else np.where(fixed.reshape(d.shape), x, y)
        return x


def nearest(bvh, P, reach=1.0):
    loc = np.zeros_like(P); nrm = np.zeros_like(P); fi = np.full(len(P), -1); S = np.full(len(P), reach)
    for k, p in enumerate(P):
        l, n, f, d = bvh.find_nearest(Vector(p), reach)
        if l is not None:
            loc[k] = l; nrm[k] = n; fi[k] = f; S[k] = (Vector(p) - l).dot(n)
    return loc, nrm, fi, S


def bary(P, A, B, C):
    v0, v1, v2 = B - A, C - A, P - A
    d00 = (v0 * v0).sum(1); d01 = (v0 * v1).sum(1); d11 = (v1 * v1).sum(1); d20 = (v2 * v0).sum(1); d21 = (v2 * v1).sum(1)
    den = np.maximum(d00 * d11 - d01 * d01, 1e-18)
    v = (d11 * d20 - d01 * d21) / den; w = (d00 * d21 - d01 * d20) / den
    b = np.clip(np.stack([1 - v - w, v, w], 1), 0, 1)
    return b / np.maximum(b.sum(1, keepdims=True), 1e-12)


def rot_between(a, b):
    a = a / np.linalg.norm(a); b = b / np.linalg.norm(b)
    v = np.cross(a, b); c = float(a @ b)
    if np.linalg.norm(v) < 1e-9:
        return np.eye(3)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K / (1 + c)


def align_sleeves(X, rig, G):
    """turn and move each sleeve so that its centre line lies on the UO arm (shoulder joint -> wrist); fades in over BLEND from the root of the sleeve"""
    X = X.copy(); member = np.zeros(len(X))
    for sd, sg in (("L", 1.0), ("R", -1.0)):
        J = np.array(rig.matrix_world @ rig.data.bones["upper_arm." + sd].head_local)
        Hd = np.array(rig.matrix_world @ rig.data.bones["hand." + sd].head_local)
        da = (Hd - J) / np.linalg.norm(Hd - J)
        sel = (X[:, 0] * sg > abs(J[0]) + 0.05) & (X[:, 2] > J[2] - 0.6)
        if sel.sum() < 50:
            print("uo_conform_item: no sleeve on side %s" % sd); continue
        S = X[sel]
        far = S[np.argmax(np.linalg.norm(S - J, axis=1))]
        d0 = (far - J) / np.linalg.norm(far - J)
        t = (S - J) @ d0
        edges = np.linspace(np.percentile(t, 5), np.percentile(t, 98), 9)
        C = np.array([S[(t >= a) & (t < b)].mean(0) for a, b in zip(edges[:-1], edges[1:]) if ((t >= a) & (t < b)).sum() > 5])
        Cd = C[2:]                                                      # the distal part: the root mixes with the torso panel
        ds = np.linalg.svd(Cd - Cd.mean(0), full_matrices=False)[2][0]
        ds = ds if ds @ da > 0 else -ds
        cs = Cd.mean(0)
        R = rot_between(ds, da)
        target = J + ((cs - J) @ da) * da                               # the centre of the sleeve goes onto the arm line, at the same distance from the shoulder
        root = C[0]
        sx = (X - cs) @ ds
        perp = np.linalg.norm((X - cs) - sx[:, None] * ds, axis=1)          # distance from the centre line of the sleeve: the tube of the sleeve, not the side of the torso under it
        Rt = np.percentile(perp[sel & (sx > 0)], 95)
        wt = np.clip((Rt + TUBE_MARGIN - perp) / TUBE_MARGIN, 0, 1)
        s = (X - root) @ ds
        w = np.clip(s / BLEND, 0, 1) * wt * (X[:, 0] * sg > 0)
        w = G.smooth(w, 6); w = w * w * (3 - 2 * w)
        Y = (X - cs) @ R.T + target
        X = X + w[:, None] * (Y - X)
        root_ramp = np.clip((s + 0.02) / 0.05, 0, 1)                    # for the weights the whole sleeve counts, from its root (the move above fades in over BLEND)
        member = np.maximum(member, G.smooth(wt * root_ramp * (X[:, 0] * sg > 0), 2))
        off = np.linalg.norm((cs - J) - ((cs - J) @ da) * da)
        print("uo_conform_item: sleeve %s: %.1f deg off the arm, centre line %.1f cm from it -> moved onto the arm (%d vertices, fade over %.0f cm)" % (
            sd, np.degrees(np.arccos(np.clip(ds @ da, -1, 1))), 100 * off, int((w > 0).sum()), 100 * BLEND), flush=True)
    return X, member


def orient_panels(o, otri, itri, X, bvh):
    """triangles of the welded item, each panel (island of the unwelded mesh: sewing patterns come as panels, possibly with opposite winding) turned so that its
    normals point away from the body"""
    import scipy.sparse as sp
    from scipy.sparse.csgraph import connected_components
    nv = len(o.data.vertices)
    Eo = np.array([e.vertices[:] for e in o.data.edges]).reshape(-1, 2)
    _, comp = connected_components(sp.coo_matrix((np.ones(len(Eo)), (Eo[:, 0], Eo[:, 1])), shape=(nv, nv)), directed=False)
    isl = comp[otri[:, 0]]
    c = X[itri].mean(1)
    f = np.cross(X[itri[:, 1]] - X[itri[:, 0]], X[itri[:, 2]] - X[itri[:, 0]])
    l, _, _, _ = nearest(bvh, c)
    dot = ((c - l) * f).sum(1)
    out = itri.copy(); flipped = 0
    for k in np.unique(isl):
        m = isl == k
        if np.median(dot[m]) < 0:
            out[m] = out[m][:, ::-1]; flipped += 1
    print("uo_conform_item: %d panel(s), %d turned so the normals point out" % (len(np.unique(isl)), flipped))
    return out


def cloth_params(rig, X):
    """custom property uo_cloth of a loose garment, as uo_bind_item.py mark_cloth computes it"""
    band = X[(X[:, 2] > 0.4) & (X[:, 2] < 0.9)]
    centre = band[:, :2].mean(0) if len(band) else X[:, :2].mean(0)
    z_top = float(np.array(rig.matrix_world @ rig.data.bones["pelvis"].head_local)[2]) + 0.04
    z_hem = float(X[:, 2].min())
    t = min(max((z_hem - 0.15) / 0.15, 0.0), 1.0)
    return dict(centre=[round(float(centre[0]), 4), round(float(centre[1]), 4)], margin=round(CLOTH_MARGIN + (CLOTH_MARGIN_SHORT - CLOTH_MARGIN) * t, 4),
                kappa=round(CLOTH_KAPPA + (CLOTH_KAPPA_SHORT - CLOTH_KAPPA) * t, 4), z_top=round(z_top, 4), z_hem=round(z_hem, 4), ramp=0.15, drop=CLOTH_DROP)


def main():
    args = sys.argv[1:]
    src = os.path.abspath(args.pop(0))
    dst = os.path.abspath(args.pop(0)) if args and not args[0].startswith("--") else src
    g = globals()
    while args:
        f = args.pop(0)
        if f == "--set":
            k, v = args.pop(0).split("=", 1)
            assert k in g, k
            g[k] = (v.lower() in ("1", "true", "yes")) if isinstance(g[k], bool) else tuple(float(x) for x in v.split(",")) if isinstance(g[k], tuple) else type(g[k])(v)
    bpy.ops.wm.open_mainfile(filepath=src)
    rig, body = bpy.data.objects["UO_Rig"], bpy.data.objects["UO_Body"]
    items = [o for o in bpy.data.collections["Clothing"].all_objects if o.type == "MESH" and not o.hide_render]
    bones = [b.name for b in rig.data.bones]
    breg = np.array([bone_region(b) for b in bones])
    rig.data.pose_position = "REST"; bpy.context.view_layer.update()

    Vb = rest_co(body); Wb = weights(body, bones)
    me = body.data; me.calc_loop_triangles()
    tri = np.array([t.vertices[:] for t in me.loop_triangles])
    domb = np.array(bones)[Wb[tri].sum(1).argmax(1)]
    bare = np.array([b == "head" or b.split(".")[0] == "hand" or b.startswith("finger") for b in domb])   # head and hands stay bare
    fn = np.cross(Vb[tri[:, 1]] - Vb[tri[:, 0]], Vb[tri[:, 2]] - Vb[tri[:, 0]])
    vnb = np.zeros_like(Vb)
    for k in range(3):
        np.add.at(vnb, tri[:, k], fn)
    vnb /= np.maximum(np.linalg.norm(vnb, axis=1, keepdims=True), 1e-12)
    anyset = np.nonzero(~bare)[0]
    bvh_any = BVHTree.FromPolygons([Vector(p) for p in Vb], tri[anyset].tolist())
    hands = np.array([b.split(".")[0] == "hand" or b.startswith("finger") for b in domb])
    bvh_arm = {sd: BVHTree.FromPolygons([Vector(p) for p in Vb], tri[np.isin(domb, ["upper_arm." + sd, "forearm." + sd])].tolist()) for sd in ("L", "R")}
    bvh_col = BVHTree.FromPolygons([Vector(p) for p in Vb], tri[~hands].tolist())   # what the item is kept out of while it is wrapped: the head too (a collar around it)
    leg = np.array([b.split(".")[0] in ("thigh", "shin", "foot") for b in bones])
    hand = np.array([b.split(".")[0] == "hand" or b.startswith("finger") for b in bones])
    pel = bones.index("pelvis")
    crotch = float(Vb[(np.abs(Vb[:, 0]) < 0.02) & (np.abs(Vb[:, 1] - Vb[:, 1].mean()) < 0.06) & (Vb[:, 2] < 1.0) & (Vb[:, 2] > 0.6), 2].max())

    for o in items:
        V = rest_co(o)
        key = np.round(V / 1e-5).astype(np.int64)
        _, first, node = np.unique(key, axis=0, return_index=True, return_inverse=True); node = node.ravel()
        E = np.empty(len(o.data.edges) * 2, np.int32); o.data.edges.foreach_get("vertices", E)
        E = np.unique(np.sort(node[E.reshape(-1, 2)], 1), axis=0); E = E[E[:, 0] != E[:, 1]]
        X0 = V[first]; n = len(X0); G = Graph(n, E)
        o.data.calc_loop_triangles()
        otri = np.array([t.vertices[:] for t in o.data.loop_triangles])
        itri = node[otri]
        itri = orient_panels(o, otri, itri, X0, bvh_any)

        X0 = X0 + np.array(MOVE)                                         # a nudge of the whole item (e.g. a model that sits too high on the UO shoulders)
        # 1. sleeves onto the arms
        X, sleeve = align_sleeves(X0, rig, G) if SLEEVES else (X0.copy(), np.zeros(len(X0)))
        if SLEEVE_END >= 0:                                              # sleeves shortened to end SLEEVE_END past the wrist
            for sd, sg in (("L", 1.0), ("R", -1.0)):
                J = np.array(rig.matrix_world @ rig.data.bones["upper_arm." + sd].head_local); Hd = np.array(rig.matrix_world @ rig.data.bones["hand." + sd].head_local)
                ax = (Hd - J) / np.linalg.norm(Hd - J); tw = (Hd - J) @ ax
                m = (sleeve > 0.5) & (X[:, 0] * sg > 0)
                if m.sum() < 20:
                    continue
                t = (X - J) @ ax; tend = float(np.percentile(t[m], 99.5)); want = tw + SLEEVE_END
                if tend <= want:
                    continue
                t0 = want - SLEEVE_SPAN; k = (want - t0) / (tend - t0)
                w = np.clip(sleeve, 0, 1) * (X[:, 0] * sg > 0) * (t > t0)
                X = X - (w * (t - t0) * (1 - k))[:, None] * ax
                print("uo_conform_item: sleeve %s shortened: ended %.1f cm past the wrist, now %.1f cm (last %.0f cm squeezed x%.2f)" % (sd, 100 * (tend - tw), 100 * SLEEVE_END, 100 * SLEEVE_SPAN, k), flush=True)

        # 2. wrap: the target stand-off h from the model's own (aligned) stand-off
        l, _, f, _ = nearest(bvh_any, X)
        t = tri[anyset[f]]; b = bary(l, Vb[t[:, 0]], Vb[t[:, 1]], Vb[t[:, 2]])
        nn = (vnb[t] * b[..., None]).sum(1); nn /= np.maximum(np.linalg.norm(nn, axis=1, keepdims=True), 1e-12)
        sd = ((X - l) * nn).sum(1)
        base = G.smooth(sd, FOLD_SMOOTH)
        fold = np.clip(sd - base, -0.5 * FOLD_MAX, FOLD_MAX)
        h = GAP + np.clip(LOOSE_K * np.clip(base - GAP, 0, None), 0, LOOSE_MAX) + np.clip(fold, 0, None) + np.clip(fold, None, 0) * 0.5
        h = np.maximum(G.smooth(h, RELAX), GAP)
        if SKIRT:                                                       # below the crotch: the model's shape (aligned), out of the legs by GAP; blended into the shell above
            z = X0[:, 2]
            a = np.clip((z - (crotch + SKIRT_TOP - SKIRT_BAND)) / SKIRT_BAND, 0, 1); a = a * a * (3 - 2 * a)
            a = G.smooth(a, 4)
            Xk = X.copy()
            for it in range(20):
                _, nr2, _, S1 = nearest(bvh_any, Xk, 0.3)
                need = np.clip(GAP - S1, 0, None)
                if need.max() < 5e-4:
                    break
                Xk = Xk + G.smooth(need[:, None] * nr2, 3) + need[:, None] * nr2
        else:
            a = np.ones(n); Xk = X
        tc = np.sort(np.concatenate([itri[:, [0, 1]], itri[:, [1, 2]], itri[:, [2, 0]]]), 1)
        ue, cnt = np.unique(tc, axis=0, return_counts=True)
        border = np.zeros(n, bool); border[ue[cnt == 1].ravel()] = True

        be = ue[cnt == 1]                                               # the outline: smoothed only along itself
        Gb = Graph(n, be)

        def item_normals(P):
            f = np.cross(P[itri[:, 1]] - P[itri[:, 0]], P[itri[:, 2]] - P[itri[:, 0]])
            v = np.zeros_like(P)
            for k in range(3):
                np.add.at(v, itri[:, k], f)
            return v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-12)

        orient = 1.0                                                    # orient_panels: the item normals point away from the body
        L0 = np.linalg.norm(X0[E[:, 0]] - X0[E[:, 1]], axis=1)
        Xs = X.copy()
        segs = [(np.array(rig.matrix_world @ rig.data.bones[bn].head_local), np.array(rig.matrix_world @ rig.data.bones[bn].tail_local))
                for bn in ("upper_arm.L", "forearm.L", "upper_arm.R", "forearm.R")]

        def limb_out(P, fallback):
            best = np.full(len(P), np.inf); out = fallback.copy()
            for A, B in segs:
                ab = B - A; t = np.clip(((P - A) @ ab) / (ab @ ab), 0, 1)
                d = P - (A + t[:, None] * ab); dist = np.linalg.norm(d, axis=1)
                m = (dist < best) & (dist < LIMB_R) & (dist > 1e-6)
                out[m] = d[m] / dist[m, None]; best = np.minimum(best, np.where(m, dist, np.inf))
            return out

        def wrap_pass(Xs, attract):
            Ng = orient * G.smooth(item_normals(Xs), 2)
            Ng /= np.maximum(np.linalg.norm(Ng, axis=1, keepdims=True), 1e-12)
            if attract:                                                 # pulled in along its own normal, only where it faces away from the skin it is over
                ls, nrm_s, _, sd = nearest(bvh_col, Xs, 0.5)
                facing = ((Xs - ls) * Ng).sum(1) > 0
                Xs = Xs - np.clip(WRAP_PULL * (sd - h), 0, WRAP_STEP)[:, None] * facing[:, None] * Ng
            Lx = np.where(border[:, None], Gb.nsum(Xs) / np.maximum(Gb.deg, 1)[:, None] - Xs, G.nsum(Xs) / np.maximum(G.deg, 1)[:, None] - Xs)
            Lx -= (Lx * Ng).sum(1)[:, None] * Ng * (1 - WRAP_FLATTEN)    # mostly along the surface: spreads the vertices without flattening the folds
            Xs = Xs + WRAP_SMOOTH * Lx
            for _ in range(3):                                          # cloth: an edge stretches at most STRETCH x its length in the model (squeezing is free: the sleeve gathers)
                d = Xs[E[:, 1]] - Xs[E[:, 0]]; Lc = np.linalg.norm(d, axis=1)
                ex = np.clip(Lc - STRETCH * L0, 0, None) / np.maximum(Lc, 1e-12)
                corr = np.zeros_like(Xs)
                np.add.at(corr, E[:, 0], 0.5 * ex[:, None] * d); np.add.at(corr, E[:, 1], -0.5 * ex[:, None] * d)
                Xs = Xs + corr / np.maximum(G.deg, 1)[:, None] * 2
            _, nrm_s, _, sd = nearest(bvh_col, Xs, 0.5)                 # out of the skin to h along the skin normal, at most WRAP_STEP a pass, spread over the neighbours
            nrm_s = np.where((sd < 0)[:, None], limb_out(Xs, nrm_s), nrm_s)   # inside an arm: straight away from its bone (near the bone the nearest skin may be the far side)
            push = np.clip(h - sd, 0, WRAP_STEP)[:, None] * nrm_s
            Xs = Xs + push + 0.5 * G.smooth(push, 2)
            return a[:, None] * Xs + (1 - a[:, None]) * Xk, sd          # the skirt keeps the model's shape

        for it in range(WRAP_ITERS):                                    # a membrane pulled onto the body (the stand-off is continuous, so nothing tears), kept out of the skin, smoothed so it
            Xs, sd = wrap_pass(Xs, True)                                # spreads evenly and bridges hollows (armpit) like cloth
        for it in range(SETTLE_ITERS):                                  # then only kept out of the skin, until nothing is closer than GAP
            Xs, sd = wrap_pass(Xs, False)
            if sd.min() > GAP * 0.9:
                break
        sdw = nearest(bvh_col, Xs, 0.5)[3]
        print("uo_conform_item: after the wrap (+%d settle passes): %d vertices closer than GAP, %d inside, deepest %.1f mm" % (
            it + 1, int((sdw < GAP - 1e-3).sum()), int((sdw < 0).sum()), -1000 * min(sdw.min(), 0)), flush=True)
        r1 = np.linalg.norm(Xs[E[:, 0]] - Xs[E[:, 1]], axis=1) / np.maximum(L0, 1e-9)
        sd = nearest(bvh_col, Xs, 0.5)[3]
        print("uo_conform_item: %s: wrapped (%d passes): stand-off minus target p50 %.1f p90 %.1f max %.1f mm; edge length / model's p01 %.2f p99 %.2f max %.2f" % (
            o.name, WRAP_ITERS, *(1000 * np.percentile(sd - h, [50, 90, 100])), *np.percentile(r1, [1, 99, 100])), flush=True)
        if SPACE_SMOOTH > 0:                                            # the move of the wrap averaged in space: overlapping panels (flaps, knots, collar) move together
            from scipy.spatial import cKDTree
            from scipy.sparse import coo_matrix
            pr = cKDTree(X).query_pairs(SPACE_SMOOTH, output_type="ndarray")
            dd = np.linalg.norm(X[pr[:, 0]] - X[pr[:, 1]], axis=1); wk = np.exp(-(dd / (0.5 * SPACE_SMOOTH)) ** 2)
            K = coo_matrix((np.r_[wk, wk, np.ones(n)], (np.r_[pr[:, 0], pr[:, 1], np.arange(n)], np.r_[pr[:, 1], pr[:, 0], np.arange(n)])), shape=(n, n)).tocsr()
            ks = np.asarray(K.sum(1)).ravel()
            D = Xs - X
            for _ in range(SPACE_PASSES):
                D = (K @ D) / ks[:, None]
            Xs = X + D
            print("uo_conform_item: %s: the wrap's move averaged over %.0f mm in space (%d passes, %.0f neighbours per vertex)" % (o.name, 1000 * SPACE_SMOOTH, SPACE_PASSES, 2 * len(pr) / n), flush=True)
        for it in range(FINAL_ITERS):                                   # what the blend or a concave spot (armpit, crotch) brought too close: out to GAP
            _, nr2, _, S1 = nearest(bvh_any, Xs, 0.3)
            nr2 = np.where((S1 < 0)[:, None], limb_out(Xs, nr2), nr2)    # inside an arm: straight away from its bone
            need = np.clip(GAP * 0.9 - S1, 0, None)
            if need.max() < 5e-4:
                break
            Xs = Xs + G.smooth(need[:, None] * nr2, 2) + need[:, None] * nr2
        S1 = nearest(bvh_any, Xs, 0.3)[3]
        print("uo_conform_item: %s: after the last push (%d passes): %d vertices inside the skin, deepest %.1f mm" % (o.name, it + 1, int((S1 < 0).sum()), -1000 * min(S1.min(), 0)), flush=True)
        X1 = Xs
        S1 = nearest(bvh_any, X1, 0.3)[3]
        print("uo_conform_item: %s: %d vertices; shell %.0f mm + looseness / folds: stand-off p50 %.1f / p90 %.1f / max %.1f cm (model %.1f / %.1f / %.1f), min %.1f mm%s" % (
            o.name, n, 1000 * GAP, *(100 * np.percentile(S1, [50, 90, 100])),
            *(100 * np.percentile(nearest(bvh_any, X0, 0.5)[3], [50, 90, 100])), 1000 * S1.min(), "; skirt below %.2f m" % (crotch + SKIRT_TOP) if SKIRT else ""), flush=True)

        # 3. weights: those of the skin under the item
        l, _, f, _ = nearest(bvh_any, X1)
        t = tri[anyset[f]]; b = bary(l, Vb[t[:, 0]], Vb[t[:, 1]], Vb[t[:, 2]])
        Wn = G.smooth((Wb[t] * b[..., None]).sum(1), SMOOTH)
        for side in (".L", ".R"):                                       # hands and fingers -> forearm
            j = [k for k, bn in enumerate(bones) if hand[k] and bn.endswith(side)]
            Wn[:, bones.index("forearm" + side)] += Wn[:, j].sum(1); Wn[:, j] = 0
        Wn[:, ~np.array([rig.data.bones[bn].use_deform for bn in bones])] = 0
        Wn = np.clip(Wn, 0, None); Wn /= np.maximum(Wn.sum(1, keepdims=True), 1e-12)
        if TORSO_ARM < 1:                                               # the front and back of the item stay on the torso when an arm goes up (the skin of the upper chest and the shoulder
            ch = bones.index("chest")                                   # carries 30-90 % of the arm: the item followed the raised arm and slid to one side in the spells); the sleeve takes the arm
            for sd, sg in (("L", 1.0), ("R", -1.0)):
                da = nearest(bvh_arm[sd], X1, 0.5)[3]                    # all of the arm within TORSO_ARM_NEAR of the skin of the arm (the sleeve, the cap of the shoulder, the armpit:
                f = np.clip(1 - (np.abs(da) - TORSO_ARM_NEAR) / TORSO_ARM_FADE, 0, 1)   # with less, the root of the sleeve lagged behind a raised arm and left the upper arm bare),
                f = np.maximum(G.smooth(f * f * (3 - 2 * f), 4), sleeve)              # fading to TORSO_ARM over TORSO_ARM_FADE: the front and back of the chest
                keep = TORSO_ARM + (1 - TORSO_ARM) * f
                for bn in ("upper_arm." + sd, "forearm." + sd):
                    j = bones.index(bn); mv = Wn[:, j] * (1 - keep)
                    Wn[:, j] -= mv; Wn[:, ch] += mv
        Wleg = Wn[:, leg].copy()
        if SKIRT:
            Wn[:, pel] += Wn[:, leg].sum(1); Wn[:, leg] = 0
        Wn[Wn < 0.01] = 0; Wn /= np.maximum(Wn.sum(1, keepdims=True), 1e-12)

        X1 = Xs

        # write: shape, weights, armature, loose-garment data
        Mi = np.linalg.inv(np.array(o.matrix_world))
        if o.data.shape_keys:
            o.shape_key_clear()
        o.data.vertices.foreach_set("co", (X1[node] @ Mi[:3, :3].T + Mi[:3, 3]).astype(np.float32).ravel()); o.data.update()
        for vg in list(o.vertex_groups):
            o.vertex_groups.remove(vg)
        Wv = Wn[node]
        for j, bn in enumerate(bones):
            nz = np.nonzero(Wv[:, j] > 0)[0]
            if len(nz):
                vg = o.vertex_groups.new(name=bn)
                for k in nz:
                    vg.add([int(k)], float(Wv[k, j]), "REPLACE")
        if o.parent != rig:
            mw = o.matrix_world.copy(); o.parent = rig; o.matrix_parent_inverse = rig.matrix_world.inverted(); o.matrix_world = mw
        arm = next((m for m in o.modifiers if m.type == "ARMATURE"), None) or o.modifiers.new("Armature", "ARMATURE")
        arm.object = rig; arm.use_vertex_groups = True; arm.use_bone_envelopes = False
        li = list(np.nonzero(leg)[0])
        for nm in ("thigh.L", "shin.L", "foot.L", "thigh.R", "shin.R", "foot.R"):
            at = o.data.attributes.get("uo_leg_" + nm) or o.data.attributes.new(name="uo_leg_" + nm, type="FLOAT", domain="POINT")
            at.data.foreach_set("value", (Wleg[:, li.index(bones.index(nm))][node] if SKIRT else np.zeros(len(node))).astype(np.float32))
        rs = np.stack([Wn[:, breg == r].sum(1) for r in ("torso", "arm.L", "arm.R")], 1) + np.c_[Wn[:, leg].sum(1), np.zeros((n, 2))]
        at = o.data.attributes.get("uo_region") or o.data.attributes.new(name="uo_region", type="INT", domain="POINT")
        lab = rs.argmax(1)
        lab = np.where((lab > 0) & (rs[:, 0] >= ROOT_SHARE), lab + 2, lab)     # the root of a sleeve (some weight of the torso): kept off both
        at.data.foreach_set("value", lab[node].astype(np.int32))     # 0 torso part, 1 / 2 left / right sleeve, 3 / 4 their roots: cloth_lib.conform_push, render_uo_layer.py
        o["uo_conform"] = json.dumps(dict(gap=POSE_GAP))
        if SKIRT and (Wleg.sum(1) > 0.05).any():
            o["uo_cloth"] = json.dumps(cloth_params(rig, X1))
        elif "uo_cloth" in o:
            del o["uo_cloth"]
        print("uo_conform_item: %s: weights as the skin under it%s" % (o.name, "; skirt follows the pelvis, legs push it (uo_cloth %s)" % o["uo_cloth"] if "uo_cloth" in o else ""), flush=True)
    bpy.ops.wm.save_as_mainfile(filepath=dst)
    print("uo_conform_item: saved", dst)
    sys.stdout.flush(); os._exit(0)


if __name__ == "__main__":
    main()
