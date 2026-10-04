"""Calibration of the cloth of loose garments against the ORIGINAL robes of the game, in numpy (no Cycles): a replica of a robe is posed by the poses of pose_capture.py,
solved by cloth_lib.py and rasterised on the canvas of the body frames; compared with the sprite frame by frame below the hips.

    python robe_calib.py POSES.npz [--sprite pipeline/body13/mul/anim_0469.vd] [--acts 4,0,2,9,16,21] [--set k=v,...] [--sweep name=v1,v2,...] [--img out.png]

Parameters (--set / --sweep): alpha_hip, alpha_hem (share of the thigh weight in the pose: 0 = the hanging part follows the pelvis only), gap, iters, k_stretch,
k_squeeze, free_ramp (m below the waist over which the pin is released), solve (0 = no cloth: the skeleton pose only), rx, ry (half width / depth of the hem).
Result: IoU of the lower part (rows below `hip`), the width of the hem against the sprite's (px, + = ours wider), per action.
"""
import argparse, itertools, json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "..", "vdtool"))
import vdtool                                                    # noqa: E402
import cloth_lib as cl                                           # noqa: E402

CW, CH, CANCH = 145, 133, (75, 92)
DEFAULT = dict(alpha_hip=0.0, alpha_hem=0.0, gap=0.012, iters=30, k_stretch=0.9, k_squeeze=0.15, omega=1.0, free_ramp=0.18, solve=0, hull=1, margin=0.05, kappa=0.8, tent=1, drop=0.15, lam_hem=0.0, lam_pow=1.0, foot=0.0, shin=1.0, thigh=1.0, rx0=0.215, rx1=0.30, ry=0.22, hip=0.95,
               z_top=1.02, z_hem=0.08, n_around=40, n_rings=26)


def tube(p):
    N, K = int(p["n_around"]), int(p["n_rings"])
    V, T = [], []
    for k in range(K + 1):
        z = p["z_top"] + (p["z_hem"] - p["z_top"]) * k / K
        t = (p["z_top"] - z) / (p["z_top"] - p["z_hem"])
        ax = p["rx0"] + (p["rx1"] - p["rx0"]) * t ** 0.8; ay = 0.17 + (p["ry"] - 0.17) * min(1, t * 3)
        for i in range(N):
            V.append((ax * np.cos(2 * np.pi * i / N), -0.02 + ay * np.sin(2 * np.pi * i / N), z))
    for k in range(K):
        for i in range(N):
            a, b, c, d = k * N + i, k * N + (i + 1) % N, (k + 1) * N + (i + 1) % N, (k + 1) * N + i
            T += [(a, b, c), (a, c, d)]
    V = np.array(V); T = np.array(T)
    E = np.unique(np.sort(np.r_[T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]], 1), axis=0)
    return V, T, E


def raster_mask(P2, tri):
    """pixel-centre coverage of triangles (P2: (n, 2) px) on the CH x CW canvas"""
    mask = np.zeros((CH, CW), bool)
    A, B, C = (P2[tri[:, k]] for k in range(3))
    mn = np.floor(np.minimum(np.minimum(A, B), C)).astype(int); mx = np.ceil(np.maximum(np.maximum(A, B), C)).astype(int)
    den = (B[:, 1] - C[:, 1]) * (A[:, 0] - C[:, 0]) + (C[:, 0] - B[:, 0]) * (A[:, 1] - C[:, 1])
    ok = np.abs(den) > 1e-12; size = np.clip(mx - mn, 0, 24)
    for dy in range(int(size[:, 1].max(initial=0)) + 1):
        for dx in range(int(size[:, 0].max(initial=0)) + 1):
            t = np.nonzero(ok & (dx <= size[:, 0]) & (dy <= size[:, 1]))[0]
            px, py = mn[t, 0] + dx, mn[t, 1] + dy; cx, cy = px + 0.5, py + 0.5
            l0 = ((B[t, 1] - C[t, 1]) * (cx - C[t, 0]) + (C[t, 0] - B[t, 0]) * (cy - C[t, 1])) / den[t]
            l1 = ((C[t, 1] - A[t, 1]) * (cx - C[t, 0]) + (A[t, 0] - C[t, 0]) * (cy - C[t, 1])) / den[t]
            kk = (l0 >= -1e-4) & (l1 >= -1e-4) & (1 - l0 - l1 >= -1e-4) & (px >= 0) & (py >= 0) & (px < CW) & (py < CH)
            mask[py[kk], px[kk]] = True
    return mask


def sprite_masks(path):
    _, blocks = vdtool.read_vd(path)
    out = {}
    for b in blocks:
        ms = []
        for f in b["frames"]:
            m = np.zeros((CH, CW), bool)
            a = vdtool.frame_rgba(f, b["palette"])[..., 3] > 0
            x0, y0 = CANCH[0] - f["cx"], CANCH[1] - f["cy"] - f["h"]
            h, w = a.shape
            ys, xs = slice(max(y0, 0), min(y0 + h, CH)), slice(max(x0, 0), min(x0 + w, CW))
            m[ys, xs] = a[ys.start - y0:ys.stop - y0, xs.start - x0:xs.stop - x0]
            ms.append(m)
        out[(b["action"], b["dir"])] = ms
    return out


class Calib:
    def __init__(self, poses_path, sprite_path):
        d = np.load(poses_path, allow_pickle=True)
        self.d = d; self.key = d["key"]; self.skin = d["skin"]; self.dirm = d["dirm"]; self.bones = [str(b) for b in d["bones"]]
        self.P, self.V = d["P"], d["V"]
        self.caps = cl.Capsules(self.bones, d["rest_head"], d["rest_tail"], d["body_rest"], d["body_dom"])
        self.spr = sprite_masks(sprite_path)
        self.index = {(int(a), int(dr), int(i)): n for n, (a, dr, i) in enumerate(self.key)}

    def project(self, X):
        hv = np.c_[X, np.ones(len(X))] @ self.V.T
        h = hv @ self.P.T; ndc = h[:, :2] / h[:, 3:4]
        return np.stack([(ndc[:, 0] + 1) * 0.5 * CW, (1 - ndc[:, 1]) * 0.5 * CH], 1)

    def evaluate(self, p, acts=(4, 0, 2, 9, 16, 21), keep_masks=False):
        V0, T, E = tube(p)
        n = len(V0)
        L0 = np.linalg.norm(V0[E[:, 1]] - V0[E[:, 0]], axis=1)
        z = V0[:, 2]; t = np.clip((p["z_top"] - z) / (p["z_top"] - p["z_hem"]), 0, 1)
        free = np.clip((p["z_top"] - z) / p["free_ramp"], 0, 1)
        alpha = p["alpha_hip"] + (p["alpha_hem"] - p["alpha_hip"]) * t
        side = np.clip(V0[:, 0] / 0.06, -1, 1) * 0.5 + 0.5            # 0 = left thigh, 1 = right
        ip, itl, itr = self.bones.index("pelvis"), self.bones.index("thigh.L"), self.bones.index("thigh.R")
        Vh = np.c_[V0, np.ones(n)]
        row_hip = CANCH[1] - (p["hip"] - 0.07) * 36 * np.cos(np.radians(28.4557))
        res, masks = [], {}
        for a in acts:
            nfr = int(self.key[(self.key[:, 0] == a) & (self.key[:, 1] == 0)][:, 2].max()) + 1
            for i in range(nfr):
                S = self.skin[self.index[(a, 0, i)]]
                X0 = (1 - alpha)[:, None] * (Vh @ S[ip].T)[:, :3] + (alpha * (1 - side))[:, None] * (Vh @ S[itl].T)[:, :3] + (alpha * side)[:, None] * (Vh @ S[itr].T)[:, :3]
                if p["lam_hem"] > 0:                                  # gravity: the more the cloth hangs, the less it follows the tilt of the pelvis
                    W0 = np.array([0.0, -0.02, p["z_top"]]); Wp = (S[ip] @ np.append(W0, 1))[:3]
                    for fr_ in np.unique(np.round(p["lam_hem"] * t ** p["lam_pow"], 3)):
                        mm = np.round(p["lam_hem"] * t ** p["lam_pow"], 3) == fr_
                        Rh = cl.hang_matrix(S[ip], fr_)
                        X0[mm] = (1 - alpha[mm])[:, None] * (Wp + (V0[mm] - W0) @ Rh.T) + alpha[mm][:, None] * X0[mm]
                if p["hull"]:
                    heads, tails = self.caps.posed(S)
                    sc_ = np.array([p["foot"] if "foot" in n else p["shin"] if "shin" in n else p["thigh"] for n in [self.bones[j] for j in self.caps.idx]])
                    k = sc_ > 0
                    X0 = X0 + cl.hull_push(V0, S[ip], heads[k], tails[k], self.caps.radius[k] * sc_[k], margin=p["margin"], kappa=p["kappa"], z_top=p["z_top"], z_hem=p["z_hem"], use_tent=bool(p["tent"]), drop=p["drop"])
                if p["solve"]:
                    heads, tails = self.caps.posed(S)
                    X = cl.solve(X0, E, L0, free, heads, tails, self.caps.radius, gap=p["gap"], iters=int(p["iters"]), k_stretch=p["k_stretch"], k_squeeze=p["k_squeeze"], omega=p["omega"])
                else:
                    X = X0
                for dr in range(5):
                    D = self.dirm[self.index[(a, dr, i)]]
                    Xw = X @ D[:3, :3].T + D[:3, 3]
                    m = raster_mask(self.project(Xw), T)
                    g = self.spr.get((a, dr))
                    if g is None or i >= len(g) or not g[i].any():
                        continue
                    g = g[i]; r0, g0 = m[int(row_hip):], g[int(row_hip):]
                    ys = np.nonzero(g.any(1))[0]; rows = range(ys.max() - 7, ys.max() + 1)
                    rows = [y for y in rows if g[y].any()] or [ys.max()]
                    wr = np.mean([np.ptp(np.nonzero(m[y])[0]) + 1 if m[y].any() else 0 for y in rows]); wg = np.mean([np.ptp(np.nonzero(g[y])[0]) + 1 for y in rows])
                    res.append(dict(a=a, d=dr, i=i, iou=(r0 & g0).sum() / max((r0 | g0).sum(), 1), dw=wr - wg))
                    if keep_masks:
                        masks[(a, dr, i)] = (m, g)
        return res, masks


def fit_rest(cal, p, acts=(4,), keys=("rx0", "rx1", "ry", "z_hem")):
    """radii and hem height of the replica tube from the stand frames (no cloth): the rest shape of the garment, so that what is measured afterwards is the dynamics"""
    from scipy import optimize
    q = dict(p); q["hull"] = 0; q["solve"] = 0
    x0 = np.array([q[k] for k in keys])

    def cost(x):
        for k, v in zip(keys, x):
            q[k] = float(v)
        res, _ = cal.evaluate(q, acts)
        return 1 - np.mean([r["iou"] for r in res]) if res else 1.0

    r = optimize.minimize(cost, x0, method="Nelder-Mead", options=dict(xatol=0.003, fatol=1e-4, maxiter=120))
    out = dict(p)
    out.update({k: float(v) for k, v in zip(keys, r.x)})
    return out


def summarize(res):
    s = dict(frames=len(res), iou=float(np.mean([r["iou"] for r in res])), dw=float(np.mean([r["dw"] for r in res])), dw_abs=float(np.mean([abs(r["dw"]) for r in res])), by={})
    for a in sorted({r["a"] for r in res}):
        q = [r for r in res if r["a"] == a]
        s["by"][a] = (float(np.mean([r["iou"] for r in q])), float(np.mean([r["dw"] for r in q])))
    return s


def fmt(s):
    return "IoU %.3f | hem width %+.2f px (abs %.2f) | %s" % (s["iou"], s["dw"], s["dw_abs"], " ".join("%d:%.2f/%+.1f" % (a, v[0], v[1]) for a, v in s["by"].items()))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("poses"); ap.add_argument("--sprite", default=os.path.join(HERE, "body13", "mul", "anim_0469.vd")); ap.add_argument("--acts", default="4,0,2,9,16,21")
    ap.add_argument("--set", default=""); ap.add_argument("--sweep", action="append", default=[]); ap.add_argument("--img"); ap.add_argument("--fit-rest", action="store_true", help="fit the radii / hem height of the replica to the stand frames first")
    a = ap.parse_args()
    cal = Calib(a.poses, a.sprite)
    p = dict(DEFAULT)
    for kv in filter(None, a.set.split(",")):
        k, v = kv.split("="); p[k] = float(v)
    if a.fit_rest:
        p = fit_rest(cal, p)
        print("rest shape fitted on the stand frames: rx0 %.3f rx1 %.3f ry %.3f z_hem %.3f" % (p["rx0"], p["rx1"], p["ry"], p["z_hem"]))
    acts = tuple(int(x) for x in a.acts.split(","))
    sweeps = [(sw.split("=")[0], [float(x) for x in sw.split("=")[1].split(",")]) for sw in a.sweep]
    for combo in itertools.product(*[v for _, v in sweeps]) if sweeps else [()]:
        q = dict(p); q.update({k: v for (k, _), v in zip(sweeps, combo)})
        res, _ = cal.evaluate(q, acts)
        print(" ".join("%s=%g" % (k, v) for (k, _), v in zip(sweeps, combo)) or "default", "|", fmt(summarize(res)), flush=True)
