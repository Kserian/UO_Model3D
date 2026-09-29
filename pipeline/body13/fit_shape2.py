"""regularised shape fit (keeps a natural anatomy): search along parameter axes and along grouped directions
(whole limb girth, limb taper, whole torso width / depth); penalties on limb taper / anisotropy changes and on
deviation from the measured proportions.
usage: python fit_shape2.py views.npz out.json [--init p.json] [--passes N] [--skin skel] [--sub K]"""
import sys, json, time, numpy as np
from shape13 import Shape, default_params, flat, unflat, PARTS, load_params, save_params, LIMBS
import fastr

views, out = sys.argv[1], sys.argv[2]
arg = lambda k, d: type(d)(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d
PASSES = arg("--passes", 8); SUB = arg("--sub", 1); REG = arg("--reg", 0.03)
d = np.load(views); bones = list(d["bones"]); sel = np.arange(0, len(d["keys"]), SUB)
S = Shape(d["U"], d["BV"], d["BDOM"], bones)
if "--skin" in sys.argv:                                  # 55-bone skin weights (views npz holds 55 matrices per view)
    from skel13 import Skel13
    r = np.load("rig_poses.npz")
    K = Skel13(S, r["R"], r["parent"], bones, S.build(load_params(arg("--init", "")) if "--init" in sys.argv else None, full=True)); Wd = K.SW
else:
    PWu = S.PW[S.used]; Wd = np.zeros((len(PWu), len(bones)))
    for j, p in enumerate(PARTS): Wd[:, bones.index(p)] = PWu[:, j]
idx, w = fastr.sparse_weights(Wd)
CW = np.einsum("vij,vbjk->vbik", d["C"][sel], d["W"][sel]); T = fastr.tris_of(S.faces); masks = d["masks"][sel]
like = default_params()
p0 = load_params(arg("--init", "")) if "--init" in sys.argv else default_params()
x = flat(p0)
names = []
for k in sorted(like):
    names += ["%s[%d]" % (k, i) for i in range(np.size(like[k]))]
names = np.array(names)
lo = np.array([-0.05 if n.startswith("tc") else 0.6 for n in names]); hi = np.array([0.05 if n.startswith("tc") else 1.7 for n in names])
# directions: axes + groups
D = [np.eye(len(x))[i] * (0.01 if names[i].startswith("tc") else 0.06) for i in range(len(x))]
def grp(prefix, vec):
    v = np.zeros(len(x)); ii = [i for i, n in enumerate(names) if n.startswith(prefix + "[")]
    v[ii] = vec; return v
for l in LIMBS:
    D.append(grp(l, np.array([1, 1, 1, 1]) * 0.05))            # whole girth
    D.append(grp(l, np.array([-1, 1, -1, 1]) * 0.05))          # taper
    D.append(grp(l, np.array([1, 1, -1, -1]) * 0.05))          # side vs front
D.append(grp("tw", np.ones(7) * 0.04)); D.append(grp("td", np.ones(7) * 0.04)); D.append(grp("tc", np.ones(7) * 0.006))
D.append(grp("head3", np.array([1, 1, 0]) * 0.04))
D = np.array(D)


def penalty(p):
    pen = 0.0
    for l in LIMBS:
        g = p[l]
        pen += (g[0] - g[1]) ** 2 + (g[2] - g[3]) ** 2              # taper change
        pen += 0.5 * ((g[0] - g[2]) ** 2 + (g[1] - g[3]) ** 2)      # anisotropy change
        pen += 0.2 * np.sum((g - 1) ** 2)
    pen += 5 * sum(np.sum(np.diff(p[k], 2) ** 2) for k in ("tw", "td")) + 500 * np.sum(np.diff(p["tc"], 2) ** 2)
    pen += 0.2 * (np.sum((p["tw"] - 1) ** 2) + np.sum((p["td"] - 1) ** 2))
    pen += np.sum((p["neck"] - 1) ** 2) + np.sum((p["head3"] - 1) ** 2) + (p["head"][0] - 1) ** 2 + (p["footl"][0] - 1) ** 2
    return pen


def cost(x):
    p = unflat(x)
    r = fastr.score(fastr.project(S.build(p), CW, idx, w), T, masks)
    iou = (r[:, 0] / np.maximum(r[:, 1], 1)).mean()
    return -(iou - REG * penalty(p)), iou, r


f, iou, r = cost(x)
print("start IoU %.4f outside %.1f missing %.1f pen %.3f (views %d)" % (iou, r[:, 2].mean(), r[:, 3].mean(), penalty(unflat(x)), len(sel)), flush=True)
scale = 1.0; t0 = time.time()
for ps in range(PASSES):
    improved = 0
    for j in np.random.RandomState(ps).permutation(len(D)):
        for sgn in (1, -1):
            y = np.clip(x + sgn * scale * D[j], lo, hi)
            fy, iy, ry = cost(y)
            if fy < f - 1e-7:
                x, f, iou, r = y, fy, iy, ry; improved += 1
                while True:
                    y = np.clip(x + sgn * scale * D[j], lo, hi)
                    fy, iy, ry = cost(y)
                    if fy < f - 1e-7: x, f, iou, r = y, fy, iy, ry
                    else: break
                break
    print("pass %d IoU %.4f outside %.1f missing %.1f pen %.3f improved %d scale %.2f %.0fs"
          % (ps, iou, r[:, 2].mean(), r[:, 3].mean(), penalty(unflat(x)), improved, scale, time.time() - t0), flush=True)
    save_params(out, unflat(x), iou=float(iou))
    if improved < 4:
        scale *= 0.5
        if scale < 0.1: break
p = unflat(x)
for k in sorted(p):
    print("%-10s" % k, np.round(p[k], 3))
