"""Refine the rigged mesh against ALL sprite frames (2D contour ICP in 5 views per frame).

Optimises symmetric per-vertex offsets of the rest mesh together with small per-frame pose corrections.
Losses per (frame, view):
  inside : every projected vertex must lie inside the sprite silhouette (distance transform, bilinear)
  cover  : every sprite pixel must be near a projected vertex; uncovered pixels pull the nearest rim vertex
  smooth : Laplacian of the offsets, pose-correction prior
"""
import pickle, time, sys
import numpy as np
import jax, jax.numpy as jnp, optax
from scipy.ndimage import distance_transform_edt, binary_erosion
from scipy.spatial import cKDTree
from body import *
from fit import params_to_shape, pose_from_params
from rig import bone_defs
from targets import targets

ITERS = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
BATCH = 8
EXCLUDE = set(range(23, 30))            # mounted: rider sprites have the horse cut out

sf = pickle.load(open("shape_fit.pkl", "rb"))
S = params_to_shape({k: jnp.asarray(v) for k, v in sf["params"]["shape"].items()}, {k: jnp.asarray(v) for k, v in sf["fixed"].items()})
anim = pickle.load(open("anim_fit.pkl", "rb"))
md = pickle.load(open("mesh_data.pkl", "rb"))
V0 = jnp.asarray(md["v"], jnp.float32)
W = jnp.asarray(md["W"], jnp.float32)
tris = np.asarray(md["tris"])
mirror = np.asarray(md["mirror"])
NV = V0.shape[0]
P0, _ = fk(S, zero_pose())
defs = bone_defs({k: np.asarray(v) for k, v in S.items()}, np.asarray(P0))
joint_of = {d[0]: d[1] for d in defs}
BONE_JOINT = np.array([JI[joint_of[b]] for b in md["bones"]])   # in the weight-matrix column order

# edges for the Laplacian
E = set()
for f in md["faces"]:
    for a, b in zip(f, f[1:] + f[:1]):
        E.add((min(a, b), max(a, b)))
E = np.array(sorted(E))
deg = np.bincount(E.ravel(), minlength=NV).astype(np.float32)
EI, EJ = jnp.asarray(E[:, 0]), jnp.asarray(E[:, 1])
DEG = jnp.asarray(np.maximum(deg, 1.0))   # loose vertices have no edges
MIR = jnp.asarray(mirror)
FLIP = jnp.array([-1.0, 1.0, 1.0])

# ---------------------------------------------------------------- samples
samples = []  # (action, frame)
for a in sorted(anim):
    if a in EXCLUDE:
        continue
    for i in range(anim[a]["poses"]["trans"].shape[0]):
        samples.append((a, i))
NS = len(samples)
pose0 = {k: jnp.asarray(np.stack([anim[a]["poses"][k][i] for a, i in samples])) for k in ("ball", "hinge", "trans")}
print("frames", NS, "views", NS * 5, flush=True)
H, Wc = CANVAS_H, CANVAS_W
masks = np.zeros((NS, 5, H, Wc), bool)
cache_t = {}
for s, (a, i) in enumerate(samples):
    if a not in cache_t:
        cache_t[a] = targets(a)
    masks[s] = cache_t[a][i][..., 3] > 127
DTO = np.stack([[np.maximum(distance_transform_edt(~masks[s, d]) - 0.5, 0) for d in range(5)] for s in range(NS)]).astype(np.float32)
DTO = jnp.asarray(DTO)
CAM = [camera(S, d) for d in range(5)]
RIGHT = jnp.stack([c[0] for c in CAM]); UP = jnp.stack([c[1] for c in CAM])
FWD = jnp.cross(RIGHT, UP)
SC = S["scale"]


def symmetric(delta):
    return 0.5 * (delta + delta[MIR] * FLIP)


def posed_verts(delta, pp):
    pose = pose_from_params(pp)
    P, R = fk(S, pose)
    Rb = R[BONE_JOINT]                      # (B,3,3)
    tb = P[BONE_JOINT] - jnp.einsum("bij,bj->bi", Rb, P0[BONE_JOINT])
    v = V0 + symmetric(delta)
    X = jnp.einsum("bij,vj->vbi", Rb, v) + tb[None]
    return jnp.einsum("vb,vbi->vi", W, X)


PX_OFF = 0.5   # UO anchor sits on the pixel centre (measured: best alignment with +0.5 px in x)


def project(X):
    x = ANCHOR_X + PX_OFF + SC * (X @ RIGHT.T)       # (V,5)
    y = ANCHOR_Y - SC * (X @ UP.T)
    return jnp.stack([x, y], -1).transpose(1, 0, 2)  # (5,V,2)


def bilinear(img, xy):
    x = jnp.clip(xy[:, 0] - 0.5, 0, img.shape[1] - 1.001)
    y = jnp.clip(xy[:, 1] - 0.5, 0, img.shape[0] - 1.001)
    x0 = jnp.floor(x).astype(int); y0 = jnp.floor(y).astype(int)
    fx, fy = x - x0, y - y0
    return (img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x0 + 1] * fx * (1 - fy)
            + img[y0 + 1, x0] * (1 - fx) * fy + img[y0 + 1, x0 + 1] * fx * fy)


@jax.jit
def forward(delta, pp):
    X = posed_verts(delta, pp)
    return project(X), X


def sample_loss(delta, pp, pp0, dto, cv, ct, cm):
    """dto (5,H,W); cv (5,K) vertex idx; ct (5,K,2) target px; cm (5,K) mask."""
    X = posed_verts(delta, pp)
    p = project(X)
    inside = sum(jnp.mean(bilinear(dto[d], p[d]) ** 2) for d in range(5))
    pc = jnp.take_along_axis(p, cv[..., None], axis=1)
    cover = jnp.sum(cm * jnp.sum((pc - ct) ** 2, -1)) / (jnp.sum(cm) + 1.0)
    prior = sum(jnp.sum((pp[k] - pp0[k]) ** 2) for k in ("ball", "hinge")) * 0.3 + jnp.sum((pp["trans"] - pp0["trans"]) ** 2) * 5.0
    return 4.0 * inside + cover + prior, (inside, cover)


def total_loss(params, idx, dto, cv, ct, cm):
    delta = params["delta"]
    pp = {k: params[k][idx] for k in ("ball", "hinge", "trans")}
    p0 = {k: pose0[k][idx] for k in ("ball", "hinge", "trans")}
    l, (ins, cov) = jax.vmap(lambda a, b, c, d, e, f: sample_loss(delta, a, b, c, d, e, f),
                             in_axes=({"ball": 0, "hinge": 0, "trans": 0}, {"ball": 0, "hinge": 0, "trans": 0}, 0, 0, 0, 0))(pp, p0, dto, cv, ct, cm)
    d = symmetric(delta)
    lap = d - (jax.ops.segment_sum(d[EJ], EI, NV) + jax.ops.segment_sum(d[EI], EJ, NV)) / DEG[:, None]
    smooth = jnp.sum(lap ** 2) * 300.0 + jnp.sum(d ** 2) * 0.05
    return jnp.mean(l) + smooth, (jnp.mean(ins), jnp.mean(cov), smooth)


vg = jax.jit(jax.value_and_grad(total_loss, has_aux=True))
K = 400


def correspondences(p, X, s):
    """For sample s: uncovered sprite pixels -> nearest rim vertex (per view)."""
    cv = np.zeros((5, K), np.int32); ct = np.zeros((5, K, 2), np.float32); cm = np.zeros((5, K), np.float32)
    Xn = np.asarray(X)
    fn = np.cross(Xn[tris[:, 1]] - Xn[tris[:, 0]], Xn[tris[:, 2]] - Xn[tris[:, 0]])
    nrm = np.zeros_like(Xn)
    for k in range(3):
        np.add.at(nrm, tris[:, k], fn)
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-12)
    for d in range(5):
        pd = np.asarray(p[d])
        tree = cKDTree(pd)
        ys, xs = np.nonzero(masks[s, d])
        pix = np.stack([xs + 0.5, ys + 0.5], 1)
        dist, _ = tree.query(pix)
        unc = pix[dist > 0.8]
        if len(unc) == 0:
            continue
        rim = np.nonzero(np.abs(nrm @ np.asarray(FWD[d])) < 0.35)[0]
        if len(rim) == 0:
            continue
        _, j = cKDTree(pd[rim]).query(unc)
        n = min(len(unc), K)
        sel = np.random.choice(len(unc), n, replace=False) if len(unc) > K else np.arange(n)
        cv[d, :n] = rim[j[sel]]; ct[d, :n] = unc[sel]; cm[d, :n] = 1.0
    return cv, ct, cm


def iou_all(params, n=None):
    res = []
    for s in range(NS if n is None else n):
        pp = {k: params[k][s] for k in ("ball", "hinge", "trans")}
        p, _ = forward(params["delta"], pp)
        for d in range(5):
            img = np.zeros((H, Wc), bool)
            q = np.asarray(p[d]); xi = np.clip(q[:, 0].astype(int), 0, Wc - 1); yi = np.clip(q[:, 1].astype(int), 0, H - 1)
            img[yi, xi] = True
            from scipy.ndimage import binary_closing, binary_fill_holes
            img = binary_fill_holes(binary_closing(img, iterations=1))
            m = masks[s, d]
            res.append((img & m).sum() / max((img | m).sum(), 1))
    return float(np.mean(res))


params = dict(delta=jnp.zeros((NV, 3), jnp.float32), **{k: pose0[k] for k in ("ball", "hinge", "trans")})
opt = optax.adam(optax.exponential_decay(3e-3, ITERS, 0.2))
st = opt.init(params)
print("IoU before (vertex splat, all frames):", round(iou_all(params), 4), flush=True)
rng = np.random.default_rng(0)
t0 = time.time()
for it in range(ITERS):
    idx = rng.choice(NS, BATCH, replace=False)
    cvs, cts, cms = [], [], []
    for s in idx:
        pp = {k: params[k][s] for k in ("ball", "hinge", "trans")}
        p, X = forward(params["delta"], pp)
        cv, ct, cm = correspondences(p, X, s)
        cvs.append(cv); cts.append(ct); cms.append(cm)
    (l, aux), g = vg(params, jnp.asarray(idx), DTO[idx], jnp.asarray(np.stack(cvs)), jnp.asarray(np.stack(cts)), jnp.asarray(np.stack(cms)))
    up, st = opt.update(g, st, params)
    params = optax.apply_updates(params, up)
    if it % 100 == 0 or it == ITERS - 1:
        print(f"it {it} loss {float(l):.4f} inside {float(aux[0]):.4f} cover {float(aux[1]):.3f} smooth {float(aux[2]):.4f} "
              f"max|d| {float(jnp.abs(symmetric(params['delta'])).max()):.3f} {time.time()-t0:.0f}s", flush=True)
print("IoU after (vertex splat, all frames):", round(iou_all(params), 4), flush=True)
out = dict(delta=np.asarray(symmetric(params["delta"])), samples=samples,
           poses={k: np.asarray(params[k]) for k in ("ball", "hinge", "trans")})
pickle.dump(out, open("refine_mesh.pkl", "wb"))
print("saved refine_mesh.pkl")
