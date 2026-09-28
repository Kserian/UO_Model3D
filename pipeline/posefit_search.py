"""Local multi-start search for frames stuck in local minima (mostly arms swinging weapons).
For each frame: current pose + random perturbations of ONE arm (shoulder/elbow/wrist) and of the torso,
each optimised; keep the best data fit; then refine the whole action with temporal smoothness.
No left/right swapping: every candidate is a local perturbation of the current (verified) pose."""
import sys, os, time, pickle
import numpy as np
import jax, jax.numpy as jnp, optax
from posefit_mesh import *

BASE = sys.argv[sys.argv.index("--base") + 1]
OUT = sys.argv[sys.argv.index("--out") + 1]
NCAND = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 10
ACTS = [int(a) for k, a in enumerate(sys.argv[1:], 1) if a.isdigit() and sys.argv[k - 1] not in ("--n", "--base", "--out")]
base = pickle.load(open(BASE, "rb"))
res = pickle.load(open(OUT, "rb")) if os.path.exists(OUT) else {}
rng = np.random.default_rng(1)


def single_fit_fn(a):
    mounted = jnp.asarray(a in MOUNTED)

    def loss(pp, nb, dto, bpx, bm, w_nb):
        ins, cov = frame_terms(pp, dto, bpx, bm, mounted)
        l = 4.0 * ins + cov + 200.0 * limit_penalty(pp) + 0.02 * natural_prior(pp)
        l += w_nb * (jnp.sum((pp["ball"] - nb["ball"]) ** 2) + jnp.sum((pp["hinge"] - nb["hinge"]) ** 2)
                     + 20.0 * jnp.sum((pp["trans"] - nb["trans"]) ** 2))
        return l, (ins, cov)
    vg = jax.jit(jax.value_and_grad(loss, has_aux=True))
    ev = jax.jit(loss)

    def fit(init, nb, dto, bpx, bm, iters=250, lr=0.02, w_nb=0.0):
        opt = optax.adam(optax.exponential_decay(lr, iters, 0.3))
        pp = {k: jnp.asarray(v) for k, v in init.items()}; st = opt.init(pp)
        nbj = {k: jnp.asarray(v) for k, v in nb.items()}
        for _ in range(iters):
            (l, _), g = vg(pp, nbj, dto, bpx, bm, w_nb)
            up, st = opt.update(g, st, pp)
            pp = optax.apply_updates(pp, up)
        l, (ins, cov) = ev(pp, nbj, dto, bpx, bm, 0.0)
        lim = float(limit_penalty(pp))
        return {k: np.asarray(v) for k, v in pp.items()}, float(4.0 * ins + cov), lim
    return fit


ARM = {"L": ("shoulder.L", "elbow.L", "wrist.L"), "R": ("shoulder.R", "elbow.R", "wrist.R")}


from scipy.spatial.transform import Rotation as Rot


def yaw_compose(rv, deg):
    return (Rot.from_euler("z", deg, degrees=True) * Rot.from_rotvec(rv)).as_rotvec()


def twist_candidate(p, deg):
    """Turn the upper body by `deg` around the vertical: 1/3 pelvis (legs counter-rotated), 1/3 spine, 1/3 chest."""
    q = {k: v.copy() for k, v in p.items()}
    part = deg / 3.0
    q["ball"][BI[JI["pelvis"]]] = yaw_compose(q["ball"][BI[JI["pelvis"]]], part)
    for h in ("hip.L", "hip.R"):
        q["ball"][BI[JI[h]]] = yaw_compose(q["ball"][BI[JI[h]]], -part)
    for j in ("spine", "chest"):
        q["ball"][BI[JI[j]]] = yaw_compose(q["ball"][BI[JI[j]]], part)
    return q


TWISTS = [int(t) for t in os.environ.get("UO_TWISTS", "-90,-60,-30,30,60,90").split(",") if t]
LEANS = [int(t) for t in os.environ.get("UO_LEANS", "").split(",") if t]


def roll_compose(rv, deg):
    return (Rot.from_euler("y", deg, degrees=True) * Rot.from_rotvec(rv)).as_rotvec()


def lean_candidate(p, deg):
    """Bend the upper body sideways by `deg` (half spine, half chest), head kept upright."""
    q = {k: v.copy() for k, v in p.items()}
    for j in ("spine", "chest"):
        q["ball"][BI[JI[j]]] = roll_compose(q["ball"][BI[JI[j]]], deg / 2.0)
    q["ball"][BI[JI["neck"]]] = roll_compose(q["ball"][BI[JI["neck"]]], -deg / 2.0)
    return q


KINDS = [int(k) for k in os.environ.get("UO_KINDS", "0,1,2").split(",")]   # 0/1 arm L/R, 2 torso, 3 leg, 4 whole body


def perturb(p):
    q = {k: v.copy() for k, v in p.items()}
    kind = KINDS[rng.integers(0, len(KINDS))]
    if kind == 3:                                  # one leg
        s_ = "L" if rng.integers(0, 2) == 0 else "R"
        q["ball"][BI[JI["hip." + s_]]] += rng.normal(0, 0.5, 3)
        q["hinge"][HI[JI["knee." + s_]]] = np.clip(q["hinge"][HI[JI["knee." + s_]]] + rng.normal(0, 0.6), 0.0, 2.5)
        q["ball"][BI[JI["ankle." + s_]]] = rng.normal(0, 0.2, 3)
        return q
    if kind == 4:                                  # whole body orientation + position
        q["ball"][BI[JI["pelvis"]]] = (Rot.from_rotvec(rng.normal(0, 0.25, 3)) * Rot.from_rotvec(q["ball"][BI[JI["pelvis"]]])).as_rotvec()
        q["trans"] = q["trans"] + rng.normal(0, 0.03, 3)
        return q
    if kind < 2:                                   # one arm
        sh, el, wr = ARM["L" if kind == 0 else "R"]
        q["ball"][BI[JI[sh]]] += rng.normal(0, 0.7, 3)
        q["hinge"][HI[JI[el]]] = np.clip(q["hinge"][HI[JI[el]]] + rng.normal(0, 0.8), -2.5, 0.0)
        q["ball"][BI[JI[wr]]] = rng.normal(0, 0.3, 3)
    else:                                          # torso + head
        for j in ("spine", "chest", "neck"):
            q["ball"][BI[JI[j]]] += rng.normal(0, 0.2, 3)
    return q


for a in ACTS:
    t0 = time.time()
    F, dto, bpx, bm, masks = prepare(a)
    fit = single_fit_fn(a)
    cur = {k: np.asarray(v) for k, v in base[a]["poses"].items()}
    if os.environ.get("UO_CLAV") and "clav" not in cur:
        cur["clav"] = np.zeros((cur["trans"].shape[0], 2, 3), np.float32)
    poses = []
    for i in range(F):
        c0 = {k: v[i] for k, v in cur.items()}
        best = fit(c0, c0, dto[i], bpx[i], bm[i], iters=150)
        starts = [twist_candidate(c0, t) for t in TWISTS] + [lean_candidate(c0, t) for t in LEANS] + [perturb(c0) for _ in range(NCAND)]
        if i > 0:
            starts.append({k: v for k, v in poses[-1].items()})           # continue from the improved previous frame
        for st_ in starts:
            p, l, lim = fit(st_, c0, dto[i], bpx[i], bm[i], iters=300)
            if lim < 0.01 and l < best[1]:
                best = (p, l, lim)
        poses.append(best[0])
    batch = {k: np.stack([p[k] for p in poses]) for k in cur}
    batch, _ = fit_action(a, batch, iters=200, lr=0.004, log=False)
    r, lim = evaluate(a, batch, masks)
    res = pickle.load(open(OUT, "rb")) if os.path.exists(OUT) else {}
    res[a] = dict(poses=batch, iou=r, limits=lim)
    pickle.dump(res, open(OUT, "wb"))
    r0 = base[a]["iou"]
    print(f"action {a:2d} worstIoU {r0[:,0].mean():.3f} -> {r[:,0].mean():.3f}  min {r0[:,0].min():.3f} -> {r[:,0].min():.3f}"
          f"  max limit {lim.max():.4f}  {time.time()-t0:.0f}s", flush=True)
