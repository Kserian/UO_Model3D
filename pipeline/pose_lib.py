"""The UO rig in numpy: forward kinematics, linear blend skinning and a pixel-centre coverage raster of the body through the UO camera,
fast enough for pose fitting (no Blender needed after the export).

    python pose_lib.py export ../model/UO_Body_0x190.blend OUT.npz      (bpy 4.2: rest pose, weights, triangles, camera, keys of all 35 actions)
    python pose_lib.py check  ../model/UO_Body_0x190.blend OUT.npz      (bpy: pose matrices and silhouettes against Blender's own)

Blender's conventions: pose matrix of a bone = parent pose matrix (scale removed when Inherit Scale = None) @ rest offset @ T(location) R(quaternion) S(scale);
skinning = sum of w * pose @ rest^-1 over the deforming bones, divided by the summed weight (Armature modifier, no preserve volume).
The canvas is the one of the original body frames (145x133, anchor (75, 92), 36 px/m) like body_part_raster.py.
"""
import sys, os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CW, CH = 145, 133
STEP = 3
LOOP = {0, 1, 2, 3, 4, 5, 6, 7, 8, 15, 23, 24, 25}


# ---------------------------------------------------------------- quaternions (w, x, y, z)
def qnorm(q):
    return q / np.linalg.norm(q, axis=-1, keepdims=True)


def qmul(a, b):
    aw, ax, ay, az = np.moveaxis(a, -1, 0); bw, bx, by, bz = np.moveaxis(b, -1, 0)
    return np.stack([aw * bw - ax * bx - ay * by - az * bz, aw * bx + ax * bw + ay * bz - az * by,
                     aw * by - ax * bz + ay * bw + az * bx, aw * bz + ax * by - ay * bx + az * bw], -1)


def qconj(q):
    return q * np.array([1.0, -1, -1, -1])


def qmat(q):
    q = qnorm(np.asarray(q, float)); w, x, y, z = np.moveaxis(q, -1, 0)
    return np.stack([np.stack([1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)], -1),
                     np.stack([2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)], -1),
                     np.stack([2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)], -1)], -2)


def matq(R):
    """rotation matrices (..., 3, 3) -> unit quaternions (..., 4), w >= 0"""
    from scipy.spatial.transform import Rotation
    sh = R.shape[:-2]; q = Rotation.from_matrix(R.reshape(-1, 3, 3)).as_quat()[:, [3, 0, 1, 2]]
    q[q[:, 0] < 0] *= -1
    return q.reshape(sh + (4,))


def qexp(v):
    """rotation vectors (..., 3) -> quaternions"""
    a = np.linalg.norm(v, axis=-1, keepdims=True); s = np.where(a > 1e-12, np.sin(a / 2) / np.maximum(a, 1e-12), 0.5)
    return np.concatenate([np.cos(a / 2), v * s], -1)


def qlog(q):
    """quaternions -> rotation vectors (shortest)"""
    q = np.where(q[..., :1] < 0, -q, q); v = q[..., 1:]; n = np.linalg.norm(v, axis=-1, keepdims=True)
    a = 2 * np.arctan2(n, q[..., :1])
    return np.where(n > 1e-12, v / np.maximum(n, 1e-12) * a, 2 * v)


def qangle(a, b):
    return 2 * np.arccos(np.clip(np.abs(np.sum(a * b, -1)), 0, 1))


def qslerp(a, b, t):
    d = np.sum(a * b, -1, keepdims=True); b = np.where(d < 0, -b, b); d = np.abs(d)
    th = np.arccos(np.clip(d, -1, 1)); s = np.sin(th)
    w0 = np.where(s > 1e-6, np.sin((1 - t) * th) / np.maximum(s, 1e-6), 1 - t); w1 = np.where(s > 1e-6, np.sin(t * th) / np.maximum(s, 1e-6), t)
    return qnorm(w0 * a + w1 * b)


def ortho_y(R):
    """Blender's orthogonalize_m3_stable(R, 1, true): keep the direction of the Y column, make X and Z orthogonal to it and to each other
    (the shear between them split evenly), unit length"""
    x, y, z = R[:, 0].copy(), R[:, 1].copy(), R[:, 2].copy()
    ly2 = y @ y
    x -= y * (x @ y) / ly2; z -= y * (z @ y) / ly2; y /= np.sqrt(ly2)
    nz, nx = z / np.linalg.norm(z), x / np.linalg.norm(x)
    c = nz @ nx
    if 1e-4 < abs(c) < 1 - 1e-7:                                     # blender: v2 = Z, v3 = X (axis order after the primary Y)
        ang = np.arccos(c); tgt = ang + (np.pi / 2 - ang) / 2
        t = nz - nx * c; nz = t * (np.sin(tgt) / np.linalg.norm(t)) + nx * np.cos(tgt)
        t = nx - nz * (nz @ nx); nx = t / np.linalg.norm(t)
    return np.stack([nx, y, nz], 1)


# ---------------------------------------------------------------- rig
class Rig:
    def __init__(self, path):
        z = np.load(path, allow_pickle=True)
        self.z = z
        self.bones = [str(b) for b in z["bones"]]; self.bi = {b: i for i, b in enumerate(self.bones)}
        self.parent = z["parent"]; self.rest = z["rest"]; self.noscale = z["noscale"]
        self.order = list(range(len(self.bones)))                   # export writes parents before children
        self.offset = np.array([np.linalg.inv(self.rest[p]) @ self.rest[b] if p >= 0 else self.rest[b] for b, p in enumerate(self.parent)])
        self.restinv = np.linalg.inv(self.rest)
        self.V = z["verts"]                                          # rest vertices in armature space (n, 3)
        self.W = z["W"]; self.WB = z["WB"]                           # (n, k) weights normalised, (n, k) bone index (-1 = none)
        self.T = z["tris"]
        self.CAM = z["cam"]                                          # (5, 4, 4): armature space -> clip space per direction
        self.vbone = self.WB[np.arange(len(self.WB)), np.argmax(self.W, 1)]   # dominant bone of a vertex
        self.actions = {int(a): str(n) for a, n in zip(z["act_id"], z["act_name"])}

    def keys(self, aid):
        """basis values of all bones for the frames of action aid: q (n, B, 4), loc (n, B, 3), scale (n, B, 3)"""
        z = self.z; s = z["key_act"] == aid
        return z["key_q"][s].copy(), z["key_loc"][s].copy(), z["key_scale"][s].copy()

    def fk(self, q, loc, scale, M=None, start=None):
        """pose matrices (B, 4, 4) in armature space from basis values of one frame. With M and start (bone indices) only the
        subtrees of `start` are recomputed in place (the rest of M is taken as is)."""
        B = len(self.bones)
        Rq = qmat(q)
        basis = np.zeros((B, 4, 4)); basis[:, :3, :3] = Rq * scale[:, None, :]; basis[:, :3, 3] = loc; basis[:, 3, 3] = 1
        if M is None:
            M = np.zeros((B, 4, 4)); todo = self.order
        else:
            todo = self.subtree(start)
        for b in todo:
            p = self.parent[b]
            if p < 0:
                M[b] = self.offset[b] @ basis[b]
            elif self.noscale[b]:                                    # Blender: rotation / scale from the orthogonalised parent, location through the full parent
                Po = M[p].copy(); Po[:3, :3] = ortho_y(Po[:3, :3])
                rs = Po @ self.offset[b]; lm = M[p] @ self.offset[b]
                M[b] = rs @ basis[b]; M[b][:3, 3] = lm[:3, :3] @ loc[b] + lm[:3, 3]
            else:
                M[b] = M[p] @ self.offset[b] @ basis[b]
        return M

    def subtree(self, start):
        """bone indices of the subtrees rooted at `start`, parents before children"""
        s = set(start); out = []
        for b in self.order:
            if b in s or self.parent[b] in s:
                s.add(b); out.append(b)
        return out

    def skin(self, M, vidx=None):
        """deformed vertices (armature space) for pose matrices M; vidx = subset of vertices"""
        K = M @ self.restinv                                         # (B, 4, 4)
        V = self.V if vidx is None else self.V[vidx]
        W = self.W if vidx is None else self.W[vidx]; WB = self.WB if vidx is None else self.WB[vidx]
        out = np.zeros((len(V), 3))
        for k in range(W.shape[1]):
            b = WB[:, k]; ok = b >= 0
            if not ok.any(): continue
            Kb = K[np.where(ok, b, 0)]
            p = np.einsum("nij,nj->ni", Kb[:, :3, :3], V) + Kb[:, :3, 3]
            out += (W[:, k] * ok)[:, None] * p
        return out

    def project(self, X, d, depth=False):
        h = np.c_[X, np.ones(len(X))] @ self.CAM[d].T
        p = h[:, :2] / h[:, 3:4]
        P = np.stack([(p[:, 0] + 1) * 0.5 * CW, (1 - p[:, 1]) * 0.5 * CH], 1)
        return (P, h[:, 2] / h[:, 3]) if depth else P

    def horse(self, aid, i):
        """(5, CH, CW) nearest horse-proxy depth inside the horse sprite (inf elsewhere), or None when the frame is not mounted"""
        z = self.z; k = "horse_%d_%d" % (aid, i)
        if k + "_v" not in z.files: return None
        V, T, HM = z[k + "_v"], z[k + "_t"], z[k + "_m"]
        out = []
        for d in range(5):
            P, Zd = self.project(V, d, True)
            _, dep = coverage_fast(P, T, Zd); dep = dep.reshape(CH, CW)
            dep[~HM[d]] = np.inf
            out.append(dep)
        return np.array(out)


try:                                                                    # optional: pip install numba (the same raster ~20x faster)
    import numba

    @numba.njit(cache=True)
    def _cov_nb(P, tris, Z, use_z, cnt, dep):
        for t in range(tris.shape[0]):
            a, b, c = tris[t, 0], tris[t, 1], tris[t, 2]
            Ax, Ay, Bx, By, Cx, Cy = P[a, 0], P[a, 1], P[b, 0], P[b, 1], P[c, 0], P[c, 1]
            den = (By - Cy) * (Ax - Cx) + (Cx - Bx) * (Ay - Cy)
            if abs(den) <= 1e-12: continue
            x0 = int(np.floor(min(Ax, Bx, Cx))); y0 = int(np.floor(min(Ay, By, Cy)))
            x1 = int(np.ceil(max(Ax, Bx, Cx))); y1 = int(np.ceil(max(Ay, By, Cy)))
            w = min(max(x1 - x0, 0), 16); h = min(max(y1 - y0, 0), 16)
            for dy in range(h + 1):
                py = y0 + dy
                if py < 0 or py >= cnt.shape[0]: continue
                cy = py + 0.5
                for dx in range(w + 1):
                    px = x0 + dx
                    if px < 0 or px >= cnt.shape[1]: continue
                    cx = px + 0.5
                    l0 = ((By - Cy) * (cx - Cx) + (Cx - Bx) * (cy - Cy)) / den
                    l1 = ((Cy - Ay) * (cx - Cx) + (Ax - Cx) * (cy - Cy)) / den
                    if l0 >= -1e-4 and l1 >= -1e-4 and 1 - l0 - l1 >= -1e-4:
                        cnt[py, px] += 1
                        if use_z:
                            z = l0 * Z[a] + l1 * Z[b] + (1 - l0 - l1) * Z[c]
                            if z < dep[py, px]: dep[py, px] = z
    HAVE_NUMBA = True
except ImportError:
    HAVE_NUMBA = False


def coverage_fast(P, tris, Z=None):
    if HAVE_NUMBA:
        cnt = np.zeros((CH, CW), np.int64); dep = np.full((CH, CW), np.inf)
        _cov_nb(np.ascontiguousarray(P, np.float64), np.ascontiguousarray(tris, np.int64), np.ascontiguousarray(Z if Z is not None else np.zeros(1), np.float64),
                Z is not None, cnt, dep)
        return cnt.ravel() if Z is None else (cnt.ravel(), dep.ravel())
    return coverage_np(P, tris, Z)


def coverage_np(P, tris, Z=None):
    """same as coverage_count, flattened (CH * CW,) int64 counts; triangles bucketed by their pixel box so every bucket is one vectorised pass.
    With Z (depth per vertex, smaller = nearer) also returns the nearest depth per pixel (inf = empty)."""
    T = P[tris]
    A, B, C = T[:, 0], T[:, 1], T[:, 2]
    mn = np.floor(T.min(1)).astype(np.int64); mx = np.ceil(T.max(1)).astype(np.int64)
    den = (B[:, 1] - C[:, 1]) * (A[:, 0] - C[:, 0]) + (C[:, 0] - B[:, 0]) * (A[:, 1] - C[:, 1])
    ok = np.abs(den) > 1e-12
    w = np.clip(mx[:, 0] - mn[:, 0], 0, 16) + 1; h = np.clip(mx[:, 1] - mn[:, 1], 0, 16) + 1
    cnt = np.zeros(CH * CW, np.int64)
    dep = np.full(CH * CW, np.inf) if Z is not None else None
    ZT = Z[tris] if Z is not None else None
    key = w * 32 + h
    for k in np.unique(key[ok]):
        t = np.nonzero(ok & (key == k))[0]; ww, hh = int(k // 32), int(k % 32)
        dx = np.tile(np.arange(ww), hh); dy = np.repeat(np.arange(hh), ww)
        px_ = mn[t, 0][:, None] + dx[None]; py_ = mn[t, 1][:, None] + dy[None]; cx, cy = px_ + 0.5, py_ + 0.5
        Ax, Ay, Bx, By, Cx, Cy, dn = (A[t, 0][:, None], A[t, 1][:, None], B[t, 0][:, None], B[t, 1][:, None], C[t, 0][:, None], C[t, 1][:, None], den[t][:, None])
        l0 = ((By - Cy) * (cx - Cx) + (Cx - Bx) * (cy - Cy)) / dn
        l1 = ((Cy - Ay) * (cx - Cx) + (Ax - Cx) * (cy - Cy)) / dn
        kk = (l0 >= -1e-4) & (l1 >= -1e-4) & (1 - l0 - l1 >= -1e-4) & (px_ >= 0) & (py_ >= 0) & (px_ < CW) & (py_ < CH)
        lin = py_[kk] * CW + px_[kk]
        cnt += np.bincount(lin, minlength=CH * CW)
        if Z is not None:
            zz = (l0 * ZT[t, 0][:, None] + l1 * ZT[t, 1][:, None] + (1 - l0 - l1) * ZT[t, 2][:, None])[kk]
            np.minimum.at(dep, lin, zz)
    return cnt if Z is None else (cnt, dep)


def dil8(m):
    """3x3 binary dilation of a (CH, CW) bool mask"""
    d = m.copy()
    d[1:] |= m[:-1]; d[:-1] |= m[1:]
    e = d.copy(); e[:, 1:] |= d[:, :-1]; e[:, :-1] |= d[:, 1:]
    return e


def sil_cost(s, b, bd=None, edge_w=1.0):
    """(1 - IoU) + edge_w * (pixels off by >= 2 px from the other silhouette) / union; >= 2 px = outside its 3x3 dilation
    (same as distance_transform_edt >= 2 of arm_joint_fit.py / action_smooth_fit.py)"""
    u = max((s | b).sum(), 1); c = 1 - (s & b).sum() / u
    if edge_w:
        bd = dil8(b) if bd is None else bd
        c += edge_w * ((s & ~bd).sum() + (b & ~dil8(s)).sum()) / u
    return c


def err2(s, b):
    """pixels off by >= 2 px (model outside the dilated sprite + sprite outside the dilated model)"""
    return int((s & ~dil8(b)).sum() + (b & ~dil8(s)).sum())


class SilEval:
    """silhouette cost of one UO frame (5 directions) for poses that change only the subtrees of `chain` bones: the rest of the body is
    rasterised once (counts), the moving triangles every call"""

    def __init__(self, rig, orig, horse=None, edge_w=1.0):
        self.R, self.O, self.edge_w = rig, orig, edge_w            # orig: (5, CH, CW) bool
        self.OD = np.array([dil8(o) for o in orig])
        self.horse = horse                                          # (5, CH, CW) horse depth inside its sprite (Rig.horse) or None
        self.chain = None

    def set_base(self, M, chain_bones):
        R = self.R
        sub = R.subtree([R.bi[b] for b in chain_bones])
        movb = np.zeros(len(R.bones), bool); movb[sub] = True
        mv = (np.where(R.WB >= 0, movb[np.where(R.WB >= 0, R.WB, 0)], False) & (R.W > 0)).any(1)
        mt = mv[R.T].any(1)
        self.vidx = np.nonzero(mv)[0]; self.tmov = R.T[mt]; self.tsta = R.T[~mt]
        X = R.skin(M)
        self.Xs = X.copy()
        self.static = []
        for d in range(5):
            if self.horse is None:
                self.static.append(coverage_fast(R.project(X, d), self.tsta))
            else:                                                    # mounted: the horse hides the body where it is nearer (depth of the static part kept)
                P, Zd = R.project(X, d, True); self.static.append(coverage_fast(P, self.tsta, Zd))
        self.chain = chain_bones

    def _mask(self, d, X):
        R = self.R
        if self.horse is None:
            return ((self.static[d] + coverage_fast(R.project(X, d), self.tmov)) > 0).reshape(CH, CW)
        P, Zd = R.project(X, d, True)
        c1, z1 = coverage_fast(P, self.tmov, Zd); c0, z0 = self.static[d]
        s = ((c0 + c1) > 0).reshape(CH, CW); zb = np.minimum(z0, z1).reshape(CH, CW)
        return s & ~(self.horse[d] < zb)

    def masks(self, M):
        Xv = self.R.skin(M, self.vidx)
        X = self.Xs; X[self.vidx] = Xv
        return [self._mask(d, X) for d in range(5)]

    def cost(self, M):
        S = self.masks(M)
        return float(np.mean([sil_cost(s, self.O[d], self.OD[d], self.edge_w) for d, s in enumerate(S)]))

    def full_masks(self, M):
        return full_masks(self.R, M, self.horse)


def full_masks(R, M, horse=None):
    """body silhouettes (5, CH, CW) of pose M, the horse hiding what it is in front of"""
    X = R.skin(M); out = []
    for d in range(5):
        if horse is None:
            out.append((coverage_fast(R.project(X, d), R.T) > 0).reshape(CH, CW))
        else:
            P, Zd = R.project(X, d, True); c, z = coverage_fast(P, R.T, Zd)
            out.append((c > 0).reshape(CH, CW) & ~(horse[d] < z.reshape(CH, CW)))
    return np.array(out)


def coverage_count(P, tris, out=None):
    """number of triangles covering each pixel centre (CH, CW) int16; P = projected vertices (n, 2) px; pixel-centre rule like body_part_raster.py"""
    cnt = np.zeros((CH, CW), np.int16) if out is None else out
    T = P[tris]
    A, B, C = T[:, 0], T[:, 1], T[:, 2]
    mn = np.floor(T.min(1)).astype(int); mx = np.ceil(T.max(1)).astype(int)
    den = (B[:, 1] - C[:, 1]) * (A[:, 0] - C[:, 0]) + (C[:, 0] - B[:, 0]) * (A[:, 1] - C[:, 1])
    ok = np.abs(den) > 1e-12; size = np.clip(mx - mn, 0, 16)
    for dy in range(int(size[:, 1].max(initial=0)) + 1):
        for dx in range(int(size[:, 0].max(initial=0)) + 1):
            t = np.nonzero(ok & (dx <= size[:, 0]) & (dy <= size[:, 1]))[0]
            if not len(t): continue
            px_ = mn[t, 0] + dx; py_ = mn[t, 1] + dy; cx, cy = px_ + 0.5, py_ + 0.5
            l0 = ((B[t, 1] - C[t, 1]) * (cx - C[t, 0]) + (C[t, 0] - B[t, 0]) * (cy - C[t, 1])) / den[t]
            l1 = ((C[t, 1] - A[t, 1]) * (cx - C[t, 0]) + (A[t, 0] - C[t, 0]) * (cy - C[t, 1])) / den[t]
            kk = (l0 >= -1e-4) & (l1 >= -1e-4) & (1 - l0 - l1 >= -1e-4) & (px_ >= 0) & (py_ >= 0) & (px_ < CW) & (py_ < CH)
            np.add.at(cnt, (py_[kk], px_[kk]), 1)
    return cnt


# ---------------------------------------------------------------- export / check (bpy)
def export(blend, out):
    import bpy
    sys.path.insert(0, HERE)
    from arm_refit import setup
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc = bpy.context.scene
    rig, body = bpy.data.objects["UO_Rig"], bpy.data.objects["UO_Body"]
    sc.camera = bpy.data.objects["UO_Camera"]; setup(sc)
    bones = []
    def walk(b):
        bones.append(b.name)
        for c in b.children: walk(c)
    for b in rig.data.bones:
        if b.parent is None: walk(b)
    bi = {b: i for i, b in enumerate(bones)}
    Bd = rig.data.bones
    rest = np.array([np.array(Bd[b].matrix_local) for b in bones])
    parent = np.array([bi[Bd[b].parent.name] if Bd[b].parent else -1 for b in bones])
    noscale = np.array([Bd[b].inherit_scale == "NONE" for b in bones])
    assert all(Bd[b].inherit_scale in ("FULL", "NONE") for b in bones)
    assert all(Bd[b].use_inherit_rotation for b in bones)
    me = body.data
    Mba = np.array(rig.matrix_world.inverted() @ body.matrix_world)
    rig["uo_direction"] = 0; rig.update_tag(); bpy.context.view_layer.update()
    Mba = np.array(rig.matrix_world.inverted() @ body.matrix_world)
    co = np.array([v.co[:] for v in me.vertices]); V = co @ Mba[:3, :3].T + Mba[:3, 3]
    gname = {g.index: g.name for g in body.vertex_groups}
    deform = {b.name for b in Bd if b.use_deform}
    rows = []
    for v in me.vertices:
        r = [(bi[gname[g.group]], g.weight) for g in v.groups if gname[g.group] in deform and gname[g.group] in bi and g.weight > 0]
        rows.append(r)
    K = max(len(r) for r in rows)
    W = np.zeros((len(rows), K)); WB = -np.ones((len(rows), K), int)
    for i, r in enumerate(rows):
        s = sum(w for _, w in r)
        for k, (b, w) in enumerate(r): W[i, k] = w / s; WB[i, k] = b
    me.calc_loop_triangles()
    tris = np.array([t.vertices[:] for t in me.loop_triangles])
    cam = []
    for d in range(5):
        rig["uo_direction"] = d; rig.update_tag(); bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get(); c = sc.camera.evaluated_get(dg)
        cam.append(np.array(c.calc_matrix_camera(dg, x=CW, y=CH)) @ np.array(c.matrix_world.inverted()) @ np.array(rig.matrix_world))
    rig["uo_direction"] = 0; rig.update_tag(); bpy.context.view_layer.update()
    P = rig.pose.bones
    acts = sorted([a for a in bpy.data.actions if "uo_action" in a], key=lambda a: int(a["uo_action"]))
    kq, kl, ks, ka, kf, km = [], [], [], [], [], []
    for act in acts:
        rig.animation_data.action = act
        for i in range(int(act["uo_frames"])):
            sc.frame_set(1 + STEP * i); bpy.context.view_layer.update()
            kq.append([P[b].rotation_quaternion[:] for b in bones]); kl.append([P[b].location[:] for b in bones]); ks.append([P[b].scale[:] for b in bones])
            km.append([np.array(P[b].matrix) for b in bones]); ka.append(int(act["uo_action"])); kf.append(i)
    import base64, zlib, json
    HD = {}
    masks = json.loads(bpy.data.texts["uo_horse_masks.json"].as_string())["masks"] if "uo_horse_masks.json" in bpy.data.texts else {}
    Mr = np.linalg.inv(np.array(rig.matrix_world))
    for ob in bpy.data.objects:
        if not ob.name.startswith("Horse_a") or ob.type != "MESH": continue
        a_, f_ = (int(x) for x in ob.name[len("Horse_a"):].split("_f"))
        ob.hide_viewport = ob.hide_render = False
    bpy.context.view_layer.update()
    for ob in bpy.data.objects:
        if not ob.name.startswith("Horse_a") or ob.type != "MESH": continue
        a_, f_ = (int(x) for x in ob.name[len("Horse_a"):].split("_f"))
        dg = bpy.context.evaluated_depsgraph_get(); ev = ob.evaluated_get(dg); m2 = ev.to_mesh()
        hv = np.array([v.co[:] for v in m2.vertices]); m2.calc_loop_triangles(); ht = np.array([t.vertices[:] for t in m2.loop_triangles])
        Mw = np.array(ev.matrix_world); ev.to_mesh_clear()
        hv = hv @ (Mr @ Mw)[:3, :3].T + (Mr @ Mw)[:3, 3]
        HM = np.zeros((5, CH, CW), bool)
        for d in range(5):
            v = masks.get("%d,%d,%d" % (a_, f_, d))
            if v is None: continue
            bits = np.unpackbits(np.frombuffer(zlib.decompress(base64.b64decode(v)), np.uint8))[:120 * 136].reshape(120, 136).astype(bool)
            HM[d, 92 - 86:92 - 86 + 120, 75 - 68:75 - 68 + 136] = bits
        HD["horse_%d_%d_v" % (a_, f_)] = hv; HD["horse_%d_%d_t" % (a_, f_)] = ht; HD["horse_%d_%d_m" % (a_, f_)] = HM
    np.savez_compressed(out, **HD, bones=np.array(bones), parent=parent, rest=rest, noscale=noscale, verts=V, W=W, WB=WB, tris=tris, cam=np.array(cam),
                        key_q=np.array(kq), key_loc=np.array(kl), key_scale=np.array(ks), key_mat=np.array(km), key_act=np.array(ka), key_frame=np.array(kf),
                        act_id=np.array([int(a["uo_action"]) for a in acts]), act_name=np.array([a.name for a in acts]),
                        frames=np.array([int(a["uo_frames"]) for a in acts]))
    print("exported", out, len(bones), "bones", len(V), "verts", len(tris), "tris", len(ka), "frames")


def check(blend, npz):
    """FK against Blender's pose matrices (all frames) and the coverage against body_part_raster.py (a few frames)"""
    import bpy
    sys.path.insert(0, HERE)
    from body_part_raster import raster
    from arm_refit import setup
    R = Rig(npz); z = R.z
    err = 0.0
    for n in range(len(z["key_act"])):
        M = R.fk(z["key_q"][n], z["key_loc"][n], z["key_scale"][n])
        err = max(err, np.abs(M - z["key_mat"][n]).max())
    print("FK max abs error vs Blender pose matrices: %.2e" % err)
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc = bpy.context.scene; rig, body = bpy.data.objects["UO_Rig"], bpy.data.objects["UO_Body"]
    sc.camera = bpy.data.objects["UO_Camera"]; setup(sc)
    acts = {int(a["uo_action"]): a for a in bpy.data.actions if "uo_action" in a}
    from arm_joint_fit import horse_masks
    ious = []
    for aid, i in [(0, 2), (9, 3), (17, 4), (21, 4), (26, 1), (23, 3), (29, 1)]:
        rig.animation_data.action = acts[aid]
        n = np.nonzero((z["key_act"] == aid) & (z["key_frame"] == i))[0][0]
        S = full_masks(R, R.fk(z["key_q"][n], z["key_loc"][n], z["key_scale"][n]), R.horse(aid, i))
        hob, HM = horse_masks(aid, i)
        for d in range(5):
            rig["uo_direction"] = d; sc.frame_set(1 + STEP * i); rig.update_tag(); body.update_tag(); bpy.context.view_layer.update()
            dg = bpy.context.evaluated_depsgraph_get(); cam = sc.camera.evaluated_get(dg)
            Pm, Vm = np.array(cam.calc_matrix_camera(dg, x=CW, y=CH)), np.array(cam.matrix_world.inverted())
            lab, dep = raster(body, dg, Pm, Vm, None)
            if hob is not None and d in HM:
                hl, hd = raster(hob, dg, Pm, Vm, None); lab[(hl >= 0) & (hd < dep) & HM[d]] = -1
            b = lab >= 0; m = S[d]
            ious.append((m & b).sum() / max((m | b).sum(), 1))
    print("coverage vs body_part_raster: min IoU %.5f, mean %.5f" % (min(ious), np.mean(ious)))


def qa(npz, out=None):
    """silhouette IoU and >= 2 px errors of all 1050 frames (keys of the export) against the original body frames"""
    from PIL import Image
    import json
    R = Rig(npz); z = R.z; res = {}
    for n in range(len(z["key_act"])):
        aid, i = int(z["key_act"][n]), int(z["key_frame"][n]); name = R.actions[aid]
        S = full_masks(R, R.fk(z["key_q"][n], z["key_loc"][n], z["key_scale"][n]), R.horse(aid, i))
        for d in range(5):
            o = np.array(Image.open(os.path.join(HERE, "..", "client/body_0x190_frames/frames/%s/dir%d/%02d.png" % (name, d, i))).convert("RGBA"))[..., 3] > 0
            r = res.setdefault(aid, [[], 0])
            if o.any(): r[0].append((S[d] & o).sum() / max((S[d] | o).sum(), 1))
            r[1] += err2(S[d], o)
    allv = [v for r in res.values() for v in r[0]]
    print("frames %d  IoU %.4f  err2 %d" % (len(allv), np.mean(allv), sum(r[1] for r in res.values())))
    for aid, r in sorted(res.items()): print("  %2d %-26s IoU %.4f err2 %4d" % (aid, R.actions[aid], np.mean(r[0]), r[1]))
    if out: json.dump({"iou": float(np.mean(allv)), "err2": int(sum(r[1] for r in res.values())),
                       "actions": {str(a): {"iou": float(np.mean(r[0])), "err2": int(r[1])} for a, r in res.items()}}, open(out, "w"), indent=1)


if __name__ == "__main__":
    if sys.argv[1] == "qa":
        qa(os.path.abspath(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else None)
    elif sys.argv[1] == "export":
        export(os.path.abspath(sys.argv[2]), os.path.abspath(sys.argv[3]))
    elif sys.argv[1] == "check":
        check(os.path.abspath(sys.argv[2]), os.path.abspath(sys.argv[3]))
