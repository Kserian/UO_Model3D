#!/usr/bin/env python3
"""medal_art_2d - item art (icon of the medal in a backpack / on the ground, art.mul) drawn in 2D.

    python medal_art_2d.py OUT_DIR [--name Red] [--colors dark;mid;light;hi] [--tilt 54] [--turn -40]

UO draws a lying item seen from above at an angle, so the medal is built lying on a plane (ribbon loop in the shape of a slightly curled heart + steel disc on a bail), turned by --turn
degrees and tilted towards the camera by --tilt; every screen pixel is mapped back onto the plane, so the ribbon keeps its true width and the disc
becomes an ellipse.  Same light, ribbon colours and steel as medal_gump_2d.py (key light from the upper left).  Drawn at 8 x, the thickness of the
disc and of the ribbon shows as a darker side wall below the edge, down-sampled with a coverage threshold (hard edges: art has no alpha), and a
1 px dark outline is added like on every UO art.  The object is fitted into 44 x 32 px (outline included).
Writes Medal_<name>_Art.png (44 x 32, transparent) and Medal_<name>_Art_preview.png (on a backpack-brown tile, 8 x).
Requires: numpy, pillow.
"""
import argparse
import os
import sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from medal_gump_2d import RIBBON, ramp, bezier

K = 8
AW, AH = 44, 32
LIGHT = np.array([-0.55, 0.45, 0.70]); LIGHT /= np.linalg.norm(LIGHT)
OUTLINE = (22, 8, 10)

W_RIB = 0.0205          # ribbon width, m
R_DISC = 0.0425         # disc radius
KH = 0.0054             # m per unit of the heart curve


def heart_arms(n=90):
    """the ribbon lies in a heart: both arms start at the eyelet (bottom point) and meet in the notch at the top (left arm first)."""
    t = np.linspace(np.pi, 0, n)
    x = 16 * np.sin(t) ** 3
    y = 13 * np.cos(t) - 5 * np.cos(2 * t) - 2 * np.cos(3 * t) - np.cos(4 * t)
    right = np.c_[x, y] * KH
    left = np.c_[-x, y] * KH
    return [left, right]


STRANDS = heart_arms()
APEX_V = STRANDS[0][0, 1]
EYELET = np.array([0.0, APEX_V - 0.004])
DISC_C = np.array([0.0, APEX_V - 0.004 - 0.0105 - R_DISC * 0.78])


def poly(pts, n=120):
    return bezier(pts, n)


def seg_dist(U, V, pts):
    best = np.full(U.shape, 1e9); arc = np.zeros(U.shape); side = np.zeros(U.shape)
    cum = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(pts, axis=0).T))])
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        d = b - a; L2 = float(d @ d)
        t = np.clip(((U - a[0]) * d[0] + (V - a[1]) * d[1]) / L2, 0, 1)
        qx, qy = a[0] + t * d[0], a[1] + t * d[1]
        dist = np.hypot(U - qx, V - qy)
        m = dist < best
        best = np.where(m, dist, best); arc = np.where(m, cum[i] + t * np.sqrt(L2), arc)
        side = np.where(m, np.sign((U - a[0]) * d[1] - (V - a[1]) * d[0]), side)
    return best, arc, side


def field(U, V, paths):
    """height (m), ribbon mask, metal mask, ribbon texture of the medal at table-frame points."""
    H = np.zeros(U.shape); rib = np.zeros(U.shape, bool); tex = np.ones(U.shape)
    for k, pts in enumerate(paths):
        d, arc, side = seg_dist(U, V, pts)
        r = d / (W_RIB / 2)
        m = r < 1
        inner = (side * (1 if k == 0 else -1)) > 0
        fold = 0.0006 * np.sin(2 * np.pi * (arc / 0.07 + 0.3 * k))
        bank = 0.0018 * np.clip(arc / 0.10, 0, 1) * (side * (1 if k == 0 else -1)) * np.clip(r, 0, 1)      # the ribbon is slightly curled
        h = 0.0032 * np.sqrt(np.clip(1 - r ** 2, 0, 1)) ** 0.7 + fold + bank
        weave = 0.5 + 0.5 * np.sin(2 * np.pi * (arc / 0.012 + side * d / 0.012 * (1 if k == 0 else -1)))
        up = m & (h + 0.0001 * k >= H)
        H = np.where(up, h + 0.0001 * k, H)
        edge = np.clip((r - 0.30) / 0.70, 0, 1) ** 1.3
        tex = np.where(up, (0.92 + 0.08 * weave) * (1 - np.where(inner, 0.62, 0.30) * edge), tex)
        rib |= up
    # eyelet ring and disc (steel)
    # the bail: a short steel capsule from the eyelet down to the top of the disc
    top = np.array([0.0, DISC_C[1] + R_DISC * 0.95])
    dd, _, _ = seg_dist(U, V, np.array([EYELET, top]))
    ring = dd < 0.0072
    Re = dd / 0.0072
    Rd = np.hypot(U - DISC_C[0], V - DISC_C[1]) / R_DISC
    disc = Rd < 1
    rim = np.clip(1 - np.abs(Rd - 0.86) / 0.17, 0, 1)
    hd = 0.0045 + 0.0030 * rim ** 0.8 * (Rd > 0.66) + 0.0042 * np.clip(1 - (Rd / 0.82) ** 2, 0, 1) * (Rd <= 0.78) + 0.0007 * np.clip(1 - np.abs(Rd - 0.5) / 0.14, 0, 1) * (Rd < 0.66)
    hr = 0.0040 + 0.0030 * np.sqrt(np.clip(1 - Re ** 2, 0, 1))
    metal = disc | ring
    H = np.where(disc, hd + 0.003, np.where(ring, hr + 0.003, H))
    return H, rib | metal, metal, tex, Rd


def render(tilt, turn, colors, seed=3):
    th, ph = np.radians(tilt), np.radians(turn)
    # fit: project the outline samples of the object at scale 1
    t = np.linspace(0, 1, 200)
    pts = np.vstack([s for s in STRANDS]
                    + [DISC_C + R_DISC * np.c_[np.cos(2 * np.pi * t), np.sin(2 * np.pi * t)]])
    pad = W_RIB / 2
    rot = lambda p: np.c_[p[:, 0] * np.cos(ph) - p[:, 1] * np.sin(ph), p[:, 0] * np.sin(ph) + p[:, 1] * np.cos(ph)]
    q = rot(pts)
    ext_x = q[:, 0].max() - q[:, 0].min() + 2 * pad + 0.008
    ext_y = (q[:, 1].max() - q[:, 1].min()) * np.sin(th) + 2 * pad * np.sin(th) + 0.008 + 0.012 * np.cos(th)
    s = min((AW - 2) / ext_x, (AH - 2) / ext_y)                 # px per metre (1 px outline on every side)
    cx = (q[:, 0].max() + q[:, 0].min()) / 2; cy = (q[:, 1].max() + q[:, 1].min()) / 2
    ys, xs = np.mgrid[0:AH * K, 0:AW * K]
    sx, sy = (xs + 0.5) / K - AW / 2, (ys + 0.5) / K - AH / 2
    up_ = sx / s + cx                                              # camera-frame plane coordinates
    vp_ = -sy / (s * np.sin(th)) + cy
    inv = lambda u, v: (u * np.cos(ph) + v * np.sin(ph), -u * np.sin(ph) + v * np.cos(ph))
    paths = STRANDS
    def eval_h(u, v):
        U, V = inv(u, v)
        return field(U, V, paths)
    H, cov, metal, tex, Rd = eval_h(up_, vp_)
    eps = 0.0012
    Hx = eval_h(up_ + eps, vp_)[0]; Hy = eval_h(up_, vp_ + eps)[0]
    # the side wall: the same shape pushed down on the screen by its thickness
    gx, gy = (Hx - H) / eps, (Hy - H) / eps
    n = np.dstack([-gx, -gy, np.ones_like(gx)]); n /= np.linalg.norm(n, axis=-1, keepdims=True)
    lam = np.clip(n @ LIGHT, 0, 1)
    V = np.array([0.0, -np.cos(th), np.sin(th)])
    Hh = LIGHT + V; Hh /= np.linalg.norm(Hh)
    spec = np.clip(n @ Hh, 0, 1)
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal(H.shape) * 0.02
    rib = cov & ~metal
    I = 0.14 + 0.92 * lam
    rc = ramp(np.clip(I * tex * (1 + noise), 0, 1.4), colors)
    rc = rc + (spec ** 40)[..., None] * 28 * rib[..., None]
    steel = np.array([150.0, 152.0, 164.0])[None, None, :] * (0.30 + 0.88 * lam)[..., None]
    steel = steel + (spec ** 22)[..., None] * 110
    steel = np.where(((Rd > 0.72) & (Rd < 1))[..., None], steel * 1.05 + 8, steel)
    steel = np.where((~(Rd < 1))[..., None], steel * 0.78, steel)            # the eyelet ring is a little darker than the disc face
    rgb = np.where(metal[..., None], steel, rc)
    # side walls (thickness) below the lower edge
    def wall(mask, drop_px, col):
        d = max(1, int(round(drop_px * K)))
        sh = np.zeros_like(mask); sh[d:] = mask[:-d]
        return sh & ~cov, col
    w1, c1 = wall(cov & metal, 0.9 * np.sin(th) + 0.5, None)
    w2, c2 = wall(cov & rib, 0.45, None)
    wall_mask = (w1 | w2)
    wall_rgb = np.where((w1)[..., None], np.array([70.0, 72.0, 84.0]), np.array([26.0, 3.0, 8.0]))
    allc = cov | wall_mask
    allrgb = np.where(cov[..., None], rgb, wall_rgb)
    return allc, np.clip(allrgb, 0, 255)


def to_art(cov, rgb, thr=0.5):
    h, w = cov.shape
    c = cov.reshape(h // K, K, w // K, K).mean((1, 3))
    col = (rgb * cov[..., None]).reshape(h // K, K, w // K, K, 3).sum((1, 3)) / np.maximum(cov.reshape(h // K, K, w // K, K).sum((1, 3)), 1)[..., None]
    s = np.clip((c - thr) / (0.95 - thr), 0, 1)
    col = col * (0.62 + 0.38 * (s * s * (3 - 2 * s)))[..., None]           # soft fringe, like the gump
    on = c > thr
    out = np.zeros((AH, AW, 4), np.uint8)
    out[..., :3] = np.where(on[..., None], np.clip(np.round(col), 0, 255), 0).astype(np.uint8)
    out[..., 3] = np.where(on, 255, 0)
    # 1 px outline (4-neighbourhood), then colours never 0 (transparent in the client)
    p = np.pad(on, 1)
    near = p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]
    ol = near & ~on
    out[ol, :3] = OUTLINE; out[ol, 3] = 255
    dead = (out[..., 3] > 0) & (out[..., :3].max(-1) < 8)
    out[..., :3][dead] = 8
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out'); ap.add_argument('--name', default='Red')
    ap.add_argument('--colors'); ap.add_argument('--tilt', type=float, default=54); ap.add_argument('--turn', type=float, default=-40)
    o = ap.parse_args()
    colors = dict(RIBBON)
    if o.colors:
        for k, v in zip(('dark', 'mid', 'light', 'hi'), o.colors.split(';')):
            colors[k] = tuple(int(x) for x in v.split(','))
    os.makedirs(o.out, exist_ok=True)
    cov, rgb = render(o.tilt, o.turn, colors)
    art = to_art(cov, rgb)
    Image.fromarray(art).save(os.path.join(o.out, f'Medal_{o.name}_Art.png'))
    bg = Image.new('RGBA', (AW, AH), (74, 52, 34, 255)); bg.alpha_composite(Image.fromarray(art))
    bg.resize((AW * 8, AH * 8), Image.NEAREST).convert('RGB').save(os.path.join(o.out, f'Medal_{o.name}_Art_preview.png'))


if __name__ == '__main__':
    main()
