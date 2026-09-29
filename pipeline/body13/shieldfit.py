"""calibrate a shield (disc) on the left forearm from the original UO shield frames (anim.mul, heater 582):
centre + normal + radius in the forearm's local frame, one for all frames, maximising the IoU with the sprite.
usage: shieldfit.py anim bone out.json"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
import sys, json, numpy as np
sys.path.insert(0, HERE)
from itemframes import load, canvas
from shape13 import Shape, load_params
from skel13 import Skel13
from posefit13 import Frame13
from fk import rig_world
from fastr import raster_one

ANIM, BONE, OUT = int(sys.argv[1]), sys.argv[2], sys.argv[3]
POSES = sys.argv[sys.argv.index("--poses") + 1] if "--poses" in sys.argv else "poses13_r3.json"
r = np.load("rig_poses.npz"); v = np.load("views_all.npz"); bones = list(r["bones"])
S = Shape(v["U"], v["BV"], v["BDOM"], bones); Vf = S.build(load_params("shape_r2.json"), full=True)
K = Skel13(S, r["R"], r["parent"], bones, Vf); P = json.load(open(POSES))
fk = {tuple(int(x) for x in k): n for n, k in enumerate(r["keys"])}
it = load(ANIM); b = K.ix[BONE]
Ms, masks = [], []; cache = {}
for n, k in enumerate(v["keys"]):
    a, i, d = (int(x) for x in k)
    m = canvas(it.get((a, d)), i)[..., 3] > 0
    if not m.any() or "%d,%d" % (a, i) not in P: continue
    if (a, i) not in cache:
        f = fk[(a, i)]
        fr = Frame13(K, None, None, None, None, r["Brel"], None, None, [], r["loc"][f], r["quat"][f])
        cache[(a, i)] = fr.skin(np.array(P["%d,%d" % (a, i)]["x"]))[b] @ K.R[b]
    Ms.append(v["C"][n] @ rig_world(d) @ cache[(a, i)]); masks.append(m)
Ms = np.array(Ms); masks = np.array(masks); print("views with the shield", len(Ms))
NB = 32; FAN = np.array([[0, 1 + k, 1 + (k + 1) % NB] for k in range(NB)], np.int32)


def disc(c, nrm, rad, sx=1.0):
    nrm = nrm / np.linalg.norm(nrm); a = np.cross(nrm, [0, 1, 0]);
    if np.linalg.norm(a) < 1e-3: a = np.cross(nrm, [1, 0, 0])
    a /= np.linalg.norm(a); b_ = np.cross(nrm, a)
    t = np.linspace(0, 2 * np.pi, NB, endpoint=False)
    return np.vstack([c, c + rad * (np.outer(np.cos(t), a) * sx + np.outer(np.sin(t), b_))])


def score(x, sel=slice(None)):
    c = x[:3]; nrm = np.array([np.sin(x[3]) * np.cos(x[4]), np.sin(x[3]) * np.sin(x[4]), np.cos(x[3])])
    D = disc(c, nrm, x[5], x[6]); Dh = np.c_[D, np.ones(len(D))]
    tot = 0.0; MM = Ms[sel]; mm = masks[sel]
    for k in range(len(MM)):
        h = Dh @ MM[k].T; Sxy = np.stack([(h[:, 0] + 1) * 68.0, (1 - h[:, 1]) * 60.0], 1)
        img = np.zeros((120, 136), np.bool_); raster_one(Sxy, FAN, img)
        tot += (img & mm[k]).sum() / max((img | mm[k]).sum(), 1)
    return tot / len(MM)


# start: forearm middle, pushed out along -Z (back of the forearm), facing out
L = np.linalg.norm(K.R[K.ix[BONE.replace("forearm", "hand")]][:3, 3] - K.R[b][:3, 3])
best = (-1, None)
for ox in (-0.08, 0.0, 0.08):
    for oz in (-0.08, 0.0, 0.08):
        for th in np.linspace(0.2, np.pi - 0.2, 6):
            for ph in np.linspace(-np.pi, np.pi, 8, endpoint=False):
                x = np.array([ox, L * 0.5, oz, th, ph, 0.3, 1.0]); s = score(x, slice(None, None, 6))
                if s > best[0]: best = (s, x)
x = best[1]; f = score(x); print("coarse IoU %.3f" % f)
steps = np.array([0.02, 0.02, 0.02, 0.08, 0.08, 0.02, 0.05])
for sc_ in (2, 1, 0.5, 0.25):
    for _ in range(3):
        imp = False
        for j in range(7):
            for sg in (1, -1):
                y = x.copy(); y[j] += sg * steps[j] * sc_; fy = score(y)
                if fy > f + 1e-4: x, f = y, fy; imp = True; break
        if not imp: break
    print("scale %.2f IoU %.4f" % (sc_, f), flush=True)
nrm = np.array([np.sin(x[3]) * np.cos(x[4]), np.sin(x[3]) * np.sin(x[4]), np.cos(x[3])])
json.dump(dict(anim=ANIM, bone=BONE, centre=x[:3].tolist(), normal=nrm.tolist(), radius=float(x[5]), stretch=float(x[6]), iou=float(f)), open(OUT, "w"), indent=1)
print("centre", np.round(x[:3], 3), "normal", np.round(nrm, 3), "radius %.2f stretch %.2f IoU %.4f" % (x[5], x[6], f))
