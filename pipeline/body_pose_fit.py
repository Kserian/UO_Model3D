"""Silhouette-driven refinement of the POSES of the body (per pose: small corrections of bone rotations / pelvis location / limb scales).

    python body_pose_fit.py pose.npz fk.npz --out corr.npz [--iters 4] [--lam 1.0] [--holdout-dir 3] [--max-rot 0.12] [--scale]

A pose (action, frame) is shared by the 5 directions, so its 5 silhouettes constrain the 3D pose together. For every pose we fit
theta = (rotation vectors of the fitted bones, pelvis location, optionally x/z scale of limb bones) so that the contour of the model moves onto the
contour of the sprites. Same contour constraints as body_shape_fit.py (signed distance of the model contour to the sprite contour along the 2D normal),
Jacobian by finite differences of the forward kinematics (exact for inherit-scale-NONE bones too), damped Gauss-Newton with an absolute ridge (--lam-*, px^2 per rad^2 / m^2) towards the
ORIGINAL pose and a hard cap on the accumulated rotation. The body shape (rest vertices) is not touched. `--holdout-dir d` keeps direction d out of the fit
and reports its IoU: poses that are right in 3D improve there too. Writes corr.npz: for each pose the new loc / quat / scl of every bone.
Needs numpy, scipy, pillow.
"""
import argparse, time
import numpy as np
from scipy.ndimage import distance_transform_edt, map_coordinates, binary_dilation
import body_shape_lib as L
import body_pose_lib as PL
from body_shape_fit import signed_dist, vertex_normals

ROT = ["pelvis", "spine", "chest", "neck", "head", "clavicle.L", "clavicle.R", "upper_arm.L", "upper_arm.R", "forearm.L", "forearm.R", "hand.L", "hand.R",
       "thigh.L", "thigh.R", "shin.L", "shin.R", "foot.L", "foot.R", "toe.L", "toe.R"]
SCALE = ["upper_arm.L", "upper_arm.R", "forearm.L", "forearm.R", "hand.L", "hand.R", "thigh.L", "thigh.R", "shin.L", "shin.R", "foot.L", "foot.R", "head"]


class Params:
    """layout of theta: (kind, bone, axis) with kind r (rotation vector), t (translation of the pelvis), s (log-scale)"""
    def __init__(self, K, scale):
        self.items = [("r", K.idx[n], a) for n in ROT if n in K.idx for a in range(3)] + [("t", K.idx["pelvis"], a) for a in range(3)]
        if scale:
            self.items += [("s", K.idx[n], a) for n in SCALE if n in K.idx for a in (0, 2)]
        self.n = len(self.items)

    def apply(self, K, base, theta):
        loc, quat, scl = [x.copy() for x in base]
        for (k, b, a), v in zip(self.items, theta):
            if k == "r":
                pass
            elif k == "t":
                loc[b, a] += v
            else:
                scl[b, a] *= np.exp(v)
        for b in sorted({b for k, b, a in self.items if k == "r"}):
            w = np.array([v for (k, bb, a), v in zip(self.items, theta) if k == "r" and bb == b])
            quat[b] = PL.qmul(quat[b] / np.linalg.norm(quat[b]), PL.rotvec_to_quat(w))
        return loc, quat, scl


def contour_rows(S, f, M, clip, band, side):
    """contour vertices of frame f for pose matrices M: (idx, n2 (n,2), t (n,) target shift in px, J (2,3))"""
    S.M[f] = M
    m, lab, depth, X, xy, z = L.model_mask(S, f)
    smd = signed_dist(m); sdg = signed_dist(S.G[f])
    pc = np.stack([xy[:, 1] - 0.5, xy[:, 0] - 0.5])
    s_m = map_coordinates(smd, pc, order=1, mode="nearest"); s_g = map_coordinates(sdg, pc, order=1, mode="nearest")
    ix = np.clip(xy[:, 0].astype(int), 0, S.CW - 1); iy = np.clip(xy[:, 1].astype(int), 0, S.CH - 1)
    vis = z <= depth[iy, ix] + 0.03
    if S.hm[f].any():
        vis &= ~binary_dilation(S.hm[f], iterations=2)[iy, ix]
    Xn = vertex_normals(X, S.tris)
    T = S.Vm @ S.MW[f]; view = np.linalg.inv(T)[:3, :3] @ np.array([0, 0, 1.0])
    nz = np.abs(Xn @ view) / np.linalg.norm(view)
    sel = vis & (np.abs(s_m) < band) & (nz < side) & (np.abs(s_g) < 6)
    if not sel.any():
        return None
    idx = np.nonzero(sel)[0]
    gy, gx = np.gradient(smd)
    ny = map_coordinates(gy, pc[:, idx], order=1, mode="nearest"); nx = map_coordinates(gx, pc[:, idx], order=1, mode="nearest")
    nn = np.hypot(nx, ny); good = nn > 1e-6
    idx, nx, ny, nn = idx[good], nx[good], ny[good], nn[good]
    n2 = np.stack([nx, ny], 1) / nn[:, None]
    Pt = (S.Pm @ S.Vm @ S.MW[f])[:2, :3]
    J = np.stack([Pt[0] * 0.5 * S.CW, -Pt[1] * 0.5 * S.CH])
    t = -np.clip(s_g[idx] - s_m[idx], -clip, clip)
    return idx, n2, t, J


def fit_pose(S, K, P, p, frames, theta0, args, hold_frames=()):
    base = (K.loc[p], K.quat[p], K.scl[p])
    theta = theta0.copy(); R4 = np.c_[S.rest, np.ones(S.N)]
    reg = np.array([args.lam_rot if k == "r" else args.lam_t if k == "t" else args.lam_s for k, b, a in P.items])
    cap = np.array([args.max_rot if k == "r" else args.max_t if k == "t" else args.max_s for k, b, a in P.items])
    M0 = {f: S.M[f].copy() for f in frames}
    eps = 1e-4
    def skin(th):
        return K.skin(*P.apply(K, base, th))
    for it in range(args.iters):
        Mc = skin(theta)
        Mp = [skin(theta + eps * np.eye(P.n)[j]) for j in range(P.n)]                     # finite-difference pose matrices
        H = np.zeros((P.n, P.n)); g = np.zeros(P.n); used = 0
        for f in frames:
            r = contour_rows(S, f, Mc, args.clip, args.band, args.side)
            if r is None:
                continue
            idx, n2, t, Jc = r
            Rv = R4[idx]; wi = S.wi[idx]; ww = S.ww[idx]                                     # (n,K)
            X0 = (np.einsum("nkij,nj->nki", Mc[wi], Rv)[..., :3] * ww[..., None]).sum(1)
            A = np.zeros((len(idx), P.n))
            for j in range(P.n):
                Xj = (np.einsum("nkij,nj->nki", Mp[j][wi], Rv)[..., :3] * ww[..., None]).sum(1)
                dX = (Xj - X0) / eps                                                         # (n,3) body-local displacement per unit parameter
                A[:, j] = np.einsum("nc,cd,nd->n", n2, Jc, dX)
            H += A.T @ A; g += A.T @ t; used += len(idx)
        if used == 0:
            break
        step = np.linalg.solve(H + np.diag(reg) + 1e-9 * np.eye(P.n), g - reg * theta)
        theta = np.clip(theta + args.damp * step, -cap, cap)
    for f in frames:
        S.M[f] = M0[f]
    return theta


def score_poses(S, K, P, thetas, poses, frames_of, mask=None):
    """mean IoU over frames of the given poses with thetas applied"""
    ious = []
    for p in poses:
        base = (K.loc[p], K.quat[p], K.scl[p]); M = K.skin(*P.apply(K, base, thetas[p]))
        for f in frames_of[p]:
            old = S.M[f].copy(); S.M[f] = M
            m = L.model_mask(S, f)[0]; g = S.G[f]; S.M[f] = old
            ious.append((m & g).sum() / max((m | g).sum(), 1))
    return float(np.mean(ious))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("pose"); ap.add_argument("fk"); ap.add_argument("--out"); ap.add_argument("--iters", type=int, default=4)
    ap.add_argument("--lam-rot", type=float, default=3000.0); ap.add_argument("--lam-t", type=float, default=3e6); ap.add_argument("--lam-s", type=float, default=3e4)
    ap.add_argument("--max-rot", type=float, default=0.12); ap.add_argument("--max-t", type=float, default=0.03); ap.add_argument("--max-s", type=float, default=0.1)
    ap.add_argument("--scale", action="store_true"); ap.add_argument("--damp", type=float, default=0.7); ap.add_argument("--clip", type=float, default=2.0)
    ap.add_argument("--band", type=float, default=1.0); ap.add_argument("--side", type=float, default=0.6); ap.add_argument("--holdout-dir", type=int, default=-1)
    ap.add_argument("--bones", type=str, default="", help="comma list: restrict the fitted rotation bones (pelvis loc stays unless --no-loc)"); ap.add_argument("--no-loc", action="store_true")
    ap.add_argument("--poses", type=str, default="", help="subset lo:hi[:step] of pose indices")
    a = ap.parse_args()
    S = L.Scene(a.pose); K = PL.FK(a.fk)
    if a.bones:
        ROT[:] = [n for n in a.bones.split(",") if n in K.idx]
    P = Params(K, a.scale)
    if a.no_loc:
        P.items = [it for it in P.items if it[0] != "t"]; P.n = len(P.items)
    assert K.bones == S.bones
    frames_of = {}
    for f, (act, d, i) in enumerate(S.key):
        if S.ok[f]:
            frames_of.setdefault(K.pose_index[(int(act), int(i))], []).append(f)
    poses = sorted(frames_of)
    if a.poses:
        lo, hi, st = ([int(x) for x in a.poses.split(":")] + [1])[:3]; poses = [p for p in poses if lo <= p < hi and (p - lo) % st == 0]
    thetas = {p: np.zeros(P.n) for p in range(len(K.key))}
    fit_frames = {p: [f for f in frames_of[p] if S.key[f][1] != a.holdout_dir] for p in poses}
    hold_frames = {p: [f for f in frames_of[p] if S.key[f][1] == a.holdout_dir] for p in poses}
    print("params per pose:", P.n, " poses:", len(poses), flush=True)
    t0 = time.time()
    sc0_fit = score_poses(S, K, P, thetas, poses, fit_frames); sc0_hold = score_poses(S, K, P, thetas, poses, hold_frames) if a.holdout_dir >= 0 else float("nan")
    print("start: fit-dirs IoU %.4f  hold-out dir IoU %.4f" % (sc0_fit, sc0_hold), flush=True)
    for n, p in enumerate(poses):
        thetas[p] = fit_pose(S, K, P, p, fit_frames[p], thetas[p], a)
        if n % 20 == 19:
            print("  pose %d/%d  %.0fs" % (n + 1, len(poses), time.time() - t0), flush=True)
    sc1_fit = score_poses(S, K, P, thetas, poses, fit_frames); sc1_hold = score_poses(S, K, P, thetas, poses, hold_frames) if a.holdout_dir >= 0 else float("nan")
    allf = {p: frames_of[p] for p in poses}
    print("end:   fit-dirs IoU %.4f  hold-out dir IoU %.4f  all %.4f -> %.4f" % (sc1_fit, sc1_hold, score_poses(S, K, P, {p: np.zeros(P.n) for p in thetas}, poses, allf), score_poses(S, K, P, thetas, poses, allf)), flush=True)
    rot = np.array([[np.linalg.norm(thetas[p][3 * i:3 * i + 3]) for i in range(len([1 for k, b, aa in P.items if k == "r"]) // 3)] for p in poses])
    print("mean |rot| deg per bone:", dict(zip(ROT, np.degrees(rot.mean(0)).round(2))))
    if a.out:
        loc = np.zeros_like(K.loc); quat = np.zeros_like(K.quat); scl = np.zeros_like(K.scl)
        for p in range(len(K.key)):
            loc[p], quat[p], scl[p] = P.apply(K, (K.loc[p], K.quat[p], K.scl[p]), thetas[p])
        np.savez_compressed(a.out, loc=loc, quat=quat, scl=scl, key=K.key, theta=np.array([thetas[p] for p in range(len(K.key))]), bones=np.array(K.bones))


if __name__ == "__main__":
    main()
