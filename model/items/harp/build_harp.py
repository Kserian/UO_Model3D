"""Repair and fatten a scanned harp glb for the item pipeline (UO_Model3D).
Input: a glb whose strings, pins and eyelets are on BOTH faces of the frame (the model is wrong). Output: strings only on ONE face (the front, Blender y < 0),
the hole of every removed pin / eyelet closed flush with the wood, the frame grown in every plane, and the 10 strings rebuilt as clean round cylinders with a pin ball on each.
The textures stay byte-identical (only the index / vertex buffers change).

    python build_harp.py in.glb out.glb [FRAME_W 0.11] [FRAME_T 0.03] [STRING_R 0.028]      (model units; the model is 1.9 high: a 0.65 m item is x0.33; 1 game px = 2.8 cm = 0.085 units)
    FRAME_W grows the frame IN ITS PLANE (the width of the arms and the neck), FRAME_T across it (the thickness). Measure with widths.py (pixels at 36 px/m).
"""
import json, struct, io, sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
src, dst = sys.argv[1], sys.argv[2]
FRAME_W = float(sys.argv[3]) if len(sys.argv) > 3 else 0.11
FRAME_T = float(sys.argv[4]) if len(sys.argv) > 4 else 0.03
STRING_R = float(sys.argv[5]) if len(sys.argv) > 5 else 0.028
FRAME = FRAME_T
SEG = 12
d = open(src, "rb").read()
L = struct.unpack_from("<I", d, 12)[0]; j = json.loads(d[20:20+L]); bo = 20 + L
bl = struct.unpack_from("<I", d, bo)[0]; b0 = bo + 8; binc = bytes(d[b0:b0+bl])
def bvbytes(i):
    bv = j["bufferViews"][i]; o = b0 + bv.get("byteOffset", 0); return d[o:o + bv["byteLength"]]
def acc(i):
    a = j["accessors"][i]; bv = j["bufferViews"][a["bufferView"]]
    ct = {5126: "<f4", 5125: "<u4"}[a["componentType"]]; nc = {"SCALAR": 1, "VEC2": 2, "VEC3": 3}[a["type"]]
    off = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    r = np.frombuffer(binc, dtype=ct, count=a["count"] * nc, offset=off); return (r.reshape(-1, nc) if nc > 1 else r).copy()
p = j["meshes"][0]["primitives"][0]
pos = acc(p["attributes"]["POSITION"]).astype(np.float64); nor = acc(p["attributes"]["NORMAL"]).astype(np.float64); uv = acc(p["attributes"]["TEXCOORD_0"]).astype(np.float64)
idx = acc(p["indices"]).astype(np.int64).reshape(-1, 3)
mr = np.array(Image.open(io.BytesIO(bvbytes(j["images"][1]["bufferView"]))))[..., 2]
bc = np.array(Image.open(io.BytesIO(bvbytes(j["images"][0]["bufferView"]))).convert("RGB"))
def sample(img, u):
    H, W = img.shape[:2]; return img[np.clip((u[..., 1] % 1.0) * H, 0, H-1).astype(int), np.clip((u[..., 0] % 1.0) * W, 0, W-1).astype(int)]
vm = sample(mr, uv).astype(float)                                   # metal value per vertex (blue channel of the metal-roughness map)
vc = sample(bc, uv).astype(float); vsat = (vc.max(1) - vc.min(1)) / np.maximum(vc.max(1), 1.0)
fb = vm[idx].mean(1); metal = fb > 128; fsat = vsat[idx].mean(1)
fc = pos[idx].mean(1); cy = -fc[:, 2]; cz = fc[:, 1]               # Blender y (front = -y), height
yb = -pos[:, 2]; zb = pos[:, 1]; xb = pos[:, 0]
RES = 0.0005; X0, Z0 = -0.75, -1.0
def cell(x, z): return ((x - X0) / RES).astype(int), ((z - Z0) / RES).astype(int)
gx, gz = cell(fc[:, 0], cz); vx, vz = cell(xb, zb)
r = 12e-3 / RES; yy, xx = np.mgrid[-int(r) - 2:int(r) + 3, -int(r) - 2:int(r) + 3]
disc = lambda rad: (xx ** 2 + yy ** 2) <= (rad / RES) ** 2
SHAPE = (int(1.5 / RES), int(2.0 / RES))
dele = np.zeros(len(idx), bool)
strings_front = []
silver = None
for side in (+1, -1):                                               # +1 = back (y > 0), -1 = front
    sm = metal & (side * cy >= 0)
    img = np.zeros(SHAPE, bool); img[gx[sm], gz[sm]] = True; img = ndi.binary_dilation(img, iterations=2)
    core = ndi.binary_erosion(img, structure=disc(4e-3))            # thick blobs = pin heads and eyelets (a string is thinner than 8 mm)
    mask = ndi.binary_dilation(core, structure=disc(8e-3 if side > 0 else 14e-3)); lab, nl = ndi.label(mask)
    dil = ndi.binary_dilation(mask, structure=disc(6e-3)); dlab, _ = ndi.label(dil)
    if side < 0: labF, dlabF, maskF, nlF = lab, dlab, mask, nl
    else: lab_back_any = lab
    # strings: narrow peaks of the metal outside the discs along x
    cand = sm & (lab[gx, gz] == 0)
    xs = np.sort(fc[cand, 0]); parts = np.split(xs, np.where(np.diff(xs) > 0.012)[0] + 1)
    near = np.zeros(len(idx), bool); cols = []
    for pr in parts:
        if len(pr) < 150: continue
        xk = float(np.median(pr)); sel = cand & (np.abs(fc[:, 0] - xk) < 0.006)
        if cz[sel].max() - cz[sel].min() < 0.2: continue
        near |= np.abs(fc[:, 0] - xk) < 0.014
        cols.append((xk, float(np.median(cy[sel])), float(cz[sel].max()), float(cz[sel].min()), sel))
    stringy = near & (side * cy > 0.04) & (fb > 56) & (lab[gx, gz] == 0)          # debris of the scanned strings (metal-ish, not the pale wood of the neck)
    dele |= cand | stringy
    if side == -1:
        strings_front = cols
        allf = np.unique(idx[np.any([c[4] for c in cols], 0)].ravel()); okm = allf[vm[allf] > 128]
        silver = uv[okm[np.argmax(vc[okm].sum(1))]].copy()
    # discs: flatten onto the plane of the wood round them (a pin head, an eyelet, the walls of its hole)
    vl = lab[vx, vz]; flat = (vl > 0) & (side * yb > 0.0); nfl = 0
    for k in range(1, (nl + 1) if side > 0 else 1):
        ys, xs_ = np.nonzero(lab == k); ring = (dlab == dlab[ys[0], xs_[0]]) & ~mask
        rv = ring[vx, vz] & (side * yb > 0.02) & (vm < 56)
        if rv.sum() < 12: rv = ring[vx, vz] & (side * yb > 0.0) & (vm < 90)
        if rv.sum() < 12: continue
        A = np.c_[np.ones(rv.sum()), xb[rv], zb[rv]]; t = yb[rv]
        w = np.linalg.lstsq(A, t, rcond=None)[0]; res = np.abs(A @ w - t); ok = res < max(0.0015, np.median(res) * 2.5)
        if ok.sum() >= 8: w = np.linalg.lstsq(A[ok], t[ok], rcond=None)[0]
        sel = flat & (vl == k)
        if not sel.any(): continue
        ynew = w[0] + w[1] * xb[sel] + w[2] * zb[sel]
        moved = np.zeros(len(pos), bool); moved[np.nonzero(sel)[0]] = np.abs(ynew - yb[sel]) > 1.5e-3
        pos[sel, 2] = -ynew
        n_b = np.array([-w[1], side * 1.0, -w[2]]) * (1.0 if side > 0 else -1.0); n_b /= np.linalg.norm(n_b)
        nor[sel] = np.array([n_b[0], n_b[2], -n_b[1]])
        ri = np.nonzero(rv)[0][ok] if ok.sum() >= 8 else np.nonzero(rv)[0]
        cl = sample(bc, uv[ri]).astype(float); m = np.median(cl, 0)
        uv[moved] = uv[ri[np.argmin(np.linalg.norm(cl - m, axis=1))]]
        nfl += 1
    print("side %s: discs %d (flattened %d), strings %d, faces deleted so far %d" % ("back" if side > 0 else "front", nl, nfl, len(cols), dele.sum()))
# ---- loose debris of the scanned strings: pieces of the mesh that no longer touch the frame (small connected components outside the pin / eyelet discs) are dropped
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
keyp = np.round(pos / 2e-5).astype(np.int64); _, wv = np.unique(keyp, axis=0, return_inverse=True); wv = wv.ravel()
alive = np.nonzero(~dele)[0]; fw = wv[idx[alive]]
E = np.concatenate([fw[:, [0, 1]], fw[:, [1, 2]], fw[:, [2, 0]]]); m_ = wv.max() + 1
ncomp, clab = connected_components(coo_matrix((np.ones(len(E)), (E[:, 0], E[:, 1])), shape=(m_, m_)), directed=False)
fcomp = clab[fw[:, 0]]; sizes = np.bincount(fcomp, minlength=ncomp)
protect = (labF[gx, gz] > 0)[alive] | (lab_back_any[gx, gz] > 0)[alive]
drop = 0
for c in np.nonzero((sizes > 0) & (sizes < 4000))[0]:
    sel = fcomp == c
    if protect[sel].mean() > 0.5: continue
    dele[alive[sel]] = True; drop += int(sel.sum())
print("loose debris dropped: %d faces (components kept: %d large)" % (drop, int((sizes >= 4000).sum())))
# ---- the frame grows in every plane: along the smoothed normals welded by position (UV seams do not open)
key = np.round(pos / 2e-5).astype(np.int64); _, wl = np.unique(key, axis=0, return_inverse=True); wl = wl.ravel()
nn = np.zeros((wl.max() + 1, 3)); np.add.at(nn, wl, nor); nn /= np.maximum(np.linalg.norm(nn, axis=1, keepdims=True), 1e-9)
dn = nn[wl] * np.array([FRAME_W, FRAME_W, FRAME_T])                # glTF (x, up, z = across the plane)
vlF = labF[vx, vz]
for k in range(1, nlF + 1):                                         # front pin heads / eyelets stay whole and ride on the grown surface under them
    ys, xs_ = np.nonzero(labF == k); ring = (dlabF == dlabF[ys[0], xs_[0]]) & ~maskF
    rv = ring[vx, vz] & (yb < -0.02) & (vm < 56); selk = (vlF == k) & (yb < 0.0)
    if rv.sum() >= 4 and selk.any(): dn[selk] = dn[rv].mean(0)
pos0 = pos.copy(); pos = pos + dn
print("frame grown by %.3f in the plane, %.3f across; bbox %s -> %s" % (FRAME_W, FRAME_T, np.ptp(pos0, 0).round(3), np.ptp(pos, 0).round(3)))
# ---- new strings (cylinders) and pin balls on the front
usedv = np.zeros(len(pos), bool); usedv[idx[~dele].ravel()] = True
surf = np.nonzero(usedv & (yb < -0.02) & (vm < 56) & (zb > 0.55))[0]                # wood of the front neck (to find its surface under a pin)
newp, newn, newu, newt = [], [], [], []
def uvs(a_, h): return silver + np.array([0.0003 * a_ / (2 * np.pi), 0.0003 * h])
def tube(x, y, z0, z1, R):
    b = len(pos) + len(newp)
    for h, zz in ((1.0, z1), (0.0, z0)):
        for a_ in np.linspace(0, 2 * np.pi, SEG, endpoint=False):
            nx, nz_ = np.cos(a_), np.sin(a_)
            newp.append((x + R * nx, zz, -y - R * nz_)); newn.append((nx, 0.0, -nz_)); newu.append(uvs(a_, h))
    for q in range(SEG):
        a0, a1 = b + q, b + (q + 1) % SEG
        newt.extend([(a0, a0 + SEG, a1), (a1, a0 + SEG, a1 + SEG)])
def ball(c, R):
    b = len(pos) + len(newp); nu, nv = SEG, SEG // 2 + 1
    for iv in range(nv):
        th = np.pi * iv / (nv - 1)
        for iu in range(nu):
            ph = 2 * np.pi * iu / nu
            nrm = np.array([np.sin(th) * np.cos(ph), np.cos(th), -np.sin(th) * np.sin(ph)])   # glTF (x, up, z)
            newp.append(tuple(np.array(c) + R * nrm)); newn.append(tuple(nrm)); newu.append(uvs(ph, np.cos(th)) + np.array([0.0, 0.0]))
    for iv in range(nv - 1):
        for iu in range(nu):
            a0 = b + iv * nu + iu; a1 = b + iv * nu + (iu + 1) % nu
            newt.extend([(a0, a0 + nu, a1), (a1, a0 + nu, a1 + nu)])
for xk, yk, ztop, zbot, sel in strings_front:
    ys_ = yk - FRAME                                                # as before: just in front of the surface the string lay on, now that the surface moved out
    near_ = surf[np.argmin((xb[surf] - xk) ** 2 + (zb[surf] - ztop) ** 2)]
    ysurf = -pos[near_, 2]                                          # the grown surface of the neck under this pin (Blender y, negative)
    tube(xk, ys_, zbot - 0.05, ztop, STRING_R)
print("strings %d, new vertices %d, triangles %d" % (len(strings_front), len(newp), len(newt)))
pos = np.concatenate([pos, np.array(newp).reshape(-1, 3)]); nor = np.concatenate([nor, np.array(newn).reshape(-1, 3)]); uv = np.concatenate([uv, np.array(newu).reshape(-1, 2)])
tri = np.concatenate([idx[~dele], np.array(newt, dtype=np.int64).reshape(-1, 3)]).astype("<u4")
b = binc
def add(arr, target):
    global b
    b = b + b"\0" * ((-len(b)) % 4); off = len(b); b = b + arr.tobytes()
    j["bufferViews"].append({"buffer": 0, "byteOffset": off, "byteLength": arr.nbytes, "target": target}); return len(j["bufferViews"]) - 1
for name, arr in (("POSITION", pos.astype("<f4")), ("NORMAL", nor.astype("<f4")), ("TEXCOORD_0", uv.astype("<f4"))):
    a = dict(j["accessors"][p["attributes"][name]]); a["bufferView"] = add(arr, 34962); a["byteOffset"] = 0; a["count"] = len(arr)
    if name == "POSITION": a["min"] = arr.min(0).tolist(); a["max"] = arr.max(0).tolist()
    j["accessors"].append(a); p["attributes"][name] = len(j["accessors"]) - 1
ia = dict(j["accessors"][p["indices"]]); ia["bufferView"] = add(tri.ravel(), 34963); ia["byteOffset"] = 0; ia["count"] = int(tri.size); ia["componentType"] = 5125; ia.pop("min", None); ia.pop("max", None)
j["accessors"].append(ia); p["indices"] = len(j["accessors"]) - 1
j["buffers"][0]["byteLength"] = len(b)
js = json.dumps(j, separators=(",", ":")).encode(); js += b" " * ((-len(js)) % 4)
open(dst, "wb").write(struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(js) + 8 + len(b)) + struct.pack("<I4s", len(js), b"JSON") + js + struct.pack("<I4s", len(b), b"BIN\0") + b)
print("written", dst)
