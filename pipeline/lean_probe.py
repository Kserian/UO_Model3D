import sys, pickle, numpy as np, jax.numpy as jnp
from scipy.spatial.transform import Rotation as Rot
from posefit_mesh import *
from posefit_mesh import _posed_j
P = pickle.load(open(sys.argv[1], "rb")); a, i = int(sys.argv[2]), int(sys.argv[3])
T = targets(a); m = T[..., 3] > 127
p0 = {k: np.asarray(v[i]) for k, v in P[a]["poses"].items()}
def iou(p):
    X = _posed_j({k: jnp.asarray(v) for k, v in p.items()}); r = []
    for d in range(5):
        mk = raster_vec(np.asarray(project(X, d))[tris], CANVAS_W, CANVAS_H); s = m[i, d]
        r.append((mk & s).sum() / max((mk | s).sum(), 1))
    return np.round(r, 3), np.mean(r)
def rot(p, joint, axis, deg):
    q = {k: v.copy() for k, v in p.items()}
    q["ball"][BI[JI[joint]]] = (Rot.from_euler(axis, deg, degrees=True) * Rot.from_rotvec(q["ball"][BI[JI[joint]]])).as_rotvec()
    return q
print("base", iou(p0))
for ax in "xyz":
    for j in ("pelvis", "spine", "chest"):
        for deg in (-8, -4, 4, 8):
            r, mn = iou(rot(p0, j, ax, deg))
            print(ax, j, deg, r, round(mn, 4))
for dx in (-0.03, -0.015, 0.015, 0.03):
    q = {k: v.copy() for k, v in p0.items()}; q["trans"][0] += dx; print("trans x", dx, iou(q))
