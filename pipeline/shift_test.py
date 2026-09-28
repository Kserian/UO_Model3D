"""How much would a per-(frame, direction) 2D image shift of the model improve the IoU? (integer shifts, +-3 px)"""
import sys, pickle, numpy as np, jax.numpy as jnp
from posefit_mesh import *
from posefit_mesh import _posed_j
from vd import ACTIONS_PEOPLE
P = pickle.load(open(sys.argv[1], "rb"))
R = 3
allsh = []
for a in range(35):
    T = targets(a); m = T[..., 3] > 127; F = len(T)
    hid = (horse_masks(a, F) & ~m) if a in HORSE_OF else np.zeros_like(m)
    i0 = []; ib = []; sh = []
    for i in range(F):
        X = _posed_j({k: jnp.asarray(v[i]) for k, v in P[a]["poses"].items()})
        for d in range(5):
            mk = raster_vec(np.asarray(project(X, d))[tris], CANVAS_W, CANVAS_H)
            s = m[i, d]; best = (-1, 0, 0)
            for dy in range(-R, R + 1):
                for dx in range(-R, R + 1):
                    k = np.roll(np.roll(mk, dy, 0), dx, 1) & ~hid[i, d]
                    iou = (k & s).sum() / max((k | s).sum(), 1)
                    if dx == 0 and dy == 0: z = iou
                    if iou > best[0]: best = (iou, dx, dy)
            i0.append(z); ib.append(best[0]); sh.append(best[1:])
    sh = np.array(sh); allsh.append(sh)
    nz = (np.abs(sh).max(1) > 0).mean()
    print(f"{a:2d} {ACTIONS_PEOPLE[a]:24s} IoU {np.mean(i0):.3f} -> {np.mean(ib):.3f}  shifted views {nz:.2f}  mean|shift| {np.abs(sh).mean(0)}", flush=True)
