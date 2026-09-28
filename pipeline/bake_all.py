"""Bake the UV texture from ALL non-mounted sprite frames (refined mesh + refined poses), robust weighted mean."""
import sys, pickle, time
import numpy as np
from scipy.ndimage import binary_erosion
TEX = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 1024
sys.argv = ["refine_mesh.py", "0"]
exec(open("refine_mesh.py").read().split("params = dict(delta=")[0])
SS = 3
r = pickle.load(open("refine_mesh.pkl", "rb"))
delta = jnp.asarray(r["delta"])
poses = {k: jnp.asarray(v) for k, v in r["poses"].items()}
tri_uv = np.asarray(md["tri_uv"])


def raster_vec(P, fn_depth, W_, H_, maxbox=24):
    """Vectorised rasteriser for small triangles. P (T,3,2) pixel coords. Returns (tri, px, py, bary) of covered centres."""
    mn = np.floor(P.min(1)).astype(int); mx = np.ceil(P.max(1)).astype(int)
    size = np.clip(mx - mn, 0, maxbox)
    a, b, c = P[:, 0], P[:, 1], P[:, 2]
    den = (b[:, 1] - c[:, 1]) * (a[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (a[:, 1] - c[:, 1])
    ok = np.abs(den) > 1e-12
    out_t, out_x, out_y, out_b = [], [], [], []
    for dy in range(int(size[:, 1].max()) + 1):
        for dx in range(int(size[:, 0].max()) + 1):
            sel = ok & (dx <= size[:, 0]) & (dy <= size[:, 1])
            t = np.nonzero(sel)[0]
            px = mn[t, 0] + dx; py = mn[t, 1] + dy
            cx, cy = px + 0.5, py + 0.5
            aa, bb, cc, dd = a[t], b[t], c[t], den[t]
            l0 = ((bb[:, 1] - cc[:, 1]) * (cx - cc[:, 0]) + (cc[:, 0] - bb[:, 0]) * (cy - cc[:, 1])) / dd
            l1 = ((cc[:, 1] - aa[:, 1]) * (cx - cc[:, 0]) + (aa[:, 0] - cc[:, 0]) * (cy - cc[:, 1])) / dd
            l2 = 1 - l0 - l1
            m = (l0 >= -1e-4) & (l1 >= -1e-4) & (l2 >= -1e-4) & (px >= 0) & (py >= 0) & (px < W_) & (py < H_)
            out_t.append(t[m]); out_x.append(px[m]); out_y.append(py[m]); out_b.append(np.stack([l0[m], l1[m], l2[m]], 1))
    return np.concatenate(out_t), np.concatenate(out_x), np.concatenate(out_y), np.concatenate(out_b)


# texel -> (triangle, barycentric)
t0 = time.time()
uvpx = tri_uv.copy(); uvpx[..., 0] *= TEX; uvpx[..., 1] = (1 - uvpx[..., 1]) * TEX
tt, tx, ty, tb = raster_vec(uvpx, None, TEX, TEX)
key = ty * TEX + tx
_, first = np.unique(key, return_index=True)
tt, tx, ty, tb = tt[first], tx[first], ty[first], tb[first]
NT = len(tt)
print("texels", NT, f"{time.time()-t0:.1f}s", flush=True)

# per-view brightness gains (UO light is fixed while the body turns)
cores = np.zeros_like(masks)
for s in range(NS):
    for d in range(5):
        cores[s, d] = binary_erosion(masks[s, d], iterations=1)
colors = {}
for s, (a, i) in enumerate(samples):
    colors[s] = cache_t[a][i][..., :3]
means = np.zeros(5)
for d in range(5):
    means[d] = np.mean([colors[s][d][cores[s, d]].mean() for s in range(NS)])
gains = means.mean() / means
print("direction gains", np.round(gains, 3), flush=True)


def vert_normals(X):
    fn = np.cross(X[tris[:, 1]] - X[tris[:, 0]], X[tris[:, 2]] - X[tris[:, 0]])
    n = np.zeros_like(X)
    for k in range(3):
        np.add.at(n, tris[:, k], fn)
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)


def gather(pass_mean=None, sigma=28.0):
    acc = np.zeros((NT, 3)); wsum = np.zeros(NT)
    for s in range(NS):
        pp = {k: poses[k][s] for k in ("ball", "hinge", "trans")}
        p, X = forward(delta, pp)
        p = np.asarray(p); X = np.asarray(X)
        nrm = vert_normals(X)
        Pt = np.einsum("nk,nkd->nd", tb, X[tris[tt]])
        Nt = np.einsum("nk,nkd->nd", tb, nrm[tris[tt]])
        Nt /= np.maximum(np.linalg.norm(Nt, axis=1, keepdims=True), 1e-12)
        for d in range(5):
            f = np.asarray(FWD[d]); depth = X @ f
            # z-buffer at SS x resolution
            zb = np.full((H * SS, Wc * SS), -np.inf)
            zt, zx, zy, zbc = raster_vec(p[d][tris] * SS, None, Wc * SS, H * SS)
            np.maximum.at(zb, (zy, zx), np.einsum("nk,nk->n", zbc, depth[tris[zt]]))
            sx = ANCHOR_X + PX_OFF + SC * (Pt @ np.asarray(RIGHT[d]))
            sy = ANCHOR_Y - SC * (Pt @ np.asarray(UP[d]))
            dz = Pt @ f
            facing = Nt @ f
            xi, yi = np.floor(sx).astype(int), np.floor(sy).astype(int)
            zx_, zy_ = np.clip(np.floor(sx * SS).astype(int), 0, Wc * SS - 1), np.clip(np.floor(sy * SS).astype(int), 0, H * SS - 1)
            ok = (xi >= 0) & (xi < Wc) & (yi >= 0) & (yi < H) & (facing > 0.2)
            ok &= dz >= zb[zy_, zx_] - 0.015
            ok[ok] &= cores[s, d][yi[ok], xi[ok]]
            if not ok.any():
                continue
            col = colors[s][d][yi[ok], xi[ok]].astype(np.float64) * gains[d]
            w = facing[ok] ** 2
            if pass_mean is not None:
                diff = np.linalg.norm(col - pass_mean[ok], axis=1)
                w = w * np.exp(-0.5 * (diff / sigma) ** 2)
            acc[ok] += col * w[:, None]; wsum[ok] += w
        if s % 40 == 0:
            print(f"  frame {s}/{NS} {time.time()-t0:.0f}s", flush=True)
    mean = acc / np.maximum(wsum, 1e-9)[:, None]
    return mean, wsum


m1, w1 = gather()
m2, w2 = gather(pass_mean=m1)
print("covered texels %.1f%%" % (100 * (w2 > 1e-6).mean()), flush=True)
tex = np.zeros((TEX, TEX, 3)); wt = np.zeros((TEX, TEX))
tex[ty, tx] = np.clip(m2, 0, 255); wt[ty, tx] = (w2 > 1e-6)
pickle.dump(dict(tex=tex, wt=wt, cover=np.zeros((TEX, TEX), bool)), open("bake_all.pkl", "wb"))
from texbake import pull_push_fill
from PIL import Image
filled = pull_push_fill(tex, wt)
Image.fromarray(np.clip(filled, 0, 255).astype(np.uint8)).save("UO_Body_Texture_allframes.png")
print("saved texture", f"{time.time()-t0:.0f}s", flush=True)
