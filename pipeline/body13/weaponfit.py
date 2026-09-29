"""calibrate how a weapon sits in the hand from the original UO weapon frames (anim.mul, e.g. katana 627):
a rigid stick (grip point + direction + length) in the hand bone's local frame, one for all frames, maximising the
IoU of the drawn stick with the weapon sprite. usage: weaponfit.py anim bone out.json [--len 0.9]"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
import sys, json, numpy as np
from numba import njit
sys.path.insert(0, HERE)
from itemframes import load, canvas
from shape13 import Shape, load_params
from skel13 import Skel13
from posefit13 import Frame13
from fk import rig_world

ANIM, BONE, OUT = int(sys.argv[1]), sys.argv[2], sys.argv[3]
r = np.load("rig_poses.npz"); v = np.load("views_all.npz"); bones = list(r["bones"])
S = Shape(v["U"], v["BV"], v["BDOM"], bones); Vf = S.build(load_params("shape_r2.json"), full=True)
K = Skel13(S, r["R"], r["parent"], bones, Vf); P = json.load(open(sys.argv[sys.argv.index("--poses") + 1] if "--poses" in sys.argv else "poses13_r3.json"))
fk = {tuple(int(x) for x in k): n for n, k in enumerate(r["keys"])}
it = load(ANIM); b = K.ix[BONE]
views = []; cache = {}
for n, k in enumerate(v["keys"]):
    a, i, d = (int(x) for x in k)
    m = canvas(it.get((a, d)), i)[..., 3] > 0
    if not m.any() or "%d,%d" % (a, i) not in P: continue
    if (a, i) not in cache:
        f = fk[(a, i)]
        fr = Frame13(K, None, None, None, None, r["Brel"], None, None, [], r["loc"][f], r["quat"][f])
        Sk = fr.skin(np.array(P["%d,%d" % (a, i)]["x"]))
        cache[(a, i)] = Sk[b] @ K.R[b]                                   # bone pose matrix (armature)
    M = v["C"][n] @ rig_world(d) @ cache[(a, i)]
    views.append((M, m))
print("views with the weapon", len(views))
Ms = np.array([x[0] for x in views]); masks = np.array([x[1] for x in views])


from scipy.ndimage import distance_transform_edt
DT = np.array([distance_transform_edt(~m) for m in masks])               # distance to the sprite
PIX = [np.argwhere(m)[:, ::-1] + 0.5 for m in masks]                        # sprite pixel centres (x, y)
NP = max(len(p) for p in PIX); PX = np.zeros((len(PIX), NP, 2)); PN = np.array([len(p) for p in PIX])
for k, p in enumerate(PIX): PX[k, :len(p)] = p


@njit(cache=True)
def score(Ms, DT, PX, PN, p0, u, L, rad):
    """- mean symmetric chamfer distance (px) between the projected stick and the sprite (higher is better)"""
    tot = 0.0; ns = 40
    for k in range(Ms.shape[0]):
        M = Ms[k]
        a0 = p0; a1 = p0 + u * L
        ax = (M[0, 0] * a0[0] + M[0, 1] * a0[1] + M[0, 2] * a0[2] + M[0, 3] + 1.0) * 68.0
        ay = (1.0 - (M[1, 0] * a0[0] + M[1, 1] * a0[1] + M[1, 2] * a0[2] + M[1, 3])) * 60.0
        bx = (M[0, 0] * a1[0] + M[0, 1] * a1[1] + M[0, 2] * a1[2] + M[0, 3] + 1.0) * 68.0
        by = (1.0 - (M[1, 0] * a1[0] + M[1, 1] * a1[1] + M[1, 2] * a1[2] + M[1, 3])) * 60.0
        d1 = 0.0
        for s in range(ns + 1):
            x = ax + (bx - ax) * s / ns; y = ay + (by - ay) * s / ns
            xi = min(max(int(x), 0), 135); yi = min(max(int(y), 0), 119)
            d1 += min(DT[k, yi, xi], 15.0)
        d1 /= ns + 1
        d2 = 0.0; ex = bx - ax; ey = by - ay; ll = ex * ex + ey * ey + 1e-9
        for j in range(PN[k]):
            qx = PX[k, j, 0]; qy = PX[k, j, 1]
            t = ((qx - ax) * ex + (qy - ay) * ey) / ll
            t = min(max(t, 0.0), 1.0)
            dx = ax + ex * t - qx; dy = ay + ey * t - qy
            d2 += min(np.sqrt(dx * dx + dy * dy), 15.0)
        d2 /= max(PN[k], 1)
        tot += 0.5 * (d1 + d2)
    return -tot / Ms.shape[0]


def unit(th, ph):
    return np.array([np.sin(th) * np.cos(ph), np.sin(th) * np.sin(ph), np.cos(th)])


L0 = float(sys.argv[sys.argv.index("--len") + 1]) if "--len" in sys.argv else 0.9
best = (-np.inf, None)
# coarse search of the direction (hand local), grip at the fist centre
fist = np.linalg.inv(K.R[b])[:3, :3] @ (np.mean([K.R[K.ix[f + BONE[-2:]]][:3, 3] for f in ("finger2-1", "finger5-1")], 0) - K.R[b][:3, 3])
print("fist centre in hand space", np.round(fist, 3))
for th in np.linspace(0, np.pi, 13):
    for ph in np.linspace(-np.pi, np.pi, 24, endpoint=False):
        u = unit(th, ph); s = score(Ms[::3], DT[::3], PX[::3], PN[::3], fist, u, L0, 1.2)
        if s > best[0]: best = (s, (th, ph))
print("coarse best dir", np.round(best[1], 3), "chamfer %.2f px" % -best[0])
x = np.array([best[1][0], best[1][1], fist[0], fist[1], fist[2], L0])
f = score(Ms, DT, PX, PN, fist, unit(x[0], x[1]), x[5], 1.2)
steps = np.array([0.1, 0.1, 0.02, 0.02, 0.02, 0.08])
for sc_ in (1, 0.5, 0.25, 0.12):
    for _ in range(3):
        imp = False
        for j in range(6):
            for sg in (1, -1):
                y = x.copy(); y[j] += sg * steps[j] * sc_
                fy = score(Ms, DT, PX, PN, y[2:5], unit(y[0], y[1]), y[5], 1.2)
                if fy > f + 1e-4: x, f = y, fy; imp = True; break
        if not imp: break
    print("scale %.2f chamfer %.3f px" % (sc_, -f), flush=True)
u = unit(x[0], x[1]); p0 = x[2:5]
json.dump(dict(anim=ANIM, bone=BONE, grip=p0.tolist(), dir=u.tolist(), length=float(x[5]), iou=float(f)), open(OUT, "w"), indent=1)
print("grip (hand local)", np.round(p0, 3), "dir", np.round(u, 3), "length %.2f" % x[5], "chamfer %.3f px" % -f)
