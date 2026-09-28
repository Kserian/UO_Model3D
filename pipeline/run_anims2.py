"""Per-frame pose fitting with chamfer (distance-transform) terms and coarse-to-fine blur.
Limb identity is never swapped: every frame starts from the previous frame (frame 0 from the stand pose)."""
import sys, time, pickle, os
import numpy as np
import jax, jax.numpy as jnp, optax
from scipy.ndimage import distance_transform_edt
from PIL import Image
from body import *
from fit import *
from targets import targets
from vd import ACTIONS_PEOPLE
from viz import overlay_row

sf = pickle.load(open("shape_fit.pkl", "rb"))
fixed = {k: jnp.asarray(v) for k, v in sf["fixed"].items()}
S = params_to_shape({k: jnp.asarray(v) for k, v in sf["params"]["shape"].items()}, fixed)
prev_res = pickle.load(open("anim_fit_run1.pkl", "rb"))
stand_pose = {k: jnp.asarray(v[0]) for k, v in prev_res[4]["poses"].items()}

CYCLIC = {0, 1, 2, 3, 23, 24}
MOUNTED = set(range(23, 30))
out_path = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "anim_fit2.pkl"
acts = [int(a) for a in sys.argv[1:] if a.isdigit()]
results = pickle.load(open(out_path, "rb")) if os.path.exists(out_path) else {}
FIRST_FROM = {9: 7, 10: 7, 11: 7, 18: 7, 19: 8, 12: 8, 13: 8, 14: 8}   # frame 0 starts from the combat stance
PER_FRAME_FROM = {2: 0, 3: 0, 15: 0}                                 # cycle starts from the fitted walk


def lookup(a):
    for f in ("anim_fit2a.pkl", "anim_fit2b.pkl", out_path, "anim_fit_run1.pkl"):
        if os.path.exists(f):
            r = pickle.load(open(f, "rb"))
            if a in r:
                if f == "anim_fit_run1.pkl" and a not in (0, 1, 4, 5, 6, 16, 30, 31, 32, 34):
                    continue   # only trust the good first-pass results
                return r[a]["poses"]
    return None

BI = {j: i for i, j in enumerate(BALL_IDX)}
HI = {j: i for i, j in enumerate(HINGE_IDX)}
MIR = jnp.array([1.0, -1.0, -1.0])


def swap(pp, balls, hinges):
    b, h = pp["ball"], pp["hinge"]
    for l in balls:
        il, ir = BI[JI[l + ".L"]], BI[JI[l + ".R"]]
        bl, br = b[il], b[ir]
        b = b.at[il].set(br * MIR).at[ir].set(bl * MIR)
    for l in hinges:
        il, ir = HI[JI[l + ".L"]], HI[JI[l + ".R"]]
        hl, hr = h[il], h[ir]
        h = h.at[il].set(hr).at[ir].set(hl)
    return dict(ball=b, hinge=h, trans=pp["trans"])


# Left/right hypotheses for the FIRST frame only. In the front (dir 0) and back (dir 4) views left and right limbs
# are on fixed screen sides and a forward foot is drawn lower, so these two views decide which limb is which.
LR_VARIANTS = {
    "legs": lambda p: swap(p, ["hip", "ankle"], ["knee"]),
    "arms": lambda p: swap(p, ["shoulder", "wrist"], ["elbow"]),
    "both": lambda p: swap(p, ["hip", "ankle", "shoulder", "wrist"], ["knee", "elbow"]),
}


RIDE_LEGS = {  # riding template: thighs forward and spread around the horse, knees bent
    "hip.L": [-1.2, -0.55, 0.0], "hip.R": [-1.2, 0.55, 0.0], "ankle.L": [0.3, 0.0, 0.0], "ankle.R": [0.3, 0.0, 0.0]}
RIDE_KNEE = 1.4
RIDE_IDX = np.array([BI[JI[j]] for j in RIDE_LEGS])
RIDE_VAL = jnp.asarray(np.array(list(RIDE_LEGS.values())), jnp.float32)
KNEE_IDX = np.array([HI[JI["knee.L"]], HI[JI["knee.R"]]])


def ride_prior(pp):
    # UO rider sprites have the parts behind the horse removed, so the legs are held near a riding pose
    return 8.0 * (jnp.sum((pp["ball"][RIDE_IDX] - RIDE_VAL) ** 2) + jnp.sum((pp["hinge"][KNEE_IDX] - RIDE_KNEE) ** 2))


def mounted_init():
    ball = np.asarray(stand_pose["ball"]).copy(); hinge = np.asarray(stand_pose["hinge"]).copy()
    for j, v in RIDE_LEGS.items():
        ball[BI[JI[j]]] = v
    hinge[HI[JI["knee.L"]]] = RIDE_KNEE
    hinge[HI[JI["knee.R"]]] = RIDE_KNEE
    return dict(ball=jnp.asarray(ball), hinge=jnp.asarray(hinge), trans=jnp.asarray([0.0, 0.0, 0.45]))


LIMITS = {  # joint: ((xlo,xhi),(ylo,yhi),(zlo,zhi)) on the axis-angle vector in the rest frame
    "hip.L": ((-2.3, 0.6), (-0.9, 0.5), (-0.7, 0.7)), "hip.R": ((-2.3, 0.6), (-0.5, 0.9), (-0.7, 0.7)),
    "ankle.L": ((-0.8, 0.8), (-0.5, 0.5), (-0.5, 0.5)), "ankle.R": ((-0.8, 0.8), (-0.5, 0.5), (-0.5, 0.5)),
    "spine": ((-0.8, 0.8), (-0.6, 0.6), (-0.7, 0.7)), "chest": ((-0.8, 0.8), (-0.6, 0.6), (-0.7, 0.7)),
    "neck": ((-0.8, 0.8), (-0.6, 0.6), (-0.9, 0.9)), "head": ((-0.8, 0.8), (-0.6, 0.6), (-0.9, 0.9)),
    "wrist.L": ((-1.2, 1.2), (-1.2, 1.2), (-1.2, 1.2)), "wrist.R": ((-1.2, 1.2), (-1.2, 1.2), (-1.2, 1.2)),
}
LIM_IDX = np.array([BI[JI[j]] for j in LIMITS])
LIM_LO = jnp.asarray(np.array([[r[0] for r in v] for v in LIMITS.values()]), jnp.float32)
LIM_HI = jnp.asarray(np.array([[r[1] for r in v] for v in LIMITS.values()]), jnp.float32)


def limit_penalty(pp):
    b = pp["ball"][LIM_IDX]
    return jnp.sum(jax.nn.relu(LIM_LO - b) ** 2 + jax.nn.relu(b - LIM_HI) ** 2) * 20.0


def full_loss(pp, alpha, dt, gw, pix, tau, wch):
    pose = pose_from_params(pp)
    P, R = fk(S, pose)
    occs, dmins = [], []
    for d in range(5):
        o, dist = render_sil(S, P, R, d, tau=tau, return_parts=True, pix=pix)
        occs.append(o); dmins.append(jnp.min(dist, 0))
    occ = jnp.stack(occs); dmin = jnp.stack(dmins)
    data = jnp.mean((occ - alpha) ** 2) * 100.0
    cham = jnp.mean(occ * dt) + jnp.mean(alpha * jax.nn.relu(dmin))
    reg = 1e-3 * jnp.sum(pp["ball"] ** 2) + hinge_limit_penalty(pp["hinge"]) + limit_penalty(pp)
    reg = reg + jnp.where(gw == 0.0, ride_prior(pp), 0.0)
    mz = foot_min_z(S, P, R)
    ground = gw * (mz ** 2) * 100.0 + 10.0 * jax.nn.relu(-mz - 0.01) ** 2 * 100
    return data + wch * cham + reg + ground, data


for a in acts:
    t0 = time.time()
    T = targets(a)
    F = len(T)
    Anp = T[..., 3].astype(np.float32) / 255.0
    y0, y1, x0, x1 = crop_box(Anp, margin=10)
    A = Anp[..., y0:y1, x0:x1]
    DT = np.stack([[distance_transform_edt(A[i, d] < 0.5) for d in range(5)] for i in range(F)]).astype(np.float32)
    A = jnp.asarray(A); DT = jnp.asarray(DT)
    pix = PIX[y0:y1, x0:x1]
    gw = 0.0 if a in MOUNTED else 1.0
    coarse = jax.jit(jax.value_and_grad(lambda pp, al, dt: full_loss(pp, al, dt, gw, pix, 1.2, 2.0)[0]))
    fine = jax.jit(jax.value_and_grad(lambda pp, al, dt: full_loss(pp, al, dt, gw, pix, 0.45, 0.0)[0]))
    fine_eval = jax.jit(lambda pp, al, dt: full_loss(pp, al, dt, gw, pix, 0.45, 0.0))

    @jax.jit
    def front_back(pp, al):
        P, R = fk(S, pose_from_params(pp))
        return sum(jnp.mean((render_sil(S, P, R, d, pix=pix) - al[d]) ** 2) * 100 for d in (0, 4))

    def run(fn, pp, al, dt, n, lr):
        opt = optax.adam(lr); st = opt.init(pp)
        for _ in range(n):
            l, g = fn(pp, al, dt)
            up, st = opt.update(g, st, pp)
            pp = optax.apply_updates(pp, up)
        return pp

    base = mounted_init() if a in MOUNTED else stand_pose
    if a in FIRST_FROM and lookup(FIRST_FROM[a]) is not None:
        base = {k: jnp.asarray(v[0]) for k, v in lookup(FIRST_FROM[a]).items()}
    extra = lookup(PER_FRAME_FROM[a]) if a in PER_FRAME_FROM else None
    cyc = a in CYCLIC

    def fit_frame(i, init):
        # starts: previous frame (and, for run/advance cycles, the walk frame with the same index);
        # each start: plain silhouette fit, and long-range pull + fit; keep the best. Limb identity is never swapped.
        starts = [init]
        if extra is not None and i < extra["trans"].shape[0]:
            starts.append({k: jnp.asarray(v[i]) for k, v in extra.items()})
        best, bl = None, np.inf
        for st0 in starts:
            c1 = run(fine, st0, A[i], DT[i], 300, 0.02)
            c2 = run(fine, run(coarse, st0, A[i], DT[i], 120, 0.03), A[i], DT[i], 300, 0.02)
            for c in (c1, c2):
                l = float(fine_eval(c, A[i], DT[i])[0])
                if l < bl:
                    best, bl = c, l
        return best, bl

    poses, losses = [], []
    prev = base
    for i in range(F):
        p, l = fit_frame(i, prev)
        if i == 0:
            fb = float(front_back(p, A[0]))
            chosen = "as fitted"
            for vn, fn_ in LR_VARIANTS.items():
                q = run(fine, fn_(p), A[0], DT[0], 300, 0.015)
                ql = float(fine_eval(q, A[0], DT[0])[0]); qfb = float(front_back(q, A[0]))
                if qfb < 0.95 * fb and ql < 1.05 * l:
                    p, l, fb, chosen = q, ql, qfb, vn + " L/R matched to original"
            print(f"  action {a} frame 0 left/right: {chosen}", flush=True)
        poses.append(p); losses.append(l)
        prev = p
    if cyc and F > 1:
        # second pass around the loop: frame 0 continues from the last frame, and so on
        prev = poses[-1]
        for i in range(F):
            p, l = fit_frame(i, prev)
            if l < losses[i]:
                poses[i], losses[i] = p, l
            prev = poses[i]

    batch = jax.tree.map(lambda *xs: jnp.stack(xs), *poses)

    def joint_loss(bp):
        l, d = jax.vmap(lambda pp, al, dt: full_loss(pp, al, dt, gw, pix, 0.45, 0.0))(bp, A, DT)
        sm = 0.0
        if F > 1:
            for k in ("ball", "hinge", "trans"):
                x = bp[k]
                sm += jnp.sum((x[1:] - x[:-1]) ** 2)
                if cyc:
                    sm += 0.5 * jnp.sum((x[0] - x[-1]) ** 2)
        return jnp.sum(l) + 0.05 * sm, jnp.sum(d)
    jvg = jax.jit(jax.value_and_grad(joint_loss, has_aux=True))
    opt2 = optax.adam(optax.exponential_decay(0.01, 250, 0.3)); st = opt2.init(batch)
    for _ in range(250):
        (l, d), g = jvg(batch)
        up, st = opt2.update(g, st, batch)
        batch = optax.apply_updates(batch, up)
    worst = []
    rows = []
    for i in range(F):
        pp = jax.tree.map(lambda x: x[i], batch)
        P, R = fk(S, pose_from_params(pp))
        occ = [render_sil(S, P, R, dd, pix=pix) for dd in range(5)]
        o = np.stack([np.asarray(x) for x in occ]) > 0.5
        s = np.asarray(A[i]) > 0.5
        worst.append(min((o[d] & s[d]).sum() / max((o[d] | s[d]).sum(), 1) for d in range(5)))
        rows.append(overlay_row(T[i][:, y0:y1, x0:x1], occ, zoom=3))
    results = pickle.load(open(out_path, "rb")) if os.path.exists(out_path) else {}
    results[a] = dict(poses=jax.tree.map(np.asarray, batch), worst_iou=worst, crop=(y0, y1, x0, x1))
    pickle.dump(results, open(out_path, "wb"))
    im = Image.new("RGB", (rows[0].width, sum(r.height for r in rows)))
    yy = 0
    for r in rows:
        im.paste(r, (0, yy)); yy += r.height
    os.makedirs("qa2", exist_ok=True)
    im.save(f"qa2/a{a:02d}_{ACTIONS_PEOPLE[a]}.png")
    print(f"action {a:2d} {ACTIONS_PEOPLE[a]:24s} frames={F} worstIoU mean={np.mean(worst):.3f} min={np.min(worst):.3f} {time.time()-t0:.0f}s", flush=True)
