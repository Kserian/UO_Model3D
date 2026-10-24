"""Fill the see-through gap between the gold frame of a banner and the cloth of the banner (Radiant Star Girdle): new faces in the same glb, the same material, the texture of the banner's middle.

    python uo_fill_banner_gap.py IN.glb OUT.glb [--png mask.png] [--res 0.003] [--zmax 0.74] [--mirror 0.16]

The model (one mesh, 265k vertices) has a central banner whose gold border hugs the cloth and, ~4 cm outside it and ~4 cm further back, a thin outer frame (two vertical strips and a V at the
bottom); between them there are no faces (the back of the skirt, or the body, shows through). Done in the front view (x, z of Blender = glTF x, y; the front is -y of Blender = +z of glTF):
  1. the faces of the front layer (all vertices at y < -0.25, |x| < 0.30) are rasterised; their union C is a ring (the banner, its border, the outer strips, the V, the waistband); the
     gap is fill_holes(C) minus C, the pieces of it that are big enough (the holes of the ornaments stay), widened by one pixel under the neighbours (`--overlap`);
  2. a regular grid of vertices in the gap, depth y by linear interpolation of the front layer's vertices (+1 mm: behind the frame, so it never hides it), normals of the nearest vertex;
  3. UV: the affine map (x, z) -> UV fitted on the cloth of the banner (|x| < 0.12), the colour of the cloth triangle found at the point MIRRORED about x = +-`--mirror` (the inner edge of the border), z not below
     `--zmin_uv` (above the crest at the bottom): the filled part carries the cloth's own colours, no gold;
  4. the arrays of the glb are extended (positions, normals, uv, indices; the images and everything else byte for byte).
"""
import argparse, json, struct, sys
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from scipy.interpolate import LinearNDInterpolator, NearestNDInterpolator
from scipy.spatial import cKDTree


def read_glb(path):
    f = open(path, "rb").read()
    jl = struct.unpack("<I", f[12:16])[0]
    j = json.loads(f[20:20 + jl]); off = 20 + jl + 8
    return j, f[off:off + struct.unpack("<I", f[20 + jl:24 + jl])[0]]


def accessor(j, bin_, k):
    a = j["accessors"][k]; bv = j["bufferViews"][a["bufferView"]]
    nc = {"SCALAR": 1, "VEC2": 2, "VEC3": 3}[a["type"]]; dt = {5126: np.float32, 5125: np.uint32, 5123: np.uint16}[a["componentType"]]
    start = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    return np.frombuffer(bin_, dt, a["count"] * nc, start).reshape(-1, nc).copy()


def write_glb(path, j, bin_):
    jb = json.dumps(j, separators=(",", ":")).encode(); jb += b" " * (-len(jb) % 4); bin_ = bin_ + b"\0" * (-len(bin_) % 4)
    out = struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(jb) + 8 + len(bin_)) + struct.pack("<II", len(jb), 0x4E4F534A) + jb + struct.pack("<II", len(bin_), 0x004E4942) + bin_
    open(path, "wb").write(out)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("inp"); ap.add_argument("out")
    ap.add_argument("--png"); ap.add_argument("--res", type=float, default=0.003); ap.add_argument("--zmax", type=float, default=0.74, help="the gap starts under the waistband: nothing above this z")
    ap.add_argument("--mirror", type=float, default=0.16); ap.add_argument("--zmin_uv", type=float, default=-0.5); ap.add_argument("--min_area", type=float, default=0.004, help="m2: smaller holes stay")
    ap.add_argument("--xlo", type=float, default=0.075); ap.add_argument("--tol", type=float, default=16.0); ap.add_argument("--k", type=int, default=14); ap.add_argument("--xhi", type=float, default=0.14); ap.add_argument("--overlap", type=int, default=2); ap.add_argument("--behind", type=float, default=0.002)
    a = ap.parse_args()
    j, bin_ = read_glb(a.inp)
    prim = j["meshes"][0]["primitives"][0]; at = prim["attributes"]
    P = accessor(j, bin_, at["POSITION"]); N = accessor(j, bin_, at["NORMAL"]); UV = accessor(j, bin_, at["TEXCOORD_0"]); I = accessor(j, bin_, prim["indices"]).ravel().reshape(-1, 3)
    B = np.c_[P[:, 0], -P[:, 2], P[:, 1]].astype(np.float64)                      # Blender: x, y (front = -y), z up
    BN = np.c_[N[:, 0], -N[:, 2], N[:, 1]]
    front = (B[:, 1] < -0.25) & (np.abs(B[:, 0]) < 0.30)
    tri = I[front[I].all(1)]
    # rasterise the union of the front-layer faces in (x, z)
    r = a.res; x0, z0 = -0.30, -0.97; W = int(0.60 / r) + 1; H = int(1.97 / r) + 1
    im = Image.new("L", (W, H), 0); dr = ImageDraw.Draw(im)
    X = (B[:, 0] - x0) / r; Y = (B[:, 2] - z0) / r
    for t in tri:
        dr.polygon([(X[t[0]], Y[t[0]]), (X[t[1]], Y[t[1]]), (X[t[2]], Y[t[2]])], fill=255)
    C = np.array(im) > 0
    C = ndimage.binary_closing(C, iterations=1)                                        # hairline cracks between the rasterised triangles
    filled = ndimage.binary_fill_holes(C)
    gap = filled & ~C
    zz = z0 + (np.arange(H) + 0.5) * r; gap[zz > a.zmax, :] = False
    lab, n = ndimage.label(gap)
    area = ndimage.sum(gap, lab, range(1, n + 1)) * r * r
    keep = np.isin(lab, 1 + np.nonzero(area >= a.min_area)[0])
    print("gap pieces: %s m2 (kept those >= %.3f)" % (", ".join("%.4f" % x for x in sorted(area)[::-1][:8]), a.min_area))
    fillm = ndimage.binary_dilation(keep, iterations=a.overlap) if a.overlap else keep
    if a.png:
        v = np.zeros((H, W, 3), np.uint8); v[C] = (120, 120, 120); v[keep] = (230, 80, 60); Image.fromarray(v[::-1]).save(a.png)
    # vertices on the grid of the gap
    ys, xs = np.nonzero(fillm)
    idx = -np.ones(fillm.shape, np.int64); idx[ys, xs] = np.arange(len(ys))
    gx = x0 + (xs + 0.5) * r; gz = z0 + (ys + 0.5) * r
    fv = np.nonzero(front)[0]; fv = fv[(B[fv, 2] < a.zmax + 0.05)]
    pts = np.c_[B[fv, 0], B[fv, 2]]
    gy = LinearNDInterpolator(pts, B[fv, 1])(np.c_[gx, gz])
    nn = NearestNDInterpolator(pts, B[fv, 1])(np.c_[gx, gz]); gy = np.where(np.isnan(gy), nn, gy)
    gy = ndimage.gaussian_filter1d(gy, 0) if False else gy + a.behind                  # a mm behind the neighbours
    nrm = BN[fv][cKDTree(pts).query(np.c_[gx, gz])[1]]; nrm[:, 1] = -np.abs(nrm[:, 1]); nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-9)
    # faces: quads of the grid, two triangles each (counter-clockwise seen from the front = -y of Blender = +z of glTF)
    q = fillm[:-1, :-1] & fillm[1:, :-1] & fillm[:-1, 1:] & fillm[1:, 1:]
    qy, qx = np.nonzero(q)
    a0, a1, a2, a3 = idx[qy, qx], idx[qy, qx + 1], idx[qy + 1, qx + 1], idx[qy + 1, qx]       # x grows to the right, z (row) up: a0 bottom-left, a1 bottom-right, a2 top-right, a3 top-left
    F = np.r_[np.c_[a0, a1, a2], np.c_[a0, a2, a3]]
    # UV: the texture of this model is a mosaic of small charts (every vertex of the banner has its own place in the atlas), so no map (x, z) -> uv exists. Every new triangle copies the chart of the cloth
    # triangle NEXT to the border, found at the mirror image of the triangle about x = +-`--mirror` (x clamped to [xlo, xhi]: not into the ornaments in the middle): the new triangle takes the colour of the
    # centre of that triangle's chart (one uv for its three corners; the corners are not shared).
    sx = np.abs(B[:, 0])
    ct = I[front[I].all(1)]
    cx = B[ct][:, :, 0].mean(1); cz = B[ct][:, :, 2].mean(1)
    pa, pb, pc = B[ct[:, 0]], B[ct[:, 1]], B[ct[:, 2]]
    area2 = (pb[:, 0] - pa[:, 0]) * (pc[:, 2] - pa[:, 2]) - (pc[:, 0] - pa[:, 0]) * (pb[:, 2] - pa[:, 2])
    cloth = (np.abs(cx) > a.xlo) & (np.abs(cx) < a.xhi) & (cz > a.zmin_uv) & (cz < 0.65) & (np.abs(area2) > 2e-5) & (B[ct][:, :, 1].max(1) < -0.30)
    src = ct[cloth]
    # only triangles whose chart is plain cloth: the colour of the base-colour image at the centre of the chart within `--tol` (RGB) of the median of all (no gold of the border, no grey of a stain)
    img = j["images"][0]; bvw = j["bufferViews"][img["bufferView"]]
    import io
    tex = np.asarray(Image.open(io.BytesIO(bin_[bvw.get("byteOffset", 0):bvw.get("byteOffset", 0) + bvw["byteLength"]])).convert("RGB")).astype(np.float32)
    uvc = UV[src].mean(1); th, tw = tex.shape[:2]
    col = tex[np.clip((uvc[:, 1] * th).astype(int), 0, th - 1), np.clip((uvc[:, 0] * tw).astype(int), 0, tw - 1)]      # colour at the centre of every source chart
    sc_ = np.c_[cx[cloth], cz[cloth]]
    tree_s = cKDTree(sc_)
    print("cloth triangles to take the colour from: %d" % len(src))

    def mirror(x, z):
        ax = np.abs(x); m = np.where(ax > a.mirror, 2 * a.mirror - ax, ax)
        return np.sign(x + 1e-12) * np.clip(m, a.xlo + 0.005, a.xhi - 0.005), np.maximum(z, a.zmin_uv + 0.005)

    tcx = gx[F].mean(1); tcz = gz[F].mean(1)
    mcx, mcz = mirror(tcx, tcz)
    kk = min(a.k, len(sc_)); cand = tree_s.query(np.c_[mcx, mcz], k=kk)[1]                      # the k nearest cloth triangles to the mirror image of every new triangle
    cc = col[cand]; med = np.median(cc, axis=1)                                         # their colours; the local median is the cloth (gold of the border and grey of a stain are further than `--tol`)
    good = np.linalg.norm(cc - med[:, None, :], axis=2) < a.tol
    rnd = np.random.default_rng(1).random(cand.shape); rnd[~good] = -1.0                # a random one of the good ones: neighbours do not get the same cloth (stripes)
    near = cand[np.arange(len(cand)), rnd.argmax(1)]
    sv = src[near]                                                                     # (T, 3) source vertices
    Uv = UV[sv]                                                                         # (T, 3, 2): the corners of the source triangles in the atlas
    Xs = np.stack([B[sv][:, :, 0], B[sv][:, :, 2], np.ones(sv.shape)], 2)              # (T, 3, 3): rows [x, z, 1]
    coef = np.linalg.solve(Xs, Uv)                                                      # uv = [x, z, 1] @ coef: the map of the source triangle (its linear part orients and scales the new one)
    flip = np.where(np.abs(tcx) > a.mirror, -1.0, 1.0)[:, None]                         # the mirror reverses x outside the border
    ox = (gx[F] - tcx[:, None]) * flip; oz = gz[F] - tcz[:, None]
    # the centre of the new triangle's chart = the centre of the source triangle's chart, the corners around it by the (small) offsets: no extrapolation out of the chart and no degenerate
    # uv triangle (the tangent frame of the normal map is undefined then: grey blocks)
    guv = Uv.mean(1)[:, None, :] + np.einsum("tk,tj->tkj", ox, coef[:, 0, :]) + np.einsum("tk,tj->tkj", oz, coef[:, 1, :])
    nv = len(P); T = len(F)
    newP = np.c_[gx[F].ravel(), gz[F].ravel(), -gy[F].ravel()].astype(np.float32)        # back to glTF: (x, z of Blender, -y of Blender)
    newN = np.c_[nrm[F][:, :, 0].ravel(), nrm[F][:, :, 2].ravel(), -nrm[F][:, :, 1].ravel()].astype(np.float32)
    guv = guv.reshape(-1, 2).astype(np.float32)
    F = np.arange(T * 3).reshape(-1, 3)
    P2 = np.r_[P, newP]; N2 = np.r_[N, newN]; UV2 = np.r_[UV, guv]; I2 = np.r_[I.ravel(), (F + nv).ravel().astype(np.uint32)].astype(np.uint32)
    gx = newP[:, 0]
    # extend the buffers: the four accessors' buffer views get the new data appended; everything else stays
    views = {}
    for name, k, arr in (("POSITION", at["POSITION"], P2), ("NORMAL", at["NORMAL"], N2), ("TEXCOORD_0", at["TEXCOORD_0"], UV2), ("indices", prim["indices"], I2)):
        views[j["accessors"][k]["bufferView"]] = (k, arr)
    newbin = bytearray(); newviews = []
    for i, bv in enumerate(j["bufferViews"]):
        if i in views:
            k, arr = views[i]; data = np.ascontiguousarray(arr).tobytes()
            acc = j["accessors"][k]; acc["count"] = int(len(arr.reshape(-1, {"SCALAR": 1, "VEC2": 2, "VEC3": 3}[acc["type"]])))
            if acc["type"] == "VEC3" and "min" in acc:
                acc["min"] = arr.min(0).tolist(); acc["max"] = arr.max(0).tolist()
            if acc["type"] == "VEC2" and "min" in acc:
                acc["min"] = arr.min(0).tolist(); acc["max"] = arr.max(0).tolist()
            acc["byteOffset"] = 0
        else:
            data = bin_[bv.get("byteOffset", 0):bv.get("byteOffset", 0) + bv["byteLength"]]
        newbin += b"\0" * (-len(newbin) % 4); bv["byteOffset"] = len(newbin); bv["byteLength"] = len(data); newbin += data
    j["buffers"][0]["byteLength"] = len(newbin)
    write_glb(a.out, j, bytes(newbin))
    print("added %d vertices, %d triangles (%.3f m2) -> %s" % (len(newP), T, T / 2 * r * r, a.out))


if __name__ == "__main__":
    main()
