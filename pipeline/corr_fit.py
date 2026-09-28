"""Per-frame corrective shapes: rest-space vertex offsets D (a Blender shape key per UO frame) so that the
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
POSES = sys.argv[sys.argv.index("--poses") + 1]
OUT = sys.argv[sys.argv.index("--out") + 1]
ACTS = [int(a) for k, a in enumerate(sys.argv[1:], 1) if a.isdigit() and sys.argv[k - 1] not in ("--poses", "--out")]
ITERS = int(os.environ.get("UO_CITERS", "400"))
ROUNDS = int(os.environ.get("UO_CROUNDS", "3"))
SUP = 4
VIEWS = [int(v) for v in os.environ.get("UO_CVIEWS", "0,1,2,3,4").split(",")]
NT = 700                       # max boundary targets per view
NR = 64                        # max repel points per view
NC = 1400                      # max candidate (near-boundary) vertices per view for the reach term
P = pickle.load(open(POSES, "rb"))
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


res = pickle.load(open(OUT, "rb")) if os.path.exists(OUT) else {}
for a in ACTS:
    T = targets(a); F = len(T); M = T[..., 3] > 127
    hid = (horse_masks(a, F) & ~M) if a in HORSE_OF else np.zeros_like(M)
    mounted = jnp.asarray(a in HORSE_OF)
    for i in range(F):
        t0 = time.time()
        pp = {k: jnp.asarray(v[i]) for k, v in P[a]["poses"].items()}
        sdf_r = jnp.asarray(np.stack([sdf_sq(M[i, d]) for d in range(5)]))
        sdf_a = jnp.asarray(np.stack([sdf_sq(M[i, d] | hid[i, d]) for d in range(5)]))
        tg = np.zeros((5, NT, 2), np.float32); tm = np.zeros((5, NT), np.float32)
        for d in range(5):
            t = targets_of(M[i, d], hid[i, d])
            if len(t) > NT:
                t = t[np.linspace(0, len(t) - 1, NT).astype(int)]
            tg[d, :len(t)] = t; tm[d, :len(t)] = 1
        rp = np.zeros((5, NR, 2), np.float32); rm = np.zeros((5, NR), np.float32)
        r0, b0, area, _ = raster_check(np.zeros((NV, 3)), pp, M[i], hid[i])
        Dpx = jnp.zeros((NV, 3), jnp.float32)
        for rnd in range(ROUNDS):
            Xc = np.asarray(posed_with(pp, V0 + Dpx / 36.0))
            cand = np.zeros((5, NC), np.int32); cmask = np.zeros((5, NC), np.float32)
            for d in range(5):
                pc = np.asarray(project(jnp.asarray(Xc), d))
                sd = np.asarray(bilin(sdf_r[d], jnp.asarray(pc)))
                idx = np.nonzero(np.abs(sd) < 4.0)[0]
                if len(idx) > NC:
                    idx = idx[np.argsort(np.abs(sd[idx]))[:NC]]
                cand[d, :len(idx)] = idx; cmask[d, :len(idx)] = 1
            opt = optax.adam(optax.exponential_decay(0.05, ITERS, 0.2)); st = opt.init(Dpx)
            args = (pp, sdf_r, sdf_a, jnp.asarray(tg), jnp.asarray(tm), jnp.asarray(rp), jnp.asarray(rm), 5.0, mounted,
                    jnp.asarray(cand), jnp.asarray(cmask))
            for it in range(ITERS):
                (l, aux), g = vg(Dpx, *args)
                up, st = opt.update(g, st, Dpx); Dpx = optax.apply_updates(Dpx, up)
            r1, b1, _, bpts = raster_check(np.asarray(Dpx), pp, M[i], hid[i])
            if r1 + b1 == 0 or rnd == ROUNDS - 1:
                break
            for d in range(5):                       # remember offending pixel centres, keep previous ones too
                old = rp[d][rm[d] > 0]
                allp = np.concatenate([old, bpts[d]], 0)[:NR]
                rp[d] = 0; rm[d] = 0; rp[d, :len(allp)] = allp; rm[d, :len(allp)] = 1
        res = pickle.load(open(OUT, "rb")) if os.path.exists(OUT) else {}
        res[(a, i)] = dict(D=(np.asarray(Dpx) / 36.0).astype(np.float32), before=(int(r0), int(b0)), after=(int(r1), int(b1)),
                           area=int(area))
        pickle.dump(res, open(OUT, "wb"))
        print(f"a{a:2d} f{i}: missing {r0:4d} -> {r1:3d}   outside {b0:4d} -> {b1:3d}   (area {area}, "
              f"IoU {1-(r0+b0)/(area+b0):.3f} -> {1-(r1+b1)/(area+b1):.3f})  max|D| {np.abs(np.asarray(Dpx)).max():.2f}px  "
              f"rounds {rnd+1}  {time.time()-t0:.0f}s", flush=True)
