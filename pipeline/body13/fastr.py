"""fast linear blend skinning + silhouette raster (numba), same pixel rule as eval_iou.py"""
import numpy as np
from numba import njit, prange

WIDTH, HEIGHT = 136, 120


def sparse_weights(Wd, k=6):
    """dense (N,B) weights -> (N,k) bone indices + weights (renormalised)"""
    idx = np.argsort(-Wd, 1)[:, :k]
    w = np.take_along_axis(Wd, idx, 1)
    w /= np.maximum(w.sum(1, keepdims=True), 1e-9)
    return idx.astype(np.int32), w.astype(np.float64)


@njit(parallel=True, cache=True)
def project(V, CW, idx, w):
    """V (N,3) rest verts, CW (nv,B,4,4) camera@skin mats -> (nv,N,2) pixel coords"""
    nv = CW.shape[0]; N = V.shape[0]; K = idx.shape[1]
    out = np.empty((nv, N, 2))
    for v in prange(nv):
        for n in range(N):
            x = 0.0; y = 0.0; h = 0.0
            for k in range(K):
                wk = w[n, k]
                if wk == 0.0:
                    continue
                M = CW[v, idx[n, k]]
                x += wk * (M[0, 0] * V[n, 0] + M[0, 1] * V[n, 1] + M[0, 2] * V[n, 2] + M[0, 3])
                y += wk * (M[1, 0] * V[n, 0] + M[1, 1] * V[n, 1] + M[1, 2] * V[n, 2] + M[1, 3])
                h += wk * (M[3, 0] * V[n, 0] + M[3, 1] * V[n, 1] + M[3, 2] * V[n, 2] + M[3, 3])
            out[v, n, 0] = (x / h + 1.0) * 0.5 * 136.0
            out[v, n, 1] = (1.0 - y / h) * 0.5 * 120.0
    return out


@njit(cache=True)
def raster_one(S, T, img):
    for t in range(T.shape[0]):
        ax = S[T[t, 0], 0]; ay = S[T[t, 0], 1]; bx = S[T[t, 1], 0]; by = S[T[t, 1], 1]; cx = S[T[t, 2], 0]; cy = S[T[t, 2], 1]
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) <= 1e-12:
            continue
        x0 = int(np.floor(min(ax, bx, cx))); x1 = int(np.ceil(max(ax, bx, cx)))
        y0 = int(np.floor(min(ay, by, cy))); y1 = int(np.ceil(max(ay, by, cy)))
        if x0 < 0: x0 = 0
        if y0 < 0: y0 = 0
        if x1 > 135: x1 = 135
        if y1 > 119: y1 = 119
        for py in range(y0, y1 + 1):
            qy = py + 0.5
            for px in range(x0, x1 + 1):
                qx = px + 0.5
                l0 = ((by - cy) * (qx - cx) + (cx - bx) * (qy - cy)) / den
                if l0 < -1e-4: continue
                l1 = ((cy - ay) * (qx - cx) + (ax - cx) * (qy - cy)) / den
                if l1 < -1e-4: continue
                if 1.0 - l0 - l1 < -1e-4: continue
                img[py, px] = True


@njit(parallel=True, cache=True)
def raster(S, T):
    nv = S.shape[0]
    out = np.zeros((nv, 120, 136), np.bool_)
    for v in prange(nv):
        raster_one(S[v], T, out[v])
    return out


@njit(parallel=True, cache=True)
def score(S, T, masks):
    """per view: intersection, union, outside, missing"""
    nv = S.shape[0]
    res = np.zeros((nv, 4), np.int64)
    for v in prange(nv):
        img = np.zeros((120, 136), np.bool_)
        raster_one(S[v], T, img)
        o = masks[v]
        a = 0; u = 0; out = 0; mis = 0
        for y in range(120):
            for x in range(136):
                m = img[y, x]; g = o[y, x]
                if m and g: a += 1
                if m or g: u += 1
                if m and not g: out += 1
                if g and not m: mis += 1
        res[v, 0] = a; res[v, 1] = u; res[v, 2] = out; res[v, 3] = mis
    return res


def tris_of(faces):
    T = []
    for f in faces:
        f = list(f)
        for j in range(1, len(f) - 1):
            T.append((f[0], f[j], f[j + 1]))
    return np.array(T, np.int32)
