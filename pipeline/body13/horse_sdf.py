"""signed distance grids (m, < 0 inside) of the horse proxies (rig space) -> horse_sdf.npz
+ depth-raster helpers for mounted fitting (the horse hides the rider's far side)"""
import numpy as np
from numba import njit
from scipy.ndimage import distance_transform_edt

H = 0.02          # voxel size


@njit(cache=True)
def column_crossings(V, T, x0, y0, nx, ny, h, maxc):
    zc = np.zeros((nx, ny, maxc)); nc = np.zeros((nx, ny), np.int32)
    for t in range(T.shape[0]):
        a = V[T[t, 0]]; b = V[T[t, 1]]; c = V[T[t, 2]]
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(den) < 1e-14:
            continue
        i0 = int(np.ceil((min(a[0], b[0], c[0]) - x0) / h - 0.5)); i1 = int(np.floor((max(a[0], b[0], c[0]) - x0) / h - 0.5))
        j0 = int(np.ceil((min(a[1], b[1], c[1]) - y0) / h - 0.5)); j1 = int(np.floor((max(a[1], b[1], c[1]) - y0) / h - 0.5))
        for i in range(max(i0, 0), min(i1, nx - 1) + 1):
            px = x0 + (i + 0.5) * h
            for j in range(max(j0, 0), min(j1, ny - 1) + 1):
                py = y0 + (j + 0.5) * h
                l0 = ((b[1] - c[1]) * (px - c[0]) + (c[0] - b[0]) * (py - c[1])) / den
                l1 = ((c[1] - a[1]) * (px - c[0]) + (a[0] - c[0]) * (py - c[1])) / den
                l2 = 1 - l0 - l1
                if l0 < 0 or l1 < 0 or l2 < 0:
                    continue
                if nc[i, j] < maxc:
                    zc[i, j, nc[i, j]] = l0 * a[2] + l1 * b[2] + l2 * c[2]; nc[i, j] += 1
    return zc, nc


def sdf_grid(V, T):
    lo = V.min(0) - 0.1; hi = V.max(0) + 0.1
    n = np.ceil((hi - lo) / H).astype(int)
    zc, nc = column_crossings(V, T.astype(np.int64), lo[0], lo[1], n[0], n[1], H, 64)
    inside = np.zeros(n, bool)
    zs = lo[2] + (np.arange(n[2]) + 0.5) * H
    for i in range(n[0]):
        for j in range(n[1]):
            k = nc[i, j]
            if k < 2:
                continue
            z = np.sort(zc[i, j, :k])
            cnt = np.searchsorted(z, zs)                  # crossings below each voxel centre
            inside[i, j] = cnt % 2 == 1
    d_out = distance_transform_edt(~inside) * H; d_in = distance_transform_edt(inside) * H
    return lo, (d_out - d_in).astype(np.float32)


@njit(cache=True)
def sample(sdf, lo, h, P):
    out = np.empty(P.shape[0]); nx, ny, nz = sdf.shape
    for n in range(P.shape[0]):
        fx = (P[n, 0] - lo[0]) / h - 0.5; fy = (P[n, 1] - lo[1]) / h - 0.5; fz = (P[n, 2] - lo[2]) / h - 0.5
        i = int(np.floor(fx)); j = int(np.floor(fy)); k = int(np.floor(fz))
        if i < 0 or j < 0 or k < 0 or i >= nx - 1 or j >= ny - 1 or k >= nz - 1:
            out[n] = 1.0; continue
        tx = fx - i; ty = fy - j; tz = fz - k
        s = 0.0
        for di in range(2):
            for dj in range(2):
                for dk in range(2):
                    wgt = (tx if di else 1 - tx) * (ty if dj else 1 - ty) * (tz if dk else 1 - tz)
                    s += wgt * sdf[i + di, j + dj, k + dk]
        out[n] = s
    return out


@njit(cache=True)
def depth_raster(S, Z, T, D):
    """min depth per pixel (pixel-centre rule); D preset to inf"""
    for t in range(T.shape[0]):
        ax = S[T[t, 0], 0]; ay = S[T[t, 0], 1]; bx = S[T[t, 1], 0]; by = S[T[t, 1], 1]; cx = S[T[t, 2], 0]; cy = S[T[t, 2], 1]
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) <= 1e-12:
            continue
        x0 = max(int(np.floor(min(ax, bx, cx))), 0); x1 = min(int(np.ceil(max(ax, bx, cx))), 135)
        y0 = max(int(np.floor(min(ay, by, cy))), 0); y1 = min(int(np.ceil(max(ay, by, cy))), 119)
        for py in range(y0, y1 + 1):
            qy = py + 0.5
            for px in range(x0, x1 + 1):
                qx = px + 0.5
                l0 = ((by - cy) * (qx - cx) + (cx - bx) * (qy - cy)) / den
                if l0 < -1e-4: continue
                l1 = ((cy - ay) * (qx - cx) + (ax - cx) * (qy - cy)) / den
                if l1 < -1e-4: continue
                l2 = 1.0 - l0 - l1
                if l2 < -1e-4: continue
                z = l0 * Z[T[t, 0]] + l1 * Z[T[t, 1]] + l2 * Z[T[t, 2]]
                if z < D[py, px]:
                    D[py, px] = z


if __name__ == "__main__":
    h = np.load("horse.npz"); out = {}
    for k in h.files:
        if k.startswith("v_"):
            tag = k[2:]; lo, g = sdf_grid(h[k], h["t_" + tag])
            out["lo_" + tag] = lo; out["g_" + tag] = g
            print(tag, g.shape, "inside voxels", (g < 0).sum(), flush=True)
    np.savez_compressed("horse_sdf.npz", **out)
