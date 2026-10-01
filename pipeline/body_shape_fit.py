"""Silhouette-driven refinement of the REST shape of the body (displacement D of the rest vertices, shared by all frames).

    python body_shape_fit.py pose.npz --out D.npz [--iters 4] [--lam 30] [--mu 1] [--holdout 5]

Poses stay as they are. For every frame the contour vertices of the model (projected within 1 px of the model silhouette, facing sideways)
are compared with the sprite silhouette: signed distance s (px) of the vertex to the sprite contour. Each (vertex, frame) gives one linear
constraint on the rest displacement d_v:  g . d_v = -s  with g = A^T J^T n (A: skinning linear part, J: camera Jacobian, n: 2D outward normal).
The per-vertex normal equations are solved together with a mesh-Laplacian smoothness + small-norm prior (sparse solve). Frames of the
hold-out actions (action % holdout == 2) are not used for the fit and only scored. Needs numpy, scipy, pillow.
"""
import argparse, sys, time
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spl
from scipy.ndimage import distance_transform_edt, map_coordinates
import body_shape_lib as L


def signed_dist(m):
    """signed distance (px) from pixel centres to the contour of mask m (positive outside)"""
    if not m.any():
        return np.full(m.shape, 50.0)
    return np.where(m, -(distance_transform_edt(m) - 0.5), distance_transform_edt(~m) - 0.5)


def vertex_normals(X, tris):
    n = np.cross(X[tris[:, 1]] - X[tris[:, 0]], X[tris[:, 2]] - X[tris[:, 0]])
    out = np.zeros_like(X)
    for k in range(3):
        np.add.at(out, tris[:, k], n)
    return out / np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-12)


def laplacian(N, tris, rest=None, floor=0.005):
    """graph Laplacian; with `rest` the edges are weighted 1/length (floor 5 mm): short edges (eyes, mouth, fingers) hold their vertices together"""
    E = np.sort(np.concatenate([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]]), 1)
    E = np.unique(E, axis=0)
    w = np.ones(len(E)) if rest is None else 0.02 / np.maximum(np.linalg.norm(rest[E[:, 0]] - rest[E[:, 1]], axis=1), floor)
    A = sp.coo_matrix((w, (E[:, 0], E[:, 1])), shape=(N, N)); A = A + A.T
    return sp.diags(np.asarray(A.sum(1)).ravel()) - A


def mesh_report(S, D):
    """rest mesh quality after D: flipped faces and edge-length ratio percentiles"""
    t, r0, r1 = S.tris, S.rest, S.rest + D
    fn = lambda X: (lambda n: n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12))(np.cross(X[t[:, 1]] - X[t[:, 0]], X[t[:, 2]] - X[t[:, 0]]))
    flips = int(((fn(r0) * fn(r1)).sum(1) < 0).sum())
    E = np.unique(np.sort(np.concatenate([t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]]]), 1), axis=0)
    ratio = np.linalg.norm(r1[E[:, 0]] - r1[E[:, 1]], axis=1) / np.maximum(np.linalg.norm(r0[E[:, 0]] - r0[E[:, 1]], axis=1), 1e-9)
    return flips, np.percentile(ratio, [0, 1, 99, 100])


def repair_flips(S, D, passes=12):
    """halve the displacement of the vertices of faces that the displacement flips (thumb, toes: tiny faces), until none is left"""
    t, r0 = S.tris, S.rest
    fn = lambda X: (lambda n: n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12))(np.cross(X[t[:, 1]] - X[t[:, 0]], X[t[:, 2]] - X[t[:, 0]]))
    n0 = fn(r0); D = D.copy()
    for _ in range(passes):
        bad = np.nonzero((n0 * fn(r0 + D)).sum(1) < 0.1)[0]
        if not len(bad):
            break
        D[np.unique(t[bad])] *= 0.5
    return D


def constraints(S, D, frames, clip=2.0, band=1.0, side=0.6, verbose=False):
    """normal equations H (N,3,3), b (N,3) from the contour vertices of `frames`"""
    H = np.zeros((S.N, 3, 3)); b = np.zeros((S.N, 3)); cnt = np.zeros(S.N)
    for f in frames:
        m, lab, depth, X, xy, z = L.model_mask(S, f, D)
        smd = signed_dist(m); sdg = signed_dist(S.G[f])
        pc = np.stack([xy[:, 1] - 0.5, xy[:, 0] - 0.5])                    # map_coordinates wants (row, col) in pixel-centre index space
        s_m = map_coordinates(smd, pc, order=1, mode="nearest"); s_g = map_coordinates(sdg, pc, order=1, mode="nearest")
        ix = np.clip(xy[:, 0].astype(int), 0, S.CW - 1); iy = np.clip(xy[:, 1].astype(int), 0, S.CH - 1)
        vis = z <= depth[iy, ix] + 0.03
        if S.hm[f].any():                                                  # near the horse the contour is the horse's, not the body's
            from scipy.ndimage import binary_dilation
            vis &= ~binary_dilation(S.hm[f], iterations=2)[iy, ix]
        Xn = vertex_normals(X, S.tris)
        # camera forward axis in body-local space: nz = normal . view
        T = S.Vm @ S.MW[f]; view = np.linalg.inv(T)[:3, :3] @ np.array([0, 0, 1.0])
        nz = np.abs(Xn @ view) / np.linalg.norm(view)
        sel = vis & (np.abs(s_m) < band) & (nz < side) & (np.abs(s_g) < 6)
        if not sel.any():
            continue
        idx = np.nonzero(sel)[0]
        # 2D outward normal from the gradient of the model sdf
        gy, gx = np.gradient(smd)
        ny = map_coordinates(gy, pc[:, idx], order=1, mode="nearest"); nx = map_coordinates(gx, pc[:, idx], order=1, mode="nearest")
        nn = np.hypot(nx, ny); good = nn > 1e-6
        idx, nx, ny, nn = idx[good], nx[good], ny[good], nn[good]
        n2 = np.stack([nx, ny], 1) / nn[:, None]
        # Jacobian of pixel position wrt body-local position: orthographic -> constant 2x3 (take it from the projection matrix)
        Pt = (S.Pm @ S.Vm @ S.MW[f])[:2, :3]; Pw = (S.Pm @ S.Vm @ S.MW[f])[3, :3]
        # orthographic: w = 1, so xy = ((Pt X + t)+1)/2 * (CW, -CH) ...
        J = np.stack([Pt[0] * 0.5 * S.CW, -Pt[1] * 0.5 * S.CH])             # (2,3) px per metre of body-local displacement
        A = S.linear(f)[idx]                                               # (n,3,3)
        g = np.einsum("nk,ki,nij->nj", n2, J, A)                           # (n,3): px of contour shift per metre of rest displacement
        t = -np.clip(s_g[idx] - s_m[idx], -clip, clip)                     # outward shift (px) that moves the model contour onto the sprite contour
        w = 1.0
        H[idx] += w * g[:, :, None] * g[:, None, :]; b[idx] += w * (g * (t + np.einsum("nj,nj->n", g, D[idx]))[:, None])
        cnt[idx] += 1
    return H, b, cnt


def solve_normal(S, H, b, lam, mu, Lap, n):
    """displacement along the rest normal only: d_v = s_v n_v, scalar field s (a mesh can't tear or fold much when vertices only slide out / in)"""
    Hs = np.einsum("ni,nij,nj->n", n, H, n); bs = np.einsum("ni,ni->n", n, b)
    s = spl.spsolve((sp.diags(Hs) + lam * Lap + mu * sp.identity(S.N)).tocsc(), bs)
    return s[:, None] * n


def solve(S, H, b, lam, mu, Lap, bilap=False):
    N = S.N
    cols = np.repeat(np.arange(3 * N).reshape(N, 3)[:, None, :], 3, 1).ravel()
    rows = np.repeat(np.arange(3 * N).reshape(N, 3)[:, :, None], 3, 2).ravel()
    Hs = sp.coo_matrix((H.ravel(), (rows, cols)), shape=(3 * N, 3 * N)).tocsc()
    Lm = (Lap.T @ Lap) / 8.0 if bilap else Lap                  # bilap: penalises the roughness of D (bending), /8 ~ mean degree^2/... scale
    K = sp.kron(Lm, sp.identity(3)).tocsc()
    Aff = Hs + lam * K + mu * sp.identity(3 * N)
    return spl.spsolve(Aff.tocsc(), b.ravel()).reshape(N, 3)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("pose"); ap.add_argument("--out"); ap.add_argument("--iters", type=int, default=3)
    ap.add_argument("--lam", type=float, default=30.0); ap.add_argument("--mu", type=float, default=1.0); ap.add_argument("--holdout", type=int, default=5)
    ap.add_argument("--weighted", action="store_true", help="edge weights 1/length in the smoothness term"); ap.add_argument("--bilap", action="store_true"); ap.add_argument("--normal", action="store_true", help="displace along the rest normal only"); ap.add_argument("--holdout-dir", type=int, default=-1); ap.add_argument("--clip", type=float, default=2.0); ap.add_argument("--maxd", type=float, default=0.04)
    a = ap.parse_args()
    S = L.Scene(a.pose); Lap = laplacian(S.N, S.tris, S.rest if a.weighted else None); RN = vertex_normals(S.rest, S.tris)
    act = S.key[:, 0]
    hk = (act % a.holdout == 2) if a.holdout > 0 else np.zeros(len(act), bool)
    test = np.nonzero(S.ok & hk)[0]; train = np.nonzero(S.ok & ~hk)[0]
    if a.holdout_dir >= 0:                                    # stricter test: a whole direction (a view never used by the fit)
        test = np.nonzero(S.ok & (S.key[:, 1] == a.holdout_dir))[0]; train = np.nonzero(S.ok & (S.key[:, 1] != a.holdout_dir))[0]
    if a.holdout <= 0:                                        # final fit: all frames (the 'test' numbers are then in-sample)
        test = train
    D = np.zeros((S.N, 3))
    r0 = L.score(S, D, test); r1 = L.score(S, D, train)
    print("start: train IoU %.4f  test IoU %.4f" % (r1["iou"], r0["iou"]), flush=True)
    for it in range(a.iters):
        t0 = time.time()
        H, b, cnt = constraints(S, D, train, clip=a.clip)
        Dn = solve_normal(S, H, b, a.lam, a.mu, Lap, RN) if a.normal else solve(S, H, b, a.lam, a.mu, Lap, a.bilap)
        nrm = np.linalg.norm(Dn, axis=1); sc = np.minimum(1.0, a.maxd / np.maximum(nrm, 1e-12)); D = repair_flips(S, Dn * sc[:, None])
        r0 = L.score(S, D, test); r1 = L.score(S, D, train)
        print("iter %d: constrained verts %d  |D| mean %.4f max %.4f m  train IoU %.4f (out %.1f miss %.1f)  test IoU %.4f (out %.1f miss %.1f)  %.0fs" %
              (it, (cnt > 0).sum(), nrm.mean(), nrm.max(), r1["iou"], r1["outside"], r1["missing"], r0["iou"], r0["outside"], r0["missing"], time.time() - t0), flush=True)
        fl, er = mesh_report(S, D)
        print("   mesh: flipped faces %d  edge ratio min %.2f p1 %.2f p99 %.2f max %.2f" % ((fl,) + tuple(er)), flush=True)
        if a.out:
            np.savez_compressed(a.out, D=D)


if __name__ == "__main__":
    main()
