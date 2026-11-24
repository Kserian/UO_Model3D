#!/usr/bin/env python3
"""medal_gump_2d - paperdoll gump of a medal (ribbon + disc) worn over the body gump 0xC (male) / 0xD (female), drawn in 2D.

    python medal_gump_2d.py OUT_DIR [--ribbon dark R,G,B mid R,G,B light R,G,B hi R,G,B] [--name Red]

Writes for both sexes  Medal_<name>_Male.png / Medal_<name>_Female.png  (260 x 237, item layer only, binary alpha = gump rules),
the same on the body  *_on_body.png  and a 4 x preview.  The item gump sits on the body gump pixel for pixel (body gump 12 geometry of the
Nelderim client, see uo_render_paperdoll.py), so it is only the medal, no skin.

The ribbon and the disc are small height fields (drawn at 6 x), shaded like the body gump: key light from the upper left (the left side of
the body gump is 11-20 levels brighter than the right one), ambient fill, a twill weave on the ribbon, a steel disc with a raised rim and
an embossed ring.  Down-sampling averages the colour of the covered sub-pixels; a pixel is opaque when more than half is covered, and
only pixels on the body silhouette are kept (the ribbon lies on the skin).  Colours are 15 bit, never 0 (0 is transparent).
Requires: numpy, pillow.
"""
import argparse
import os
import numpy as np
from PIL import Image

K = 6                                    # super-sampling
DS = 0.94                                # disc size relative to the first version (diameter ~9.4 px)
GW, GH = 260, 237
LIGHT = np.array([-0.60, -0.45, 0.66]); LIGHT /= np.linalg.norm(LIGHT)

# gump pixel geometry (x right, y down), measured on the body gumps
GEOM = {
    'Male': dict(body='paperdoll_male_0xc.png',
                 left=((81.8, 80.2), (82.2, 84.8), (88.5, 90.2), (94.0, 92.6)),
                 right=((100.8, 80.2), (100.9, 85.2), (98.0, 89.8), (94.8, 92.6)),
                 apex=(94.4, 92.6), disc=(94.4, 99.6), width=2.4),
    'Female': dict(body='paperdoll_female_0xd.png',
                   left=((82.4, 80.8), (82.8, 85.0), (88.2, 89.8), (92.4, 92.4)),
                   right=((99.6, 80.8), (99.6, 85.0), (96.8, 89.6), (93.0, 92.4)),
                   apex=(92.7, 92.4), disc=(92.7, 99.4), width=2.3),
}
# single pixels removed by hand after the render (they stuck out of the ribbon's stair step): (x, y) in gump pixels
FIX = {'Female': [(85, 88)]}
RIBBON = dict(dark=(30, 2, 6), mid=(90, 8, 16), light=(139, 24, 32), hi=(204, 62, 68))   # red: mid / light are the two reds of the animation


def bezier(p, n=80):
    p = np.array(p, float)
    t = np.linspace(0, 1, n)[:, None]
    return ((1 - t) ** 3) * p[0] + 3 * ((1 - t) ** 2) * t * p[1] + 3 * (1 - t) * t ** 2 * p[2] + t ** 3 * p[3]


def seg_dist(X, Y, pts):
    """distance of every (X, Y) to the polyline, the arc length at the nearest point and the side (+/-)."""
    best = np.full(X.shape, 1e9); arc = np.zeros(X.shape); side = np.zeros(X.shape)
    cum = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(pts, axis=0).T))])
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        d = b - a; L2 = float(d @ d)
        t = np.clip(((X - a[0]) * d[0] + (Y - a[1]) * d[1]) / L2, 0, 1)
        qx, qy = a[0] + t * d[0], a[1] + t * d[1]
        dist = np.hypot(X - qx, Y - qy)
        m = dist < best
        best = np.where(m, dist, best)
        arc = np.where(m, cum[i] + t * np.sqrt(L2), arc)
        side = np.where(m, np.sign((X - a[0]) * d[1] - (Y - a[1]) * d[0]), side)
    return best, arc, side


def ramp(I, c):
    """intensity -> colour through dark / mid / light / hi."""
    stops = [0.0, 0.42, 0.78, 1.35]
    cols = np.array([c['dark'], c['mid'], c['light'], c['hi']], float)
    out = np.zeros(I.shape + (3,))
    for ch in range(3):
        out[..., ch] = np.interp(I, stops, cols[:, ch])
    return out


def render(geom, colors, seed=3):
    x0, y0, x1, y1 = 70, 74, 122, 122
    ys, xs = np.mgrid[y0 * K:y1 * K, x0 * K:x1 * K]
    X, Y = (xs + 0.5) / K, (ys + 0.5) / K
    H = np.zeros(X.shape); layer = np.zeros(X.shape, int); tex = np.ones(X.shape)
    cov = np.zeros(X.shape, bool); rib = np.zeros(X.shape, bool)
    w = geom['width']
    # two strands, then the stem where they lie side by side
    for k, key in enumerate(('left', 'right')):
        pts = bezier(geom[key])
        d, arc, side = seg_dist(X, Y, pts)
        taper = 0.58 + 0.42 * np.clip(arc / 3.6, 0, 1) ** 0.8            # the ribbon turns round the neck
        r = d / (w * taper / 2)
        m = r < 1
        fold = 0.07 * np.sin(2 * np.pi * (arc / 5.2 + 0.31 * k))
        h = (0.55 * np.sqrt(np.clip(1 - r ** 2, 0, 1)) ** 0.7 + fold) * taper
        weave = 0.5 + 0.5 * np.sin(2 * np.pi * (arc / 0.85 + side * d / 0.85 * (1 if k == 0 else -1)))
        up = m & (h >= H)
        H = np.where(up, h + 0.06 * k, H); tex = np.where(up, (0.90 + 0.10 * weave) * (1 - 0.40 * np.clip((r - 0.72) / 0.28, 0, 1) ** 1.5), tex); rib |= up
    ax, ay = geom['apex']; dx, dy = geom['disc']
    stem = np.array([[ax, ay - 0.5], [ax + 0.02, (ay + dy) / 2 - 0.3], [dx, dy - 4.8]])
    d, arc, side = seg_dist(X, Y, stem)
    sw = w * 1.45
    r = d / (sw / 2)
    m = r < 1
    h = 0.62 * np.sqrt(np.clip(1 - r ** 2, 0, 1)) ** 0.7 + 0.07 * np.sin(2 * np.pi * (arc / 4.6 + 0.2))
    # the seam between the two strands runs down the middle of the stem
    h = h - 0.10 * np.exp(-((side * d) / 0.28) ** 2)
    weave = 0.5 + 0.5 * np.sin(2 * np.pi * (arc / 0.85 + side * d / 0.85))
    up = m & (h + 0.1 >= H)
    H = np.where(up, h + 0.1, H); tex = np.where(up, (0.90 + 0.10 * weave) * (1 - 0.40 * np.clip((r - 0.72) / 0.28, 0, 1) ** 1.5), tex); rib |= up
    # ring joining the ribbon to the disc, then the disc
    R = np.hypot(X - dx, Y - (dy - 5.0)) / DS
    ring = (R < 1.7) & (R > 0.8)
    Rd = np.hypot(X - dx, Y - dy) / DS
    disc = Rd < 5.0
    Hd = np.zeros_like(H)
    rim = np.clip(1 - np.abs(Rd - 4.3) / 0.8, 0, 1)
    face = np.clip(1 - (Rd / 4.2) ** 2, 0, 1) * 0.50
    emb = np.clip(1 - np.abs(Rd - 2.3) / 0.6, 0, 1) * 0.10
    Hd = 0.95 * rim ** 0.8 * (Rd > 3.4) + face * (Rd <= 3.7) + emb * (Rd < 3.3)
    Hd = Hd + 0.15
    metal = disc | ring
    Hm = np.where(disc, Hd, np.where(ring, 1.1 * np.clip(1 - np.abs(R - 1.25) / 0.45, 0, 1) + 0.4, 0))
    Hall = np.where(metal, Hm + 0.7, H)
    cov = rib | metal
    # shading
    gy, gx = np.gradient(Hall * K)
    n = np.dstack([-gx, -gy, np.ones_like(gx)]); n /= np.linalg.norm(n, axis=-1, keepdims=True)
    lam = np.clip(n @ LIGHT, 0, 1)
    I = 0.14 + 0.92 * lam
    Hh = LIGHT + np.array([0, 0, 1.0]); Hh /= np.linalg.norm(Hh)
    spec = np.clip(n @ Hh, 0, 1)
    # cavity darkening at the border of the ribbon and under the rim
    edge = np.clip(1 - np.minimum(np.where(rib, 1, 0) * 0 + 1, 1), 0, 1)
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal(X.shape) * 0.02
    rc = ramp(np.clip(I * tex * (1 + noise), 0, 1.4), colors)
    rc = rc + (spec ** 40)[..., None] * 32 * (rib & ~metal)[..., None]
    steel_base = np.array([150.0, 152.0, 164.0])
    steel = steel_base[None, None, :] * (0.30 + 0.88 * lam)[..., None]
    steel = steel + (spec ** 22)[..., None] * 110 + (np.clip(1 - np.abs(Rd - 2.55) / 0.4, 0, 1) * 0)[..., None]
    steel = np.where(((Rd > 3.4) & (Rd < 5.0))[..., None], steel * 1.06 + 8, steel)
    rgb = np.where(metal[..., None], steel, rc)
    # outline: a thin dark edge so the disc and the ribbon read against the skin (the body gump has the same dark edge)
    return cov, np.clip(rgb, 0, 255), (x0, y0, x1, y1), metal


def to_gump(cov, rgb, win, body_alpha, thr=0.38, metal=None):
    """6 x -> 1 x. Soft edges: the colour of a border pixel is darkened by how little of it is covered (a fringe instead of a stair step)."""
    x0, y0, x1, y1 = win
    h, w = cov.shape
    c = cov.reshape(h // K, K, w // K, K).mean((1, 3))
    col = (rgb * cov[..., None]).reshape(h // K, K, w // K, K, 3).sum((1, 3)) / np.maximum(cov.reshape(h // K, K, w // K, K).sum((1, 3)), 1)[..., None]
    s = np.clip((c - thr) / (0.95 - thr), 0, 1)
    s = s * s * (3 - 2 * s)                                    # smoothstep
    dark = 0.50
    if metal is not None:
        mshare = (metal * cov).reshape(h // K, K, w // K, K).sum((1, 3)) / np.maximum(cov.reshape(h // K, K, w // K, K).sum((1, 3)), 1)
        dark = 0.50 + 0.22 * mshare                           # steel keeps more of its light at the border
    col = col * (dark + (1 - dark) * s)[..., None]
    out = np.zeros((GH, GW, 4), np.uint8)
    win = out[y0:y1, x0:x1]
    on = (c > thr) & body_alpha[y0:y1, x0:x1]
    win[..., :3] = np.where(on[..., None], np.clip(np.round(col), 0, 255), 0).astype(np.uint8)
    dead = on & (win[..., :3].max(-1) < 8)
    win[..., :3][dead] = 8
    win[..., 3] = np.where(on, 255, 0)
    return out


def make_gump(sex, colors, bodies):
    """the medal gump (260 x 237 RGBA) of one sex and the body gump it sits on."""
    g = GEOM[sex]
    body = Image.open(os.path.join(bodies, g['body'])).convert('RGBA')
    balpha = np.asarray(body)[..., 3] > 0
    cov, rgb, win, metal = render(g, colors)
    gump = to_gump(cov, rgb, win, balpha, metal=metal.astype(float))
    for x, y in FIX.get(sex, []):
        gump[y, x] = 0
    return body, gump


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out'); ap.add_argument('--name', default='Red')
    ap.add_argument('--colors', help='dark;mid;light;hi as R,G,B;R,G,B;R,G,B;R,G,B (ribbon ramp)')
    ap.add_argument('--bodies', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'docs', 'paperdoll'))
    o = ap.parse_args()
    colors = dict(RIBBON)
    if o.colors:
        for k, v in zip(('dark', 'mid', 'light', 'hi'), o.colors.split(';')):
            colors[k] = tuple(int(x) for x in v.split(','))
    os.makedirs(o.out, exist_ok=True)
    for sex in GEOM:
        body, gump = make_gump(sex, colors, o.bodies)
        Image.fromarray(gump).save(os.path.join(o.out, f'Medal_{o.name}_{sex}.png'))
        comp = body.copy(); comp.alpha_composite(Image.fromarray(gump))
        comp.save(os.path.join(o.out, f'Medal_{o.name}_{sex}_on_body.png'))


if __name__ == '__main__':
    main()
