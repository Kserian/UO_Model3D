"""Parametric body-part shape search scored by the TRUE silhouette IoU (rasterised mesh vs sprites), poses fixed.
Parameters: radial thickness of upper arm / forearm / thigh / shin, hand & head size, foot length & width."""
import os, sys, pickle, time, json
import numpy as np
import jax, jax.numpy as jnp
from multiprocessing import Pool
os.environ.setdefault("UO_DELTA", "refine_infl.pkl")
from posefit_mesh import (md, defs, P0, pose_from_params, fk, S, W, BONE_JOINT, project, raster_vec, tris, targets,
                          horse_masks, HORSE_OF, CANVAS_W, CANVAS_H)

POSES = sys.argv[1] if len(sys.argv) > 1 else "final_poses_v5.pkl"
STEP = int(os.environ.get("UO_FSTEP", "2"))
final = pickle.load(open(POSES, "rb"))
base = np.asarray(md["v"] + pickle.load(open(os.environ["UO_DELTA"], "rb"))["delta"], np.float64)
Wn = np.asarray(md["W"], np.float64); bones = md["bones"]
bd = {d[0]: (np.asarray(d[2], float), np.asarray(d[3], float)) for d in defs}

PARAMS = ["upper_arm", "forearm", "thigh", "shin", "hand", "head", "foot_len", "foot_w"]


def shaped(s):
    V = base.copy(); disp = np.zeros_like(V)
    for j, b in enumerate(bones):
        g = b.split(".")[0]
        h, t = bd[b]; u = (t - h) / np.linalg.norm(t - h)
        rel = base - h; along = (rel @ u)[:, None] * u; rad = rel - along
        if g in ("upper_arm", "forearm", "thigh", "shin"):
            dj = (s[g] - 1) * rad
        elif g == "hand":
            dj = (s["hand"] - 1) * rel
        elif g == "head":
            c = h + 0.5 * (t - h); dj = (s["head"] - 1) * (base - c)
        elif g == "foot":
            dj = (s["foot_len"] - 1) * along + (s["foot_w"] - 1) * rad
        else:
            continue
        disp += Wn[:, j:j + 1] * dj
    return V + disp


@jax.jit
def posed_with(pp, V):
    pose = pose_from_params(pp)
    P, R = fk(S, pose)
    Rb = R[BONE_JOINT]
    tb = P[BONE_JOINT] - jnp.einsum("bij,bj->bi", Rb, P0[BONE_JOINT])
    X = jnp.einsum("bij,vj->vbi", Rb, V) + tb[None]
    return jnp.einsum("vb,vbi->vi", W, X)


SAMPLES = []
MASKS = {}
for a in range(35):
    T = targets(a); m = T[..., 3] > 127; F = len(T)
    hid = (horse_masks(a, F) & ~m) if a in HORSE_OF else np.zeros_like(m)
    for i in range(0, F, STEP):
        SAMPLES.append((a, i)); MASKS[(a, i)] = (m[i], hid[i])


def score_proj(item):
    (a, i), P2s = item
    s, hid = MASKS[(a, i)]
    out = []
    for d in range(5):
        mk = raster_vec(P2s[d][tris], CANVAS_W, CANVAS_H) & ~hid[d]
        out.append((mk & s[d]).sum() / max((mk | s[d]).sum(), 1))
    return out


def score(s, pool):
    V = jnp.asarray(shaped(s), jnp.float32)
    items = []
    for a, i in SAMPLES:
        X = posed_with({k: jnp.asarray(v[i]) for k, v in final[a]["poses"].items()}, V)
        items.append(((a, i), [np.asarray(project(X, d)) for d in range(5)]))
    r = np.array(pool.map(score_proj, items, chunksize=8))
    acts = np.array([a for a, _ in SAMPLES])
    per_act = np.array([r[acts == a].mean() for a in range(35)])
    return per_act.mean(), per_act


if __name__ == "__main__":
    s = {p: 1.0 for p in PARAMS}
    with Pool(4) as pool:
        t0 = time.time()
        best, pa = score(s, pool)
        print("start mean IoU %.4f  (%d frames, %.0fs)" % (best, len(SAMPLES), time.time() - t0), flush=True)
        for step in (0.10, 0.05, 0.025):
            improved = True
            while improved:
                improved = False
                for p in PARAMS:
                    for sg in (+1, -1):
                        c = dict(s); c[p] = s[p] + sg * step
                        v, pa_c = score(c, pool)
                        if v > best + 1e-4:
                            best, s, pa = v, c, pa_c; improved = True
                            print("  %s -> %.3f   mean IoU %.4f" % (p, c[p], v), flush=True)
                            break
            print("step %.3f done: %s  IoU %.4f" % (step, json.dumps({k: round(v, 3) for k, v in s.items()}), best), flush=True)
            json.dump(s, open("param_shape.json", "w"))
    V = shaped(s)
    pickle.dump(dict(delta=(V - np.asarray(md["v"])).astype(np.float32), params=s), open("refine_param.pkl", "wb"))
    print("saved refine_param.pkl", flush=True)
