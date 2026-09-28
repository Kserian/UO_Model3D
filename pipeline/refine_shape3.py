"""Shape refinement v3: symmetric per-vertex offsets of the rest mesh with the poses FIXED (v5), all 35 actions,
same data terms as the pose fit (lower body may hide behind the horse). Epoch-shuffled batches, small decaying lr."""
import os, sys, time, pickle
import numpy as np
import jax, jax.numpy as jnp, optax
os.environ.setdefault("UO_DELTA", "refine_infl.pkl")
from posefit_mesh import prepare, pose_from_params, fk, S, W, P0, BONE_JOINT, project, bilinear, md, LEGV, MOUNTED

ITERS = int(sys.argv[1]) if len(sys.argv) > 1 else 900
POSES = os.environ.get("UO_POSES", "final_poses_v5.pkl")
OUTF = os.environ.get("UO_SHAPE_OUT", "refine_shape3.pkl")
final = pickle.load(open(POSES, "rb"))
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
        samples.append((a, i)); D.append(np.asarray(dto[i])); BP.append(np.asarray(bpx[i])); BMK.append(np.asarray(bm[i]))
D = jnp.asarray(np.stack(D)); BP = jnp.asarray(np.stack(BP)); BMK = jnp.asarray(np.stack(BMK))
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
        ins += jnp.mean(jnp.where(LEGV, bilinear(dto[d, 0], p), bilinear(dto[d, 1], p)) ** 2)
        dist = jnp.sqrt(jnp.min(jnp.sum((bpx[d][:, None, :] - p[None, :, :]) ** 2, -1), 1) + 1e-9)
        cov += jnp.sum(bm[d] * jax.nn.relu(dist - 0.7) ** 2) / (jnp.sum(bm[d]) + 1.0)
    return ins, cov


def data_loss(delta, idx):
    pp = {k: v[idx] for k, v in POSE.items()}
    ins, cov = jax.vmap(lambda a, b, c, d: frame_loss(delta, a, b, c, d))(pp, D[idx], BP[idx], BMK[idx])
    return jnp.mean(4.0 * ins + cov), (jnp.mean(ins), jnp.mean(cov))


def reg_loss(delta):
    d = sym(delta)
    lap = d - (jax.ops.segment_sum(d[EJ], EI, NV) + jax.ops.segment_sum(d[EI], EJ, NV)) / deg[:, None]
    dd = d - delta0
    return jnp.sum(lap ** 2) * 300.0 + jnp.sum(dd ** 2) * 0.5


def loss(delta, idx):
    l, aux = data_loss(delta, idx)
    return l + reg_loss(delta), aux


vg = jax.jit(jax.value_and_grad(loss, has_aux=True))
dl = jax.jit(data_loss)


def full(delta):
    tot = np.zeros(3); n = 0
    for s in range(0, NS, 30):
        idx = jnp.arange(s, min(s + 30, NS))
        l, (i_, c_) = dl(delta, idx)
        k = len(idx); tot += np.array([float(l), float(i_), float(c_)]) * k; n += k
    return tot / n


BATCH = 30
opt = optax.adam(optax.exponential_decay(4e-4, ITERS, 0.1))
delta = delta0; st = opt.init(delta)
rng = np.random.default_rng(0); t0 = time.time()
print("start full data loss %.4f inside %.4f cover %.4f" % tuple(full(delta)), flush=True)
perm = []
for it in range(ITERS):
    if len(perm) < BATCH:
        perm = list(rng.permutation(NS))
    idx = jnp.asarray(perm[:BATCH]); perm = perm[BATCH:]
    (l, aux), g = vg(delta, idx)
    up, st = opt.update(g, st, delta)
    delta = optax.apply_updates(delta, up)
    if (it + 1) % 150 == 0 or it == ITERS - 1:
        print(f"it {it} full data loss %.4f inside %.4f cover %.4f  {time.time()-t0:.0f}s" % tuple(full(delta)), flush=True)
        pickle.dump(dict(delta=np.asarray(sym(delta))), open(OUTF, "wb"))
print("saved", OUTF)
