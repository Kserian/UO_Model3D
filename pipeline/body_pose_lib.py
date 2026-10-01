"""Offline forward kinematics of the 210 UO poses (numpy only), from the data of body_pose_fk_export.py.

    K = FK("fk.npz"); loc, quat, scl = K.params(p)            # local pose basis of pose p, all bones
    M = K.skin(loc, quat, scl)                                 # (B,4,4) skinning matrices pose @ rest^-1, same as pose.npz `M`

Pose bone matrix = P[parent] @ Lrest @ T(loc) R(quat) S(scl); skinning matrix = P @ inv(Arest).
"""
import numpy as np


def quat_to_mat(q):
    q = q / np.linalg.norm(q, axis=-1, keepdims=True)
    w, x, y, z = q[..., 0], q[..., 1], q[..., 2], q[..., 3]
    R = np.empty(q.shape[:-1] + (3, 3))
    R[..., 0, 0] = 1 - 2 * (y * y + z * z); R[..., 0, 1] = 2 * (x * y - z * w); R[..., 0, 2] = 2 * (x * z + y * w)
    R[..., 1, 0] = 2 * (x * y + z * w); R[..., 1, 1] = 1 - 2 * (x * x + z * z); R[..., 1, 2] = 2 * (y * z - x * w)
    R[..., 2, 0] = 2 * (x * z - y * w); R[..., 2, 1] = 2 * (y * z + x * w); R[..., 2, 2] = 1 - 2 * (x * x + y * y)
    return R


def qmul(a, b):
    w1, x1, y1, z1 = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    w2, x2, y2, z2 = b[..., 0], b[..., 1], b[..., 2], b[..., 3]
    return np.stack([w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2, w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
                     w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2, w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2], -1)


def rotvec_to_quat(v):
    a = np.linalg.norm(v, axis=-1, keepdims=True); s = np.where(a > 1e-12, np.sin(a / 2) / np.maximum(a, 1e-12), 0.5)
    return np.concatenate([np.cos(a / 2), v * s], -1)


class FK:
    def __init__(self, npz):
        d = np.load(npz)
        self.bones = [str(b) for b in d["bones"]]; self.parent = d["parent"]; self.Lrest = d["Lrest"]; self.Arest = d["Arest"]
        self.noscale = d["noscale"] if "noscale" in d.files else np.zeros(len(self.bones), bool)
        self.Ainv = np.linalg.inv(self.Arest); self.key = d["key"]; self.loc, self.quat, self.scl, self.P = d["loc"], d["quat"], d["scl"], d["P"]
        self.B = len(self.bones); self.idx = {n: i for i, n in enumerate(self.bones)}
        # subtree[b] = bool mask of the bones below (and including) b; order: parents precede children?
        self.order = self._order()
        self.sub = np.zeros((self.B, self.B), bool)
        for b in range(self.B):
            k = b
            while k >= 0:
                self.sub[k, b] = True; k = self.parent[k]
        self.pose_index = {(int(a), int(i)): p for p, (a, i) in enumerate(self.key)}

    def _order(self):
        o, seen = [], set()
        def visit(b):
            if b in seen: return
            if self.parent[b] >= 0: visit(self.parent[b])
            seen.add(b); o.append(b)
        for b in range(len(self.parent)): visit(b)
        return o

    def basis(self, loc, quat, scl):
        Bm = np.zeros((self.B, 4, 4)); Bm[:, 3, 3] = 1
        Bm[:, :3, :3] = quat_to_mat(quat) * scl[:, None, :]            # R S
        Bm[:, :3, 3] = loc
        return Bm

    def pose(self, loc, quat, scl):
        Bm = self.basis(loc, quat, scl); P = np.zeros((self.B, 4, 4))
        for b in self.order:
            L = self.Lrest[b] @ Bm[b]
            if self.parent[b] < 0:
                P[b] = L
            elif self.noscale[b]:                       # inherit_scale NONE: rotation/scale part from the parent with its scale removed, position as usual
                Pp = P[self.parent[b]]; Rn = Pp[:3, :3] / np.linalg.norm(Pp[:3, :3], axis=0, keepdims=True)
                P[b] = Pp @ L; P[b][:3, :3] = Rn @ L[:3, :3]
            else:
                P[b] = P[self.parent[b]] @ L
        return P

    def skin(self, loc, quat, scl):
        return self.pose(loc, quat, scl) @ self.Ainv
