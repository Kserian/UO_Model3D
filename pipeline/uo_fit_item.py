# Fit the SELECTED item meshes onto the UO body (rest pose) before uo_bind_item.py. Place and size the item yourself;
# this script only fixes how it sits on the body:
# 1. Sleeves (MATCH_ARMS): an item made for a body with the arms lower / higher / more forward (or bent) has the UO
#    arms sticking out of its sleeves. The script finds the arm pose that fits into the sleeves and turns the sleeves
#    (and the item around the shoulders, like a skin) from that pose to the UO body's arms. Items without sleeves
#    (vest, cuirass) and sleeves that already sit on the arms are left alone.
# 2. Push: every part closer to the skin than MIN_GAP (or inside the body) is pushed out along the skin normal. A push
#    moves the whole area around it the same way and fades out smoothly over max(RADIUS, SPREAD x the push), so a
#    sleeve sitting 5 cm too deep is widened / moved as a whole instead of getting a bump; details (folds, rivets)
#    move with their area and are kept. Layers (a coat over a tunic) move together and stay in order.
# 3. MAX_GAP > 0 also pulls parts that stand off more than that back towards the skin, only where the whole area
#    around (RADIUS) stands off, so the thickness of the item is kept.
# Run it with the item selected (Alt+P); then run uo_bind_item.py. Running it again changes nothing once it fits.
# Existing shape keys get the same change. Faces much bigger than the gap can still cut through the skin between
# their corners: subdivide such an item first (Edit Mode, A, right click > Subdivide, Number of Cuts 2).
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

KIND = ""             # kind of item (as in uo_import_item.py): shirt, pants, boots, gloves, plate, legs, arms, helm, ... ("" = not given)
MIN_GAP = -1.0        # m, no part of the item closer to the skin than this (0 = only out of the body); < 0 = from KIND (GAP_BY_KIND, else 0.015)
# MIN_GAP by KIND, measured on thin body-hugging replicas against the original sprites (test_items.py --fit, IoU at 0.015 / 0.03 / 0.045):
# close-fitting cloth and leather is best at 0.015 (shirt .746/.727/.681, pants .801/.793/.747, boots .771/.755/.693, gloves .579/.576/.526); thick armour,
# helmets and sleeves at 0.03 (plate .702/.725/.706, helm .770/.783/.658, arms .615/.619/.598, legs .667/.673/.651). The sprites agree: shirts, trousers, boots
# stand 1 px (2.8 cm) off the silhouette of the body, plate / helmets / robes 2-4 px (docs/qa/layer_analysis.md). "neck" (gorget, a hard slot in uo_prepare_item.py) is 0.03 by
# its class, not measured.
GAP_BY_KIND = {"shirt": 0.015, "pants": 0.015, "boots": 0.015, "gloves": 0.015, "plate": 0.03, "legs": 0.03, "arms": 0.03, "helm": 0.03, "neck": 0.03, "robe": 0.02, "skirt": 0.02, "cloak": 0.03, "waist": 0.015, "vest": 0.02}
MAX_GAP = 0.0         # m, > 0: pull parts standing off more than this towards the skin (0 = off)
LIMIT = -1.0          # m, soft limit of how far from the skin any part of the item may stand: what is farther is brought closer (S -> LIMIT + (S - LIMIT) * LIMIT_K), smoothly over the
                      # mesh, so details are squashed, not cut. This is what keeps big pauldrons, flared cuffs and fat collars "UO-thin": the original items of a slot stand
                      # out of the body silhouette by this much at most (docs/qa/layer_analysis.md: plate 5.6-8.1 cm, shirt 5.6, helm 8.3); < 0 = LIMIT_BY_KIND, 0 = off
LIMIT_K = 0.3         # what is left of the excess: 0 = cut off at LIMIT, 1 = no limit
LIMIT_BY_KIND = {"shirt": 0.07, "plate": 0.05, "harness": 0.06, "arms": 0.07, "pants": 0.06, "legs": 0.07, "boots": 0.05, "gloves": 0.05, "helm": 0.10, "neck": 0.06, "waist": 0.05, "vest": 0.07}
RADIUS = 0.04         # m, smallest area a push spreads over
SPREAD = 3.0          # a push of d spreads over at least SPREAD * d (bigger = broader, gentler swelling)
ITERATIONS = 12       # push rounds at most (it stops as soon as nothing is too close)
MATCH_ARMS = True     # first turn the sleeves onto the arms: finds how much lower / higher / more forward the arms of
                      # the body the item was made for were, and turns the sleeves (and the item around the shoulders)
                      # by that much, so the arms sit inside the sleeves before anything is pushed
MAX_TURN = 35         # deg, the most the sleeves may be turned
MIN_GAIN = 3.0        # turn only if it fits the arms clearly better (so running the script again changes nothing)
SLIM = 1.0            # < 1 makes the item narrower below the chest (e.g. 0.85 = 15 % narrower at the hips and below),
                      # towards the body's middle; sleeves and the chest are left as they are. Run once per change:
                      # every run slims again

if MIN_GAP < 0:
    MIN_GAP = GAP_BY_KIND.get(KIND, 0.015)
if LIMIT < 0:
    LIMIT = LIMIT_BY_KIND.get(KIND, 0.0)

body = bpy.data.objects["UO_Body"]
rig = bpy.data.objects["UO_Rig"]


def body_bvh():
    me = body.data
    kb = me.shape_keys.key_blocks["Basis"] if me.shape_keys else None
    co = np.empty(len(me.vertices) * 3, np.float32)
    (kb.data if kb else me.vertices).foreach_get("co", co)
    me.calc_loop_triangles()
    tri = [t.vertices[:] for t in me.loop_triangles]
    return BVHTree.FromPolygons([Vector(p) for p in co.reshape(-1, 3)], tri)


def skin(bvh, P, reach=None):
    """nearest skin normal and signed distance (< 0 inside the body) of every point; points farther than `reach`
    get S = reach (not looked at closer - quick)"""
    N = np.zeros_like(P); S = np.full(len(P), np.inf if reach is None else reach)
    for i, p in enumerate(P):
        v = Vector(p)
        loc, nrm, fi, d = bvh.find_nearest(v) if reach is None else bvh.find_nearest(v, reach)
        if loc is not None:
            N[i] = nrm; S[i] = (v - loc).dot(nrm)
    return N, S


def push_field(Q, V, strict=False):
    """push vectors V (non-zero at the parts that are too close) -> displacement of every point: each push moves the
    points around it by its own vector, fading out over max(RADIUS, SPREAD * |push|); where pushes overlap the biggest
    sets how far and the (weighted) mean of their directions sets where to, so the area moves as one"""
    mag = np.linalg.norm(V, axis=1)
    src = np.nonzero(mag > 1e-5)[0]
    src = src[np.argsort(-mag[src])]
    F = np.zeros(len(Q)); Dsum = np.zeros_like(Q); Wsum = np.zeros(len(Q))
    for i in src:
        if F[i] >= mag[i] and Dsum[i] @ V[i] > 0.95 * np.linalg.norm(Dsum[i]) * mag[i]:
            continue                                               # already covered by a bigger push the same way
        R = max(RADIUS, SPREAD * mag[i])
        near = np.nonzero(np.abs(Q - Q[i]).max(1) < R)[0]
        w = np.clip(1 - np.sum((Q[near] - Q[i]) ** 2, 1) / R ** 2, 0, None) ** 2
        F[near] = np.maximum(F[near], mag[i] * w)
        Dsum[near] += (w ** 2)[:, None] * V[i]
        Wsum[near] += w ** 2 * mag[i]
    if strict:                                                     # pushes that disagree do not cancel out
        return F[:, None] * Dsum / np.maximum(np.linalg.norm(Dsum, axis=1), 1e-12)[:, None]
    return F[:, None] * Dsum / np.maximum(Wsum, 1e-12)[:, None]


def rot(axis, ang):
    a = np.asarray(axis, float) / np.linalg.norm(axis)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + np.sin(ang) * K + (1 - np.cos(ang)) * K @ K


def about(R, p):
    T = np.eye(4); T[:3, :3] = R; T[:3, 3] = p - R @ p
    return T


def subtree(bone):
    return {bone.name} | {c.name for c in bone.children_recursive}


class Arms:
    """the body's arms: joints, the share of every skin vertex that moves with the upper arm / forearm, arm radii"""
    def __init__(self):
        me = body.data
        kb = me.shape_keys.key_blocks["Basis"] if me.shape_keys else None
        co = np.empty(len(me.vertices) * 3, np.float32)
        (kb.data if kb else me.vertices).foreach_get("co", co)
        self.V = co.reshape(-1, 3).astype(np.float64)
        B = np.array(body.matrix_world.inverted() @ rig.matrix_world)      # armature -> body space
        Rw = np.array(body.matrix_world.inverted().to_3x3())
        self.X = Rw @ [1, 0, 0]; self.Y = Rw @ [0, 1, 0]; self.fwd = Rw @ [0, -1, 0]
        gi = {g.name: g.index for g in body.vertex_groups}
        W = np.zeros((len(self.V), len(body.vertex_groups)))
        for v in me.vertices:
            for g in v.groups:
                W[v.index, g.group] = g.weight
        bones = rig.data.bones; self.side = {}
        for sd, sg in (("L", 1), ("R", -1)):
            if "upper_arm." + sd not in bones:
                continue
            j = [B[:3, :3] @ bones[n + "." + sd].head_local + B[:3, 3] for n in ("upper_arm", "forearm", "hand")]
            wU = W[:, [gi[n] for n in subtree(bones["upper_arm." + sd]) if n in gi]].sum(1)
            wF = W[:, [gi[n] for n in subtree(bones["forearm." + sd]) if n in gi]].sum(1)
            wH = W[:, [gi[n] for n in subtree(bones["hand." + sd]) if n in gi]].sum(1)
            rU = np.percentile(seg_dist(self.V[(wU - wF) > 0.8], j[0], j[1]), 60)
            rF = np.percentile(seg_dist(self.V[((wF - wH) > 0.8)], j[1], j[2]), 60)
            kE = np.cross(j[1] - j[0], self.fwd); kE /= np.linalg.norm(kE)
            self.side[sd] = dict(s=sg, j=j, wU=wU, wF=wF, r=(rU, rF), kE=kE)

    def T(self, sd, up, fw, el):
        a = self.side[sd]; j = a["j"]
        TU = about(rot(self.Y, -a["s"] * up) @ rot(self.X, -fw), j[0])
        return TU, TU @ about(rot(a["kE"], el), j[1])


def seg_dist(P, a, b):
    ab = b - a; t = np.clip((P - a) @ ab / (ab @ ab), 0, 1)
    return np.linalg.norm(P - (a + t[:, None] * ab), axis=1)


def match_arms(Q, edges, gbvh):
    """turn the item from the arm pose it was made in to the body's pose (see MATCH_ARMS); Q: item points, body space"""
    arms = Arms(); found = {}; lim = np.radians(MAX_TURN)
    dirs = [(np.cos(t), np.sin(t)) for t in np.linspace(0, 2 * np.pi, 8, endpoint=False)]

    def cost(sd, x, misses=False):
        TU, TF = arms.T(sd, *x)
        j = arms.side[sd]["j"]; rU, rF = arms.side[sd]["r"]
        a = TU[:3, :3] @ j[0] + TU[:3, 3]; b = TU[:3, :3] @ j[1] + TU[:3, 3]; c = TF[:3, :3] @ j[2] + TF[:3, 3]
        c_ = 0.0; miss = 0
        for p0, p1, r, ts in ((a, b, rU, (0.4, 0.55, 0.7, 0.85, 1.0)), (b, c, rF, (0.15, 0.3, 0.45))):
            ax = (p1 - p0) / np.linalg.norm(p1 - p0)
            u = np.cross(ax, arms.fwd); u /= np.linalg.norm(u); w = np.cross(ax, u)
            for t in ts:
                p = Vector(p0 + t * (p1 - p0))
                for cs, sn in dirs:
                    hit = gbvh.ray_cast(p, Vector(cs * u + sn * w), 0.35)
                    if hit[0] is None:
                        c_ += 1.0; miss += 1                           # the arm is not inside the item here
                    else:
                        c_ += 4 * max(0.0, (r + 0.01 - hit[3]) / r) ** 2   # the item cuts into the arm
        return (miss, len(dirs) * 8) if misses else c_ + 2.0 * float(np.sum(np.square(x)))

    tried = []
    for sd in arms.side:
        g = np.radians(np.arange(-MAX_TURN, MAX_TURN + 0.1, 5.0))
        ge = np.radians(np.arange(-10, 60.1, 10.0))                     # elbow: -10 (straighter) .. 60 deg bent
        cand = [(cost(sd, (u, f, e)), (u, f, e)) for u in g for f in g if abs(f) <= np.radians(25) for e in ge]
        cand += [(cost(sd, tuple(x)), tuple(x)) for x in tried]        # the other sleeve's answer (same numbers = mirrored)
        f, x = min(cand, key=lambda r: r[0])                           # up, forward and elbow together: a sleeve made
        x = list(x)                                                    # with a bent elbow is found from any start
        for st in np.radians([4.0, 2.0, 1.0, 0.5]):                    # refine
            imp = True
            while imp:
                imp = False
                for k in range(3):
                    for sg in (1, -1):
                        y = list(x); y[k] = float(np.clip(y[k] + sg * st, -lim, lim) if k < 2 else np.clip(y[k] + sg * st, -0.2, 1.05))
                        fy = cost(sd, y)
                        if fy < f - 1e-9:
                            f, x, imp = fy, y, True
        tried.append(tuple(x))
        miss, rays = cost(sd, x, True)
        if miss > rays // 8:                                           # no sleeve around this arm (vest, cuirass)
            continue
        if f < cost(sd, (0.0, 0.0, 0.0)) - MIN_GAIN:                   # else the sleeve already sits on the arm
            found[sd] = x
    if not found:
        return Q, "none"
    # the item follows the posed body like the skin under it: weights from the nearest skin point, smoothed over the item
    PV = arms.V.copy(); Ts = {}
    for sd, x in found.items():
        a = arms.side[sd]; TU, TF = arms.T(sd, *x); Ts[sd] = (TU, TF)
        for w, T in ((a["wU"] - a["wF"], TU), (a["wF"], TF)):
            PV += w[:, None] * ((arms.V @ T[:3, :3].T + T[:3, 3]) - arms.V)
    kd = KDTree(len(PV))
    for i, p in enumerate(PV):
        kd.insert(p, i)
    kd.balance()
    near = np.array([kd.find(p)[1] for p in Q])
    kq = KDTree(len(Q))                                                # pieces that touch (cuffs, trims, collars)
    for i, p in enumerate(Q):                                          # move with what they touch
        kq.insert(p, i)
    kq.balance()
    touch = [(i, j) for i, p in enumerate(Q) for co, j, d in kq.find_range(p, 0.004) if j > i]
    if touch:
        edges = np.r_[edges, np.array(touch)]
    M = np.tile(np.eye(4), (len(Q), 1, 1))
    for sd in found:
        a = arms.side[sd]; TU, TF = Ts[sd]
        for w, T in ((a["wU"] - a["wF"], TU), (a["wF"], TF)):
            wq = w[near]
            for _ in range(8):                                         # smooth over the item
                acc = wq.copy(); cnt = np.ones(len(Q))
                np.add.at(acc, edges[:, 0], wq[edges[:, 1]]); np.add.at(acc, edges[:, 1], wq[edges[:, 0]])
                np.add.at(cnt, edges[:, 0], 1); np.add.at(cnt, edges[:, 1], 1)
                wq = acc / cnt
            M += wq[:, None, None] * (T - np.eye(4))
    Qh = np.c_[Q, np.ones(len(Q))]
    Qr = np.linalg.solve(M, Qh[:, :, None])[:, :3, 0]
    txt = " | ".join("%s: %+.0f up %+.0f fwd %+.0f elbow" % (sd, *np.degrees(x)) for sd, x in found.items())
    return Qr, txt


def slim(Q, edges, arms):
    """narrower below the chest (see SLIM): each height is scaled towards the middle of the body at that height"""
    V = arms.V
    armw = sum(a["wU"] for a in arms.side.values())
    B = np.array(body.matrix_world.inverted() @ rig.matrix_world)
    zt = (B @ np.r_[list(rig.data.bones["chest"].head_local), 1])[2]      # chest: nothing changes above
    zf = (B @ np.r_[list(rig.data.bones["pelvis"].head_local), 1])[2]     # pelvis: full SLIM below
    core = V[armw < 0.3]
    kb = np.clip(((core[:, 2] - core[:, 2].min()) / 0.02).astype(int), 0, None)
    nb = kb.max() + 1
    cnt = np.bincount(kb, minlength=nb).astype(float)
    cx = np.bincount(kb, core[:, 0], nb); cy = np.bincount(kb, core[:, 1], nb)
    ok = cnt > 0; ib = np.arange(nb)
    cx = np.interp(ib, ib[ok], cx[ok] / cnt[ok]); cy = np.interp(ib, ib[ok], cy[ok] / cnt[ok])
    for _ in range(3):                                                 # smooth the middle line over height
        cx = np.convolve(np.pad(cx, 2, mode="edge"), np.ones(5) / 5, "valid")
        cy = np.convolve(np.pad(cy, 2, mode="edge"), np.ones(5) / 5, "valid")
    k = np.clip(((Q[:, 2] - core[:, 2].min()) / 0.02).astype(int), 0, nb - 1)
    c = np.c_[cx[k], cy[k]]
    kd = KDTree(len(V))
    for i, p in enumerate(V):
        kd.insert(p, i)
    kd.balance()
    aw = armw[np.array([kd.find(p)[1] for p in Q])]
    for _ in range(8):                                                 # smooth over the item
        acc = aw.copy(); n = np.ones(len(Q))
        np.add.at(acc, edges[:, 0], aw[edges[:, 1]]); np.add.at(acc, edges[:, 1], aw[edges[:, 0]])
        np.add.at(n, edges[:, 0], 1); np.add.at(n, edges[:, 1], 1)
        aw = acc / n
    t = np.clip((zt - Q[:, 2]) / max(zt - zf, 1e-6), 0, 1); t = t * t * (3 - 2 * t)
    s = 1 - (1 - SLIM) * t * np.clip(1 - 2 * aw, 0, 1)
    out = Q.copy(); out[:, :2] = c + (Q[:, :2] - c) * s[:, None]
    return out


def fit(ob, bvh):
    me = ob.data
    M = np.array(body.matrix_world.inverted() @ ob.matrix_world)       # item -> body space
    Mi = np.linalg.inv(M)
    base = me.shape_keys.key_blocks[0] if me.shape_keys else None
    co = np.empty(len(me.vertices) * 3, np.float32)
    (base.data if base else me.vertices).foreach_get("co", co)
    local = co.reshape(-1, 3).astype(np.float64)
    P0 = local @ M[:3, :3].T + M[:3, 3]
    # vertices at the same place (split at UV seams / sharp edges) move as one, so the item does not tear open
    key = np.round(P0 / 1e-5).astype(np.int64)
    _, first, node = np.unique(key, axis=0, return_index=True, return_inverse=True)
    node = node.ravel(); Q0 = P0[first]
    Q = Q0.copy()
    S0 = skin(bvh, Q0, MIN_GAP + 0.3)[1][node]
    turn = ""
    if MATCH_ARMS or SLIM < 1 or LIMIT > 0:
        me.calc_loop_triangles()
        tri = node[np.array([t.vertices[:] for t in me.loop_triangles])]
        edges = np.unique(np.sort(np.r_[tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]], 1), axis=0)
        edges = edges[edges[:, 0] != edges[:, 1]]
    if MATCH_ARMS:
        gbvh = BVHTree.FromPolygons([Vector(p) for p in Q0], tri.tolist())
        Q, turn = match_arms(Q0, edges, gbvh)
        turn = " | sleeves turned: " + turn
    if SLIM < 1:
        Q = slim(Q, edges, Arms())
        turn += " | slimmed to %.2f" % SLIM
    if LIMIT > 0:                                                    # bring what stands out too far closer to the skin (smoothly), never nearer than LIMIT
        N, S = skin(bvh, Q, 0.6)
        over = np.where(S < 0.6, np.maximum(0, S - LIMIT), 0.0)
        if (over > 1e-4).any():
            V = -(1 - LIMIT_K) * over[:, None] * N
            for _ in range(6):                                       # the nearest skin point jumps from one place to another: smooth the displacement over the mesh
                acc = V.copy(); cnt = np.ones(len(Q))
                np.add.at(acc, edges[:, 0], V[edges[:, 1]]); np.add.at(acc, edges[:, 1], V[edges[:, 0]])
                np.add.at(cnt, edges[:, 0], 1); np.add.at(cnt, edges[:, 1], 1)
                V = 0.5 * V + 0.5 * acc / cnt[:, None]
            Q = Q + V
            turn += " | limited to %.0f cm: %d verts pulled in (max %.1f cm)" % (100 * LIMIT, (np.linalg.norm(V, axis=1) > 1e-4).sum(), 100 * np.linalg.norm(V, axis=1).max())
    rounds = 0
    Sn = skin(bvh, Q)[1]
    close = np.nonzero(Sn < MIN_GAP + 0.05)[0]                        # only these can end up too close
    for rounds in range(1, ITERATIONS + 1):                          # push out
        N = np.zeros_like(Q); S = np.full(len(Q), np.inf)
        N[close], S[close] = skin(bvh, Q[close])
        need = np.maximum(0, MIN_GAP - S)
        if not (need > 2e-4).any():
            rounds -= 1
            break
        Q = Q + push_field(Q, np.where(need[:, None] > 2e-4, need[:, None] * N, 0), strict=rounds > ITERATIONS // 2)
    if MAX_GAP > 0:                                                  # pull in (thickness kept)
        N, S = skin(bvh, Q)
        pull = np.maximum(0, S - MAX_GAP); out = np.zeros(len(Q))
        kd = KDTree(len(Q))
        for i, p in enumerate(Q):
            kd.insert(p, i)
        kd.balance()
        for j in range(len(Q)):
            out[j] = min(pull[i] for co, i, d in kd.find_range(Q[j], RADIUS))
        Q = Q - out[:, None] * N
    S1 = skin(bvh, Q, MIN_GAP + 0.3)[1][node]
    D = (Q - Q0)[node]
    delta = D @ Mi[:3, :3].T                                         # back to item space
    if me.shape_keys:
        for k in me.shape_keys.key_blocks:
            c = np.empty(len(me.vertices) * 3, np.float32); k.data.foreach_get("co", c)
            k.data.foreach_set("co", (c.reshape(-1, 3) + delta).ravel().astype(np.float32))
    me.vertices.foreach_set("co", (local + delta).ravel().astype(np.float32))
    me.update()
    mv = np.linalg.norm(D, axis=1)
    print("uo_fit_item: %s | inside body %d -> %d verts | closest %.1f -> %.1f mm | moved %d verts, max %.1f mm | %d rounds"
          % (ob.name, (S0 < 0).sum(), (S1 < 0).sum(), S0.min() * 1000, S1.min() * 1000,
             (mv > 1e-4).sum(), mv.max() * 1000, rounds) + turn)


pose = rig.data.pose_position
rig.data.pose_position = "REST"
bpy.context.view_layer.update()
try:
    bvh = body_bvh()
    for ob in [o for o in bpy.context.selected_objects if o.type == "MESH" and o != body]:
        fit(ob, bvh)
finally:
    rig.data.pose_position = pose
