"""item-level validation: body-hugging shell items (offset of the body skin, same weights) rendered like
render_uo_layer (limbs / head hide the item when > MARGIN in front, EXACT_BODY: only on the original body pixels)
and compared with the real UO item sprites from anim.mul.
usage: itemval.py model(v13|v12|v12c) [--items shirt,pants,...] [--out json] [--img png] [--shape s.json --poses p.json]"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
import sys, json, base64, zlib, time, numpy as np
sys.path.insert(0, HERE)
from itemframes import load, canvas
from horse_sdf import depth_raster
from fk import rig_world
import fastr

MODEL = sys.argv[1]
arg = lambda k, d: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
ITEMS = {  # name: (anim id, parts (UO bones, no side), thickness m, cut (bone, keep t > t0))
    "shirt":  (434, ["pelvis", "spine", "chest", "clavicle", "upper_arm", "neck"], 0.012, None),
    "plate":  (527, ["pelvis", "spine", "chest", "clavicle", "neck"], 0.03, None),
    "arms":   (528, ["upper_arm", "forearm", "clavicle"], 0.025, None),
    "pants":  (431, ["pelvis", "thigh", "shin"], 0.012, None),
    "legs":   (529, ["pelvis", "thigh", "shin"], 0.03, None),
    "boots":  (477, ["shin", "foot"], 0.015, ("shin", 0.35)),
    "gloves": (530, ["hand", "forearm"], 0.015, ("forearm", 0.55)),
    "helm":   (563, ["head"], 0.02, None),
}
SEL = arg("--items", ",".join(ITEMS)).split(",")
OCC = {"head", "upper_arm", "forearm", "hand", "thigh", "shin", "foot"}
MARGIN = 0.01
ORIG = json.load(open(os.path.join(HERE, "..", "uo_original_frames.json")))["frames"]
v = np.load("views_all.npz"); keys = [tuple(int(x) for x in k) for k in v["keys"]]
SUB = {"upper_arm_twist": "upper_arm", "forearm_twist": "forearm", "toe": "foot"}


def base_of(n):
    b = n[:-2] if n.endswith((".L", ".R")) else n
    return "hand" if b.startswith("finger") else SUB.get(b, b)


def normals(V, F4):
    a, b, c, e = V[F4[:, 0]], V[F4[:, 1]], V[F4[:, 2]], V[F4[:, 3]]
    fn = np.cross(c - a, e - b); n = np.zeros_like(V)
    for k in range(4): np.add.at(n, F4[:, k], fn)
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)


if MODEL == "v13":
    from shape13 import Shape, load_params
    from skel13 import Skel13
    from posefit13 import Frame13
    r = np.load("rig_poses.npz"); bones = list(r["bones"])
    S = Shape(v["U"], v["BV"], v["BDOM"], bones); Vf = S.build(load_params(arg("--shape", "shape_r2.json")), full=True); V = Vf[S.used]
    K = Skel13(S, r["R"], r["parent"], bones, Vf); P = json.load(open(arg("--poses", "poses13_r3.json")))
    names, SW, faces, R = K.names, K.SW, S.faces, K.R
    fk = {tuple(int(x) for x in k): n for n, k in enumerate(r["keys"])}
    def skin(n, a, i, d):
        if "%d,%d" % (a, i) not in P: return None
        f = fk[(a, i)]
        fr = Frame13(K, None, None, None, None, r["Brel"], None, None, [], r["loc"][f], r["quat"][f])
        return fr.skin(np.array(P["%d,%d" % (a, i)]["x"]))
else:
    m = np.load("v12_mesh.npz", allow_pickle=True); V = m["BV"]; SW = m["BW"] / np.maximum(m["BW"].sum(1, keepdims=True), 1e-9)
    names = list(m["bones"]); faces = [list(f) for f in m["faces"]]; R = np.load("rig_poses.npz")["R"]
    CORR = np.load("v12_corr.npz")["V"] if MODEL == "v12c" else None
    def skin(n, a, i, d):
        return np.linalg.inv(rig_world(d)) @ v["W"][n]

F4 = np.array([f if len(f) == 4 else list(f) + [f[-1]] for f in faces])
T = fastr.tris_of(faces)
dom = np.array([base_of(names[j]) for j in SW.argmax(1)])
side = np.array([names[j][-2:] for j in SW.argmax(1)])
occ_tri = T[np.isin(dom[T[:, 0]], list(OCC))]
idx, w = fastr.sparse_weights(SW)


def item_tris(parts, filt, Vr):
    keep = np.isin(dom, parts)
    if filt is not None:
        bname, t0 = filt
        for s in (".L", ".R"):
            j = names.index(bname + s); h = R[j][:3, 3]; ax = R[j][:3, 1]
            child = {"shin": "foot", "forearm": "hand"}[bname] + s
            L = np.linalg.norm(R[names.index(child)][:3, 3] - h)
            t = ((Vr - h) @ ax) / L
            keep &= ~((dom == bname) & (side == s) & (t < t0))
    return T[keep[T].all(1)]


def lbs(Sk, X, Nr):
    M = Sk[idx]                                                            # (N, k, 4, 4)
    Mw = np.einsum("nk,nkij->nij", w, M)
    Xp = np.einsum("nij,nj->ni", Mw[:, :3, :3], X) + Mw[:, :3, 3]
    Np = np.einsum("nij,nj->ni", Mw[:, :3, :3], Nr)
    return Xp, Np


def depth(Xw, Tt, C):
    h = np.c_[Xw, np.ones(len(Xw))] @ C.T
    D = np.full((120, 136), np.inf)
    depth_raster(np.stack([(h[:, 0] + 1) * 68.0, (1 - h[:, 1]) * 60.0], 1), h[:, 2].copy(), Tt.astype(np.int32), D)
    return D


its = {nm: load(ITEMS[nm][0]) for nm in SEL}
N0 = normals(V, F4); TR0 = {nm: item_tris(ITEMS[nm][1], ITEMS[nm][3], V) for nm in SEL}
stats = {nm: [] for nm in SEL}; imgs = {}; t0 = time.time()
for n, (a, i, d) in enumerate(keys):
    Sk = skin(n, a, i, d)
    if Sk is None: continue
    Vr = CORR[n].astype(np.float64) if MODEL == "v12c" else V
    Nr = N0 if MODEL != "v12c" else normals(Vr, F4)
    Xb, Nb = lbs(Sk, Vr, Nr)
    C = v["C"][n] @ rig_world(d); zs = np.linalg.norm(C[2, :3])
    Do = depth(Xb, occ_tri, C)
    o = np.frombuffer(zlib.decompress(base64.b64decode(ORIG["%d,%d,%d" % (a, i, d)])), np.uint8).reshape(120, 136, 4)[..., 3] > 0
    for nm in SEL:
        gt = canvas(its[nm].get((a, d)), i)[..., 3] > 0
        if not gt.any(): continue
        Xi = Xb + Nb * ITEMS[nm][2]
        Di = depth(Xi, TR0[nm] if MODEL != "v12c" else item_tris(ITEMS[nm][1], ITEMS[nm][3], Vr), C)
        vis = np.isfinite(Di) & ~((Do < Di - MARGIN * zs) & o)
        stats[nm].append(((vis & gt).sum(), (vis | gt).sum(), (vis & ~gt).sum(), (gt & ~vis).sum()))
        if "--img" in sys.argv and (a, i, d) in ((9, 2, 1), (9, 3, 3), (16, 3, 0), (12, 3, 2), (0, 3, 1)):
            img = np.zeros((120, 136, 3), np.uint8) + 25; img[o] = 80
            img[vis & gt] = (190, 190, 190); img[vis & ~gt] = (230, 60, 60); img[gt & ~vis] = (60, 120, 255)
            imgs.setdefault(nm, []).append(np.pad(img[18:100, 34:104], ((1, 1), (1, 1), (0, 0)), constant_values=90))
    if n % 200 == 0: print("view %d/%d %.0fs" % (n, len(keys), time.time() - t0), flush=True)
res = {}
for nm in SEL:
    s = np.array(stats[nm], float); iou = s[:, 0] / np.maximum(s[:, 1], 1)
    res[nm] = dict(iou=float(iou.mean()), out=float(s[:, 2].mean()), miss=float(s[:, 3].mean()), n=len(s))
    print("%-7s %-4s IoU %.3f  outside %.1f  missing %.1f  (%d views)" % (nm, MODEL, iou.mean(), s[:, 2].mean(), s[:, 3].mean(), len(s)), flush=True)
json.dump(res, open(arg("--out", "itemval_%s.json" % MODEL), "w"), indent=1)
if imgs:
    from PIL import Image
    big = np.concatenate([np.concatenate(r_, 1) for r_ in imgs.values()], 0)
    Image.fromarray(big).resize((big.shape[1] * 2, big.shape[0] * 2), Image.NEAREST).save(arg("--img", "itemval.png"))
