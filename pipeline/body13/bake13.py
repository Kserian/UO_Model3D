"""bake the v13 body textures from the original UO frames (MakeHuman UV layout):
albedo = sprite colour / UO lighting (ambient + diffuse * max(0, n.L), light fixed to the camera, uo_light.pkl),
robust weighted mean over every visible sample; one texture per UO direction + one from all directions.
usage: bake13.py shape.json poses.json outdir [--size 1024]"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
import sys, os, json, base64, zlib, pickle, time, numpy as np
from numba import njit
from PIL import Image
from shape13 import Shape, load_params
from skel13 import Skel13
from posefit13 import Frame13
from horse_sdf import depth_raster
from fk import rig_world
from mhlib import MH

shape_fn, poses_fn, outdir = sys.argv[1:4]
TEX = int(sys.argv[sys.argv.index("--size") + 1]) if "--size" in sys.argv else 1024
os.makedirs(outdir, exist_ok=True)
t0 = time.time()
r = np.load("rig_poses.npz"); v = np.load("views_all.npz"); bones = list(r["bones"]); P = json.load(open(poses_fn))
S = Shape(v["U"], v["BV"], v["BDOM"], bones); Vf = S.build(load_params(shape_fn), full=True); V = Vf[S.used]
K = Skel13(S, r["R"], r["parent"], bones, Vf)
LIGHT = pickle.load(open(os.path.join(HERE, "..", "uo_light.pkl"), "rb"))
Lc = np.array(LIGHT["L_camera"]); AMB, DIF = LIGHT["ambient"], LIGHT["diffuse"]
ORIG = json.load(open(os.path.join(HERE, "..", "uo_original_frames.json")))["frames"]


def load_uv():
    VT, FT, grp = [], [], None
    for line in open(MH + "base.obj"):
        if line.startswith("vt "): VT.append([float(x) for x in line.split()[1:3]])
        elif line.startswith("g "): grp = line.split()[1]
        elif line.startswith("f ") and grp == "body": FT.append([int(t.split("/")[1]) - 1 for t in line.split()[1:]])
    return np.array(VT), FT


VT, FT = load_uv()
tri_v, tri_t = [], []
for f, ft in zip(S.faces, FT):
    for j in range(1, len(f) - 1):
        tri_v.append((f[0], f[j], f[j + 1])); tri_t.append((ft[0], ft[j], ft[j + 1]))
tri_v = np.array(tri_v, np.int32); tri_t = np.array(tri_t, np.int32)


@njit(cache=True)
def texel_map(UV, tri_t, size):
    """texel centres inside UV triangles -> (y, x, tri, b0, b1, b2)"""
    out = np.zeros((size * size, 6)); n = 0
    owner = np.full((size, size), -1, np.int64)
    for t in range(tri_t.shape[0]):
        a = UV[tri_t[t, 0]] * size; b = UV[tri_t[t, 1]] * size; c = UV[tri_t[t, 2]] * size
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(den) < 1e-12: continue
        x0 = max(int(np.floor(min(a[0], b[0], c[0]))), 0); x1 = min(int(np.ceil(max(a[0], b[0], c[0]))), size - 1)
        y0 = max(int(np.floor(min(a[1], b[1], c[1]))), 0); y1 = min(int(np.ceil(max(a[1], b[1], c[1]))), size - 1)
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if owner[y, x] >= 0: continue
                qx = x + 0.5; qy = y + 0.5
                l0 = ((b[1] - c[1]) * (qx - c[0]) + (c[0] - b[0]) * (qy - c[1])) / den
                l1 = ((c[1] - a[1]) * (qx - c[0]) + (a[0] - c[0]) * (qy - c[1])) / den
                l2 = 1 - l0 - l1
                if l0 < -1e-6 or l1 < -1e-6 or l2 < -1e-6: continue
                owner[y, x] = t
                out[n, 0] = y; out[n, 1] = x; out[n, 2] = t; out[n, 3] = l0; out[n, 4] = l1; out[n, 5] = l2; n += 1
    return out[:n]


TM = texel_map(VT, tri_t, TEX)
ty = TM[:, 0].astype(int); tx = TM[:, 1].astype(int); tt = TM[:, 2].astype(int); tb = TM[:, 3:6]
NT = len(TM); print("texels", NT, "%.0fs" % (time.time() - t0), flush=True)
TV = tri_v[tt]                                                     # (NT, 3) vertex ids per texel
F4 = np.array([f if len(f) == 4 else list(f) + [f[-1]] for f in S.faces])


def normals(X):
    a, b, c, e = X[F4[:, 0]], X[F4[:, 1]], X[F4[:, 2]], X[F4[:, 3]]
    fn = np.cross(c - a, e - b); n = np.zeros_like(X)
    for k in range(4): np.add.at(n, F4[:, k], fn)
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)


def srgb2lin(c):
    c = c / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin2srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055) * 255.0


def pull_push_fill(tex, wt):
    levels = [(tex * wt[..., None], wt.copy())]
    while levels[-1][1].shape[0] > 1:
        c, w = levels[-1]; h = c.shape[0] // 2
        levels.append((c[:2 * h, :2 * h].reshape(h, 2, h, 2, 3).sum((1, 3)), w[:2 * h, :2 * h].reshape(h, 2, h, 2).sum((1, 3))))
    col = levels[-1][0] / np.maximum(levels[-1][1], 1e-9)[..., None]
    for c, w in reversed(levels[:-1]):
        up = np.repeat(np.repeat(col, 2, 0), 2, 1)[: c.shape[0], : c.shape[1]]
        own = c / np.maximum(w, 1e-9)[..., None]; a = np.clip(w, 0, 1)[..., None]
        col = own * a + up * (1 - a)
    return col


# per view samples ------------------------------------------------------------
fk = {tuple(k): n for n, k in enumerate(r["keys"])}
Vh = np.c_[V, np.ones(len(V))]


def gather():
    """yields (d, texel idx, sprite colour (linear), shading, weight) for every view"""
    cache = {}
    for n, (a, i, d) in enumerate(v["keys"]):
        key = "%d,%d" % (a, i)
        if key not in P: continue
        if (a, i) not in cache:
            f = fk[(a, i)]
            fr = Frame13(K, None, None, None, None, r["Brel"], None, None, [], r["loc"][f], r["quat"][f])
            Sk = fr.skin(np.array(P[key]["x"]))
            X = np.einsum("nb,bij,nj->ni", K.SW, Sk, Vh)[:, :3]
            cache = {(a, i): (X, normals(X))}
        X, Nv = cache[(a, i)]
        M = v["C"][n] @ rig_world(d)
        h = np.c_[X, np.ones(len(X))] @ M.T
        Sx = (h[:, 0] + 1) * 68.0; Sy = (1 - h[:, 1]) * 60.0; Z = h[:, 2].copy()
        D = np.full((120, 136), np.inf); depth_raster(np.stack([Sx, Sy], 1), Z, tri_v, D)
        Rc = M[:3, :3] / np.linalg.norm(M[:3, :3], axis=1, keepdims=True)
        ncam = Nv @ Rc.T; ncam[:, 2] *= -1
        zs = np.linalg.norm(M[2, :3])
        px = np.einsum("nk,nk->n", tb, Sx[TV]); py = np.einsum("nk,nk->n", tb, Sy[TV]); pz = np.einsum("nk,nk->n", tb, Z[TV])
        nt = np.einsum("nk,nkd->nd", tb, ncam[TV]); nt /= np.maximum(np.linalg.norm(nt, axis=1, keepdims=True), 1e-12)
        xi = np.floor(px).astype(int); yi = np.floor(py).astype(int)
        ok = (xi >= 0) & (xi < 136) & (yi >= 0) & (yi < 120) & (nt[:, 2] > 0.2)
        ok[ok] &= pz[ok] <= D[yi[ok], xi[ok]] + 0.015 * zs
        o = np.frombuffer(zlib.decompress(base64.b64decode(ORIG["%d,%d,%d" % (a, i, d)])), np.uint8).reshape(120, 136, 4)
        al = o[..., 3] > 0
        core = al.copy(); core[1:] &= al[:-1]; core[:-1] &= al[1:]; core[:, 1:] &= al[:, :-1]; core[:, :-1] &= al[:, 1:]
        ok[ok] &= core[yi[ok], xi[ok]]
        idx = np.nonzero(ok)[0]
        col = srgb2lin(o[yi[idx], xi[idx], :3].astype(np.float64))
        sh = AMB + DIF * np.maximum(nt[idx] @ Lc, 0)
        yield d, idx, col, sh, nt[idx, 2] ** 2


def accumulate(prev=None, sigma=0.08):
    """num / den per direction (robust against prev albedo per direction and for all directions)"""
    num = np.zeros((6, NT, 3)); den = np.zeros((6, NT))
    for d, idx, col, sh, w in gather():
        for slot in (d, 5):
            ww = w
            if prev is not None:
                diff = np.linalg.norm(prev[slot][idx] * sh[:, None] - col, axis=1); ww = w * np.exp(-0.5 * (diff / sigma) ** 2)
            np.add.at(num[slot], idx, ww[:, None] * col * sh[:, None]); np.add.at(den[slot], idx, ww * sh * sh)
    return num / np.maximum(den, 1e-9)[..., None], den


a1, _ = accumulate(); print("pass 1 %.0fs" % (time.time() - t0), flush=True)
a2, den = accumulate(a1); print("pass 2 %.0fs" % (time.time() - t0), flush=True)
for tag, slot in [("all", 5)] + [("dir%d" % d, d) for d in range(5)]:
    tex = np.zeros((TEX, TEX, 3)); wt = np.zeros((TEX, TEX))
    tex[ty, tx] = lin2srgb(a2[slot]); wt[ty, tx] = np.clip(den[slot] / 0.5, 0, 1)
    filled = pull_push_fill(tex, wt)
    Image.fromarray(np.clip(filled, 0, 255).astype(np.uint8)[::-1]).save(os.path.join(outdir, "UO_Body_Albedo_%s.png" % tag))
    print(tag, "covered %.1f%%" % (100 * (den[slot] > 1e-9).mean()), flush=True)
