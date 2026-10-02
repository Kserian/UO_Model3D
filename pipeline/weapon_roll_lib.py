"""Roll of a weapon about its own axis, measured from the original sprites (anim.mul ... anim5.mul).

A weapon is a shaft (the class line of weapon_motion.json, moved per pose by the class motion) with a head / blade that is NOT round: the flat of
a blade, an axe head, a halberd head. The shaft alone cannot show how the weapon is turned about itself; the projected AREA of the sprite can: a flat
blade whose normal points at the camera shows its full face, one turned edge-on shows only a sliver. This library loads the sprites + the exported poses
(weapon_pose_export.py) and gives, for any roll angle, the geometry of the weapon in every one of the 1050 views.
numpy / scipy only.
"""
import os, sys, json
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "vdtool"))
import vdtool                                                       # noqa: E402

CLASS_BONE = {"polearm.L": "hand.L", "axe2h.L": "hand.L", "bow.L": "hand.L", "weapon1h.R": "hand.R"}


def rodrigues(r):
    r = np.asarray(r, float); a = np.linalg.norm(r)
    if a < 1e-12:
        return np.eye(3)
    k = r / a; K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + np.sin(a) * K + (1 - np.cos(a)) * K @ K


def axis_rot(u, phi):
    return rodrigues(np.asarray(u, float) / np.linalg.norm(u) * phi)


class Pose:
    """exported poses of the model: world matrices of the hand bones, camera, view directions"""

    def __init__(self, npz):
        d = np.load(npz)
        self.bones = [str(b) for b in d["bones"]]; self.key = d["key"]; self.BW = d["BW"]; self.PX = d["PX"]
        self.W, self.H = (int(x) for x in d["canvas"]); self.anchor = tuple(int(x) for x in d["anchor"])
        v = self.PX[:, 2, :3]; self.view = v / np.linalg.norm(v, axis=1, keepdims=True)      # world direction of looking (depth grows along it)
        self.index = {(int(a), int(dd), int(i)): n for n, (a, dd, i) in enumerate(self.key)}

    def bone_world(self, bone):
        M = self.BW[:, self.bones.index(bone)].copy()
        M[:, :3, :3] /= np.linalg.norm(M[:, :3, :3], axis=1, keepdims=True)                  # without the pose scale (child bones inherit none)
        return M


def load_masks(pose, vd_path, action_filter=None):
    """sprite masks (and rgb) on the canvas of the poses for all (action, dir, frame) present; returns arrays aligned to pose.key (mask all-False if absent)"""
    _, blocks = vdtool.read_vd(vd_path)
    blk = {(b["action"], b["dir"]): b for b in blocks}
    N = len(pose.key); masks = np.zeros((N, pose.H, pose.W), bool); rgb = np.zeros((N, pose.H, pose.W, 3), np.uint8)
    ax, ay = pose.anchor
    for n, (a, d, i) in enumerate(pose.key):
        b = blk.get((int(a), int(d)))
        if b is None or i >= len(b["frames"]):
            continue
        f = b["frames"][i]; r = vdtool.frame_rgba(f, b["palette"]); h, w = r.shape[:2]
        x0, y0 = ax - f["cx"], ay - f["cy"] - f["h"]
        ys, xs = slice(max(y0, 0), min(y0 + h, pose.H)), slice(max(x0, 0), min(x0 + w, pose.W))
        if ys.stop > ys.start and xs.stop > xs.start:
            sub = r[ys.start - y0:ys.stop - y0, xs.start - x0:xs.stop - x0]
            masks[n, ys, xs] = sub[..., 3] > 0; rgb[n, ys, xs] = sub[..., :3]
    return masks, rgb


class ClassGeom:
    """class line + per-pose motion of weapon_motion.json: for every view the weapon frame (rotation, origin) in world"""

    def __init__(self, pose, wm, bone):
        self.bone = bone; self.pose = pose
        self.piv = np.array(wm["pivot"], float); self.u = np.array(wm["dir"], float); self.u /= np.linalg.norm(self.u)
        self.M = pose.bone_world(CLASS_BONE[bone])
        # reference frame perpendicular to the axis: e1 = hand-local X without its axis part (fixed in the bone frame, so roll 0 is a bone-frame notion)
        x = np.array([1.0, 0, 0]); e1 = x - (x @ self.u) * self.u
        if np.linalg.norm(e1) < 0.3:
            x = np.array([0, 1.0, 0]); e1 = x - (x @ self.u) * self.u
        self.e1 = e1 / np.linalg.norm(e1); self.e2 = np.cross(self.u, self.e1)
        N = len(pose.key)
        self.R = np.zeros((N, 3, 3)); self.t = np.zeros((N, 3))
        for n, (a, d, i) in enumerate(pose.key):
            p = wm["poses"].get("%d,%d" % (a, i), [0] * 6)
            self.R[n] = rodrigues(p[:3]); self.t[n] = p[3:]
        # axis in world
        Rb = self.M[:, :3, :3] @ self.R                                                      # bone frame -> world, with the pose turn
        self.Rw = Rb                                                                         # weapon frame (before extra roll) -> world: columns Rb@e1_0 ..
        self.d_w = Rb @ self.u                                                               # axis direction in world (N,3)
        self.o_w = np.einsum("nij,nj->ni", self.M[:, :3, :3], self.piv + self.t) + self.M[:, :3, 3]   # point of the axis (the pivot) in world

    def uv(self, phi):
        """world directions of the in-plane (u) and normal (v) vectors of a flat head rolled by phi (N,) or scalar, about the axis"""
        phi = np.broadcast_to(np.asarray(phi, float), (len(self.d_w),))
        c, s = np.cos(phi)[:, None], np.sin(phi)[:, None]
        e1 = self.Rw @ self.e1; e2 = self.Rw @ self.e2
        return c * e1 + s * e2, -s * e1 + c * e2

    def project_vec(self, vec):
        """image 2-vector of world directions vec (N,3)"""
        return np.einsum("nij,nj->ni", self.pose.PX[:, :2, :3], vec)


# ---------------------------------------------------------------------------------------------------------------------------------------------
# planar head model: the head / blade is a flat plate T(s, u) (s along the shaft, u across, both in m) turned about the shaft by phi
# ---------------------------------------------------------------------------------------------------------------------------------------------
from scipy import ndimage                                                                   # noqa: E402

WIN = 128                                                                                   # half... full size of the crop window per view (px)


class PlateFit:
    """all views of one weapon (sprite masks cropped to windows) + the class geometry; learns the plate T for given rolls and scores rolls"""

    def __init__(self, pose, G, masks, ext, step=0.015, umax=0.36, tol=1):
        self.pose, self.G, self.tol = pose, G, tol
        area = masks.reshape(len(masks), -1).sum(1)
        self.ok = np.nonzero(area > 5)[0]; ok = self.ok; n = len(ok)
        Lm = pose.PX[:, :2, :3]; c0 = pose.PX[:, :2, 3]
        self.c = np.einsum("nij,nj->ni", Lm, G.o_w) + c0                                      # pixel of the pivot point on the axis (N,2)
        self.a = np.einsum("nij,nj->ni", Lm, G.d_w)                                           # px per m along the axis
        self.B1 = np.einsum("nij,nj->ni", Lm, G.Rw @ G.e1); self.B2 = np.einsum("nij,nj->ni", Lm, G.Rw @ G.e2)
        # window per view: centred on the sprite
        self.org = np.zeros((len(masks), 2), int); self.crop = np.zeros((len(masks), WIN, WIN), bool); self.dil = np.zeros((len(masks), WIN, WIN), bool)
        for k in ok:
            ys, xs = np.nonzero(masks[k]); cy, cx = int(ys.mean()), int(xs.mean())
            y0, x0 = cy - WIN // 2, cx - WIN // 2; self.org[k] = (x0, y0)
            m = np.zeros((WIN, WIN), bool)
            yy0, xx0 = max(y0, 0), max(x0, 0); yy1, xx1 = min(y0 + WIN, masks.shape[1]), min(x0 + WIN, masks.shape[2])
            m[yy0 - y0:yy1 - y0, xx0 - x0:xx1 - x0] = masks[k, yy0:yy1, xx0:xx1]
            self.crop[k] = m; self.dil[k] = ndimage.binary_dilation(m, np.ones((2 * tol + 1, 2 * tol + 1), bool))
        self.step = step
        s_lo, s_hi = ext
        self.sg = np.arange(s_lo - 0.08, s_hi + 0.08, step); self.ug = np.arange(-umax, umax + 1e-9, step)
        S, U = np.meshgrid(self.sg, self.ug, indexing="ij"); self.cells = np.stack([S.ravel(), U.ravel()], 1)       # (nc, 2)

    def points(self, k_idx, cells, phi):
        """pixel coordinates (n_views, n_cells, 2) in the crop windows of views k_idx for cells (nc,2) at roll phi (scalar or (n_views,))"""
        phi = np.broadcast_to(np.asarray(phi, float), (len(k_idx),))
        c, s = np.cos(phi)[:, None], np.sin(phi)[:, None]
        b = c * self.B1[k_idx] + s * self.B2[k_idx]                                            # (n,2) px per m across, in the plate plane
        x = self.c[k_idx][:, None, :] + cells[None, :, 0:1] * self.a[k_idx][:, None, :] + cells[None, :, 1:2] * b[:, None, :]
        return x - self.org[k_idx][:, None, :]

    def learn(self, phis, thr=0.75, k_idx=None, dilate=True):
        """plate = cells whose pixel lies in the (3x3 dilated) sprite in at least `thr` of the views; phis: roll per view (N,) (any array indexed by view)"""
        k_idx = self.ok if k_idx is None else k_idx
        hit = np.zeros(len(self.cells))
        for k in k_idx:
            p = self.points(np.array([k]), self.cells, phis[k])[0]
            xi = np.floor(p[:, 0]).astype(int); yi = np.floor(p[:, 1]).astype(int)
            inside = (xi >= 0) & (xi < WIN) & (yi >= 0) & (yi < WIN)
            h = np.zeros(len(self.cells), bool); h[inside] = (self.dil if dilate else self.crop)[k][yi[inside], xi[inside]]
            hit += h
        score = hit / len(k_idx)
        return self.cells[score >= thr], score

    def cost(self, k_idx, T, phi_cands, tol=True):
        """pixel count of the mismatch between the splatted plate T and the sprite, per view and candidate roll: (n_views, n_cand).
        tol: a pixel only counts when it is more than 1 px (3x3) away from the other mask (the class line is only good to ~1 px)"""
        out = np.zeros((len(k_idx), len(phi_cands)))
        for j, k in enumerate(k_idx):
            p = self.points(np.full(len(phi_cands), k), T, phi_cands)                           # (nphi, nT, 2)
            xi = np.floor(p[..., 0]).astype(int); yi = np.floor(p[..., 1]).astype(int)
            inside = (xi >= 0) & (xi < WIN) & (yi >= 0) & (yi < WIN)
            img = np.zeros((len(phi_cands), WIN * WIN), bool)
            ph = np.broadcast_to(np.arange(len(phi_cands))[:, None], xi.shape)
            img[ph[inside], (yi * WIN + xi)[inside]] = True
            if not tol:
                out[j] = (img ^ self.crop[k].ravel()[None]).sum(1)
                continue
            im = img.reshape(-1, WIN, WIN); e = im
            for _ in range(self.tol):                                                          # dilate the splat by tol px (square)
                d = e.copy(); d[:, 1:] |= e[:, :-1]; d[:, :-1] |= e[:, 1:]
                e = d.copy(); e[:, :, 1:] |= d[:, :, :-1]; e[:, :, :-1] |= d[:, :, 1:]
            out[j] = (im & ~self.dil[k][None]).sum((1, 2)) + (self.crop[k][None] & ~e).sum((1, 2))
        return out


# ---------------------------------------------------------------------------------------------------------------------------------------------
def area_init(pose, G, masks):
    """roll of every pose from the projected sprite area alone: area ~ c0 + Ap |n.view| + Ae |u.view| (plate normal / in-plane vector), mod 180 deg.
    Alternates between per-pose roll (grid) and the 3 coefficients; returns {(action, frame): phi} (rad, [0, pi)) and the rms error (px)"""
    from scipy.optimize import nnls
    area = masks.reshape(len(masks), -1).sum(1).astype(float); ok = area > 5; v = pose.view
    grid = np.deg2rad(np.arange(0, 180, 3.0)); F = []
    for ph in grid:
        eu, ev = G.uv(ph); F.append(np.stack([np.abs((ev * v).sum(1)), np.abs((eu * v).sum(1))], 1))
    F = np.array(F)
    pk = {}
    for n, (a, d, i) in enumerate(pose.key):
        if ok[n]:
            pk.setdefault((int(a), int(i)), []).append(n)
    best = None
    for seed in range(8):
        rng = np.random.default_rng(seed); coef = np.array([area[ok].min(), rng.uniform(20, 200), rng.uniform(20, 200)]); idx = {}
        for it in range(6):
            for k, ns in pk.items():
                err = ((coef[0] + F[:, ns, 0] * coef[1] + F[:, ns, 1] * coef[2] - area[ns]) ** 2).sum(1); idx[k] = err.argmin()
            rows = np.array([[1, F[idx[k], n, 0], F[idx[k], n, 1]] for k, ns in pk.items() for n in ns]); ys = np.array([area[n] for ns in pk.values() for n in ns])
            coef, _ = nnls(rows, ys)
        rms = np.sqrt(((rows @ coef - ys) ** 2).mean())
        if best is None or rms < best[0]:
            best = (rms, dict(idx), coef)
    rms, idx, coef = best
    return {k: float(grid[j]) for k, j in idx.items()}, float(rms), coef


def head_offset_sign(P, phi_view, s_head):
    """sign cue for the 180 deg ambiguity: observed offset of the sprite's head part from the shaft line (px, along the image normal of the axis)
    times the predicted normal component of the in-plane vector; returns q (N,): > 0 means 'phi as given', < 0 means 'phi + 180'"""
    q = np.zeros(len(P.pose.key))
    for k in P.ok:
        ys, xs = np.nonzero(P.crop[k]); X = np.stack([xs + 0.5, ys + 0.5], 1)
        a = P.a[k]; na = np.linalg.norm(a)
        if na < 1e-6:
            continue
        t = a / na; nrm = np.array([-t[1], t[0]])
        rel = X + P.org[k] - P.c[k]; sig = rel @ t; nu = rel @ nrm
        head = sig > s_head * na
        if head.sum() < 3:
            continue
        b = np.cos(phi_view[k]) * P.B1[k] + np.sin(phi_view[k]) * P.B2[k]
        q[k] = nu[head].mean() * (b @ nrm)
    return q


def viterbi(U, lam, cands):
    """best path through per-frame costs U (nf, nc) with a quadratic cost lam * (angle change / 30 deg)^2 between consecutive frames"""
    nf, nc = U.shape
    d = np.angle(np.exp(1j * (cands[:, None] - cands[None, :])))
    Tr = lam * (d / np.deg2rad(30.0)) ** 2
    cost = U[0].copy(); back = np.zeros((nf, nc), int)
    for f in range(1, nf):
        tot = cost[None, :] + Tr; back[f] = tot.argmin(1); cost = tot.min(1) + U[f]
    path = np.zeros(nf, int); path[-1] = cost.argmin()
    for f in range(nf - 1, 0, -1):
        path[f - 1] = back[f][path[f]]
    return path


# ---------------------------------------------------------------------------------------------------------------------------------------------
CANDS = np.deg2rad(np.arange(0, 360, 6.0))                                                  # roll candidates (rad)


def pose_groups(pose, ok):
    """{(action, frame): [view indices of the 5 directions that have a sprite]}"""
    okset = set(int(x) for x in ok); pk = {}
    for n, (a, d, i) in enumerate(pose.key):
        if n in okset:
            pk.setdefault((int(a), int(i)), []).append(n)
    return pk


def dp_rolls(P, pk, T_list, deltas, smooth=0.25, cands=CANDS, weights=None):
    """roll per pose by dynamic programming along every action: sum over weapons w of the mismatch of plate T_w at roll (candidate + delta_w),
    plus a quadratic penalty on the roll change between consecutive frames. P, T_list, deltas: one entry per weapon; pk per weapon (same keys needed
    only for the union). Returns {(a, i): roll}, total cost, and the unary cost tensor {(a,i): (nc,)}"""
    keys = sorted({k for p in pk for k in p}); out = {}; tot = 0.0; unary = {}
    weights = weights or [1.0] * len(P)
    for a in sorted({k[0] for k in keys}):
        fr = sorted(i for (aa, i) in keys if aa == a)
        U = np.zeros((len(fr), len(cands)))
        for f, i in enumerate(fr):
            for w in range(len(P)):
                ns = pk[w].get((a, i))
                if ns:
                    U[f] += weights[w] * P[w].cost(np.array(ns), T_list[w], cands + deltas[w]).sum(0)
            unary[(a, i)] = U[f]
        lam = smooth * np.median(U.max(1) - U.min(1))
        path = viterbi(U, lam, cands)
        for f, i in enumerate(fr):
            out[(a, i)] = float(cands[path[f]]); tot += U[f, path[f]]
    return out, tot, unary


def fit_single(pose, G, masks, ext, iters=4, smooth=0.25, thr=0.85, log=None, sign=True, tol=1):
    """roll per pose of ONE weapon on the class geometry G: area init (mod 180) -> sign from the head offset -> alternate plate learning and dynamic
    programming. Returns dict(P, T, pk, phi_pose, phi_view, cost_hist, area_rms)"""
    P = PlateFit(pose, G, masks, ext, tol=tol); pk = pose_groups(pose, P.ok)
    phiA, rms, coef = area_init(pose, G, masks)
    phi = np.zeros(len(pose.key))
    for k, ns in pk.items():
        phi[ns] = phiA[k]
    if sign:
        q = head_offset_sign(P, phi, ext[0] + 0.6 * (ext[1] - ext[0]))
        for k, ns in pk.items():
            if q[ns].sum() < 0:
                phi[ns] += np.pi
    hist = []; T = None
    for it in range(iters):
        T, _ = P.learn(phi, thr=thr)
        if len(T) < 5:
            break
        pr, tot, _ = dp_rolls([P], [pk], [T], [0.0], smooth=smooth)
        for k, v in pr.items():
            phi[pk[k]] = v
        hist.append(tot / len(P.ok))
        if log: log("  it %d: plate cells %d, mismatch px/view %.1f" % (it, len(T), hist[-1]))
    return dict(P=P, T=T, pk=pk, phi_view=phi, phi_pose={k: float(phi[ns[0]]) for k, ns in pk.items()}, hist=hist, area_rms=rms)


def mismatch(P, T, phi_view, per_view=False):
    """mean tolerant mismatch (px per view) of plate T at the given roll per view (N,)"""
    out = np.zeros(len(P.ok))
    for j, k in enumerate(P.ok):
        out[j] = P.cost(np.array([k]), T, np.array([phi_view[k]]))[0, 0]
    return out if per_view else float(out.mean())


def const_mismatch(P, T, cands=CANDS):
    """best single roll for all views (a weapon rolled by one fixed angle in the class frame): (mismatch px/view, angle)"""
    tot = np.zeros(len(cands))
    for k in P.ok:
        tot += P.cost(np.array([k]), T, cands)[0]
    j = tot.argmin()
    return float(tot[j] / len(P.ok)), float(cands[j])


def circ_mean(z):
    return float(np.angle(np.sum(z)))


def merge_class(fits, weights=None, iters=6, ref=None):
    """one roll per pose for the class + one offset per weapon from independent per-weapon rolls (each only known up to its own constant offset, and
    mod 180 where the head is symmetric). Returns phi_pose {(a,i): rad}, delta [rad per weapon] (weapon roll = class roll + delta), sym [bool per weapon]"""
    nw = len(fits); weights = weights or [1.0] * nw
    keys = sorted(set().union(*[f["phi_pose"].keys() for f in fits]))
    ref = int(np.argmax(weights)) if ref is None else ref
    phi = dict(fits[ref]["phi_pose"]); delta = np.zeros(nw); sym = [False] * nw
    for it in range(iters):
        for w, f in enumerate(fits):
            if w == ref:
                continue
            common = [k for k in f["phi_pose"] if k in phi]
            d = np.array([f["phi_pose"][k] - phi[k] for k in common])
            r1, r2 = abs(np.exp(1j * d).mean()), abs(np.exp(2j * d).mean())
            sym[w] = bool(r1 < 0.8 * r2)                                              # symmetric head: only the 180 deg estimate means anything
            delta[w] = circ_mean(np.exp(2j * d)) / 2 if sym[w] else circ_mean(np.exp(1j * d))
        new = {}
        for k in keys:
            z = 0j
            for w, f in enumerate(fits):
                if k in f["phi_pose"]:
                    a = f["phi_pose"][k] - delta[w]
                    if sym[w] and k in phi and np.cos(a - phi[k]) < 0:
                        a += np.pi
                    z += weights[w] * np.exp(1j * a)
            new[k] = float(np.angle(z)) if abs(z) > 0 else phi.get(k, 0.0)
        phi = new
    return phi, delta, sym


def refine_class(pose, fits, phi, delta, iters=3, smooth=0.25, thr=0.85, log=None, weights=None):
    """all weapons of a class together: learn each plate at (class roll + offset), roll per pose by dynamic programming over the summed mismatch of all
    weapons, offsets by a scan; delta snaps to the 6 deg grid"""
    Ps = [f["P"] for f in fits]; pks = [f["pk"] for f in fits]; delta = np.array([round(d / np.deg2rad(6)) * np.deg2rad(6) for d in delta])
    for it in range(iters):
        Ts = []
        for w, f in enumerate(fits):
            pv = np.zeros(len(pose.key))
            for k, ns in pks[w].items():
                pv[ns] = phi[k] + delta[w]
            Ts.append(Ps[w].learn(pv, thr=thr)[0])
        phi, tot, unary = dp_rolls(Ps, pks, Ts, delta, smooth=smooth, weights=weights)
        for w, f in enumerate(fits):                                                   # offset scan: weapon w's mismatch at phi_p + delta' for delta' on the grid
            cost = np.zeros(len(CANDS))
            for k, ns in pks[w].items():
                cost += Ps[w].cost(np.array(ns), Ts[w], phi[k] + CANDS).sum(0)
            delta[w] = CANDS[cost.argmin()] if w != 0 else delta[w]
        if log: log("  class iteration %d: total mismatch %.1f px/view-weapon, offsets %s deg" % (it, tot / sum(len(P.ok) for P in Ps), np.round(np.rad2deg(delta)).astype(int)))
    return phi, delta, Ts
