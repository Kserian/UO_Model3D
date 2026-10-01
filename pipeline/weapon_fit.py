"""Offline calibration of how UO holds a weapon, from the original weapon animation (anim.mul) and the exported poses of the model.

A weapon is a straight shaft (a stick: two end points) in the local frame of a hand bone. Metric = symmetric chamfer distance in pixels
between the projected stick and the sprite (mean of: stick samples -> nearest sprite pixel, sprite pixels -> nearest point of the stick),
like the report (8.3). numpy / scipy only.

    python weapon_fit.py rigid  WP.npz VDDIR ANIM BONE [--len 1.0]            one rigid stick in the bone for all frames (report 8.3)
    python weapon_fit.py perpose WP.npz VDDIR ANIM BONE [--len 1.0] [--out F.json]   + a correction (turn, shift in the bone frame) per pose
Library: Views (masks, distance transforms, projection), rigid_fit, chamfer.
"""
import os, sys, json
import numpy as np
from scipy import ndimage, optimize

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "vdtool"))
import vdtool                                                       # noqa: E402


class Views:
    """all (pose, direction) views of one weapon animation: sprite masks on the canvas of WP.npz, distance transforms, projection rows"""

    def __init__(self, wp_npz, vd_path, bones=None, max_px=60):
        d = np.load(wp_npz)
        self.bones = [str(b) for b in d["bones"]]; self.W, self.H = (int(x) for x in d["canvas"]); ax, ay = (int(x) for x in d["anchor"])
        _, blocks = vdtool.read_vd(vd_path)
        blk = {(b["action"], b["dir"]): b for b in blocks}
        keep, masks = [], []
        for n, (a, di, i) in enumerate(d["key"]):
            b = blk.get((int(a), int(di)))
            if b is None or i >= len(b["frames"]):
                continue
            f = b["frames"][i]; rgba = vdtool.frame_rgba(f, b["palette"]); h, w = rgba.shape[:2]
            m = np.zeros((self.H, self.W), bool); x0, y0 = ax - f["cx"], ay - f["cy"] - f["h"]
            ys, xs = slice(max(y0, 0), min(y0 + h, self.H)), slice(max(x0, 0), min(x0 + w, self.W))
            if ys.stop > ys.start and xs.stop > xs.start:
                m[ys, xs] = rgba[ys.start - y0:ys.stop - y0, xs.start - x0:xs.stop - x0, 3] > 0
            if m.sum() >= 4:
                keep.append(n); masks.append(m)
        keep = np.array(keep)
        self.n = len(keep); self.key = d["key"][keep]; self.PX = d["PX"][keep]; self.BW = d["BW"][keep]; self.masks = np.array(masks)
        self.DT = np.array([ndimage.distance_transform_edt(~m) for m in self.masks]).astype(np.float32)
        rng = np.random.default_rng(0)
        self.pts = np.zeros((self.n, max_px, 2)); self.npts = np.zeros(self.n, int)
        for k, m in enumerate(self.masks):
            p = np.argwhere(m)[:, ::-1] + 0.5
            if len(p) > max_px:
                p = p[rng.choice(len(p), max_px, replace=False)]
            self.pts[k, :len(p)] = p; self.npts[k] = len(p)

    def bone_world(self, bone, unscaled=True):
        """world matrices of a bone's pose; unscaled: the scale of the pose (up to 1.3 in the hand) removed from the rotation columns, i.e. what a
        child bone with inherit_scale NONE gets"""
        M = self.BW[:, self.bones.index(bone)].copy()
        if unscaled:
            M[:, :3, :3] /= np.linalg.norm(M[:, :3, :3], axis=1, keepdims=True)
        return M

    def project(self, Mbone, P):
        """points P (..., 3) in the local frame of a bone with world matrices Mbone (n,4,4) -> pixels (n, ..., 2)"""
        Pw = np.einsum("nij,...j->n...i", Mbone[:, :3, :3], P) + Mbone[:, :3, 3].reshape((self.n,) + (1,) * (P.ndim - 1) + (3,))
        Pw1 = np.concatenate([Pw, np.ones(Pw.shape[:-1] + (1,))], -1)
        return np.einsum("nij,n...j->n...i", self.PX[:, :2], Pw1)


def chamfer(V, A, B, ns=40, cap=15.0, parts=False):
    """per view symmetric chamfer (px) of the segments A -> B in pixel coordinates (n,2); capped at `cap` px"""
    t = np.linspace(0, 1, ns + 1)[None, :, None]
    S = A[:, None] + (B - A)[:, None] * t                                  # (n, ns+1, 2) samples of the stick
    xi = np.clip(S[..., 0].astype(int), 0, V.W - 1); yi = np.clip(S[..., 1].astype(int), 0, V.H - 1)
    d1 = np.minimum(V.DT[np.arange(V.n)[:, None], yi, xi], cap).mean(1)
    e = (B - A)[:, None]; ll = (e ** 2).sum(-1) + 1e-9
    tt = np.clip((((V.pts - A[:, None]) * e).sum(-1)) / ll, 0, 1)
    dd = np.sqrt(((A[:, None] + e * tt[..., None] - V.pts) ** 2).sum(-1))
    valid = np.arange(V.pts.shape[1])[None] < V.npts[:, None]
    d2 = (np.minimum(dd, cap) * valid).sum(1) / np.maximum(V.npts, 1)
    return (d1, d2) if parts else 0.5 * (d1 + d2)


def unit(th, ph):
    return np.array([np.sin(th) * np.cos(ph), np.sin(th) * np.sin(ph), np.cos(th)])


def rigid_fit(V, bone, L0=1.0, grip0=(0, 0, 0), verbose=True):
    """one rigid stick (p0, direction, length) in the bone frame for all views; returns dict and per-view chamfer"""
    M = V.bone_world(bone)
    def f(x):
        p0 = x[2:5]; u = unit(x[0], x[1]); a, b = V.project(M, np.array([p0, p0 + u * x[5]]))[:, 0], None
        pr = V.project(M, np.array([p0, p0 + u * x[5]]))
        return chamfer(V, pr[:, 0], pr[:, 1]).mean()
    best = (1e9, None)
    for th in np.linspace(0, np.pi, 9):
        for ph in np.linspace(-np.pi, np.pi, 16, endpoint=False):
            x = np.array([th, ph, *grip0, L0]); v = f(x)
            if v < best[0]: best = (v, x)
    r = optimize.minimize(f, best[1], method="Powell", options=dict(xtol=1e-3, ftol=1e-5, maxiter=4000))
    x = r.x; p0 = x[2:5]; u = unit(x[0], x[1]); pr = V.project(M, np.array([p0, p0 + u * x[5]]))
    per = chamfer(V, pr[:, 0], pr[:, 1])
    if verbose:
        print("rigid in %s: grip %s dir %s len %.2f  chamfer mean %.2f median %.2f px" % (bone, np.round(p0, 3), np.round(u, 3), x[5], per.mean(), np.median(per)))
    return dict(bone=bone, p0=p0.tolist(), u=u.tolist(), length=float(x[5])), per


def rodrigues(r):
    a = np.linalg.norm(r)
    if a < 1e-12:
        return np.eye(3)
    k = r / a; K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + np.sin(a) * K + (1 - np.cos(a)) * K @ K


def perpose_fit(Vs_, line, extents, bone, ridge=(0.02, 0.2), ns=24, verbose=True):
    """per pose (action, frame; the 5 directions share it): turn r (rotation vector, rad) and shift t (m) in the bone frame, applied to the sticks of
    the class line (p0, u) about its point nearest to the bone origin, minimising the chamfer over the views of that pose of all weapons in Vs_ (each with its
    own extent (s0, s1) along the line). A stick leaves 2 of 6 degrees free (turn about its axis, shift along it): the ridge keeps them at 0.
    Returns {(a, i): (r, t)} and the per-view chamfer of every weapon."""
    p0 = np.array(line["p0"]); u = np.array(line["u"]); piv = p0 - u * (p0 @ u)
    Ms = [V.bone_world(bone) for V in Vs_]
    ends = [np.array([piv + u * e[0], piv + u * e[1]]) for e in extents]
    poses = sorted({(int(a), int(i)) for V in Vs_ for a, _, i in V.key})
    out, per = {}, [np.zeros(V.n) for V in Vs_]
    for (a, i) in poses:
        parts = []
        for w, V in enumerate(Vs_):
            sel = np.nonzero((V.key[:, 0] == a) & (V.key[:, 2] == i))[0]
            if len(sel):
                parts.append((w, sel, _sub(V, sel), Ms[w][sel]))
        def res(x):
            R = rodrigues(x[:3]); out_ = []
            for w, sel, Vs, Mb in parts:
                E = (ends[w] - piv) @ R.T + piv + x[3:]
                pr = Vs.project(Mb, E); A, B = pr[:, 0], pr[:, 1]
                t = np.linspace(0, 1, ns + 1)[None, :, None]; S = A[:, None] + (B - A)[:, None] * t
                d1 = np.stack([ndimage.map_coordinates(Vs.DT[k], [S[k, :, 1] - 0.5, S[k, :, 0] - 0.5], order=1, mode="nearest") for k in range(Vs.n)])
                e = (B - A)[:, None]; ll = (e ** 2).sum(-1) + 1e-9
                tt = np.clip((((Vs.pts - A[:, None]) * e).sum(-1)) / ll, 0, 1)
                d2 = np.sqrt(((A[:, None] + e * tt[..., None] - Vs.pts) ** 2).sum(-1)) * (np.arange(Vs.pts.shape[1])[None] < Vs.npts[:, None])
                out_ += [(d1 / np.sqrt(ns + 1)).ravel(), (d2 / np.sqrt(np.maximum(Vs.npts, 1))[:, None]).ravel()]
            return np.concatenate(out_ + [x[:3] / ridge[0] * 0.1, x[3:] / ridge[1] * 0.1])
        r = optimize.least_squares(res, np.zeros(6), loss="soft_l1", f_scale=3.0, x_scale=np.array([0.2] * 3 + [0.05] * 3))
        R = rodrigues(r.x[:3])
        for w, sel, Vs, Mb in parts:
            E = (ends[w] - piv) @ R.T + piv + r.x[3:]
            pr = Vs.project(Mb, E); per[w][sel] = chamfer(Vs, pr[:, 0], pr[:, 1])
        out[(a, i)] = (r.x[:3].tolist(), r.x[3:].tolist())
    if verbose:
        print("per-pose fit in %s: chamfer mean %s px" % (bone, ", ".join("%.2f" % p.mean() for p in per)))
    return out, per


def apply_class(V, bone, line, poses, fit_extent=True):
    """stick of a class line (p0, u) moved by the per-pose corrections; only the two ends along the line are fitted for this weapon.
    Returns the per-view chamfer and the extent (s0, s1) in m from the point of the line nearest to the bone origin."""
    M = V.bone_world(bone); p0 = np.array(line["p0"]); u = np.array(line["u"]); piv = np.array(line["piv"]) if "piv" in line else p0 - u * (p0 @ u)
    Rt = []
    for a, i, _ in [(k[0], k[2], 0) for k in V.key]:
        r, t = poses.get((int(a), int(i)), ([0, 0, 0], [0, 0, 0])); Rt.append((rodrigues(np.array(r)), np.array(t)))
    def ends(s0, s1):
        E = np.array([piv + u * s0, piv + u * s1])
        return np.array([(E - piv) @ R.T + piv + t for R, t in Rt])                # (n, 2, 3)
    def pr(s0, s1):
        E = ends(s0, s1)
        Pw = np.einsum("nij,nkj->nki", M[:, :3, :3], E) + M[:, None, :3, 3]
        Pw1 = np.concatenate([Pw, np.ones(Pw.shape[:-1] + (1,))], -1)
        return np.einsum("nij,nkj->nki", V.PX[:, :2], Pw1)
    f = lambda s: (lambda p: chamfer(V, p[:, 0], p[:, 1]).mean())(pr(*s))
    best = (1e9, None)
    for s0 in np.linspace(-1.5, 0.5, 9):
        for s1 in np.linspace(s0 + 0.3, s0 + 3.0, 10):
            v = f((s0, s1))
            if v < best[0]: best = (v, (s0, s1))
    r = optimize.minimize(f, best[1], method="Powell", options=dict(xtol=1e-3, ftol=1e-5))
    p = pr(*r.x)
    return chamfer(V, p[:, 0], p[:, 1]), r.x


def _sub(V, sel):
    class S: pass
    s = S(); s.n = len(sel); s.W, s.H = V.W, V.H
    for k in ("key", "PX", "BW", "masks", "DT", "pts", "npts"): setattr(s, k, getattr(V, k)[sel])
    s.project = lambda Mb, P, s=s: Views.project(s, Mb, P)
    return s


if __name__ == "__main__":
    if sys.argv[1] == "class":                                             # class WP.npz VDDIR BONE OUT.json ANIM [ANIM ...] [--line LINE.json]
        wp, vd, bone, out = sys.argv[2:6]; anims = [a for a in sys.argv[6:] if a.isdigit()]
        Vs = [Views(wp, os.path.join(vd, "anim_%04d.vd" % int(a))) for a in anims]
        if "--line" in sys.argv:
            rig = json.load(open(sys.argv[sys.argv.index("--line") + 1]))["rigid"]
        else:
            rig, _ = rigid_fit(Vs[0], bone, 1.6)
        poses = {}
        for it in range(3):
            ex = [apply_class(V, bone, rig, poses)[1] for V in Vs]
            print("iteration", it, "extents", [tuple(np.round(e, 2)) for e in ex])
            poses, per = perpose_fit(Vs, rig, ex, bone)
        ex = [apply_class(V, bone, rig, poses)[1] for V in Vs]
        res = {a: float(apply_class(V, bone, rig, poses)[0].mean()) for a, V in zip(anims, Vs)}
        print("final chamfer per weapon:", {a: round(v, 2) for a, v in res.items()})
        json.dump(dict(anims=[int(a) for a in anims], bone=bone, rigid=rig, extents={a: [float(x) for x in e] for a, e in zip(anims, ex)}, chamfer=res,
                       poses={"%d,%d" % k: v for k, v in poses.items()}), open(out, "w"))
        sys.exit()
    if sys.argv[1] == "xline":                                             # xline WP.npz VDDIR POLEARM.json BONE ANIM_WITH_OWN_LINE...: own rigid line, polearm motion
        wp, vd, cls, bone = sys.argv[2:6]; C = json.load(open(cls)); poses = {tuple(int(x) for x in k.split(",")): v for k, v in C["poses"].items()}
        p0 = np.array(C["rigid"]["p0"]); u = np.array(C["rigid"]["u"]); piv = (p0 - u * (p0 @ u)).tolist()
        for anim in sys.argv[6:]:
            V = Views(wp, os.path.join(vd, "anim_%04d.vd" % int(anim)))
            rig, per_r = rigid_fit(V, bone, 1.0, verbose=False); rig["piv"] = piv
            per, x = apply_class(V, bone, rig, poses)
            print("anim %s: own rigid line %.2f px; own line + polearm motion %.2f px (median %.2f)" % (anim, per_r.mean(), per.mean(), np.median(per)))
        sys.exit()
    if sys.argv[1] == "cross":                                             # cross WP.npz VDDIR CLASS.json BONE ANIM...
        wp, vd, cls, bone = sys.argv[2:6]; C = json.load(open(cls)); poses = {tuple(int(x) for x in k.split(",")): v for k, v in C["poses"].items()}
        for anim in sys.argv[6:]:
            V = Views(wp, os.path.join(vd, "anim_%04d.vd" % int(anim)))
            per0, x0 = apply_class(V, bone, C["rigid"], {})
            per, x = apply_class(V, bone, C["rigid"], poses)
            print("anim %s: class line, rigid %.2f px -> with the per-pose motion %.2f px (median %.2f), extent %.2f..%.2f m" % (anim, per0.mean(), per.mean(), np.median(per), x[0], x[1]))
        sys.exit()
    cmd, wp, vd, anim, bone = sys.argv[1:6]
    V = Views(wp, os.path.join(vd, "anim_%04d.vd" % int(anim)))
    print("views", V.n)
    L0 = float(sys.argv[sys.argv.index("--len") + 1]) if "--len" in sys.argv else 1.0
    if cmd == "rigid":
        rig, per = rigid_fit(V, bone, L0)
        if "--out" in sys.argv:
            json.dump(dict(anim=int(anim), rigid=rig, chamfer=float(per.mean())), open(sys.argv[sys.argv.index("--out") + 1], "w"))
    elif cmd == "perpose":
        rig, per0 = rigid_fit(V, bone, L0)
        _, x = apply_class(V, bone, rig, {})
        fit, per = perpose_fit([V], rig, [x], bone)
        if "--out" in sys.argv:
            json.dump(dict(anim=int(anim), rigid=rig, poses={"%d,%d" % k: v for k, v in fit.items()}), open(sys.argv[sys.argv.index("--out") + 1], "w"))
