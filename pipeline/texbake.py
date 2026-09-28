"""Project sprite colours onto the model's UV texture (5 views + mirror-partner samples)."""
import numpy as np
from body import ANCHOR_X, ANCHOR_Y


def cam_basis(theta, d):
    yaw = -d * np.pi / 4
    c, s = np.cos(-yaw), np.sin(-yaw)
    Rz = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])
    right = Rz @ np.array([1.0, 0, 0])
    up = Rz @ np.array([0, np.sin(theta), np.cos(theta)])
    fwd = np.cross(right, up)  # toward camera
    return right, up, fwd


def to_screen(p, theta, scale, d):
    r, u, f = cam_basis(theta, d)
    return np.stack([ANCHOR_X + scale * (p @ r), ANCHOR_Y - scale * (p @ u), p @ f], -1)


def tri_raster(pts2, fn, W, H):
    """Rasterise triangles given 2D points (T,3,2); calls fn(tri_index, xs, ys, bary(n,3)) for covered pixel centres."""
    for t in range(len(pts2)):
        a, b, c = pts2[t]
        x0 = max(int(np.floor(min(a[0], b[0], c[0]))), 0)
        x1 = min(int(np.ceil(max(a[0], b[0], c[0]))), W - 1)
        y0 = max(int(np.floor(min(a[1], b[1], c[1]))), 0)
        y1 = min(int(np.ceil(max(a[1], b[1], c[1]))), H - 1)
        if x1 < x0 or y1 < y0:
            continue
        ys, xs = np.mgrid[y0:y1 + 1, x0:x1 + 1]
        px = xs.ravel() + 0.5
        py = ys.ravel() + 0.5
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(den) < 1e-12:
            continue
        l0 = ((b[1] - c[1]) * (px - c[0]) + (c[0] - b[0]) * (py - c[1])) / den
        l1 = ((c[1] - a[1]) * (px - c[0]) + (a[0] - c[0]) * (py - c[1])) / den
        l2 = 1 - l0 - l1
        m = (l0 >= -1e-4) & (l1 >= -1e-4) & (l2 >= -1e-4)
        if m.any():
            fn(t, xs.ravel()[m], ys.ravel()[m], np.stack([l0[m], l1[m], l2[m]], 1))


def zbuffer(vs, tris, W, H, ss):
    """vs: (N,3) screen x,y (canvas px), depth-toward-camera. Returns zbuf (H*ss, W*ss)."""
    zb = np.full((H * ss, W * ss), -np.inf)
    p2 = vs[tris][..., :2] * ss
    z = vs[tris][..., 2]

    def fn(t, xs, ys, bc):
        zz = bc @ z[t]
        np.maximum.at(zb, (ys, xs), zz)
    tri_raster(p2, fn, W * ss, H * ss)
    return zb


def vertex_normals(v, tris):
    fn = np.cross(v[tris[:, 1]] - v[tris[:, 0]], v[tris[:, 2]] - v[tris[:, 0]])
    n = np.zeros_like(v)
    for k in range(3):
        np.add.at(n, tris[:, k], fn)
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)


def erode(mask, it=1):
    m = mask.copy()
    for _ in range(it):
        n = m.copy()
        n[1:] &= m[:-1]; n[:-1] &= m[1:]; n[:, 1:] &= m[:, :-1]; n[:, :-1] &= m[:, 1:]
        m = n
    return m


def bake(tris, tri_uv, posed, mirror, sprites, theta, scale, size=1024, ss=4, mirror_w=0.6, eps=0.02):
    """tris (T,3) vertex idx; tri_uv (T,3,2) in [0,1]; posed (N,3); mirror (N,) partner index;
    sprites: list of 5 canvas RGBA uint8 (H,W,4) for file dirs 0..4. Returns RGBA float texture and weight map."""
    H, W = sprites[0].shape[:2]
    nrm = vertex_normals(posed, tris)
    # texel -> (triangle, barycentric)
    tex_tri = np.full((size, size), -1, np.int64)
    tex_bc = np.zeros((size, size, 3))

    def fn(t, xs, ys, bc):
        tex_tri[ys, xs] = t
        tex_bc[ys, xs] = bc
    uvpx = tri_uv.copy()
    uvpx[..., 0] *= size
    uvpx[..., 1] = (1 - uvpx[..., 1]) * size
    tri_raster(uvpx, fn, size, size)
    ys, xs = np.nonzero(tex_tri >= 0)
    t = tex_tri[ys, xs]
    bc = tex_bc[ys, xs]
    acc = np.zeros((len(t), 3))
    wsum = np.zeros(len(t))
    # equalise overall brightness between directions (UO lights are fixed while the body turns)
    means = []
    for img in sprites:
        core = erode(img[..., 3] > 127, 1)
        means.append(img[core][:, :3].mean())
    gains = np.mean(means) / np.array(means)
    for use_mirror, wm in ((False, 1.0), (True, mirror_w)):
        idx = tris[t] if not use_mirror else mirror[tris[t]]
        P = np.einsum("nk,nkd->nd", bc, posed[idx])
        N = np.einsum("nk,nkd->nd", bc, nrm[idx])
        N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)
        for d in range(5):
            scr_v = to_screen(posed, theta, scale, d)
            zb = zbuffer(scr_v, tris, W, H, ss)
            sp = to_screen(P, theta, scale, d)
            _, _, fwd = cam_basis(theta, d)
            facing = N @ fwd
            xi = np.floor(sp[:, 0]).astype(int)
            yi = np.floor(sp[:, 1]).astype(int)
            zx = np.clip(np.floor(sp[:, 0] * ss).astype(int), 0, W * ss - 1)
            zy = np.clip(np.floor(sp[:, 1] * ss).astype(int), 0, H * ss - 1)
            inside = (xi >= 0) & (xi < W) & (yi >= 0) & (yi < H)
            vis = inside & (sp[:, 2] >= zb[zy, zx] - eps) & (facing > 0.15)
            img = sprites[d]
            core = erode(img[..., 3] > 127, 1)   # skip the dark 1-px outline of the sprite
            a = np.zeros(len(t))
            a[vis] = img[yi[vis], xi[vis], 3] / 255.0
            vis &= a > 0.5
            incore = np.zeros(len(t), bool)
            incore[vis] = core[yi[vis], xi[vis]]
            w = np.where(vis, facing ** 2, 0.0) * wm * np.where(incore, 1.0, 0.05)
            col = np.zeros((len(t), 3))
            col[vis] = img[yi[vis], xi[vis], :3] * gains[d]
            acc += col * w[:, None]
            wsum += w
    tex = np.zeros((size, size, 3))
    wt = np.zeros((size, size))
    ok = wsum > 1e-6
    tex[ys[ok], xs[ok]] = acc[ok] / wsum[ok, None]
    wt[ys[ok], xs[ok]] = 1.0
    return tex, wt, (tex_tri >= 0)


def pull_push_fill(tex, wt):
    """Fill holes (wt==0) from coarser mip levels."""
    levels = [(tex * wt[..., None], wt.copy())]
    while levels[-1][1].shape[0] > 1:
        c, w = levels[-1]
        h = c.shape[0] // 2
        c2 = c[:2 * h, :2 * h].reshape(h, 2, h, 2, 3).sum((1, 3))
        w2 = w[:2 * h, :2 * h].reshape(h, 2, h, 2).sum((1, 3))
        levels.append((c2, w2))
    col = levels[-1][0] / np.maximum(levels[-1][1], 1e-9)[..., None]
    for c, w in reversed(levels[:-1]):
        up = np.repeat(np.repeat(col, 2, 0), 2, 1)[: c.shape[0], : c.shape[1]]
        own = c / np.maximum(w, 1e-9)[..., None]
        a = np.clip(w, 0, 1)[..., None]
        col = own * a + up * (1 - a)
    return col
