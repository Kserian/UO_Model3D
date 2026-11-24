"""Paperdoll gumps (male / female) and the item icon (art) of the medal necklace, fitted to the ORIGINAL necklace of the client.

    python uo_medal_gump_fit.py CLIENT_DIR OUT_DIR [CHECK_DIR]       # CLIENT_DIR holds Gumpidx.mul, Gumpart.mul

A render of the 3D model cannot be placed right: the drawn paperdoll bodies (gumps 12 / 13) have another neck, shoulders and chest than the 3D body (the cord climbed to the jaw, the female medal sat 6 px off).
So the necklace is drawn on the drawn body itself: the neck centre x and the shoulder row are measured on gump 12 / 13; the same V (strands from the sides of the neck, over the collar bones) and the medal
17 px under the shoulder row are drawn for a man and a woman (equal length). The drawn bodies are turned a little, so the medal hangs on the sternum (x 94, between the breasts) and the strands meet above it in the
perspective of the body. Light from the upper left (3 reds like the animation, no black outline); what lies outside the body is cut. The original necklace gumps 50439 / 60439 were checked for the scale
(a pendant of 6 px). Art: a hand-built icon in the scale of the original necklace icons (10-12 px wide; the render of the whole necklace was 20 x 30 px): a V of ribbon with the medal, 1 px shadow outline to the lower right.
Writes gump_male.png, gump_female.png (260 x 237), art.png (44 x 32) and check_male.png / check_female.png (the gump over the original body gump 12 / 13, 6x) in CHECK_DIR if given (outside the repo).
"""
import os, sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import uo_gump_art as U

CLIENT, OUT = sys.argv[1], sys.argv[2]
CHECK = sys.argv[3] if len(sys.argv) > 3 else ""          # optional folder for check_*.png: they contain the client's body gumps, never commit them
os.makedirs(OUT, exist_ok=True)
R = 4.5                                          # medal radius in the gump (the original pendant is ca. 6 px wide)
RED, REDD, REDL, EDGE = (136, 26, 32), (112, 18, 24), (152, 34, 40), (86, 12, 18)
RIM, FACE = ((88, 88, 98), (150, 150, 160)), ((160, 160, 168), (206, 206, 212))


def gump_rgba(gid):
    return np.asarray(U.read_gump(CLIENT, gid)).astype(np.uint8)


def disc(a, cx, cy, r):
    """the medal: rim ring + face, light from the upper left"""
    h, w = a.shape[:2]; yy, xx = np.mgrid[0:h, 0:w]; d = np.hypot(xx - cx, yy - cy)
    rim = (d <= r) & (d > r - 1.3); face = d <= r - 1.3
    lit = np.clip(0.5 - 0.35 * (xx - cx) / r - 0.35 * (yy - cy) / r, 0, 1)
    for m, c0, c1 in ((rim, *RIM), (face, *FACE)):
        for c in range(3):
            a[..., c][m] = (c0[c] + (c1[c] - c0[c]) * lit[m]).astype(np.uint8)
        a[..., 3][m] = 255
    hx, hy = int(round(cx - r * 0.35)), int(round(cy - r * 0.35))          # the highlight
    a[hy, hx, :3] = (236, 236, 242); a[hy, hx, 3] = 255


def line(a, p, q, col):
    L = max(abs(q[0] - p[0]), abs(q[1] - p[1]))
    for s in np.linspace(0, 1, int(L) * 2 + 2):
        x, y = int(round(p[0] + (q[0] - p[0]) * s)), int(round(p[1] + (q[1] - p[1]) * s))
        a[y, x, :3] = col; a[y, x, 3] = 255


def anchors(bid):
    """neck centre x and shoulder row of the drawn body gump: the narrowest rows below the head are the neck, the shoulders start where the body is twice as wide"""
    m = gump_rgba(bid)[..., 3] > 0
    ys = np.nonzero(m.any(1))[0]; top = ys.min()
    w = np.array([m[y].sum() if m[y].any() else 0 for y in range(m.shape[0])], float)
    ny = top + 14 + int(np.argmin(w[top + 14:top + 32])); nw = w[ny]
    row = np.nonzero(m[ny])[0]; cx = (row.min() + row.max()) / 2.0
    sh = next(y for y in range(ny, ny + 20) if w[y] >= 2 * nw)
    return cx, sh


def spline(pts, n=60):
    """Catmull-Rom through pts"""
    P = np.array([pts[0]] + list(pts) + [pts[-1]], float); out = []
    for i in range(1, len(P) - 2):
        for t in np.linspace(0, 1, n, endpoint=False):
            out.append(0.5 * ((2 * P[i]) + (-P[i - 1] + P[i + 1]) * t + (2 * P[i - 1] - 5 * P[i] + 4 * P[i + 1] - P[i + 2]) * t * t + (-P[i - 1] + 3 * P[i] - 3 * P[i + 1] + P[i + 2]) * t ** 3))
    out.append(P[-2]); return np.array(out)


# the necklace in the same measures for both bodies: a V. The drawn bodies are turned a little, so the sternum (between the breasts: the cloth of the female body gump spans x 80..108, the male chest x 76..106)
# is at x 94, 3 px right of the neck centre: the medal hangs there (y 99, 17 px under the shoulder row for a man and a woman) and the two strands of the V (from the sides of the neck, over the collar bones, 9.5 px
# from the neck centre) meet above it in the perspective of the body: the left strand is longer than the right one
STERNUM_X, MEDAL_DY, V_HALF = 94.0, 17.0, 9.5


def strands(cx, sh):
    apex = (STERNUM_X, sh + MEDAL_DY - R - 2.0)
    out = []
    for sgn in (-1, 1):
        e = (cx + sgn * V_HALF, sh - 1.5)
        m = ((e[0] + apex[0]) / 2 + sgn * 0.9, (e[1] + apex[1]) / 2 - 0.4)       # the strand bows a little outward, over the collar bone
        out.append([e, m, apex])
    return out


def cord_pixels(cx, sh, shape, ss=8, width=1.8):
    """antialiased cord at ss x resolution; returns (coverage, side) where side > 0 is the upper left (lit) side of the cord"""
    h, w = shape[:2]
    left, right = strands(cx, sh)
    cov = np.zeros((h * ss, w * ss), np.float32); side = np.zeros_like(cov)
    yy, xx = np.mgrid[0:h * ss, 0:w * ss]; xx = (xx + 0.5) / ss; yy = (yy + 0.5) / ss
    best = np.full(cov.shape, 1e9, np.float32)
    for pts in (left, right):
        c = spline(pts)
        t = np.gradient(c, axis=0); t /= np.maximum(np.hypot(t[:, 0], t[:, 1])[:, None], 1e-9)
        n = np.stack([-t[:, 1], t[:, 0]], 1)
        x0, x1 = int((c[:, 0].min() - 2) * ss), int((c[:, 0].max() + 2) * ss); y0, y1 = int((c[:, 1].min() - 2) * ss), int((c[:, 1].max() + 2) * ss)
        for (px, py), nn in zip(c[::2], n[::2]):
            sx, sy = slice(max(int((px - 2) * ss), 0), int((px + 2) * ss)), slice(max(int((py - 2) * ss), 0), int((py + 2) * ss))
            d = np.hypot(xx[sy, sx] - px, yy[sy, sx] - py); upd = d < best[sy, sx]
            best[sy, sx] = np.where(upd, d, best[sy, sx])
            sd = (xx[sy, sx] - px) * nn[0] + (yy[sy, sx] - py) * nn[1]
            lit = nn[0] * -0.6 + nn[1] * -0.8                       # does the normal face the light (upper left)
            side[sy, sx] = np.where(upd, np.sign(sd) * lit, side[sy, sx])
    cov = (best < width / 2).astype(np.float32)
    cov = cov.reshape(h, ss, w, ss).mean((1, 3)); side = side.reshape(h, ss, w, ss).mean((1, 3))
    return cov, side


def make_gump(gender, tid, bid):
    cx, sh = anchors(bid)
    out = np.zeros((237, 260, 4), np.uint8)
    cov, side = cord_pixels(cx, sh, out.shape)
    m = (cov >= 0.4) & (gump_rgba(bid)[..., 3] > 0)                 # the cord goes round the back of the neck: only what lies on the drawn body is seen
    out[m, :3] = RED; out[m & (side > 0.25), :3] = REDL; out[m & (side < -0.25), :3] = REDD; out[m, 3] = 255
    my = sh + MEDAL_DY; cx = STERNUM_X
    disc(out, cx, my, R)
    for k in (1, 2):                                               # the ring the cord runs through
        yy_ = int(round(my - R)) - k
        out[yy_, int(round(cx)), :3] = (122, 122, 132); out[yy_, int(round(cx)), 3] = 255
    Image.fromarray(out).save(os.path.join(OUT, "gump_%s.png" % gender))
    print(gender, "neck centre x %.1f shoulder row %d, medal at y %.1f" % (cx, sh, my))
    if not CHECK:
        return
    os.makedirs(CHECK, exist_ok=True)
    body = Image.fromarray(gump_rgba(bid)).convert("RGBA")
    bg = Image.new("RGBA", body.size, (60, 70, 60, 255)); bg.alpha_composite(body); bg.alpha_composite(Image.fromarray(out))
    bg.crop((60, 60, 125, 115)).resize((390, 330), Image.NEAREST).save(os.path.join(CHECK, "check_%s.png" % gender))


def make_art():
    a = np.zeros((32, 44, 4), np.uint8); ox, oy = 15, 3          # sprite 13 x 19, placed like the original icons (centre x ca. 21, top y 1..3)
    line(a, (ox + 1, oy), (ox + 6, oy + 8), RED); line(a, (ox + 11, oy), (ox + 6, oy + 8), RED)
    for x, y in ((ox + 1, oy), (ox + 11, oy), (ox + 6, oy + 8)):
        a[y, x, :3] = REDL
    for y in (oy + 9, oy + 10):
        a[y, ox + 6, :3] = (110, 110, 120); a[y, ox + 6, 3] = 255
    disc(a, ox + 6, oy + 14, 3.8)
    solid = a[..., 3] > 0
    for y in range(31):                                           # 1 px shadow outline below / right (like the original icons)
        for x in range(43):
            if not solid[y, x] and (solid[y - 1, x] or solid[y, x - 1]):
                a[y, x, :3] = (50, 30, 34); a[y, x, 3] = 255
    Image.fromarray(a).save(os.path.join(OUT, "art.png"))


make_gump("male", 50439, 12)
make_gump("female", 60439, 13)
make_art()
