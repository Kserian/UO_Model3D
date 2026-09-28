"""Fit per-frame skeleton poses for every action (shape fixed from shape_fit.pkl)."""
import sys, time, pickle, os
import numpy as np
import jax, jax.numpy as jnp, optax
from PIL import Image
from body import *
from fit import *
from targets import targets
from vd import ACTIONS_PEOPLE
from viz import overlay_row

sf = pickle.load(open("shape_fit.pkl", "rb"))
fixed = {k: jnp.asarray(v) for k, v in sf["fixed"].items()}
S = params_to_shape({k: jnp.asarray(v) for k, v in sf["params"]["shape"].items()}, fixed)
stand_pose = jax.tree.map(lambda x: jnp.asarray(x[0]), sf["params"]["poses"])

CYCLIC = {0, 1, 2, 3, 23, 24}
MOUNTED = set(range(23, 30))
INIT_FROM = {1: 0, 3: 2, 24: 23, 8: 7}
ORDER = [4, 5, 6, 0, 1, 2, 3, 7, 8, 15, 9, 10, 11, 12, 13, 14, 16, 17, 18, 19, 20, 21, 22, 30, 31, 32, 33, 34,
         23, 24, 25, 26, 27, 28, 29]
out_path = "anim_fit.pkl"
results = pickle.load(open(out_path, "rb")) if os.path.exists(out_path) else {}
only = [int(a) for a in sys.argv[1:]] or ORDER


def mounted_init():
    p = jax.tree.map(lambda x: x, stand_pose)
    bi = {j: i for i, j in enumerate(BALL_IDX)}
    hi = {j: i for i, j in enumerate(HINGE_IDX)}
    ball = np.asarray(p["ball"]).copy(); hinge = np.asarray(p["hinge"]).copy()
    ball[bi[JI["hip.L"]]] = [-1.3, -0.5, 0.0]   # thighs forward (about X) and spread outward (about Y)
    ball[bi[JI["hip.R"]]] = [-1.3, 0.5, 0.0]
    hinge[hi[JI["knee.L"]]] = 1.3
    hinge[hi[JI["knee.R"]]] = 1.3
    return dict(ball=jnp.asarray(ball), hinge=jnp.asarray(hinge), trans=jnp.asarray([0.0, 0.0, 0.45]))


for a in only:
    if a in results:
        continue
    t0 = time.time()
    T = targets(a)
    F = len(T)
    Anp = T[..., 3].astype(np.float32) / 255.0
    y0, y1, x0, x1 = crop_box(Anp)
    A = jnp.asarray(Anp[..., y0:y1, x0:x1])
    pix = PIX[y0:y1, x0:x1]
    gw = 0.0 if a in MOUNTED else 1.0

    single = jax.jit(jax.value_and_grad(lambda pp, al: frame_loss(S, pp, al, gw, pix=pix)[0]))
    opt = optax.adam(0.02)

    if a in INIT_FROM and INIT_FROM[a] in results:
        src = results[INIT_FROM[a]]["poses"]
        inits = [jax.tree.map(lambda x: jnp.asarray(x[min(i, x.shape[0] - 1)]), src) for i in range(F)]
    else:
        inits = [mounted_init() if a in MOUNTED else stand_pose] + [None] * (F - 1)

    # --- sequential pass: each frame starts from the previous frame's solution
    poses = []
    prev = None
    for i in range(F):
        pp = inits[i] if inits[i] is not None else prev
        st = opt.init(pp)
        for it in range(350):
            l, g = single(pp, A[i])
            up, st = opt.update(g, st, pp)
            pp = optax.apply_updates(pp, up)
        poses.append(pp)
        prev = pp

    # --- joint refinement with temporal smoothness
    batch = jax.tree.map(lambda *xs: jnp.stack(xs), *poses)
    cyc = a in CYCLIC

    def joint_loss(bp):
        f = jax.vmap(lambda pp, al: frame_loss(S, pp, al, gw, pix=pix))
        l, d = f(bp, A)
        sm = 0.0
        if F > 1:
            for k in ("ball", "hinge", "trans"):
                x = bp[k]
                diff = x[1:] - x[:-1]
                sm += jnp.sum(diff ** 2)
                if cyc:
                    sm += jnp.sum((x[0] - x[-1]) ** 2) * 0.5
        return jnp.sum(l) + 0.05 * sm, jnp.sum(d)
    jvg = jax.jit(jax.value_and_grad(joint_loss, has_aux=True))
    opt2 = optax.adam(optax.exponential_decay(0.01, 300, 0.3))
    st = opt2.init(batch)
    for it in range(300):
        (l, d), g = jvg(batch)
        up, st = opt2.update(g, st, batch)
        batch = optax.apply_updates(batch, up)
    (l, d), _ = jvg(batch)
    per_frame = []
    for i in range(F):
        pp = jax.tree.map(lambda x: x[i], batch)
        per_frame.append(float(frame_loss(S, pp, A[i], gw, pix=pix)[1]))
    results[a] = dict(poses=jax.tree.map(np.asarray, batch), data_loss=per_frame, crop=(y0, y1, x0, x1))
    pickle.dump(results, open(out_path, "wb"))
    # QA overlay
    rows = []
    for i in range(F):
        pose = pose_from_params(jax.tree.map(lambda x: x[i], batch))
        P, R = fk(S, pose)
        rows.append(overlay_row(T[i][:, y0:y1, x0:x1], [render_sil(S, P, R, dd, pix=pix) for dd in range(5)], zoom=3))
    im = Image.new("RGB", (rows[0].width, sum(r.height for r in rows)))
    yy = 0
    for r in rows:
        im.paste(r, (0, yy)); yy += r.height
    os.makedirs("qa", exist_ok=True)
    im.save(f"qa/a{a:02d}_{ACTIONS_PEOPLE[a]}.png")
    print(f"action {a:2d} {ACTIONS_PEOPLE[a]:24s} frames={F} data={np.mean(per_frame):.3f} max={np.max(per_frame):.3f} {time.time()-t0:.0f}s", flush=True)
