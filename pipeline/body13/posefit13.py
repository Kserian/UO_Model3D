"""per-frame pose refit on the 55-bone v13 skeleton (5 directions share one pose).
x = [19x3 rotation increments of the UO bones | pelvis location | girth (log scale x, z) of GIRTH bones | curl.L curl.R thumb.L thumb.R toe.L toe.R]
Girth is a bone scale on local X / Z; the next bone of the chain does not inherit it (Blender: Inherit Scale = None),
leaf bones (twist, fingers, toe) do."""
import numpy as np
from posefit import rotvec, score_views
from fk import qmat, rig_world
from skel13 import SIDES

GIRTH = ["upper_arm.L", "forearm.L", "hand.L", "upper_arm.R", "forearm.R", "hand.R", "thigh.L", "shin.L", "foot.L",
         "thigh.R", "shin.R", "foot.R", "head"]
NO_INHERIT = {"forearm.L", "hand.L", "forearm.R", "hand.R", "shin.L", "foot.L", "shin.R", "foot.R"}
EXTRA = ["curl.L", "curl.R", "thumb.L", "thumb.R", "toe.L", "toe.R"]
EXTRA0 = np.array([1.0, 1.0, 1.0, 1.0, 0.0, 0.0])


class Layout:
    def __init__(self, names):
        self.names = names; self.n19 = 19
        self.gi = [names.index(b) for b in GIRTH]
        self.o_loc = 57; self.o_g = 60; self.o_e = 60 + 2 * len(GIRTH); self.size = self.o_e + len(EXTRA)

    def zero(self):
        x = np.zeros(self.size); x[self.o_e:] = EXTRA0; return x


class Frame13:
    def __init__(self, K, V, idx, w, T, Brel, C, masks, dirs, loc0, quat0, reg_rot=0.002, reg_g=0.02):
        self.K, self.V, self.idx, self.w, self.T, self.Brel = K, V, idx, w, T, Brel
        self.R, self.parent = K.R, K.parent; self.Rinv = np.linalg.inv(K.R)
        self.C, self.masks, self.dirs = C, masks, dirs
        self.RW = [rig_world(d) for d in dirs]
        self.loc0 = loc0; self.rot0 = np.array([qmat(q) for q in quat0])
        self.L = Layout(K.names); self.reg_rot, self.reg_g = reg_rot, reg_g
        self.noinh = np.array([n in NO_INHERIT for n in K.names])

    def skin(self, x):
        L = self.L; K = self.K; B = len(K.names)
        r = x[:57].reshape(19, 3); dl = x[57:60]; g = x[L.o_g:L.o_e].reshape(-1, 2); e = x[L.o_e:]
        ext = K.extra_bases({".L": e[0], ".R": e[1]}, {".L": e[2], ".R": e[3]}, {".L": e[4], ".R": e[5]})
        G = np.tile(np.eye(4), (B, 1, 1))
        for k, b in enumerate(L.gi):
            G[b, 0, 0] = np.exp(g[k, 0]); G[b, 2, 2] = np.exp(g[k, 1])
        Pn = np.zeros((B, 4, 4)); Pf = np.zeros((B, 4, 4))
        for b in range(B):
            M = np.eye(4)
            if b < 19:
                M[:3, :3] = self.rot0[b] @ rotvec(r[b]); M[:3, 3] = self.loc0[b] + (dl if b == 0 else 0)
            else:
                M[:3, :3] = ext[K.names[b]]
            p = self.parent[b]
            if p < 0:
                Pn[b] = self.R[b] @ M
            else:
                Pn[b] = (Pn[p] if self.noinh[b] else Pf[p]) @ self.Rinv[p] @ self.R[b] @ M
            Pf[b] = Pn[b] @ G[b]
        return Pf @ self.Rinv @ self.Brel

    def mats(self, x):
        S = self.skin(x)
        return np.array([self.C[k] @ self.RW[k] @ S for k in range(len(self.dirs))])

    def eval(self, x):
        res = score_views(self.V, self.mats(x), self.idx, self.w, self.T, self.masks)
        iou = (res[:, 0] / np.maximum(res[:, 1], 1)).mean()
        L = self.L
        pen = self.reg_rot * np.sum(x[:60] ** 2) + self.reg_g * np.sum(x[L.o_g:L.o_e] ** 2) + 0.002 * np.sum((x[L.o_e:] - EXTRA0) ** 2)
        return iou - pen, iou, res

    def fit(self, x0=None, steps=(0.12, 0.06, 0.03, 0.015, 0.008), passes=2, fix_extra=False):
        L = self.L; x = L.zero() if x0 is None else x0.copy()
        f, iou0, _ = self.eval(x)
        free = list(range(60)) + list(range(L.o_g, L.o_e)) + ([] if fix_extra else list(range(L.o_e, L.size)))
        mult = np.ones(L.size); mult[57:60] = 0.05; mult[L.o_g:L.o_e] = 0.5; mult[L.o_e:] = 2.0
        lo = np.full(L.size, -np.inf); hi = np.full(L.size, np.inf)
        lo[L.o_g:L.o_e] = -0.35; hi[L.o_g:L.o_e] = 0.35
        lo[L.o_e:L.o_e + 4] = -0.2; hi[L.o_e:L.o_e + 4] = 1.2; lo[L.o_e + 4:] = -0.6; hi[L.o_e + 4:] = 0.8
        for st in steps:
            for _ in range(passes):
                imp = False
                for i in free:
                    s = st * mult[i]
                    for sgn in (1, -1):
                        y = x.copy(); y[i] = np.clip(y[i] + sgn * s, lo[i], hi[i])
                        if y[i] == x[i]: continue
                        fy = self.eval(y)[0]
                        if fy > f + 1e-6:
                            x, f = y, fy; imp = True
                            while True:
                                y = x.copy(); y[i] = np.clip(y[i] + sgn * s, lo[i], hi[i])
                                if y[i] == x[i]: break
                                fy = self.eval(y)[0]
                                if fy > f + 1e-6: x, f = y, fy
                                else: break
                            break
                if not imp:
                    break
        _, iou1, res = self.eval(x)
        return x, iou0, iou1, res
