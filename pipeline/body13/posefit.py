"""per-frame pose refit against the original frames (all 5 directions share one pose).
Parameters per frame: rotation vector increment per bone (on top of the start pose) + pelvis location.
Coordinate search with shrinking steps on mean IoU of the 5 views, small pull towards the start pose."""
import numpy as np
from numba import njit
import fastr
from fastr import raster_one
from fk import qmat, rig_world


def rotvec(r):
    th = np.linalg.norm(r)
    if th < 1e-12:
        return np.eye(3)
    k = r / th; K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + np.sin(th) * K + (1 - np.cos(th)) * K @ K


@njit(cache=True)
def score_views(V, CW, idx, w, T, masks):
    nv = CW.shape[0]; N = V.shape[0]; K = idx.shape[1]
    S = np.empty((N, 2))
    tot = 0.0
    res = np.zeros((nv, 4))
    for v in range(nv):
        for n in range(N):
            x = 0.0; y = 0.0
            for k in range(K):
                wk = w[n, k]
                if wk == 0.0:
                    continue
                M = CW[v, idx[n, k]]
                x += wk * (M[0, 0] * V[n, 0] + M[0, 1] * V[n, 1] + M[0, 2] * V[n, 2] + M[0, 3])
                y += wk * (M[1, 0] * V[n, 0] + M[1, 1] * V[n, 1] + M[1, 2] * V[n, 2] + M[1, 3])
            S[n, 0] = (x + 1.0) * 68.0; S[n, 1] = (1.0 - y) * 60.0
        img = np.zeros((120, 136), np.bool_)
        raster_one(S, T, img)
        o = masks[v]
        a = 0; u = 0; out = 0; mis = 0
        for yy in range(120):
            for xx in range(136):
                m = img[yy, xx]; g = o[yy, xx]
                if m and g: a += 1
                if m or g: u += 1
                if m and not g: out += 1
                if g and not m: mis += 1
        res[v, 0] = a; res[v, 1] = u; res[v, 2] = out; res[v, 3] = mis
    return res


class Frame:
    def __init__(self, V, idx, w, T, R, parent, Brel, C, masks, dirs, loc0, quat0, movable, reg=0.002):
        self.V, self.idx, self.w, self.T = V, idx, w, T
        self.R, self.parent, self.Brel = R, parent, Brel
        self.Rinv = np.linalg.inv(R)
        self.C, self.masks, self.dirs = C, masks, dirs
        self.loc0, self.rot0 = loc0.copy(), np.array([qmat(q) for q in quat0])
        self.movable = movable; self.reg = reg
        self.RW = [rig_world(d) for d in dirs]
        self.girth_ok = [True] * len(R)

    def mats(self, x):
        B = len(self.R); P = np.zeros((B, 4, 4))
        r = x[:3 * B].reshape(B, 3); dl = x[3 * B:3 * B + 3]
        g = x[3 * B + 3:].reshape(B, 2) if len(x) > 3 * B + 3 else np.zeros((B, 2))
        for b in range(B):
            M = np.eye(4); M[:3, :3] = self.rot0[b] @ rotvec(r[b]); M[:3, 3] = self.loc0[b] + (dl if b == 0 else 0)
            p = self.parent[b]
            P[b] = (self.R[b] if p < 0 else P[p] @ self.Rinv[p] @ self.R[b]) @ M
        G = np.tile(np.eye(4), (B, 1, 1)); G[:, 0, 0] = np.exp(g[:, 0]); G[:, 2, 2] = np.exp(g[:, 1])
        S = P @ G @ self.Rinv @ self.Brel
        return np.array([self.C[k] @ self.RW[k] @ S for k in range(len(self.dirs))])

    def eval(self, x):
        res = score_views(self.V, self.mats(x), self.idx, self.w, self.T, self.masks)
        iou = (res[:, 0] / np.maximum(res[:, 1], 1)).mean()
        return iou - self.reg * np.sum(x ** 2), iou, res

    def fit(self, steps=(0.12, 0.06, 0.03, 0.015, 0.008), loc_scale=0.05, passes=2, girth=False, x0=None):
        B = len(self.R); x = np.zeros(3 * B + 3 + (2 * B if girth else 0))
        if x0 is not None:
            x[:len(x0)] = x0
        f, iou0, _ = self.eval(x); f0 = f
        free = [3 * b + k for b in range(B) if self.movable[b] for k in range(3)] + [3 * B, 3 * B + 1, 3 * B + 2]
        if girth:
            free += [3 * B + 3 + 2 * b + k for b in range(B) if self.girth_ok[b] for k in range(2)]
        for st in steps:
            for _ in range(passes):
                imp = False
                for i in free:
                    s = st * (loc_scale if 3 * B <= i < 3 * B + 3 else 1.0)
                    for sgn in (1, -1):
                        y = x.copy(); y[i] += sgn * s
                        fy = self.eval(y)[0]
                        if fy > f + 1e-6:
                            x, f = y, fy; imp = True
                            while True:
                                y = x.copy(); y[i] += sgn * s
                                fy = self.eval(y)[0]
                                if fy > f + 1e-6: x, f = y, fy
                                else: break
                            break
                if not imp:
                    break
        _, iou1, res = self.eval(x)
        return x, iou0, iou1, res
