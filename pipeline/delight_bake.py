"""Separate albedo from the UO lighting: sprite = albedo * (ambient + diffuse * max(0, n.L)), light fixed to the camera.
Estimates L, ambient, diffuse from all frames and bakes an albedo texture (linear model, sRGB output)."""
import sys, pickle, time
import numpy as np
from scipy.optimize import least_squares
TEX = 1024
sys.argv = ["bake_all.py"]
src = open("bake_all.py").read()
exec(src.split("def gather(")[0])          # setup: mesh, poses, texel map, cores, colors, raster_vec, vert_normals


def srgb2lin(c):
    c = c / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin2srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055) * 255.0


def visible_samples(s, d, X, nrm, Pt, Nt, zcache):
    f = np.asarray(FWD[d]); depth = X @ f
    if (s, d) not in zcache:
        zb = np.full((H * SS, Wc * SS), -np.inf)
        pd = (ANCHOR_X + PX_OFF + SC * (X @ np.asarray(RIGHT[d])), ANCHOR_Y - SC * (X @ np.asarray(UP[d])))
        P2 = np.stack(pd, 1)
        zt, zx, zy, zbc = raster_vec(P2[tris] * SS, None, Wc * SS, H * SS)
        np.maximum.at(zb, (zy, zx), np.einsum("nk,nk->n", zbc, depth[tris[zt]]))
        zcache[(s, d)] = zb
    zb = zcache[(s, d)]
    sx = ANCHOR_X + PX_OFF + SC * (Pt @ np.asarray(RIGHT[d])); sy = ANCHOR_Y - SC * (Pt @ np.asarray(UP[d]))
    dz = Pt @ f; facing = Nt @ f
    xi, yi = np.floor(sx).astype(int), np.floor(sy).astype(int)
    zx_, zy_ = np.clip(np.floor(sx * SS).astype(int), 0, Wc * SS - 1), np.clip(np.floor(sy * SS).astype(int), 0, H * SS - 1)
    ok = (xi >= 0) & (xi < Wc) & (yi >= 0) & (yi < H) & (facing > 0.2)
    ok &= dz >= zb[zy_, zx_] - 0.015
    ok[ok] &= cores[s, d][yi[ok], xi[ok]]
    idx = np.nonzero(ok)[0]
    col = srgb2lin(colors[s][d][yi[idx], xi[idx]].astype(np.float64))
    ncam = np.stack([Nt[idx] @ np.asarray(RIGHT[d]), Nt[idx] @ np.asarray(UP[d]), Nt[idx] @ f], 1)
    return idx, col, ncam, facing[idx] ** 2


def frame_geom(s):
    pp = {k: poses[k][s] for k in ("ball", "hinge", "trans")}
    _, X = forward(delta, pp)
    X = np.asarray(X); nrm = vert_normals(X)
    Pt = np.einsum("nk,nkd->nd", tb, X[tris[tt]])
    Nt = np.einsum("nk,nkd->nd", tb, nrm[tris[tt]])
    Nt /= np.maximum(np.linalg.norm(Nt, axis=1, keepdims=True), 1e-12)
    return X, nrm, Pt, Nt


# ---- 1) subsample for the light fit
rng = np.random.default_rng(0)
I, C, N, Wt = [], [], [], []
for s in range(0, NS, 3):
    X, nrm, Pt, Nt = frame_geom(s)
    for d in range(5):
        idx, col, ncam, w = visible_samples(s, d, X, nrm, Pt, Nt, {})
        k = rng.random(len(idx)) < 0.25
        I.append(idx[k]); C.append(col[k]); N.append(ncam[k]); Wt.append(w[k])
I = np.concatenate(I); C = np.concatenate(C); N = np.concatenate(N); Wt = np.concatenate(Wt)
print("light-fit samples", len(I), f"{time.time()-t0:.0f}s", flush=True)


def shading(params, n):
    th, ph, amb, dif = params
    L = np.array([np.sin(th) * np.cos(ph), np.sin(th) * np.sin(ph), np.cos(th)])
    return amb + dif * np.maximum(n @ L, 0.0)


def albedo_from(params):
    sh = shading(params, N)
    num = np.zeros((NT, 3)); den = np.zeros(NT)
    np.add.at(num, I, Wt[:, None] * C * sh[:, None]); np.add.at(den, I, Wt * sh * sh)
    return num / np.maximum(den, 1e-9)[:, None], den > 0


params = np.array([0.8, 2.3, 0.4, 0.6])   # initial: light from upper-left-front, 40% ambient
sel = rng.choice(len(I), min(400000, len(I)), replace=False)
for it in range(4):
    rho, has = albedo_from(params)
    ok = has[I[sel]]
    def res(p):
        p = np.array([p[0], p[1], p[2], 1.0 - p[2]])   # amb + dif = 1 (scale lives in the albedo)
        return (np.sqrt(Wt[sel][ok])[:, None] * (rho[I[sel][ok]] * shading(p, N[sel][ok])[:, None] - C[sel][ok])).ravel()
    r = least_squares(res, params[:3], bounds=([0.0, -np.pi, 0.05], [np.pi, np.pi, 0.95]))
    params = np.array([r.x[0], r.x[1], r.x[2], 1.0 - r.x[2]])
    th, ph = params[:2]
    L = [np.sin(th) * np.cos(ph), np.sin(th) * np.sin(ph), np.cos(th)]
    print(f"iter {it}: light dir (camera: right,up,toward) {np.round(L,3)} ambient {params[2]:.3f} diffuse {params[3]:.3f} "
          f"rms {np.sqrt(np.mean(r.fun**2)):.4f}", flush=True)

# ---- 2) full albedo bake (robust, streaming, 2 passes)
def full_pass(prev=None, sigma=0.08):
    num = np.zeros((NT, 3)); den = np.zeros(NT)
    for s in range(NS):
        X, nrm, Pt, Nt = frame_geom(s)
        zc = {}
        for d in range(5):
            idx, col, ncam, w = visible_samples(s, d, X, nrm, Pt, Nt, zc)
            sh = shading(params, ncam)
            if prev is not None:
                diff = np.linalg.norm(prev[idx] * sh[:, None] - col, axis=1)
                w = w * np.exp(-0.5 * (diff / sigma) ** 2)
            np.add.at(num, idx, w[:, None] * col * sh[:, None]); np.add.at(den, idx, w * sh * sh)
    return num / np.maximum(den, 1e-9)[:, None], den


alb1, _ = full_pass()
alb2, den = full_pass(alb1)
print("albedo covered %.1f%%" % (100 * (den > 1e-9).mean()), f"{time.time()-t0:.0f}s", flush=True)
tex = np.zeros((TEX, TEX, 3)); wt = np.zeros((TEX, TEX))
tex[ty, tx] = lin2srgb(alb2); wt[ty, tx] = den > 1e-9
from texbake import pull_push_fill
from PIL import Image
filled = pull_push_fill(tex, wt)
Image.fromarray(np.clip(filled, 0, 255).astype(np.uint8)).save("UO_Body_Albedo.png")
th, ph = params[:2]
light = dict(L_camera=[float(np.sin(th) * np.cos(ph)), float(np.sin(th) * np.sin(ph)), float(np.cos(th))],
             ambient=float(params[2]), diffuse=float(params[3]))
pickle.dump(light, open("uo_light.pkl", "wb"))
print("saved UO_Body_Albedo.png", light, flush=True)
