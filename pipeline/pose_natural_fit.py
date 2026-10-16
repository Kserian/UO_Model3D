"""Natural motion with the same silhouettes: re-fit of the pose keys of an action so that the rig moves like a body in 3D (no zig-zag of the head,
no twisting of the shoulder, no sliding clavicles) while the silhouette against the ORIGINAL body frames (5 directions) is not worse than now.

    python pose_lib.py export ../model/UO_Body_0x190.blend rig.npz
    python pose_natural_fit.py rig.npz OUT_DIR [--actions 0,1,2] [--jobs 4] [--sweeps 2]      (env: the weights below, e.g. LAMBDA, TWIST_W, SLIDE_W, TOL)
    python apply_pose_keys.py ../model/UO_Body_0x190.blend OUT.blend OUT_DIR                     (writes the keys; bpy 4.2)

Why: the poses were fitted frame by frame to the silhouettes (arm_joint_fit.py, rounds 1-6). Whatever the outline hardly shows was free to follow
the 1-px noise of the sprites: the head turned and tilted 5-25 deg from frame to frame, the hand flapped (up to 100 deg), the upper arm twisted
about its own axis (internal twist 20-30 deg folds the MakeHuman shoulder: the deltoid turns away from the chest), and the clavicles carried
location keys of 2-8 cm (a clavicle does not deform the mesh, so a shifted one slides the whole arm along the chest skin: a dent at the shoulder).

What this does per action (UO frames only; loops wrap):
 1. clavicle location keys -> 0; the head one size everywhere (HEAD_SCALE, median of all keys); optional SCALE=1: per-frame girth scales smoothed in time ([1, 2, 1] / 4, loops wrap);
 2. start = the armature-space orientation of every fitted bone smoothed in time (PASSES of [1, 2, 1] / 4; one-shot actions only SMOOTH_ONESHOT
    of the way, their ends kept);
 3. Gauss-Seidel sweeps over the frames, chains torso (spine, chest), head (neck, head), armR / armL (clavicle, upper arm, forearm, hand):
    Powell on   E = LAMBDA * sum_b w_b angle(G_b, mid(G_b(i-1), G_b(i+1)))^2      smooth in time
                  + TWIST_W * fade * twist_excess^2                                upper-arm twist vs the stand pose (only while the arm hangs)
                  + SLIDE_W * slide_excess^2                                       shoulder joint moving on the chest (clavicle rotation)
                  + VALGUS_W * forearm_valgus^2 + FOLD_W * shoulder_crease^2      elbow a hinge, no deeper shoulder crease than in stand
                  + Sil + 50 * max(0, Sil - Sil0 - TOL) + 0.02 * max(0, err2 - err2_0 - ERR2_TOL)
    G_b = armature-space orientation, mid = half way between the neighbours (loops wrap); Sil = (1 - IoU) + (pixels off by >= 2 px) / union,
    mean of 5 directions, horse hiding in the mounted actions (as body_part_raster.py); Sil0 / err2_0 = the same for the ORIGINAL keys.
    An infeasible result is tried again from the original keys of the chain; the best feasible candidate wins;
 4. guard: a frame still worse than the original (Sil0 + TOL, err2_0 + ERR2_TOL) is blended back towards its original keys (0.75 ... 0).
Item bones (weapon1h.R, polearm.L, axe2h.L, bow.L, shield.L) are not fitted: apply_pose_keys.py keeps their armature-space motion (they were
fitted to the original weapons). Output per action: OUT_DIR/a<aid>.json (local quaternions / locations / scales of every bone per frame + log).
Needs: numpy scipy pillow (no bpy).
"""
import sys, os, json, time
import numpy as np
from scipy.optimize import minimize
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pose_lib import Rig, SilEval, full_masks, sil_cost, err2, dil8, qmul, qexp, qnorm, qmat, matq, qangle, qslerp, LOOP, CH, CW, HERE

LAMBDA = float(os.environ.get("LAMBDA", 1.0))           # smoothness weight, per rad^2
TWIST_W = float(os.environ.get("TWIST_W", 4.0))         # upper-arm twist beyond TWIST_FREE from the stand pose, per rad^2
TWIST_FREE = np.radians(float(os.environ.get("TWIST_FREE", 3)))
SLIDE_W = float(os.environ.get("SLIDE_W", 300.0))      # shoulder joint sliding on the chest beyond SLIDE_FREE from the stand pose, per m^2
SLIDE_FREE = float(os.environ.get("SLIDE_FREE", 0.01))
VALGUS_W = float(os.environ.get("VALGUS_W", 4.0))       # forearm swing about its local Z (the elbow is a hinge), per rad^2
FOLD_W = float(os.environ.get("FOLD_W", 0.01))           # crease of the shoulder (mean rise of the dihedral angles where chest and upper arm skin meet) beyond
                                                        # the stand pose, per deg^2
GRIP_W = float(os.environ.get("GRIP_W", 0.0))          # right fist away from the grip of the 1H weapon bone (weapon1h.R, fitted to the original weapons), per m^2
GRIP_FREE = float(os.environ.get("GRIP_FREE", 0.02))
GRIP_ROT_W = float(os.environ.get("GRIP_ROT_W", 0.0))   # right fist turned against the weapon bone (their rest relation), per rad^2
                                                        # (GRIP_* off: the weapon motion jumps, a fist following it jumps too)
TOL = float(os.environ.get("TOL", 0.001))               # allowed rise of Sil per frame
ERR2_TOL = int(os.environ.get("ERR2_TOL", 0))          # allowed rise of the >= 2 px errors per frame (sum of 5 directions)
HEAD_YAW_ACTIONS = {int(x) for x in os.environ.get("HEAD_YAW_ACTIONS", "23,24").split(",") if x}   # mounted walk / run: the rider is hidden under the horse
HEAD_YAW_W = float(os.environ.get("HEAD_YAW_W", 3.0))   # head turned about the chest's own axis beyond HEAD_YAW_FREE from the mounted-stand pose, per rad^2
                                                        # (only for HEAD_YAW_ACTIONS; the heads of fighting actions are left to move)
HEAD_YAW_FREE = np.radians(float(os.environ.get("HEAD_YAW_FREE", 2)))
HEAD_LAMBDA = float(os.environ.get("HEAD_LAMBDA", 1.0))   # multiplier of the smoothness weight of neck / head in those actions
HEAD_TOL = float(os.environ.get("HEAD_TOL", 0.004))     # silhouette tolerance per frame of those actions (the horse hides the rider, the sprite outline hardly pins the head)
HEAD_ERR2_TOL = int(os.environ.get("HEAD_ERR2_TOL", 30))
MAXFEV = int(os.environ.get("MAXFEV", 400))
PASSES = int(os.environ.get("PASSES", 1))
SMOOTH_ONESHOT = float(os.environ.get("SMOOTH_ONESHOT", 0.5))   # one-shot actions (fast attacks...) start only this share of the way to the smoothed orientation
TWIST_DOWN = np.radians(float(os.environ.get("TWIST_DOWN", 60)))  # the twist prior fades out as the upper arm leaves the stand direction (0 at this angle)
SCALE = int(os.environ.get("SCALE", 0))
HEAD_SCALE = int(os.environ.get("HEAD_SCALE", 1))       # 1 = the head keeps one size in every frame of every action (median of all keys; a rigid
                                                        # helmet bound to the head scaled 0.74-1.14 from frame to frame before)
CHAINS = {"torso": ["spine", "chest"], "head": ["neck", "head"],
          "armR": ["clavicle.R", "upper_arm.R", "forearm.R", "hand.R"], "armL": ["clavicle.L", "upper_arm.L", "forearm.L", "hand.L"]}
BONE_W = {"spine": 1.0, "chest": 1.0, "neck": 1.0, "head": 2.0, "clavicle.R": 1.0, "clavicle.L": 1.0, "upper_arm.R": 1.0, "upper_arm.L": 1.0,
          "forearm.R": 0.7, "forearm.L": 0.7, "hand.R": 0.5, "hand.L": 0.5}
ITEM_BONES = ["weapon1h.R", "polearm.L", "axe2h.L", "bow.L", "shield.L"]
GIRTH = ["upper_arm.L", "forearm.L", "hand.L", "upper_arm.R", "forearm.R", "hand.R", "thigh.L", "shin.L", "foot.L", "thigh.R", "shin.R", "foot.R", "head"]
ROOT = os.path.join(HERE, "..")


def originals(aid, name, n):
    out = []
    for i in range(n):
        out.append(np.array([np.array(Image.open(os.path.join(ROOT, "client/body_0x190_frames/frames/%s/dir%d/%02d.png" % (name, d, i))).convert("RGBA"))[..., 3] > 0
                             for d in range(5)]))
    return out


def rot_of(M):
    """rotation part (B, 3, 3) of pose matrices (scale removed)"""
    return M[:, :3, :3] / np.linalg.norm(M[:, :3, :3], axis=1, keepdims=True)


def smooth_seq(Q, loop, passes, pin_ends=True):
    """[1, 2, 1] / 4 smoothing of a quaternion sequence (n, 4), sign-aligned; loops wrap, one-shot ends pinned"""
    Q = Q.copy(); n = len(Q)
    for i in range(1, n): Q[i] *= np.sign(np.sum(Q[i] * Q[i - 1])) or 1
    for _ in range(passes):
        P = Q.copy()
        for i in range(n):
            if not loop and i in (0, n - 1):
                if pin_ends or n < 3: continue
            a, b = Q[(i - 1) % n], Q[(i + 1) % n]
            if not loop: a, b = Q[max(i - 1, 0)], Q[min(i + 1, n - 1)]
            a = a * (np.sign(np.sum(a * Q[i])) or 1); b = b * (np.sign(np.sum(b * Q[i])) or 1)
            P[i] = qnorm(a + 2 * Q[i] + b)
        Q = P
    return Q


def swing_twist_y(q):
    """twist angle (rad) about local Y of quaternion q (w, x, y, z) and the swing about local Z (rad, of the swing part)"""
    tw = 2 * np.arctan2(q[2], q[0]); tw = (tw + np.pi) % (2 * np.pi) - np.pi
    t = np.array([np.cos(tw / 2), 0, np.sin(tw / 2), 0])
    sw = qmul(q, t * np.array([1, -1, -1, -1]))
    v = 2 * np.arctan2(np.linalg.norm(sw[1:]), sw[0]) * sw[1:] / max(np.linalg.norm(sw[1:]), 1e-12)
    return tw, v[2]


class ActionFit:
    def __init__(self, R, aid, log=print):
        self.R, self.aid, self.log = R, aid, log
        self.name = R.actions[aid]
        q, loc, sc = R.keys(aid)
        self.n = len(q); self.loop = aid in LOOP
        self.q0, self.loc0, self.sc0 = q.copy(), loc.copy(), sc.copy()
        self.q, self.loc, self.sc = q.copy(), loc.copy(), sc.copy()
        self.O = originals(aid, self.name, self.n)
        self.H = [R.horse(aid, i) for i in range(self.n)]
        bi = R.bi
        self.fit_bones = [b for c in CHAINS.values() for b in c]
        # stand pose twist of the upper arms relative to the chest (reference of a natural twist)
        qs, ls, ss = R.keys(4); Ms = R.fk(qs[0], ls[0], ss[0]); Gs = rot_of(Ms)
        self.tw_ref = {s: self.uarm_twist(Gs, s) for s in "LR"}
        self.slide_ref = {s: self.joint_in_chest(Ms, s) for s in "LR"}
        self.uarm_dir_ref = {s: Gs[R.bi["chest"]].T @ Gs[R.bi["upper_arm." + s]][:, 1] for s in "LR"}
        self.tol, self.err2_tol = (HEAD_TOL, HEAD_ERR2_TOL) if aid in HEAD_YAW_ACTIONS else (TOL, ERR2_TOL)
        self.yaw_w = HEAD_YAW_W if aid in HEAD_YAW_ACTIONS else 0.0
        qm, lm, sm = R.keys(25); self.head_yaw_ref = self.head_yaw(rot_of(R.fk(qm[0], lm[0], sm[0])))
        self.fold_setup(); Xs = R.skin(Ms); self.fold_ref = {s: self.fold(Xs, s) for s in "LR"}
        self.has_grip = "weapon1h.R" in R.bi
        if self.has_grip:
            h, w = R.bi["hand.R"], R.bi["weapon1h.R"]
            self.grip_off = np.linalg.inv(R.rest[h]) @ R.rest[w]
            self.grip_T = [self.M(i, orig=True)[w] for i in range(self.n)]
        self.sil0, self.e20 = [], []
        for i in range(self.n):
            S = full_masks(R, self.M(i, orig=True), self.H[i])
            self.sil0.append(float(np.mean([sil_cost(S[d], self.O[i][d]) for d in range(5)])))
            self.e20.append(sum(err2(S[d], self.O[i][d]) for d in range(5)))

    def M(self, i, orig=False):
        if orig: return self.R.fk(self.q0[i], self.loc0[i], self.sc0[i])
        return self.R.fk(self.q[i], self.loc[i], self.sc[i])

    def uarm_twist(self, G, side):
        R = self.R; c, u = R.bi["chest"], R.bi["upper_arm." + side]
        rel = (R.rest[c][:3, :3].T @ R.rest[u][:3, :3]).T @ (G[c].T @ G[u])
        return swing_twist_y(matq(rel))[0]

    def head_yaw(self, G):
        """twist (rad) of the head about the chest's own Y, the rest relation removed (+ = same sense as the head turning against the chest)"""
        R = self.R; c, h = R.bi["chest"], R.bi["head"]
        rel = (R.rest[c][:3, :3].T @ R.rest[h][:3, :3]).T @ (G[c].T @ G[h])
        return swing_twist_y(matq(rel))[0]

    def fold_setup(self):
        R = self.R; T = R.T
        def wsum(names):
            m = np.zeros(len(R.V))
            for b in names: m += (R.W * (R.WB == R.bi[b])).sum(1)
            return m
        from collections import defaultdict
        ef = defaultdict(list)
        for f, t in enumerate(T):
            for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
                ef[(min(a, b), max(a, b))].append(f)
        E = np.array([k for k, v in ef.items() if len(v) == 2]); F = np.array([ef[tuple(k)] for k in E])
        self.fold_E = {}
        for s in "LR":
            reg = (wsum(["upper_arm." + s]) > 0.05) & (wsum(["chest", "spine", "neck"]) > 0.05)
            sel = reg[E].all(1); Fs = F[sel]; tri = np.unique(Fs); remap = {t: j for j, t in enumerate(tri)}
            self.fold_E[s] = (T[tri], np.vectorize(remap.get)(Fs))
            self.fold_E[s] = self.fold_E[s] + (self._dihedral(R.V, s),)

    def _dihedral(self, X, s):
        T, Fl = self.fold_E[s][0], self.fold_E[s][1]
        n = np.cross(X[T[:, 1]] - X[T[:, 0]], X[T[:, 2]] - X[T[:, 0]]); n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
        return np.degrees(np.arccos(np.clip(np.sum(n[Fl[:, 0]] * n[Fl[:, 1]], 1), -1, 1)))

    def fold(self, X, s):
        return float(np.mean(np.clip(self._dihedral(X, s) - self.fold_E[s][2], 0, None)))

    def joint_in_chest(self, M, side):
        """shoulder joint (head of upper_arm) in the chest bone's frame (m): the clavicle does not deform the skin, so this moving is the arm
        sliding along the chest"""
        R = self.R; c, u = R.bi["chest"], R.bi["upper_arm." + side]
        Rc = M[c][:3, :3] / np.linalg.norm(M[c][:3, :3], axis=0)
        return Rc.T @ (M[u][:3, 3] - M[c][:3, 3])

    def set_local_from_arm(self, i, G_target, bones):
        """local quaternions of `bones` (parents first) so that their armature-space orientations become G_target[b] (3x3)"""
        R = self.R; M = self.M(i)
        for b in bones:
            k = R.bi[b]; p = R.parent[k]
            Pm = M[p][:3, :3]
            if R.noscale[k]:
                from pose_lib import ortho_y
                Pm = ortho_y(Pm)
            A = Pm @ R.offset[k][:3, :3]
            U, _, Vt = np.linalg.svd(A); A = U @ Vt                  # rotation part (parents of fitted bones carry no scale)
            self.q[i, k] = matq(A.T @ G_target[b])
            M = R.fk(self.q[i], self.loc[i], self.sc[i], M=M, start=[k])

    # ------------------------------------------------------------------ steps
    def prepare(self):
        R = self.R
        for s in "LR":
            self.loc[:, R.bi["clavicle." + s]] = 0.0
        if HEAD_SCALE:
            self.sc[:, R.bi["head"]] = np.median(R.z["key_scale"][:, R.bi["head"]], 0)
        if SCALE and self.n > 2:
            for b in GIRTH:
                k = R.bi[b]; v = self.sc[:, k].copy()
                for _ in range(SCALE):
                    v = 0.25 * (np.roll(v, 1, 0) + 2 * v + np.roll(v, -1, 0)) if self.loop else \
                        np.concatenate([v[:1], 0.25 * (v[:-2] + 2 * v[1:-1] + v[2:]), v[-1:]])
                self.sc[:, k] = v
        if PASSES and self.n > 2:
            G = np.array([rot_of(self.M(i)) for i in range(self.n)])      # (n, B, 3, 3)
            order = [b for b in R.bones if b in self.fit_bones]
            Gt = {}
            for b in order:
                Qb = matq(G[:, R.bi[b]])
                Qs = smooth_seq(Qb, self.loop, PASSES)
                if not self.loop: Qs = qslerp(Qb, Qs, SMOOTH_ONESHOT)
                Gt[b] = qmat(Qs)
            for i in range(self.n):
                if not self.loop and i in (0, self.n - 1): continue
                self.set_local_from_arm(i, {b: Gt[b][i] for b in order}, order)

    def chain_energy_parts(self, i, M, chain, mids, X=None):
        R = self.R; G = rot_of(M); e = 0.0
        if X is not None and FOLD_W:
            for s in "LR":
                if any(b in chain for b in ("spine", "chest", "clavicle." + s, "upper_arm." + s)):
                    e += FOLD_W * max(0.0, self.fold(X, s) - self.fold_ref[s]) ** 2
        if self.has_grip and "hand.R" in chain and (GRIP_W or GRIP_ROT_W):
            H = M[R.bi["hand.R"]].copy(); H[:3, :3] /= np.linalg.norm(H[:3, :3], axis=0)
            g = H @ self.grip_off; T = self.grip_T[i]
            e += GRIP_W * max(0.0, np.linalg.norm(g[:3, 3] - T[:3, 3]) - GRIP_FREE) ** 2
            Tr = T[:3, :3] / np.linalg.norm(T[:3, :3], axis=0)
            e += GRIP_ROT_W * qangle(matq(g[:3, :3]), matq(Tr)) ** 2
        if self.yaw_w and "head" in chain:
            e += self.yaw_w * max(0.0, abs(self.head_yaw(G) - self.head_yaw_ref) - HEAD_YAW_FREE) ** 2
        for b in chain:
            if mids is not None and b in mids:
                e += LAMBDA * (HEAD_LAMBDA if self.yaw_w and b in ("neck", "head") else 1.0) * BONE_W[b] * qangle(matq(G[R.bi[b]]), mids[b]) ** 2
        for s in "LR":
            if "clavicle." + s in chain:
                ex = max(0.0, np.linalg.norm(self.joint_in_chest(M, s) - self.slide_ref[s]) - SLIDE_FREE)
                e += SLIDE_W * ex ** 2
            if "upper_arm." + s in chain:
                ex = max(0.0, abs(self.uarm_twist(G, s) - self.tw_ref[s]) - TWIST_FREE)
                c, u = R.bi["chest"], R.bi["upper_arm." + s]
                dy = G[c].T @ G[u][:, 1]
                fade = max(0.0, 1 - np.arccos(np.clip(dy @ self.uarm_dir_ref[s], -1, 1)) / TWIST_DOWN)
                e += TWIST_W * fade * ex ** 2
            if "forearm." + s in chain:
                v = swing_twist_y(qnorm(self.q[i, R.bi["forearm." + s]]))[1]
                e += VALGUS_W * v ** 2
        return e

    def mids(self, i, chain):
        if self.n < 3: return None
        R = self.R; n = self.n
        if not self.loop and i in (0, n - 1):
            j = 1 if i == 0 else n - 2                                  # ends: stay close to the neighbour's orientation
            Gj = rot_of(self.M(j)); return {b: matq(Gj[R.bi[b]]) for b in chain}
        Ga, Gb = rot_of(self.M((i - 1) % n)), rot_of(self.M((i + 1) % n))
        return {b: qslerp(matq(Ga[R.bi[b]]), matq(Gb[R.bi[b]]), 0.5) for b in chain}

    def fit_frame(self, i, chain_name):
        R = self.R; chain = CHAINS[chain_name]; ks = [R.bi[b] for b in chain]
        M = self.M(i)
        ev = SilEval(R, self.O[i], self.H[i]); ev.set_base(M, chain)
        mids = self.mids(i, chain)
        base = self.q[i, ks].copy()
        s0, tol = self.sil0[i], self.tol
        root = [R.bi[chain[0]]]

        def pose(x):
            q = self.q[i].copy()
            for j, k in enumerate(ks):
                q[k] = qnorm(qmul(base[j], qexp(x[3 * j:3 * j + 3])))
            return q

        e2_0 = self.e20[i]

        def sil_e2(Mx):
            S = ev.masks(Mx)                                         # also leaves the posed vertices in ev.Xs
            return float(np.mean([sil_cost(S[d], self.O[i][d], ev.OD[d]) for d in range(5)])), sum(err2(S[d], self.O[i][d]) for d in range(5))

        def penal(sv, e2):
            return 50 * max(0.0, sv - s0 - tol) + 0.02 * max(0, e2 - e2_0 - self.err2_tol)

        def energy(x, parts=False):
            q = pose(x); Mx = R.fk(q, self.loc[i], self.sc[i], M=M.copy(), start=root)
            sv, e2 = sil_e2(Mx)
            qs = self.q[i].copy(); self.q[i] = q
            pr = self.chain_energy_parts(i, Mx, chain, mids, ev.Xs)
            self.q[i] = qs
            e = pr + sv + penal(sv, e2)
            return (e, sv, pr, e2) if parts else e

        x0 = np.zeros(3 * len(ks))
        e_start, s_start, p_start, e2_start = energy(x0, True)
        r = minimize(energy, x0, method="Powell", options={"xtol": 1e-3, "ftol": 1e-6, "maxfev": MAXFEV})
        e1, s1, p1, e21 = energy(r.x, True)
        cand = [(e1, s1, p1, e21, pose(r.x)), (e_start, s_start, p_start, e2_start, self.q[i].copy())]
        nfev = int(r.nfev)
        if not (s1 <= s0 + tol and e21 <= e2_0 + self.err2_tol):              # second start: the original keys of the chain
            cur = base.copy(); base[:] = self.q0[i, ks]
            r2 = minimize(energy, x0, method="Powell", options={"xtol": 1e-3, "ftol": 1e-6, "maxfev": MAXFEV})
            e3, s3, p3, e23 = energy(r2.x, True); cand.append((e3, s3, p3, e23, pose(r2.x))); nfev += int(r2.nfev)
            base[:] = cur
        # the original keys of this chain (with the clavicle location removed) as a fallback
        q_or = self.q[i].copy(); q_or[ks] = self.q0[i, ks]
        Mo = R.fk(q_or, self.loc[i], self.sc[i]); so, e2o = sil_e2(Mo)
        qs = self.q[i].copy(); self.q[i] = q_or; po = self.chain_energy_parts(i, Mo, chain, mids, ev.Xs); self.q[i] = qs
        cand.append((po + so + penal(so, e2o), so, po, e2o, q_or))
        feas = [c for c in cand if c[1] <= s0 + tol and c[3] <= e2_0 + self.err2_tol]
        best = min(feas, key=lambda c: c[0]) if feas else min(cand, key=lambda c: c[1] + 0.02 * c[3])
        self.q[i] = best[4]
        return dict(frame=i, chain=chain_name, sil0=round(s0, 5), sil_start=round(s_start, 5), sil=round(best[1], 5), prior_start=round(p_start, 5),
                    prior=round(best[2], 5), err2_0=int(e2_0), err2=int(best[3]), nfev=nfev, feasible=bool(feas))

    def frame_sil(self, i, q, loc):
        S = full_masks(self.R, self.R.fk(q, loc, self.sc[i]), self.H[i])
        return float(np.mean([sil_cost(S[d], self.O[i][d]) for d in range(5)])), sum(err2(S[d], self.O[i][d]) for d in range(5))

    def guard(self):
        """no frame ends worse than the original keys: a frame whose silhouette cost rose by more than TOL or whose >= 2 px errors rose is
        blended back towards the original keys (fitted bones and clavicle location), the largest share of the new pose that passes"""
        R = self.R; ks = [R.bi[b] for b in self.fit_bones]; cl = [R.bi["clavicle.L"], R.bi["clavicle.R"]]
        self.reverted = []
        for i in range(self.n):
            sv, e2 = self.frame_sil(i, self.q[i], self.loc[i])
            if sv <= self.sil0[i] + self.tol and e2 <= self.e20[i] + self.err2_tol: continue
            done = False
            for t in (0.75, 0.5, 0.25, 0.0):
                q = self.q[i].copy(); loc = self.loc[i].copy()
                q[ks] = qslerp(self.q0[i, ks], self.q[i, ks], t); loc[cl] = (1 - t) * self.loc0[i, cl] + t * self.loc[i, cl]
                sv2, e22 = self.frame_sil(i, q, loc)
                if (sv2 <= self.sil0[i] + self.tol and e22 <= self.e20[i] + self.err2_tol) or t == 0.0:
                    self.q[i], self.loc[i] = q, loc; done = True
                    self.reverted.append((i, t)); self.log("guard: frame %d sil %.4f err2 %d -> share %.2f of the new pose: sil %.4f err2 %d (orig %.4f, %d)" %
                                                          (i, sv, e2, t, sv2, e22, self.sil0[i], self.e20[i]))
                    break

    def keep_items(self):
        """item bones (weapons, shield) keep their ORIGINAL armature-space matrices: their local keys are solved under the new hands / forearm"""
        R = self.R
        from pose_lib import ortho_y
        for i in range(self.n):
            T0 = self.M(i, orig=True); M = self.M(i)
            for b in ITEM_BONES:
                if b not in R.bi: continue
                k = R.bi[b]; p = R.parent[k]; T = T0[k]
                if R.noscale[k]:
                    Po = M[p].copy(); Po[:3, :3] = ortho_y(Po[:3, :3])
                    rs = Po @ R.offset[k]; lm = M[p] @ R.offset[k]
                    A = np.linalg.solve(rs[:3, :3], T[:3, :3]) / self.sc[i, k][None, :]
                    U, _, Vt = np.linalg.svd(A); self.q[i, k] = matq(U @ Vt)
                    self.loc[i, k] = np.linalg.solve(lm[:3, :3], T[:3, 3] - lm[:3, 3])
                else:
                    B = np.linalg.solve(M[p] @ R.offset[k], T)
                    A = B[:3, :3] / self.sc[i, k][None, :]
                    U, _, Vt = np.linalg.svd(A); self.q[i, k] = matq(U @ Vt); self.loc[i, k] = B[:3, 3]
            M2 = self.M(i)
            self.item_err = max(getattr(self, "item_err", 0.0), max(np.abs(M2[R.bi[b]] - T0[R.bi[b]]).max() for b in ITEM_BONES if b in R.bi))

    def run(self, sweeps):
        t = time.time(); logs = []
        self.prepare()
        if self.n >= 1:
            for sw in range(sweeps):
                for ch in CHAINS:
                    for i in range(self.n):
                        lg = self.fit_frame(i, ch); lg["sweep"] = sw; logs.append(lg)
                        self.log("a%d sweep %d %s f%d sil %.4f (orig %.4f) err2 %d (orig %d) prior %.4f -> %.4f nfev %d%s" %
                                 (self.aid, sw, ch, i, lg["sil"], lg["sil0"], lg["err2"], lg["err2_0"], lg["prior_start"], lg["prior"], lg["nfev"],
                                  "" if lg["feasible"] else " INFEASIBLE"))
        self.guard()
        self.keep_items()
        self.log("item bones max matrix error %.2e" % self.item_err)
        # final report
        fin = []
        for i in range(self.n):
            S = full_masks(self.R, self.M(i), self.H[i])
            fin.append((float(np.mean([sil_cost(S[d], self.O[i][d]) for d in range(5)])), sum(err2(S[d], self.O[i][d]) for d in range(5)),
                        float(np.mean([(S[d] & self.O[i][d]).sum() / max((S[d] | self.O[i][d]).sum(), 1) for d in range(5)]))))
        S0 = [full_masks(self.R, self.M(i, True), self.H[i]) for i in range(self.n)]
        iou0 = [float(np.mean([(S0[i][d] & self.O[i][d]).sum() / max((S0[i][d] | self.O[i][d]).sum(), 1) for d in range(5)])) for i in range(self.n)]
        rep = dict(action=self.aid, name=self.name, loop=self.loop, seconds=round(time.time() - t, 1),
                   sil0=self.sil0, sil=[f[0] for f in fin], err2_0=self.e20, err2=[f[1] for f in fin], iou0=iou0, iou=[f[2] for f in fin],
                   bones=self.R.bones, q=self.q.tolist(), loc=self.loc.tolist(), scale=self.sc.tolist(), log=logs,
                   item_err=float(self.item_err), reverted=self.reverted,
                   settings=dict(LAMBDA=LAMBDA, ERR2_TOL=ERR2_TOL, HEAD_YAW_ACTIONS=sorted(HEAD_YAW_ACTIONS), HEAD_YAW_W=HEAD_YAW_W, HEAD_LAMBDA=HEAD_LAMBDA, HEAD_YAW_FREE=float(np.degrees(HEAD_YAW_FREE)), HEAD_TOL=HEAD_TOL, HEAD_ERR2_TOL=HEAD_ERR2_TOL, FOLD_W=FOLD_W, GRIP_W=GRIP_W, GRIP_FREE=GRIP_FREE, GRIP_ROT_W=GRIP_ROT_W, SLIDE_W=SLIDE_W, SLIDE_FREE=SLIDE_FREE, TWIST_W=TWIST_W, TWIST_FREE=float(np.degrees(TWIST_FREE)), VALGUS_W=VALGUS_W, TOL=TOL, MAXFEV=MAXFEV,
                                 PASSES=PASSES, SCALE=SCALE, HEAD_SCALE=HEAD_SCALE, sweeps=sweeps))
        return rep


def run_one(args):
    rig_path, aid, out_dir, sweeps = args
    R = Rig(rig_path)
    logf = open(os.path.join(out_dir, "a%02d.log" % aid), "w")
    def log(s): logf.write(s + "\n"); logf.flush()
    f = ActionFit(R, aid, log)
    rep = f.run(sweeps)
    json.dump(rep, open(os.path.join(out_dir, "a%02d.json" % aid), "w"))
    return aid, np.mean(rep["iou0"]), np.mean(rep["iou"]), sum(rep["err2_0"]), sum(rep["err2"]), rep["seconds"]


def main():
    a = sys.argv[1:]
    rig_path, out_dir = os.path.abspath(a.pop(0)), os.path.abspath(a.pop(0))
    o = {"--actions": "", "--jobs": "4", "--sweeps": "2"}
    while a: k = a.pop(0); o[k] = a.pop(0)
    os.makedirs(out_dir, exist_ok=True)
    R = Rig(rig_path)
    acts = [int(x) for x in o["--actions"].split(",")] if o["--actions"] else sorted(R.actions)
    jobs = [(rig_path, aid, out_dir, int(o["--sweeps"])) for aid in acts]
    if int(o["--jobs"]) > 1:
        from multiprocessing import Pool
        with Pool(int(o["--jobs"])) as p:
            for r in p.imap_unordered(run_one, jobs):
                print("action %2d  IoU %.4f -> %.4f  err2 %d -> %d  (%.0f s)" % r, flush=True)
    else:
        for j in jobs:
            print("action %2d  IoU %.4f -> %.4f  err2 %d -> %d  (%.0f s)" % run_one(j), flush=True)


if __name__ == "__main__":
    main()
