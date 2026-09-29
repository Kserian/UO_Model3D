"""fit cloth chain rigs to the original item frames (anim.mul), body pose fixed.
The item is seen where it is in front of the body (or off the body); legs (capsules) must stay inside the skirt."""
import numpy as np
from numba import njit
from horse_sdf import depth_raster
from fk import rig_world


def capsules(K, V, S_body, names=("thigh.L", "shin.L", "thigh.R", "shin.R", "pelvis")):
    """(head, dir, length, radius) per bone in armature space for the posed body skin matrices S_body"""
    out = []
    for n in names:
        b = K.ix[n]; Pf = S_body[b] @ K.R[b]
        child = {"thigh.L": "shin.L", "shin.L": "foot.L", "thigh.R": "shin.R", "shin.R": "foot.R", "pelvis": "spine"}[n]
        L = np.linalg.norm(K.R[K.ix[child]][:3, 3] - K.R[b][:3, 3])
        # radius from the rest body: verts mostly on this bone
        sel = K.SW[:, b] > 0.6
        rel = V[sel] - K.R[b][:3, 3]; ax = K.R[b][:3, 1]
        t = rel @ ax; rad = np.linalg.norm(rel - np.outer(t, ax), axis=1)
        r = np.percentile(rad[(t > 0.15 * L) & (t < 0.85 * L)], 60) if ((t > 0.15 * L) & (t < 0.85 * L)).sum() > 10 else 0.05
        out.append((Pf[:3, 3], Pf[:3, 1], L, r))
    return out


def penetration(X, caps, margin=-0.01):
    pen = 0.0
    for h, d, L, r in caps:
        rel = X - h; t = np.clip(rel @ d, 0, L); q = rel - np.outer(t, d)
        dist = np.linalg.norm(q, axis=1)
        pen += np.maximum(0, r + margin - dist).sum()
    return pen


class ClothFrame:
    def __init__(self, rig, CV, CF, CW, S_body, K, BV, body_T, C, dirs, masks, R_parent_name, prev=None,
                 w_pen=3.0, reg=0.002, smooth=0.01, temporal=0.01):
        self.rig, self.CV, self.CW = rig, CV, CW
        self.T = np.array([[f[0], f[1], f[2]] for f in CF] + [[f[0], f[2], f[3]] for f in CF], np.int32)
        pb = K.ix[R_parent_name]
        self.Ppar = S_body[pb] @ K.R[pb]; self.Rpar = K.R[pb]
        self.C, self.dirs, self.masks = C, dirs, masks
        self.RW = [rig_world(d) for d in dirs]
        # body depth per view
        Xb = np.einsum("nb,bij,nj->ni", K.SW, S_body, np.c_[BV, np.ones(len(BV))])[:, :3]
        self.BD = []
        for k, d in enumerate(dirs):
            M = C[k] @ self.RW[k]; h = np.c_[Xb, np.ones(len(Xb))] @ M.T
            D = np.full((120, 136), np.inf)
            depth_raster(np.stack([(h[:, 0] + 1) * 68.0, (1 - h[:, 1]) * 60.0], 1), h[:, 2].copy(), body_T, D)
            self.BD.append(D)
        self.caps = capsules(K, BV, S_body)
        self.Sb = S_body
        self.CVh = np.c_[CV, np.ones(len(CV))]
        self.w_pen, self.reg, self.smooth, self.temporal = w_pen, reg, smooth, temporal
        self.prev = prev
        self.xref = None                                               # regularise towards this (default: rest)

    def verts(self, x):
        S = self.rig.pose(x, self.Ppar, self.Rpar)
        if self.CW.shape[1] > len(S):
            S = np.concatenate([S, self.Sb])
        return np.einsum("nb,bij,nj->ni", self.CW, S, self.CVh)[:, :3]

    def masks_of(self, X):
        out = []
        for k in range(len(self.dirs)):
            M = self.C[k] @ self.RW[k]; h = np.c_[X, np.ones(len(X))] @ M.T
            D = np.full((120, 136), np.inf)
            depth_raster(np.stack([(h[:, 0] + 1) * 68.0, (1 - h[:, 1]) * 60.0], 1), h[:, 2].copy(), self.T, D)
            out.append(D < self.BD[k] - 0.003 * np.linalg.norm(M[2, :3]))      # 3 mm in front of the skin
        return np.array(out)

    def eval(self, x):
        X = self.verts(x); m = self.masks_of(X); o = self.masks
        inter = (m & o).sum((1, 2)); uni = (m | o).sum((1, 2))
        iou = (inter / np.maximum(uni, 1)).mean()
        a = x.reshape(self.rig.nc, self.rig.ns, 2)
        sm = np.sum((a - np.roll(a, 1, 0)) ** 2) if self.rig.prefix == "skirt" else np.sum(np.diff(a, axis=0) ** 2)
        tp = np.sum((x - self.prev) ** 2) if self.prev is not None else 0.0
        pen = penetration(X, self.caps)
        self.last = dict(iou=iou, pen=pen, out=(m & ~o).sum() / len(o), miss=(o & ~m).sum() / len(o))
        xr = x if self.xref is None else x - self.xref
        return iou - self.w_pen * pen - self.reg * np.sum(xr ** 2) - self.smooth * sm - self.temporal * tp, iou

    def directions(self):
        """search directions: single angles + grouped moves (level, chain, whole-cloth sway / flare)"""
        rig = self.rig; nc, ns = rig.nc, rig.ns; D = []
        eye = np.eye(nc * ns * 2)
        D += [eye[i] for i in range(nc * ns * 2)]
        th = np.array([np.arctan2(rig.R[rig.bone(k, 0)][1, 2], rig.R[rig.bone(k, 0)][0, 2]) for k in range(nc)])   # outward angle
        for s_ in range(ns):
            for c in range(2):
                v = np.zeros((nc, ns, 2)); v[:, s_, c] = 1; D.append(v.ravel())
        for k in range(nc):
            for c in range(2):
                v = np.zeros((nc, ns, 2)); v[k, :, c] = 1; D.append(v.ravel())
        for c in range(2):
            v = np.zeros((nc, ns, 2)); v[:, :, c] = 1; D.append(v.ravel())
        for phi in np.linspace(0, 2 * np.pi, 8, endpoint=False):
            v = np.zeros((nc, ns, 2)); v[:, :, 0] = np.cos(th - phi)[:, None]; v[:, :, 1] = np.sin(th - phi)[:, None]
            D.append(v.ravel())
        return np.array(D)

    def fit(self, x0, steps=(0.24, 0.12, 0.06, 0.03), passes=3):
        x = x0.copy(); f, _ = self.eval(x); D = self.directions()
        for st in steps:
            for _ in range(passes):
                imp = False
                for j in range(len(D)):
                    for sgn in (1, -1):
                        y = x + sgn * st * D[j]
                        fy, _ = self.eval(y)
                        if fy > f + 1e-6:
                            x, f = y, fy; imp = True
                            while True:
                                y = x + sgn * st * D[j]; fy, _ = self.eval(y)
                                if fy > f + 1e-6: x, f = y, fy
                                else: break
                            break
                if not imp: break
        self.eval(x)
        return x


class MountedClothFrame(ClothFrame):
    """mounted frames: the horse hides the cloth too, and the cloth must stay out of the horse proxy"""
    def __init__(self, *a, HV=None, HT=None, sdf=None, lo=None, w_horse=3.0, tol=0.03, **k):
        super().__init__(*a, **k)
        from mounted import horse_depth
        self.HD = horse_depth(HV, HT, self.C, self.dirs)
        self.BD = [np.minimum(b, h) for b, h in zip(self.BD, self.HD)]
        self.sdf, self.lo, self.w_horse, self.tol = sdf, lo, w_horse, tol

    def eval(self, x):
        from horse_sdf import sample, H
        f, iou = super().eval(x)
        X = self.verts(x)
        hp = np.maximum(0, -sample(self.sdf, self.lo, H, X) - self.tol).sum()
        self.last["hpen"] = hp
        return f - self.w_horse * hp, iou
