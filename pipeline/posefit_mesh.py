"""Pose fitting on the real skinned mesh (refined rest mesh + skin weights), all frames of an action jointly.

Loss per frame (5 UO directions):
  inside : projected vertices must lie inside the sprite silhouette (distance transform, bilinear)
  cover  : every sprite boundary pixel must have a projected vertex within ~0.7 px (min-distance, differentiable)
  limits : anatomical swing / twist limits per joint (swing-twist decomposition), hinge limits
  smooth : temporal smoothness between frames (cyclic for loops)
  prior  : pull toward a natural pose (small)
"""
import sys, os, time, pickle
import numpy as np
import jax, jax.numpy as jnp, optax
from scipy.ndimage import distance_transform_edt, binary_erosion
from body import *
from fit import params_to_shape, pose_from_params, BALL_IDX, HINGE_IDX, HINGE_AX
from rig import bone_defs
from targets import targets

sf = pickle.load(open("shape_fit.pkl", "rb"))
S = params_to_shape({k: jnp.asarray(v) for k, v in sf["params"]["shape"].items()}, {k: jnp.asarray(v) for k, v in sf["fixed"].items()})
md = pickle.load(open("mesh_data.pkl", "rb"))
ref = pickle.load(open("refine_mesh.pkl", "rb"))
DELTA_FILE = os.environ.get("UO_DELTA", "refine_mesh.pkl")        # rest-mesh offsets (shape refinement result)
V0 = jnp.asarray(md["v"] + pickle.load(open(DELTA_FILE, "rb"))["delta"], jnp.float32)
W = jnp.asarray(md["W"], jnp.float32)
P0, _ = fk(S, zero_pose())
defs = bone_defs({k: np.asarray(v) for k, v in S.items()}, np.asarray(P0))
joint_of = {d[0]: d[1] for d in defs}
BONE_JOINT = np.array([JI[joint_of[b]] for b in md["bones"]])
CAM = [camera(S, d) for d in range(5)]
RIGHT = jnp.stack([c[0] for c in CAM]); UP = jnp.stack([c[1] for c in CAM])
SC = S["scale"]
PX_OFF = 0.5
BI = {j: i for i, j in enumerate(BALL_IDX)}
HI = {j: i for i, j in enumerate(HINGE_IDX)}
MOUNTED = set(range(23, 30))
CYCLIC = {0, 1, 2, 3, 23, 24}

# lower-body vertices (ignored by the 'inside' term on mounted frames: the horse hides them in the sprites)
leg_cols = [md["bones"].index(b) for b in md["bones"] if b.split(".")[0] in ("thigh", "shin", "foot", "pelvis")]
LEGV = jnp.asarray(np.asarray(md["W"])[:, leg_cols].sum(1) > 0.5)

# ---------------------------------------------------------------- anatomical limits
sa, ca = np.sin(ARM_REST_ANGLE), np.cos(ARM_REST_ANGLE)
sl, cl = np.sin(LEG_REST_ANGLE), np.cos(LEG_REST_ANGLE)
# joint: (bone axis in rest frame, max swing deg, max |twist| deg)
LIM = {
    "spine": ((0, 0, 1), 35, 30), "chest": ((0, 0, 1), 30, 30), "neck": ((0, 0, 1), 35, 40), "head": ((0, 0, 1), 35, 45),
    "shoulder.L": ((sa, 0, -ca), 170, 75), "shoulder.R": ((-sa, 0, -ca), 170, 75),
    "wrist.L": ((sa, 0, -ca), 60, 80), "wrist.R": ((-sa, 0, -ca), 60, 80),
    "hip.L": ((sl, 0, -cl), 125, 40), "hip.R": ((-sl, 0, -cl), 125, 40),
    "ankle.L": ((0, -1, 0), 45, 25), "ankle.R": ((0, -1, 0), 45, 25),
}
LJ = list(LIM)
LIDX = np.array([BI[JI[j]] for j in LJ])
LAX = jnp.asarray(np.array([np.array(LIM[j][0]) / np.linalg.norm(LIM[j][0]) for j in LJ]), jnp.float32)
LSW = jnp.asarray(np.radians([LIM[j][1] for j in LJ]), jnp.float32)
LTW = jnp.asarray(np.radians([LIM[j][2] for j in LJ]), jnp.float32)


def swing_twist(r, a):
    th = jnp.sqrt(jnp.sum(r * r) + 1e-12)
    w = jnp.cos(th / 2); v = jnp.sin(th / 2) * r / th
    twist = 2 * jnp.arctan2(jnp.dot(v, a), w)
    twist = jnp.arctan2(jnp.sin(twist), jnp.cos(twist))
    R = rodrigues(r)
    swing = jnp.arccos(jnp.clip(jnp.dot(R @ a, a), -1 + 1e-6, 1 - 1e-6))
    return swing, twist


def limit_penalty(pp):
    b = pp["ball"][LIDX]
    sw, tw = jax.vmap(swing_twist)(b, LAX)
    pen = jnp.sum(jax.nn.relu(sw - LSW) ** 2) + jnp.sum(jax.nn.relu(jnp.abs(tw) - LTW) ** 2)
    # hips: no hyper-extension backwards, limited adduction (thigh direction in the pelvis frame)
    for side, sx in (("L", 1.0), ("R", -1.0)):
        r = pp["ball"][BI[JI["hip." + side]]]
        d = rodrigues(r) @ jnp.array([sx * sl, 0.0, -cl])
        pen += jax.nn.relu(d[1] - 0.45) ** 2 + jax.nn.relu(-sx * d[0] - 0.35) ** 2 + jax.nn.relu(d[2] - 0.6) ** 2
    h = pp["hinge"]
    for j in ("elbow.L", "elbow.R"):
        e = h[HI[JI[j]]]
        pen += jax.nn.relu(e) ** 2 + jax.nn.relu(-2.6 - e) ** 2
    for j in ("knee.L", "knee.R"):
        k = h[HI[JI[j]]]
        pen += jax.nn.relu(-k) ** 2 + jax.nn.relu(k - 2.6) ** 2
    return pen


def natural_prior(pp):
    b = pp["ball"]
    # everything but the root prefers small rotations (very weak)
    pr = jnp.sum(b[1:] ** 2) * 1.0
    if "clav" in pp:        # shoulder (clavicle) offsets: small unless the silhouettes need them, at most ~8 cm
        n = jnp.sqrt(jnp.sum(pp["clav"] ** 2, -1) + 1e-12)
        pr += 1500.0 * jnp.sum(pp["clav"] ** 2) + 50000.0 * jnp.sum(jax.nn.relu(n - 0.08) ** 2)
    return pr


# ---------------------------------------------------------------- mesh posing / projection
# arm chain bones (upper arm, forearm, hand) per side: they follow the clavicle offset
ARM_L = jnp.asarray([JI[joint_of[b]] in (JI["shoulder.L"], JI["elbow.L"], JI["wrist.L"]) for b in md["bones"]], jnp.float32)
ARM_R = jnp.asarray([JI[joint_of[b]] in (JI["shoulder.R"], JI["elbow.R"], JI["wrist.R"]) for b in md["bones"]], jnp.float32)


def posed(pp):
    pose = pose_from_params(pp)
    P, R = fk(S, pose)
    Rb = R[BONE_JOINT]
    tb = P[BONE_JOINT] - jnp.einsum("bij,bj->bi", Rb, P0[BONE_JOINT])
    if "clav" in pp:        # clavicle: the whole arm chain shifts by an offset given in the chest frame
        Rc = R[JI["chest"]]
        tb = tb + ARM_L[:, None] * (Rc @ pp["clav"][0])[None] + ARM_R[:, None] * (Rc @ pp["clav"][1])[None]
    X = jnp.einsum("bij,vj->vbi", Rb, V0) + tb[None]
    return jnp.einsum("vb,vbi->vi", W, X)


def project(X, d):
    return jnp.stack([ANCHOR_X + PX_OFF + SC * (X @ RIGHT[d]), ANCHOR_Y - SC * (X @ UP[d])], -1)


def bilinear(img, xy):
    x = jnp.clip(xy[:, 0] - 0.5, 0, img.shape[1] - 1.001)
    y = jnp.clip(xy[:, 1] - 0.5, 0, img.shape[0] - 1.001)
    x0 = jnp.floor(x).astype(int); y0 = jnp.floor(y).astype(int)
    fx, fy = x - x0, y - y0
    return (img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x0 + 1] * fx * (1 - fy)
            + img[y0 + 1, x0] * (1 - fx) * fy + img[y0 + 1, x0 + 1] * fx * fy)


NB = 260   # boundary pixels per view (padded)


GROUND = float(os.environ.get("UO_GROUND", "-0.070"))   # sole level of standing frames (the UO anchor is ~7 cm above it)
W_GROUND = float(os.environ.get("UO_W_GROUND", "1.0"))


def ground_penalty(X):
    """nothing sinks into the floor (0.3 px tolerance), in px^2 like the 'inside' term"""
    return jnp.mean(jax.nn.relu((GROUND - X[:, 2]) * SC - 0.3) ** 2)


def frame_terms(pp, dto, bpx, bm, mounted):
    X = posed(pp)
    ins = W_GROUND * 5.0 * ground_penalty(X); cov = 0.0
    for d in range(5):
        p = project(X, d)
        di = jnp.where(LEGV, bilinear(dto[d, 0], p), bilinear(dto[d, 1], p)) ** 2
        ins += jnp.mean(di)
        dist = jnp.sqrt(jnp.min(jnp.sum((bpx[d][:, None, :] - p[None, :, :]) ** 2, -1), 1) + 1e-9)
        cov += jnp.sum(bm[d] * jax.nn.relu(dist - 0.7) ** 2) / (jnp.sum(bm[d]) + 1.0)
    return ins, cov


HORSE_OF = {23: 0, 24: 1, 25: 2, 26: 2, 27: 2, 28: 2, 29: 2}   # rider action -> horse (body 0xC8) action
_horse = None


def horse_masks(a, F):
    """Masks of the horse drawn under the rider (same anchor). Rider pixels hidden by the horse are unknown."""
    global _horse
    if _horse is None:
        sys.path.insert(0, "../vdtool")
        import vdtool
        _, _horse = vdtool.read_vd("horse200.vd")
    import vdtool
    ha = HORSE_OF[a]
    out = np.zeros((F, 5, CANVAS_H, CANVAS_W), bool)
    for d in range(5):
        blk = _horse[ha * 5 + d]
        for i in range(F):
            fr = blk["frames"][i % len(blk["frames"])]
            rgba = vdtool.frame_rgba(fr, blk["palette"])
            x0, y0 = ANCHOR_X - fr["cx"], ANCHOR_Y - (fr["cy"] + fr["h"])
            ys, xs = np.nonzero(rgba[..., 3] > 0)
            ys, xs = ys + y0, xs + x0
            ok = (ys >= 0) & (ys < CANVAS_H) & (xs >= 0) & (xs < CANVAS_W)
            out[i, d, ys[ok], xs[ok]] = True
    return out


def prepare(a):
    T = targets(a)
    F = len(T)
    m = T[..., 3] > 127
    allowed = m | horse_masks(a, F) if a in HORSE_OF else m     # rider's LOWER body may be hidden behind the horse
    dto_a = np.stack([[np.maximum(distance_transform_edt(~allowed[i, d]) - 0.5, 0) for d in range(5)] for i in range(F)]).astype(np.float32)
    dto_r = np.stack([[np.maximum(distance_transform_edt(~m[i, d]) - 0.5, 0) for d in range(5)] for i in range(F)]).astype(np.float32)
    dto = np.stack([dto_a, dto_r], 2)            # (F,5,2,H,W): [allowed for legs/pelvis, rider-only for the rest]
    bpx = np.zeros((F, 5, NB, 2), np.float32); bm = np.zeros((F, 5, NB), np.float32)
    for i in range(F):
        for d in range(5):
            edge = m[i, d] & ~binary_erosion(m[i, d])
            ys, xs = np.nonzero(edge)
            if len(ys) > NB:
                sel = np.linspace(0, len(ys) - 1, NB).astype(int); ys, xs = ys[sel], xs[sel]
            n = len(ys)
            bpx[i, d, :n] = np.stack([xs + 0.5, ys + 0.5], 1); bm[i, d, :n] = 1
    return F, jnp.asarray(dto), jnp.asarray(bpx), jnp.asarray(bm), m


def fit_action(a, init, iters=500, lr=0.01, w_smooth=0.3, w_lim=200.0, w_prior=0.02, log=True):
    F, dto, bpx, bm, m = prepare(a)
    mounted = jnp.asarray(a in MOUNTED)
    cyc = a in CYCLIC
    init = {k: jnp.asarray(v) for k, v in init.items()}

    def loss(pp):
        ins, cov = jax.lax.map(lambda x: frame_terms(x[0], x[1], x[2], x[3], mounted),
                               (pp, dto, bpx, bm))
        lim = jax.vmap(limit_penalty)(pp)
        pri = jax.vmap(natural_prior)(pp)
        sm = 0.0
        if F > 1:
            for k in pp:
                x = pp[k]
                wk = 20.0 if k in ("trans", "clav") else 1.0
                sm += jnp.sum((x[1:] - x[:-1]) ** 2) * wk
                if cyc:
                    sm += jnp.sum((x[0] - x[-1]) ** 2) * wk
        total = jnp.sum(4.0 * ins + cov) + w_lim * jnp.sum(lim) + w_prior * jnp.sum(pri) + w_smooth * sm
        return total, (jnp.mean(ins), jnp.mean(cov), jnp.sum(lim))

    vg = jax.jit(jax.value_and_grad(loss, has_aux=True))
    opt = optax.adam(optax.exponential_decay(lr, iters, 0.2))
    pp = init; st = opt.init(pp)
    t0 = time.time()
    for it in range(iters):
        (l, aux), g = vg(pp)
        up, st = opt.update(g, st, pp)
        pp = optax.apply_updates(pp, up)
        if log and (it % 100 == 0 or it == iters - 1):
            print(f"    a{a} it {it} loss {float(l):.2f} inside {float(aux[0]):.3f} cover {float(aux[1]):.3f} limits {float(aux[2]):.4f} {time.time()-t0:.0f}s", flush=True)
    return {k: np.asarray(v) for k, v in pp.items()}, m


# ---------------------------------------------------------------- evaluation
from texbake import tri_raster
tris = np.asarray(md["tris"])


def raster_vec(P, W_, H_, maxbox=12):
    mn = np.floor(P.min(1)).astype(int); mx = np.ceil(P.max(1)).astype(int)
    size = np.clip(mx - mn, 0, maxbox)
    a, b, c = P[:, 0], P[:, 1], P[:, 2]
    den = (b[:, 1] - c[:, 1]) * (a[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (a[:, 1] - c[:, 1])
    ok = np.abs(den) > 1e-12
    img = np.zeros((H_, W_), bool)
    for dy in range(int(size[:, 1].max()) + 1):
        for dx in range(int(size[:, 0].max()) + 1):
            t = np.nonzero(ok & (dx <= size[:, 0]) & (dy <= size[:, 1]))[0]
            px = mn[t, 0] + dx; py = mn[t, 1] + dy
            cx, cy = px + 0.5, py + 0.5
            aa, bb, cc, dd = a[t], b[t], c[t], den[t]
            l0 = ((bb[:, 1] - cc[:, 1]) * (cx - cc[:, 0]) + (cc[:, 0] - bb[:, 0]) * (cy - cc[:, 1])) / dd
            l1 = ((cc[:, 1] - aa[:, 1]) * (cx - cc[:, 0]) + (aa[:, 0] - cc[:, 0]) * (cy - cc[:, 1])) / dd
            l2 = 1 - l0 - l1
            k = (l0 >= -1e-4) & (l1 >= -1e-4) & (l2 >= -1e-4) & (px >= 0) & (py >= 0) & (px < W_) & (py < H_)
            img[py[k], px[k]] = True
    return img


_posed_j = jax.jit(posed)
_lim_j = jax.jit(jax.vmap(limit_penalty))


def evaluate(a, poses, masks=None):
    """returns per-frame (worst-view IoU, mean IoU) and per-frame limit penalty.
    Mounted actions: model pixels that the horse would cover (and the rider sprite does not) are not errors."""
    if masks is None:
        masks = targets(a)[..., 3] > 127
    F = masks.shape[0]
    hidden = (horse_masks(a, F) & ~masks) if a in HORSE_OF else np.zeros_like(masks)
    res = []
    for i in range(F):
        pp = {k: jnp.asarray(v[i]) for k, v in poses.items()}
        X = np.asarray(_posed_j(pp))
        ious = []
        for d in range(5):
            p = np.asarray(project(jnp.asarray(X), d))
            mk = raster_vec(p[tris], CANVAS_W, CANVAS_H) & ~hidden[i, d]
            s = masks[i, d]
            ious.append((mk & s).sum() / max((mk | s).sum(), 1))
        res.append((min(ious), float(np.mean(ious))))
    lim = np.asarray(_lim_j({k: jnp.asarray(v) for k, v in poses.items()}))
    return np.array(res), lim
