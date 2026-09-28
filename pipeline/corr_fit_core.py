"""(library version of corr_fit.py) Per-frame corrective shapes: rest-space vertex offsets D (a Blender shape key per UO frame) so that the
rasterised silhouette (pixel centre rule) in all 5 UO views equals the sprite: nothing outside, nothing missing.

Loss per view (px units):
  inside : every projected vertex lies inside the pixel-square union of the sprite (signed distance, margin)
  reach  : every outward pixel side of the sprite (its midpoint) has a projected vertex within ~0.3 px
  repel  : after a raster check, vertices are pushed away from pixel centres the model covers but the sprite lacks
  reg    : Laplacian smoothness and magnitude of D
Poses are fixed (final pose file). usage: python corr_fit.py 4 0 9 --poses final_poses_v10.pkl --out corr_A.pkl"""
import sys, os, time, pickle
import numpy as np
import jax, jax.numpy as jnp, optax
from scipy.ndimage import distance_transform_edt
os.environ.setdefault("UO_DELTA", "refine_infl.pkl")
from posefit_mesh import (md, pose_from_params, fk, S, W, P0, BONE_JOINT, project, tris, targets, horse_masks, HORSE_OF,
                          LEGV, CANVAS_W, CANVAS_H, raster_vec, V0, JI)
ITERS = int(os.environ.get("UO_CITERS", "400"))
ROUNDS = int(os.environ.get("UO_CROUNDS", "3"))
SUP = 4
VIEWS = [int(v) for v in os.environ.get("UO_CVIEWS", "0,1,2,3,4").split(",")]
NT = 700                       # max boundary targets per view
NR = 64                        # max repel points per view
NC = 1400                      # max candidate (near-boundary) vertices per view for the reach term
NV = V0.shape[0]
ARM_L = jnp.asarray([JI[j] for j in ()]) if False else None
E = set()
for f in md["faces"]:
    for a_, b_ in zip(f, f[1:] + f[:1]):
        E.add((min(a_, b_), max(a_, b_)))
E = np.array(sorted(E))
deg = jnp.asarray(np.maximum(np.bincount(E.ravel(), minlength=NV), 1).astype(np.float32))
EI, EJ = jnp.asarray(E[:, 0]), jnp.asarray(E[:, 1])
import posefit_mesh as PM


def posed_with(pp, V):
    pose = pose_from_params(pp)
    Pj, R = fk(S, pose)
    Rb = R[BONE_JOINT]
    tb = Pj[BONE_JOINT] - jnp.einsum("bij,bj->bi", Rb, P0[BONE_JOINT])
    if "clav" in pp:
        Rc = R[JI["chest"]]
        tb = tb + PM.ARM_L[:, None] * (Rc @ pp["clav"][0])[None] + PM.ARM_R[:, None] * (Rc @ pp["clav"][1])[None]
    X = jnp.einsum("bij,vj->vbi", Rb, V) + tb[None]
    return jnp.einsum("vb,vbi->vi", W, X)


def sdf_sq(mask):
    """signed distance (px, + outside) to the boundary of the union of pixel squares, sampled on a SUPx grid"""
    m4 = np.kron(mask, np.ones((SUP, SUP), bool))
    return ((distance_transform_edt(~m4) - distance_transform_edt(m4)) / SUP).astype(np.float32)


def bilin(img, p):
    x = jnp.clip(p[:, 0] * SUP - 0.5, 0, img.shape[1] - 1.001); y = jnp.clip(p[:, 1] * SUP - 0.5, 0, img.shape[0] - 1.001)
    x0 = jnp.floor(x).astype(int); y0 = jnp.floor(y).astype(int); fx, fy = x - x0, y - y0
    return (img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x0 + 1] * fx * (1 - fy) + img[y0 + 1, x0] * (1 - fx) * fy
            + img[y0 + 1, x0 + 1] * fx * fy)


def targets_of(mask, unknown):
    pts = []
    H_, W_ = mask.shape
    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        nb = np.zeros_like(mask); nbu = np.zeros_like(mask)
        ys, xs = np.nonzero(mask)
        ny, nx = ys + dy, xs + dx
        ok = (ny >= 0) & (ny < H_) & (nx >= 0) & (nx < W_)
        outside = np.ones(len(ys), bool); outside[ok] = ~mask[ny[ok], nx[ok]]
        hid = np.zeros(len(ys), bool); hid[ok] = unknown[ny[ok], nx[ok]]
        sel = outside & ~hid
        pts.append(np.stack([xs[sel] + 0.5 + 0.5 * dx, ys[sel] + 0.5 + 0.5 * dy], 1))
    return np.concatenate(pts, 0).astype(np.float32)


def loss_fn(Dpx, pp, sdf_r, sdf_a, tg, tm, rp, rm, w_rep, mounted, cand, cmask):
    D = Dpx / 36.0
    X = posed_with(pp, V0 + D)
    lin = 0.0; lcov = 0.0; lrep = 0.0
    for d in VIEWS:
        p = project(X, d)
        s = jnp.where(LEGV & mounted, bilin(sdf_a[d], p), bilin(sdf_r[d], p))
        lin += jnp.mean(jax.nn.relu(s + 0.08) ** 2) * 50.0 + jnp.max(jax.nn.relu(s + 0.08)) * 0.5
        pc = p[cand[d]] + (1.0 - cmask[d])[:, None] * 1e4          # padded candidates pushed far away
        dist = jnp.sqrt(jnp.min(jnp.sum((tg[d][:, None, :] - pc[None, :, :]) ** 2, -1), 1) + 1e-9)
        lcov += jnp.sum(tm[d] * jax.nn.relu(dist - 0.3) ** 2) / (jnp.sum(tm[d]) + 1.0) * 20.0
        dr = jnp.sqrt(jnp.sum((rp[d][:, None, :] - pc[None, :, :]) ** 2, -1) + 1e-9)
        lrep += jnp.sum(rm[d][:, None] * jax.nn.relu(0.8 - dr) ** 2) * w_rep
    lap = Dpx - (jax.ops.segment_sum(Dpx[EJ], EI, NV) + jax.ops.segment_sum(Dpx[EI], EJ, NV)) / deg[:, None]
    reg = jnp.sum(lap ** 2) * float(os.environ.get("UO_CLAP", "0.05")) + jnp.sum(Dpx ** 2) * 0.0005
    return lin + lcov + lrep + reg, (lin, lcov, lrep)


vg = jax.jit(jax.value_and_grad(loss_fn, has_aux=True))


def raster_check(Dpx, pp, masks, unknown):
    X = posed_with(pp, V0 + jnp.asarray(Dpx) / 36.0)
    red = blue = area = 0; blue_pts = []
    for d in range(5):
        if d not in VIEWS:
            blue_pts.append(np.zeros((0, 2), np.float32)); continue
        mk = raster_vec(np.asarray(project(X, d))[tris], CANVAS_W, CANVAS_H) & ~unknown[d]
        s = masks[d]
        b = mk & ~s; r = s & ~mk
        red += r.sum(); blue += b.sum(); area += s.sum()
        ys, xs = np.nonzero(b); blue_pts.append(np.stack([xs + 0.5, ys + 0.5], 1).astype(np.float32))
    return red, blue, area, blue_pts




def frame_data(Mi, hidi):
    sdf_r = jnp.asarray(np.stack([sdf_sq(Mi[d]) for d in range(5)]))
    sdf_a = jnp.asarray(np.stack([sdf_sq(Mi[d] | hidi[d]) for d in range(5)]))
    tg = np.zeros((5, NT, 2), np.float32); tm = np.zeros((5, NT), np.float32)
    for d in range(5):
        t = targets_of(Mi[d], hidi[d])
        if len(t) > NT:
            t = t[np.linspace(0, len(t) - 1, NT).astype(int)]
        tg[d, :len(t)] = t; tm[d, :len(t)] = 1
    return sdf_r, sdf_a, jnp.asarray(tg), jnp.asarray(tm)


def candidates(pp, Dpx, sdf_r):
    Xc = np.asarray(posed_with(pp, V0 + Dpx / 36.0))
    cand = np.zeros((5, NC), np.int32); cmask = np.zeros((5, NC), np.float32)
    for d in range(5):
        pc = np.asarray(project(jnp.asarray(Xc), d))
        sd = np.asarray(bilin(sdf_r[d], jnp.asarray(pc)))
        idx = np.nonzero(np.abs(sd) < 4.0)[0]
        if len(idx) > NC:
            idx = idx[np.argsort(np.abs(sd[idx]))[:NC]]
        cand[d, :len(idx)] = idx; cmask[d, :len(idx)] = 1
    return jnp.asarray(cand), jnp.asarray(cmask)


# ---- pixel-level (raster-aligned) helpers used by stages 3 and 4
NP = 512                                               # max (pixel, triangle) pairs per view
TRI = jnp.asarray(tris)


def bary_min(p, t, c):
    """min barycentric coordinate of point c in projected triangle t (p: projected vertices)"""
    A, B, C = p[TRI[t, 0]], p[TRI[t, 1]], p[TRI[t, 2]]
    den = (B[:, 1] - C[:, 1]) * (A[:, 0] - C[:, 0]) + (C[:, 0] - B[:, 0]) * (A[:, 1] - C[:, 1])
    den = jnp.where(jnp.abs(den) < 1e-6, 1e-6, den)
    l0 = ((B[:, 1] - C[:, 1]) * (c[:, 0] - C[:, 0]) + (C[:, 0] - B[:, 0]) * (c[:, 1] - C[:, 1])) / den
    l1 = ((C[:, 1] - A[:, 1]) * (c[:, 0] - C[:, 0]) + (A[:, 0] - C[:, 0]) * (c[:, 1] - C[:, 1])) / den
    return jnp.minimum(jnp.minimum(l0, l1), 1 - l0 - l1)



def raster_ids(P2):
    """per pixel centre: list of covering triangle ids (all layers)"""
    cover = {}
    mn = np.floor(P2.min(1)).astype(int); mx = np.ceil(P2.max(1)).astype(int)
    A, B, C = P2[:, 0], P2[:, 1], P2[:, 2]
    den = (B[:, 1] - C[:, 1]) * (A[:, 0] - C[:, 0]) + (C[:, 0] - B[:, 0]) * (A[:, 1] - C[:, 1])
    ok = np.abs(den) > 1e-12; size = np.clip(mx - mn, 0, 16)
    ids = []
    for dy in range(int(size[:, 1].max()) + 1):
        for dx in range(int(size[:, 0].max()) + 1):
            t = np.nonzero(ok & (dx <= size[:, 0]) & (dy <= size[:, 1]))[0]
            px = mn[t, 0] + dx; py = mn[t, 1] + dy; cx, cy = px + 0.5, py + 0.5
            l0 = ((B[t, 1] - C[t, 1]) * (cx - C[t, 0]) + (C[t, 0] - B[t, 0]) * (cy - C[t, 1])) / den[t]
            l1 = ((C[t, 1] - A[t, 1]) * (cx - C[t, 0]) + (A[t, 0] - C[t, 0]) * (cy - C[t, 1])) / den[t]
            k = (l0 >= -1e-4) & (l1 >= -1e-4) & (1 - l0 - l1 >= -1e-4) & (px >= 0) & (py >= 0) & (px < CANVAS_W) & (py < CANVAS_H)
            ids.append(np.stack([py[k], px[k], t[k]], 1))
    return np.concatenate(ids, 0)


def pairs_for(P2, s, unknown):
    """exclusion pairs (blue pixel, covering triangle) and inclusion pairs (red pixel, nearest triangle)"""
    ids = raster_ids(P2)
    cov = np.zeros(s.shape, bool); cov[ids[:, 0], ids[:, 1]] = True; cov &= ~unknown
    blue = cov & ~s; red = s & ~cov
    sel = blue[ids[:, 0], ids[:, 1]]
    ex = ids[sel]
    ex_c = np.stack([ex[:, 1] + 0.5, ex[:, 0] + 0.5], 1); ex_t = ex[:, 2]
    ry, rx = np.nonzero(red)
    cen = P2.mean(1)
    in_t = np.array([np.argmin(((cen - [x + 0.5, y + 0.5]) ** 2).sum(1)) for y, x in zip(ry, rx)], int)
    in_c = np.stack([rx + 0.5, ry + 0.5], 1) if len(rx) else np.zeros((0, 2))
    return (ex_t, ex_c), (in_t, in_c), int(blue.sum()), int(red.sum())


def pad(t, c):
    tt = np.zeros(NP, np.int32); cc = np.zeros((NP, 2), np.float32); mm = np.zeros(NP, np.float32)
    n = min(len(t), NP); tt[:n] = t[:n]; cc[:n] = c[:n]; mm[:n] = 1
    return tt, cc, mm


