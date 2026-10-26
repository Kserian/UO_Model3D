# Make the spikes of a spiked ball (mace, morning star) bigger so that they read at 36 px/m: longer and thicker, the ball itself untouched.
# Run on the SELECTED mesh object(s) after uo_orient_weapon.py (shaft along +Z, head up, butt at z = 0, scale applied), before uo_place_weapon.py.
# 1. The ball: the sphere (centre on the shaft axis, radius) that most vertices lie on, found by scanning the centre height over the head (top HEAD share of the length).
# 2. The spikes: connected groups of vertices farther than SPIKE_FROM x radius from the centre (the shaft below the ball is dropped); the axis of a spike = from the centre
#    to its tip (a spike of a ball points away from the centre).
# 3. Per spike, in coordinates along its axis (t) and across it (perp): t' = r + (t - r) x LENGTH for t > r; perp' = perp x (1 + (WIDTH - 1) w(t)), w rising from 0 at
#    0.9 r to 1 at 1.05 r (the foot in the ball stays, the cone widens outside it). Vertices of the ball far from every spike axis do not move.
# The ball is stored on the object for uo_twohand.py: custom property uo_head = [z of the centre, radius, z of the bottom of the ball, z of the tip] (m, from the butt).
import math
import bpy
import numpy as np
from mathutils import Vector

LENGTH = 1.3          # spike length beyond the ball surface x this
WIDTH = 1.6           # spike thickness x this (outside the ball)
HEAD = 0.45           # share of the length (from the top) that holds the ball
SPIKE_FROM = 1.35     # vertices farther than this x radius from the centre belong to a spike
MIN_VERTS = 20        # a group of fewer vertices is not a spike
SPIKE_MAX = 4.0       # a group reaching farther than this x radius is the shaft, not a spike
BALL_R = 0.0          # m: radius (0 = found); BALL_Z = height of the centre (0 = found)
BALL_Z = 0.0


def find_ball(V, zmax):
    """centre height and radius of the sphere most vertices lie on (scan over the heights, histogram of the distances)"""
    c0 = np.array([V[:, 0].mean(), V[:, 1].mean(), 0.0])
    best = (0, 0, 0)
    for z in np.linspace(zmax * (1 - HEAD), zmax * 0.95, 60):
        d = np.linalg.norm(V - [c0[0], c0[1], z], axis=1)
        d = d[(d > 0.02) & (d < zmax * 0.3)]
        if len(d) < 100:
            continue
        h, e = np.histogram(d, bins=np.arange(0.02, zmax * 0.3, 0.004))
        k = int(np.argmax(h[:-1] + h[1:]))
        if h[k] + h[k + 1] > best[0]:
            best = (h[k] + h[k + 1], z, 0.5 * (e[k] + e[k + 2]))
    _, z, r = best
    s = np.abs(np.linalg.norm(V - [c0[0], c0[1], z], axis=1) - r) < 0.12 * r              # refine: least squares sphere on the shell
    A = np.c_[2 * V[s], np.ones(s.sum())]; b = (V[s] ** 2).sum(1)
    x = np.linalg.lstsq(A, b, rcond=None)[0]
    c = x[:3]; r2 = float(np.sqrt(max(x[3] + c @ c, 1e-9)))
    if abs(r2 - r) < 0.3 * r:
        return np.array([c0[0], c0[1], c[2]]), r2
    return np.array([c0[0], c0[1], z]), r


def run():
    from scipy import ndimage
    obs = [o for o in bpy.context.selected_objects if o.type == "MESH"]
    if not obs:
        raise RuntimeError("select the weapon first")
    for ob in obs:
        M = ob.matrix_world.copy(); Mi = M.inverted()
        V = np.array([M @ v.co for v in ob.data.vertices])
        zmax = float(V[:, 2].max())
        if BALL_R > 0 and BALL_Z > 0:
            c = np.array([V[:, 0].mean(), V[:, 1].mean(), BALL_Z]); r = BALL_R
        else:
            c, r = find_ball(V, zmax)
        d = np.linalg.norm(V - c, axis=1)
        far = np.nonzero(d > r * SPIKE_FROM)[0]
        cell = r / 6.0
        g = np.floor((V[far] - V[far].min(0)) / cell).astype(int) + 1
        vol = np.zeros(g.max(0) + 2, bool); vol[tuple(g.T)] = True
        lab, n = ndimage.label(ndimage.binary_dilation(vol))
        ids = lab[tuple(g.T)]
        axes = []
        for k in range(1, n + 1):
            m = far[ids == k]
            if len(m) < MIN_VERTS:
                continue
            dm = d[m]
            if dm.max() > SPIKE_MAX * r:
                continue
            tip = V[m[np.argmax(dm)]]
            axes.append((tip - c) / np.linalg.norm(tip - c))
        if not axes:
            raise RuntimeError("no spikes found (ball r %.3f at z %.3f)" % (r, c[2]))
        keep = []                                                                       # two groups of one spike (a sparse mesh breaks it in two): one axis
        for ax in axes:
            if all(ax @ k < math.cos(math.radians(12)) for k in keep):
                keep.append(ax)
        A = np.array(keep)
        rel = V - c
        t = rel @ A.T                                                                   # (n, spikes): along each axis
        perp = np.linalg.norm(rel[:, None, :] - t[..., None] * A[None], axis=2)          # (n, spikes): across it
        k = np.argmin(np.where(t > 0.8 * r, perp, 1e9), axis=1)
        idx = np.arange(len(V))
        tk, pk = t[idx, k], perp[idx, k]
        mine = (tk > 0.8 * r) & (pk < 0.45 * r)
        w = np.clip((tk - 0.9 * r) / (0.15 * r), 0, 1); w = w * w * (3 - 2 * w)
        t2 = np.where(tk > r, r + (tk - r) * LENGTH, tk)
        ax = A[k]
        perp_v = rel - tk[:, None] * ax
        new = c + t2[:, None] * ax + perp_v * (1 + (WIDTH - 1) * w)[:, None]
        V2 = np.where(mine[:, None], new, V)
        ob.data.vertices.foreach_set("co", np.array([Mi @ Vector(p) for p in V2]).ravel())
        ob.data.update()
        ob["uo_head"] = [float(c[2]), float(r), float(c[2] - r), float(V2[:, 2].max())]
        print("uo_spikes: %s: ball r %.3f m at z %.3f, %d spikes, %d vertices moved, length x%.2f width x%.2f, top %.3f -> %.3f m" % (
            ob.name, r, c[2], len(A), int(mine.sum()), LENGTH, WIDTH, zmax, V2[:, 2].max()))


run()
