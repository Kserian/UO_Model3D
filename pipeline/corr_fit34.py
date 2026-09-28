"""Stages 3+4 of the per-frame corrections, raster-aligned (pixel-centre rule):
  stage 3: refine the shared 3D correction D of each frame (all 5 views) with pixel-level triangle terms
  stage 4: for each view d an extra correction E_d (a shape key active only in that UO direction) using only view d
usage: UO_CINIT=corr_all.pkl python corr_fit34.py 4 0 --poses final_poses_v10.pkl --out corr34_A.pkl"""
import sys, os, time, pickle
import numpy as np
import jax, jax.numpy as jnp, optax
os.environ.setdefault("UO_DELTA", "refine_infl.pkl")
from posefit_mesh import project, tris, targets, horse_masks, HORSE_OF, LEGV, V0
import corr_fit_core as CF
from corr_fit_core import raster_ids, pairs_for, pad, bary_min, NP

POSES = sys.argv[sys.argv.index("--poses") + 1]
OUT = sys.argv[sys.argv.index("--out") + 1]
ACTS = [int(a) for k, a in enumerate(sys.argv[1:], 1) if a.isdigit() and sys.argv[k - 1] not in ("--poses", "--out")]
FRAMES = [int(x) for x in os.environ["UO_CFRAMES"].split(",")] if os.environ.get("UO_CFRAMES") else None
INIT = pickle.load(open(os.environ["UO_CINIT"], "rb"))
R3, I3 = int(os.environ.get("UO_R3", "8")), int(os.environ.get("UO_I3", "100"))
R4, I4 = int(os.environ.get("UO_R4", "8")), int(os.environ.get("UO_I4", "80"))
P = pickle.load(open(POSES, "rb"))
NV = V0.shape[0]


def loss_fn(E, Dfix, pp, sdf_r, sdf_a, tg, tm, mounted, cand, cmask, ex_t, ex_c, ex_m, in_t, in_c, in_m, wv, wreg):
    Dpx = Dfix + E
    X = CF.posed_with(pp, V0 + Dpx / 36.0)
    l = 0.0
    for d in range(5):
        p = project(X, d)
        s = jnp.where(LEGV & mounted, CF.bilin(sdf_a[d], p), CF.bilin(sdf_r[d], p))
        lin = jnp.mean(jax.nn.relu(s + 0.08) ** 2) * 50.0
        pc = p[cand[d]] + (1.0 - cmask[d])[:, None] * 1e4
        dist = jnp.sqrt(jnp.min(jnp.sum((tg[d][:, None, :] - pc[None, :, :]) ** 2, -1), 1) + 1e-9)
        lcov = jnp.sum(tm[d] * jax.nn.relu(dist - 0.3) ** 2) / (jnp.sum(tm[d]) + 1.0) * 20.0
        lex = jnp.sum(ex_m[d] * jax.nn.relu(bary_min(p, ex_t[d], ex_c[d]) + 0.03) ** 2) * 1500.0
        linc = jnp.sum(in_m[d] * jax.nn.relu(0.03 - bary_min(p, in_t[d], in_c[d])) ** 2) * 200.0
        l += wv[d] * (lin + lcov + lex + linc)
    lap = E - (jax.ops.segment_sum(E[CF.EJ], CF.EI, NV) + jax.ops.segment_sum(E[CF.EI], CF.EJ, NV)) / CF.deg[:, None]
    return l + wreg * (jnp.sum(lap ** 2) * 0.015 + jnp.sum(E ** 2) * 0.0005)


vg = jax.jit(jax.value_and_grad(loss_fn))


def optimise(E0, Dfix, pp, fd, mounted, M_, hid_, views, rounds, iters, lr=0.01):
    """alternate raster checks and optimisation; keep the best result (fewest wrong pixels in `views`)"""
    sdf_r, sdf_a, tg, tm = fd
    wv = jnp.asarray([1.0 if d in views else 0.0 for d in range(5)])
    E = jnp.asarray(E0); best = None; hist = []
    for rnd in range(rounds + 1):
        X = np.asarray(CF.posed_with(pp, V0 + (Dfix + E) / 36.0))
        data = [pairs_for(np.asarray(project(jnp.asarray(X), d))[tris], M_[d], hid_[d]) for d in range(5)]
        nb = sum(data[d][2] for d in views); nr = sum(data[d][3] for d in views); hist.append((nr, nb))
        if best is None or nb + nr < best[0]:
            best = (nb + nr, np.asarray(E), nr, nb)
        if rnd == rounds or nb + nr == 0:
            break
        ex = [pad(*x[0]) for x in data]; inc = [pad(*x[1]) for x in data]
        cand, cmask = CF.candidates(pp, Dfix + E, sdf_r)
        args = (jnp.asarray(Dfix), pp, sdf_r, sdf_a, tg, tm, mounted, cand, cmask,
                jnp.asarray(np.stack([e[0] for e in ex])), jnp.asarray(np.stack([e[1] for e in ex])), jnp.asarray(np.stack([e[2] for e in ex])),
                jnp.asarray(np.stack([e[0] for e in inc])), jnp.asarray(np.stack([e[1] for e in inc])), jnp.asarray(np.stack([e[2] for e in inc])),
                wv, 1.0)
        opt = optax.adam(optax.exponential_decay(lr, iters, 0.3)); st = opt.init(E)
        for it in range(iters):
            l, g = vg(E, *args)
            up, st = opt.update(g, st, E); E = optax.apply_updates(E, up)
    return best, hist


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
        fd = CF.frame_data(M[i], hid[i])
        D1 = INIT[(a, i)]["D"] * 36.0
        zero = np.zeros_like(D1)
        (_, E3, nr3, nb3), h3 = optimise(zero, D1, pp, fd, mounted, M[i], hid[i], range(5), R3, I3)   # stage 3 (shared)
        D3 = D1 + E3
        Ed, per = {}, []
        for d in range(5):                                                                            # stage 4 (per view)
            (_, E4, nr4, nb4), h4 = optimise(zero, D3, pp, fd, mounted, M[i], hid[i], [d], R4, I4)
            Ed[d] = (E4 / 36.0).astype(np.float32); per.append((nr4, nb4))
        area = int(M[i].sum()); r0, b0 = h3[0]
        nr = sum(p[0] for p in per); nb = sum(p[1] for p in per)
        res = pickle.load(open(OUT, "rb")) if os.path.exists(OUT) else {}
        res[(a, i)] = dict(D=(D3 / 36.0).astype(np.float32), Ed=Ed, stage3=(nr3, nb3), per_view=per, area=area)
        pickle.dump(res, open(OUT, "wb"))
        print(f"a{a:2d} f{i}: stage1 {1-(r0+b0)/(area+b0):.3f}  stage3 {1-(nr3+nb3)/(area+nb3):.3f}  per-view {1-(nr+nb)/(area+nb):.3f} "
              f"(missing {nr}, outside {nb})  {time.time()-t0:.0f}s", flush=True)
