"""Stage 3: pixel-level refinement of the per-frame corrections, aligned with the rasteriser (pixel-centre rule).
Every pixel the model covers but the sprite lacks pushes EACH covering triangle off that pixel centre (barycentric
exclusion); every sprite pixel the model misses pulls its nearest triangle over the pixel centre (inclusion).
Stage-1 terms keep the rest in place. Starts from a previous corrections file (UO_CINIT).
usage: UO_CINIT=corr_all.pkl python corr_fit3.py 4 0 --poses final_poses_v10.pkl --out corr3_A.pkl"""
import sys, os, time, pickle
import numpy as np
import jax, jax.numpy as jnp, optax
os.environ.setdefault("UO_DELTA", "refine_infl.pkl")
sys.argv_saved = list(sys.argv)
from posefit_mesh import (md, pose_from_params, fk, S, W, P0, BONE_JOINT, project, tris, targets, horse_masks, HORSE_OF,
                          LEGV, CANVAS_W, CANVAS_H, V0, JI)
import posefit_mesh as PM
import corr_fit_core as CF

POSES = sys.argv[sys.argv.index("--poses") + 1]
OUT = sys.argv[sys.argv.index("--out") + 1]
ACTS = [int(a) for k, a in enumerate(sys.argv[1:], 1) if a.isdigit() and sys.argv[k - 1] not in ("--poses", "--out")]
FRAMES = [int(x) for x in os.environ["UO_CFRAMES"].split(",")] if os.environ.get("UO_CFRAMES") else None
INIT = pickle.load(open(os.environ["UO_CINIT"], "rb"))
ROUNDS = int(os.environ.get("UO_C3ROUNDS", "8")); ITERS = int(os.environ.get("UO_C3ITERS", "150"))
NP = 512                                               # max (pixel, triangle) pairs per view
P = pickle.load(open(POSES, "rb"))
TRI = jnp.asarray(tris)


def bary_min(p, t, c):
    """min barycentric coordinate of point c in projected triangle t (p: projected vertices)"""
    A, B, C = p[TRI[t, 0]], p[TRI[t, 1]], p[TRI[t, 2]]
    den = (B[:, 1] - C[:, 1]) * (A[:, 0] - C[:, 0]) + (C[:, 0] - B[:, 0]) * (A[:, 1] - C[:, 1])
    den = jnp.where(jnp.abs(den) < 1e-6, 1e-6, den)
    l0 = ((B[:, 1] - C[:, 1]) * (c[:, 0] - C[:, 0]) + (C[:, 0] - B[:, 0]) * (c[:, 1] - C[:, 1])) / den
    l1 = ((C[:, 1] - A[:, 1]) * (c[:, 0] - C[:, 0]) + (A[:, 0] - C[:, 0]) * (c[:, 1] - C[:, 1])) / den
    return jnp.minimum(jnp.minimum(l0, l1), 1 - l0 - l1)


def loss_fn(Dpx, pp, sdf_r, sdf_a, tg, tm, mounted, cand, cmask, ex_t, ex_c, ex_m, in_t, in_c, in_m):
    base, _ = CF.loss_fn(Dpx, pp, sdf_r, sdf_a, tg, tm, jnp.zeros((5, 1, 2)), jnp.zeros((5, 1)), 0.0, mounted, cand, cmask)
    X = CF.posed_with(pp, V0 + Dpx / 36.0)
    lex = 0.0; lin = 0.0
    for d in range(5):
        p = project(X, d)
        lex += jnp.sum(ex_m[d] * jax.nn.relu(bary_min(p, ex_t[d], ex_c[d]) + 0.03) ** 2) * float(os.environ.get("UO_WEX", "400"))
        lin += jnp.sum(in_m[d] * jax.nn.relu(0.03 - bary_min(p, in_t[d], in_c[d])) ** 2) * float(os.environ.get("UO_WIN", "400"))
    return base + lex + lin, (lex, lin)


vg = jax.jit(jax.value_and_grad(loss_fn, has_aux=True))


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


res = pickle.load(open(OUT, "rb")) if os.path.exists(OUT) else {}
for a in ACTS:
    T = targets(a); F = len(T); M = T[..., 3] > 127
    hid = (horse_masks(a, F) & ~M) if a in HORSE_OF else np.zeros_like(M)
    mounted = jnp.asarray(a in HORSE_OF)
    for i in range(F):
        if FRAMES is not None and i not in FRAMES:
            continue
        t0 = time.time()
        pp = {k: jnp.asarray(v[i]) for k, v in P[a]["poses"].items()}
        sdf_r, sdf_a, tg, tm = CF.frame_data(M[i], hid[i])
        Dpx = jnp.asarray(INIT[(a, i)]["D"] * 36.0)
        hist = []
        best = None
        for rnd in range(ROUNDS + 1):
            X = np.asarray(CF.posed_with(pp, V0 + Dpx / 36.0))
            data = [pairs_for(np.asarray(project(jnp.asarray(X), d))[tris], M[i, d], hid[i, d]) for d in range(5)]
            nb, nr = sum(x[2] for x in data), sum(x[3] for x in data)
            hist.append((nr, nb))
            if best is None or nb + nr < best[0]:
                best = (nb + nr, np.asarray(Dpx), nr, nb)
            if rnd == ROUNDS or nb + nr == 0:
                break
            ex = [pad(*x[0]) for x in data]; inc = [pad(*x[1]) for x in data]
            cand, cmask = CF.candidates(pp, Dpx, sdf_r)
            args = (pp, sdf_r, sdf_a, tg, tm, mounted, cand, cmask,
                    jnp.asarray(np.stack([e[0] for e in ex])), jnp.asarray(np.stack([e[1] for e in ex])), jnp.asarray(np.stack([e[2] for e in ex])),
                    jnp.asarray(np.stack([e[0] for e in inc])), jnp.asarray(np.stack([e[1] for e in inc])), jnp.asarray(np.stack([e[2] for e in inc])))
            opt = optax.adam(optax.exponential_decay(float(os.environ.get("UO_C3LR", "0.02")), ITERS, 0.3)); st = opt.init(Dpx)
            for it in range(ITERS):
                (l, aux), g = vg(Dpx, *args)
                up, st = opt.update(g, st, Dpx); Dpx = optax.apply_updates(Dpx, up)
        _, Dbest, nr, nb = best
        area = int(M[i].sum())
        res = pickle.load(open(OUT, "rb")) if os.path.exists(OUT) else {}
        res[(a, i)] = dict(D=(Dbest / 36.0).astype(np.float32), after=(nr, nb), area=area, hist=hist)
        pickle.dump(res, open(OUT, "wb"))
        r0, b0 = hist[0]
        print(f"a{a:2d} f{i}: missing {r0:3d} -> {nr:3d}  outside {b0:3d} -> {nb:3d}  IoU {1-(r0+b0)/(area+b0):.3f} -> "
              f"{1-(nr+nb)/(area+nb):.3f}  {time.time()-t0:.0f}s", flush=True)
