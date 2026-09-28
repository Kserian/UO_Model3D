"""Experiment: would a movable shoulder (clavicle) help raised-arm frames? Per-frame free shoulder offsets
(chest frame, both sides) vs. a control refit with the same iterations. Scored by true raster IoU."""
import sys, pickle, numpy as np
import jax, jax.numpy as jnp, optax
from posefit_mesh import *
from posefit_mesh import _posed_j
P = pickle.load(open("final_poses_v6.pkl", "rb"))
FR = [(9, 6), (9, 5), (17, 4), (17, 3), (26, 2), (29, 2), (12, 3), (16, 4), (4, 0), (0, 3)]
ARMB = {s: np.array([JI[joint_of[b]] in (JI["shoulder." + s], JI["elbow." + s], JI["wrist." + s]) for b in md["bones"]]) for s in "LR"}
ML = jnp.asarray(ARMB["L"], jnp.float32); MR = jnp.asarray(ARMB["R"], jnp.float32)


def posed_ext(pp, off):
    pose = pose_from_params(pp)
    Pj, R = fk(S, pose)
    Rb = R[BONE_JOINT]
    Rc = R[JI["chest"]]
    tb = Pj[BONE_JOINT] - jnp.einsum("bij,bj->bi", Rb, P0[BONE_JOINT])
    tb = tb + ML[:, None] * (Rc @ off[0])[None] + MR[:, None] * (Rc @ off[1])[None]
    X = jnp.einsum("bij,vj->vbi", Rb, V0) + tb[None]
    return jnp.einsum("vb,vbi->vi", W, X)


def terms(X, dto, bpx, bm):
    ins = 0.0; cov = 0.0
    for d in range(5):
        p = project(X, d)
        ins += jnp.mean(jnp.where(LEGV, bilinear(dto[d, 0], p), bilinear(dto[d, 1], p)) ** 2)
        dist = jnp.sqrt(jnp.min(jnp.sum((bpx[d][:, None, :] - p[None, :, :]) ** 2, -1), 1) + 1e-9)
        cov += jnp.sum(bm[d] * jax.nn.relu(dist - 0.7) ** 2) / (jnp.sum(bm[d]) + 1.0)
    return 4.0 * ins + cov


def loss(v, nb, dto, bpx, bm, woff):
    pp, off = v["pp"], v["off"]
    l = terms(posed_ext(pp, off), dto, bpx, bm) + 200.0 * limit_penalty(pp) + 0.02 * natural_prior(pp)
    l += 0.02 * (jnp.sum((pp["ball"] - nb["ball"]) ** 2) + jnp.sum((pp["hinge"] - nb["hinge"]) ** 2))
    return l + woff * jnp.sum(off ** 2)


vg = jax.jit(jax.value_and_grad(loss))


def run(pp0, dto, bpx, bm, free):
    v = {"pp": {k: jnp.asarray(x) for k, x in pp0.items()}, "off": jnp.zeros((2, 3))}
    nb = dict(v["pp"])
    opt = optax.adam(optax.exponential_decay(0.01, 300, 0.3)); st = opt.init(v)
    for _ in range(300):
        _, g = vg(v, nb, dto, bpx, bm, 30.0)
        if not free:
            g["off"] = jnp.zeros_like(g["off"])
        up, st = opt.update(g, st, v); v = optax.apply_updates(v, up)
    return v


def iou(v, m):
    X = posed_ext(v["pp"], v["off"]); r = []
    for d in range(5):
        mk = raster_vec(np.asarray(project(X, d))[tris], CANVAS_W, CANVAS_H)
        r.append((mk & m[d]).sum() / max((mk | m[d]).sum(), 1))
    return np.mean(r)


cache = {}
for a, i in FR:
    if a not in cache:
        cache[a] = prepare(a)
    F, dto, bpx, bm, m = cache[a]
    pp0 = {k: np.asarray(x[i]) for k, x in P[a]["poses"].items()}
    base = iou({"pp": {k: jnp.asarray(x) for k, x in pp0.items()}, "off": jnp.zeros((2, 3))}, m[i])
    c = run(pp0, dto[i], bpx[i], bm[i], False); f = run(pp0, dto[i], bpx[i], bm[i], True)
    print(f"a{a} f{i}: now {base:.3f}  control {iou(c, m[i]):.3f}  with shoulder offsets {iou(f, m[i]):.3f}  "
          f"off L {np.round(np.asarray(f['off'][0])*100,1)} cm  R {np.round(np.asarray(f['off'][1])*100,1)} cm", flush=True)
