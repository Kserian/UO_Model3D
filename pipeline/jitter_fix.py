"""Temporal de-jitter: where a joint swings A->B->A between consecutive frames and the silhouettes cannot tell
(true IoU nearly unchanged), replace it by the in-between rotation of its neighbours (brief refit of the frame)."""
import sys, os, pickle, time
import numpy as np
import jax, jax.numpy as jnp, optax
from scipy.spatial.transform import Rotation as Rot, Slerp
from posefit_mesh import *
from posefit_mesh import _posed_j
from fit import BALL_IDX
BASE = sys.argv[sys.argv.index("--base") + 1]
OUT = sys.argv[sys.argv.index("--out") + 1]
ACTS = [int(a) for k, a in enumerate(sys.argv[1:], 1) if a.isdigit() and sys.argv[k - 1] not in ("--base", "--out")]
THR = float(os.environ.get("UO_JIT_THR", "12"))
base = pickle.load(open(BASE, "rb"))
NAMES = [JOINTS[j][0] for j in BALL_IDX]
CYC = {0, 1, 2, 3, 23, 24}


def ious(p, m, hid):
    X = _posed_j({k: jnp.asarray(v) for k, v in p.items()}); r = []
    for d in range(5):
        mk = raster_vec(np.asarray(project(X, d))[tris], CANVAS_W, CANVAS_H) & ~hid[d]
        r.append((mk & m[d]).sum() / max((mk | m[d]).sum(), 1))
    return np.array(r)


def fitter(a):
    mounted = jnp.asarray(a in MOUNTED)

    def loss(pp, nb, dto, bpx, bm):
        ins, cov = frame_terms(pp, dto, bpx, bm, mounted)
        l = 4.0 * ins + cov + 200.0 * limit_penalty(pp) + 0.02 * natural_prior(pp)
        return l + 0.3 * (jnp.sum((pp["ball"] - nb["ball"]) ** 2) + jnp.sum((pp["hinge"] - nb["hinge"]) ** 2)
                          + 20.0 * jnp.sum((pp["trans"] - nb["trans"]) ** 2))
    vg = jax.jit(jax.value_and_grad(loss))

    def fit(init, dto, bpx, bm, iters=150, lr=0.01):
        opt = optax.adam(optax.exponential_decay(lr, iters, 0.3))
        pp = {k: jnp.asarray(v) for k, v in init.items()}; nb = dict(pp); st = opt.init(pp)
        for _ in range(iters):
            _, g = vg(pp, nb, dto, bpx, bm)
            up, st = opt.update(g, st, pp); pp = optax.apply_updates(pp, up)
        return {k: np.asarray(v) for k, v in pp.items()}, float(limit_penalty(pp))
    return fit


res = pickle.load(open(OUT, "rb")) if os.path.exists(OUT) else {}
for a in ACTS:
    t0 = time.time()
    P = {k: np.array(v) for k, v in base[a]["poses"].items()}; F = P["trans"].shape[0]
    if F < 3:
        continue
    Fr, dto, bpx, bm, m = prepare(a)
    hid = (horse_masks(a, F) & ~m) if a in HORSE_OF else np.zeros_like(m)
    fit = fitter(a)
    changed = []
    for sweep in range(2):
        for t in range(F):
            if a not in CYC and (t == 0 or t == F - 1):
                continue
            tp, tn = (t - 1) % F, (t + 1) % F
            cand = []
            for k, n in enumerate(NAMES):
                if n == "pelvis":
                    continue
                R = Rot.from_rotvec(P["ball"][[tp, t, tn], k])
                s1 = (R[1] * R[0].inv()).magnitude(); s2 = (R[2] * R[1].inv()).magnitude(); sk = (R[2] * R[0].inv()).magnitude()
                jit = np.degrees(min(s1, s2) - sk / 2)
                if jit > THR:
                    cand.append((jit, k, n))
            for jit, k, n in sorted(cand, reverse=True):
                R = Rot.from_rotvec(P["ball"][[tp, tn], k])
                mid = Slerp([0, 1], R)([0.5]).as_rotvec()[0]
                q = {kk: v[t].copy() for kk, v in P.items()}; q["ball"][k] = mid
                q2, lim = fit(q, dto[t], bpx[t], bm[t])
                cur = {kk: v[t] for kk, v in P.items()}
                i0, i1 = ious(cur, m[t], hid[t]), ious(q2, m[t], hid[t])
                R2 = Rot.from_rotvec(np.stack([P["ball"][tp, k], q2["ball"][k], P["ball"][tn, k]]))
                jit2 = np.degrees(min((R2[1] * R2[0].inv()).magnitude(), (R2[2] * R2[1].inv()).magnitude()) - (R2[2] * R2[0].inv()).magnitude() / 2)
                ok = lim < 0.01 and i1.mean() > i0.mean() - 0.004 and i1.min() > i0.min() - 0.008 and jit2 < jit - 5
                print(f"  a{a} f{t} {n}: jitter {jit:.0f} -> {jit2:.0f}  IoU {i0.mean():.3f} -> {i1.mean():.3f}  {'ACCEPT' if ok else 'keep'}", flush=True)
                if ok:
                    for kk in P:
                        P[kk][t] = q2[kk]
                    changed.append((t, n))
    r, lim = evaluate(a, P, m)
    res = pickle.load(open(OUT, "rb")) if os.path.exists(OUT) else {}
    res[a] = dict(poses=P, iou=r, limits=lim)
    pickle.dump(res, open(OUT, "wb"))
    r0 = base[a]["iou"]
    print(f"action {a:2d} changed {changed}  worstIoU {r0[:,0].mean():.3f} -> {r[:,0].mean():.3f}  mean {r0[:,1].mean():.3f} -> {r[:,1].mean():.3f}  {time.time()-t0:.0f}s", flush=True)
