"""Shape refinement v2: symmetric per-vertex offsets of the rest mesh, poses FIXED to the plausible refit poses,
all 35 actions (mounted ones with the horse-aware masks). Differentiable inside + cover terms (no ICP)."""
import os, sys, time, pickle
import numpy as np
import jax, jax.numpy as jnp, optax
os.environ.setdefault("UO_DELTA", "refine_mesh.pkl")
import posefit_mesh as PM
from posefit_mesh import prepare, pose_from_params, fk, S, W, P0, BONE_JOINT, project, bilinear, md

ITERS = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
final = pickle.load(open("final_poses.pkl", "rb"))
base = jnp.asarray(md["v"], jnp.float32)
delta0 = jnp.asarray(pickle.load(open(os.environ["UO_DELTA"], "rb"))["delta"], jnp.float32)
mirror = jnp.asarray(md["mirror"]); FLIP = jnp.array([-1.0, 1.0, 1.0])
E = set()
for f in md["faces"]:
    for a, b in zip(f, f[1:] + f[:1]):
        E.add((min(a, b), max(a, b)))
E = np.array(sorted(E)); NV = base.shape[0]
deg = jnp.asarray(np.maximum(np.bincount(E.ravel(), minlength=NV), 1).astype(np.float32))
EI, EJ = jnp.asarray(E[:, 0]), jnp.asarray(E[:, 1])

samples, D, BP, BMK = [], [], [], []
for a in range(35):
    F, dto, bpx, bm, _ = prepare(a)
    for i in range(F):
        samples.append((a, i)); D.append(dto[i]); BP.append(bpx[i]); BMK.append(bm[i])
D = jnp.stack(D); BP = jnp.stack(BP); BMK = jnp.stack(BMK)
POSE = {k: jnp.asarray(np.stack([final[a]["poses"][k][i] for a, i in samples])) for k in ("ball", "hinge", "trans")}
NS = len(samples)
print("frames", NS, flush=True)


def sym(d):
    return 0.5 * (d + d[mirror] * FLIP)


def posed_with(pp, V):
    pose = pose_from_params(pp)
    P, R = fk(S, pose)
    Rb = R[BONE_JOINT]
    tb = P[BONE_JOINT] - jnp.einsum("bij,bj->bi", Rb, P0[BONE_JOINT])
    X = jnp.einsum("bij,vj->vbi", Rb, V) + tb[None]
    return jnp.einsum("vb,vbi->vi", W, X)


def frame_loss(delta, pp, dto, bpx, bm):
    X = posed_with(pp, base + sym(delta))
    ins = 0.0; cov = 0.0
    for d in range(5):
        p = project(X, d)
        ins += jnp.mean(bilinear(dto[d], p) ** 2)
        dist = jnp.sqrt(jnp.min(jnp.sum((bpx[d][:, None, :] - p[None, :, :]) ** 2, -1), 1) + 1e-9)
        cov += jnp.sum(bm[d] * jax.nn.relu(dist - 0.7) ** 2) / (jnp.sum(bm[d]) + 1.0)
    return ins, cov


def loss(delta, idx):
    pp = {k: v[idx] for k, v in POSE.items()}
    ins, cov = jax.vmap(lambda a, b, c, d: frame_loss(delta, a, b, c, d))(pp, D[idx], BP[idx], BMK[idx])
    d = sym(delta)
    lap = d - (jax.ops.segment_sum(d[EJ], EI, NV) + jax.ops.segment_sum(d[EI], EJ, NV)) / deg[:, None]
    reg = jnp.sum(lap ** 2) * 300.0 + jnp.sum(d ** 2) * 0.05
    return jnp.mean(4.0 * ins + cov) + reg, (jnp.mean(ins), jnp.mean(cov))


vg = jax.jit(jax.value_and_grad(loss, has_aux=True))
opt = optax.adam(optax.exponential_decay(2e-3, ITERS, 0.2))
delta = delta0; st = opt.init(delta)
rng = np.random.default_rng(0); t0 = time.time()
for it in range(ITERS):
    idx = jnp.asarray(rng.choice(NS, 8, replace=False))
    (l, aux), g = vg(delta, idx)
    up, st = opt.update(g, st, delta)
    delta = optax.apply_updates(delta, up)
    if it % 250 == 0 or it == ITERS - 1:
        print(f"it {it} loss {float(l):.3f} inside {float(aux[0]):.3f} cover {float(aux[1]):.3f} {time.time()-t0:.0f}s", flush=True)
pickle.dump(dict(delta=np.asarray(sym(delta))), open("refine_shape2.pkl", "wb"))
print("saved refine_shape2.pkl")
