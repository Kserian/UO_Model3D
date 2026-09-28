"""Split silhouette errors into 1-px boundary disagreement vs gross (>=2 px deep) errors, per action."""
import sys, pickle, numpy as np, jax.numpy as jnp
from scipy.ndimage import distance_transform_edt
from posefit_mesh import *
from posefit_mesh import _posed_j
from vd import ACTIONS_PEOPLE
P = pickle.load(open(sys.argv[1], "rb"))
rows = []
for a in range(35):
    T = targets(a); m = T[..., 3] > 127; F = len(T)
    hid = (horse_masks(a, F) & ~m) if a in HORSE_OF else np.zeros_like(m)
    thin = gross = area = 0; worst = (0, None)
    for i in range(F):
        X = _posed_j({k: jnp.asarray(v[i]) for k, v in P[a]["poses"].items()})
        for d in range(5):
            mk = raster_vec(np.asarray(project(X, d))[tris], CANVAS_W, CANVAS_H) & ~hid[i, d]
            s = m[i, d]
            red = s & ~mk; blue = mk & ~s
            dr = distance_transform_edt(~mk)[red]; db = distance_transform_edt(~s)[blue]
            g = (dr > 1.5).sum() + (db > 1.5).sum()
            thin += (dr <= 1.5).sum() + (db <= 1.5).sum(); gross += g; area += s.sum()
            if g > worst[0]: worst = (g, (i, d))
    rows.append((a, thin / area, gross / area, worst))
    print(f"{a:2d} {ACTIONS_PEOPLE[a]:24s} thin {thin/area:.3f}  gross {gross/area:.3f}  worst frame/dir {worst[1]} ({worst[0]} px)", flush=True)
