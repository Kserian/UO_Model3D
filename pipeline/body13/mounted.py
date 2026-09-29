"""mounted frames: the rider is seen only where it is in front of the horse (or off the horse); the body must stay out
of the horse proxy (penalty on skin inside it, deeper than a small tolerance - the proxy is a visual hull, a bit fat)."""
import numpy as np
from numba import njit
import fastr
from fastr import raster_one
from posefit13 import Frame13, EXTRA0
from horse_sdf import sample, depth_raster, H
from fk import rig_world

TOL = 0.04             # m of the proxy the skin may enter (visual hull is conservative)
W_PEN = 0.3            # IoU per metre of summed penetration (per vertex)


@njit(cache=True)
def score_occ(V, CW, idx, w, T, masks, HD):
    nv = CW.shape[0]; N = V.shape[0]; K = idx.shape[1]
    S = np.empty((N, 2)); Z = np.empty(N)
    res = np.zeros((nv, 4))
    for v in range(nv):
        for n in range(N):
            x = 0.0; y = 0.0; z = 0.0
            for k in range(K):
                wk = w[n, k]
                if wk == 0.0: continue
                M = CW[v, idx[n, k]]
                x += wk * (M[0, 0] * V[n, 0] + M[0, 1] * V[n, 1] + M[0, 2] * V[n, 2] + M[0, 3])
                y += wk * (M[1, 0] * V[n, 0] + M[1, 1] * V[n, 1] + M[1, 2] * V[n, 2] + M[1, 3])
                z += wk * (M[2, 0] * V[n, 0] + M[2, 1] * V[n, 1] + M[2, 2] * V[n, 2] + M[2, 3])
            S[n, 0] = (x + 1.0) * 68.0; S[n, 1] = (1.0 - y) * 60.0; Z[n] = z
        D = np.full((120, 136), np.inf)
        depth_raster(S, Z, T, D)
        o = masks[v]; hd = HD[v]
        a = 0; u = 0; out = 0; mis = 0
        for yy in range(120):
            for xx in range(136):
                m = D[yy, xx] < hd[yy, xx]
                g = o[yy, xx]
                if m and g: a += 1
                if m or g: u += 1
                if m and not g: out += 1
                if g and not m: mis += 1
        res[v, 0] = a; res[v, 1] = u; res[v, 2] = out; res[v, 3] = mis
    return res


def horse_depth(HV, HT, C, dirs):
    out = np.full((len(dirs), 120, 136), np.inf)
    for k, d in enumerate(dirs):
        M = C[k] @ rig_world(d)
        h = np.c_[HV, np.ones(len(HV))] @ M.T
        S = np.stack([(h[:, 0] + 1) * 68.0, (1 - h[:, 1]) * 60.0], 1); Z = h[:, 2].copy()
        depth_raster(S, Z, HT.astype(np.int32), out[k])
    return out


class MountedFrame(Frame13):
    def __init__(self, *a, HV=None, HT=None, sdf=None, lo=None, pen_sel=None, **k):
        super().__init__(*a, **k)
        self.HD = horse_depth(HV, HT, self.C, self.dirs)
        self.sdf, self.lo = sdf, lo
        self.pen_sel = pen_sel                           # vertices tested for penetration (legs, pelvis)

    def penetration(self, S):
        idx, w = self.idx[self.pen_sel], self.w[self.pen_sel]; V = self.V[self.pen_sel]
        Vh = np.c_[V, np.ones(len(V))]
        X = np.einsum("nk,nkij,nj->ni", w, S[idx], Vh)[:, :3]
        d = sample(self.sdf, self.lo, H, X)
        return np.maximum(0, -d - TOL).sum()

    def eval(self, x):
        S = self.skin(x)
        mats = np.array([self.C[k] @ self.RW[k] @ S for k in range(len(self.dirs))])
        res = score_occ(self.V, mats, self.idx, self.w, self.T, self.masks, self.HD)
        iou = (res[:, 0] / np.maximum(res[:, 1], 1)).mean()
        L = self.L
        pen = self.reg_rot * np.sum(x[:60] ** 2) + self.reg_g * np.sum(x[L.o_g:L.o_e] ** 2) + 0.002 * np.sum((x[L.o_e:] - EXTRA0) ** 2)
        self.last_pen = self.penetration(S)
        return iou - pen - W_PEN * self.last_pen, iou, res
