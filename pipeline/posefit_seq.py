"""Sequential, identity-preserving pose fitting on the skinned mesh.

For each action: start at the frame most similar to a trusted reference pose (stand / combat stance / previous
result), fit it, then walk frame by frame in both directions (each frame starts from its fitted neighbour),
finally refine all frames jointly with temporal smoothness. Limb identity is never swapped."""
import sys, time, pickle, os
import numpy as np
import jax, jax.numpy as jnp, optax
from posefit_mesh import *

OUT = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "posefit_seq.pkl"
ACTS = [int(a) for a in sys.argv[1:] if a.isdigit()]
anim = pickle.load(open("anim_fit.pkl", "rb"))
ref = pickle.load(open("refine_mesh.pkl", "rb"))
ridx = {s: i for i, s in enumerate(ref["samples"])}
res = pickle.load(open(OUT, "rb")) if os.path.exists(OUT) else {}


CUR = os.environ.get("UO_CURRENT")          # e.g. final_poses.pkl: warm start from the previous iteration


def current(a):
    if CUR:
        return {k: np.asarray(v) for k, v in pickle.load(open(CUR, "rb"))[a]["poses"].items()}
    F = anim[a]["poses"]["trans"].shape[0]
    return {n: np.stack([ref["poses"][n][ridx[(a, i)]] if (a, i) in ridx else anim[a]["poses"][n][i] for i in range(F)])
            for n in ("ball", "hinge", "trans")}


REF_OF = {9: 7, 10: 7, 11: 7, 18: 7, 20: 7, 31: 7, 30: 7, 15: 7, 12: 8, 13: 8, 14: 8, 19: 8,
          24: 23, 25: 23, 26: 23, 27: 23, 28: 23, 29: 23}


REF_FILES = [f for f in ("posefit_A.pkl", "posefit_B.pkl", OUT) if f]


def ref_pose(a):
    """Trusted start pose: the reference action's refitted result (any worker's file), else the stand."""
    src = REF_OF.get(a, 4 if a not in MOUNTED else 23)
    for f in REF_FILES:
        if os.path.exists(f):
            r = pickle.load(open(f, "rb"))
            if src in r and src != a:
                return {k: v[0] for k, v in r[src]["poses"].items()}, src
    c = current(4)
    return {k: v[0] for k, v in c.items()}, 4


def sil_sim(m1, m2):
    return (m1 & m2).sum() / max((m1 | m2).sum(), 1)


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

    def fit(init, nb, dto, bpx, bm, iters=300, lr=0.02, w_nb=0.05):
        opt = optax.adam(optax.exponential_decay(lr, iters, 0.3))
        pp = {k: jnp.asarray(v) for k, v in init.items()}; st = opt.init(pp)
        nbj = {k: jnp.asarray(v) for k, v in nb.items()}
        for _ in range(iters):
            (l, _), g = vg(pp, nbj, dto, bpx, bm, w_nb)
            up, st = opt.update(g, st, pp)
            pp = optax.apply_updates(pp, up)
        (l, (ins, cov)) = ev(pp, nbj, dto, bpx, bm, 0.0)
        return {k: np.asarray(v) for k, v in pp.items()}, float(4.0 * ins + cov)
    return fit


for a in ACTS:
    t0 = time.time()
    F, dto, bpx, bm, masks = prepare(a)
    fit = single_fit_fn(a)
    rp, src = ref_pose(a)
    cur = current(a)
    # start frame = the one whose sprites look most like the reference action's first frame
    ref_masks = targets(src)[0][..., 3] > 127
    sims = [np.mean([sil_sim(masks[i, d], ref_masks[d]) for d in range(5)]) for i in range(F)]
    s0 = int(np.argmax(sims))
    poses = [None] * F
    # start frame: from the reference pose and from the previous fit (projected into the limits); keep the better
    cands = [rp, {k: v[s0] for k, v in cur.items()}]
    best = None
    for c in cands:
        p, l = fit(c, c, dto[s0], bpx[s0], bm[s0], iters=500, w_nb=0.0)
        if best is None or l < best[1]:
            best = (p, l)
    poses[s0] = best[0]
    order = list(range(s0 + 1, F)) + list(range(s0 - 1, -1, -1))
    for i in order:
        nbi = i - 1 if i > s0 else i + 1
        p, l = fit(poses[nbi], poses[nbi], dto[i], bpx[i], bm[i])
        # fast motions: the neighbour can be far away -> also start from the earlier (L/R-verified) fit of this frame
        p2, l2 = fit({k: v[i] for k, v in cur.items()}, poses[nbi], dto[i], bpx[i], bm[i])
        poses[i] = p if l <= l2 else p2
    batch = {k: np.stack([p[k] for p in poses]) for k in ("ball", "hinge", "trans")}
    batch, _ = fit_action(a, batch, iters=250, lr=0.004, log=False)
    r, lim = evaluate(a, batch, masks)
    res = pickle.load(open(OUT, "rb")) if os.path.exists(OUT) else {}
    res[a] = dict(poses=batch, iou=r, limits=lim, start=s0, ref=src)
    pickle.dump(res, open(OUT, "wb"))
    print(f"action {a:2d} start f{s0} (ref {src})  worstIoU mean {r[:,0].mean():.3f} min {r[:,0].min():.3f}  "
          f"meanIoU {r[:,1].mean():.3f}  max limit pen {lim.max():.4f}  {time.time()-t0:.0f}s", flush=True)
