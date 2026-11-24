"""Paperdoll gumps (male / female) and the item icon (art) of the medal necklace, fitted to the ORIGINAL necklace of the client.

    python uo_medal_gump_fit.py CLIENT_DIR OUT_DIR [CHECK_DIR]       # CLIENT_DIR holds Gumpidx.mul, Gumpart.mul

A render of the 3D model (uo_render_medal_gump.py) cannot be placed right: the drawn paperdoll bodies (gumps 12 / 13) have another neck, shoulders and chest than the 3D body (the cord climbed to the
jaw, the female medal sat 6 px off). So the footprint of the original necklace with a pendant (gump 50439 male / 60439 female: where the chain leaves the neck base, how it runs on the chest, where the pendant hangs)
is taken from the client, recoloured as our dark red cord (the same reds as the animation, no black outline) and the pendant is replaced by our round grey medal (R 4.5 px, light from the upper left).
Only the two strands are kept (the original has a stray pixel), each runs on to the medal's edge. Art: a hand-built icon in the scale of the original necklace icons (they are 10-12 px wide: the 3D render of
the whole necklace was 20 x 30 px, twice too big): a V of ribbon with the medal, 1 px shadow outline to the lower right like the originals.
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
    rim = (d <= r + 0.5) & (d > r - 1.0); face = d <= r - 1.0
    lit = np.clip(0.5 - 0.35 * (xx - cx) / r - 0.35 * (yy - cy) / r, 0, 1)
    for m, c0, c1 in ((rim, *RIM), (face, *FACE)):
        for c in range(3):
            a[..., c][m] = (c0[c] + (c1[c] - c0[c]) * lit[m]).astype(np.uint8)
        a[..., 3][m] = 255


def line(a, p, q, col):
    L = max(abs(q[0] - p[0]), abs(q[1] - p[1]))
    for s in np.linspace(0, 1, int(L) * 2 + 2):
        x, y = int(round(p[0] + (q[0] - p[0]) * s)), int(round(p[1] + (q[1] - p[1]) * s))
        a[y, x, :3] = col; a[y, x, 3] = 255


def make_gump(gender, tid, bid):
    t = gump_rgba(tid); a = t[..., 3] > 0
    lum = t[..., :3].astype(float).mean(-1)
    br = a & (lum > 185); lb, nb = ndi.label(br, structure=np.ones((3, 3)))
    sizes = ndi.sum(br, lb, range(1, nb + 1)); k = 1 + int(np.argmax(sizes)); cy, cx = ndi.center_of_mass(lb == k)
    yy, xx = np.mgrid[0:t.shape[0], 0:t.shape[1]]
    chain = a & (np.hypot(xx - cx, yy - cy) > R + 0.5)
    chain &= ~((np.hypot(xx - cx, yy - cy) <= R + 3.0) & (lum > 150))
    lc, nc = ndi.label(chain, structure=np.ones((3, 3)))
    if nc > 2:
        sz = ndi.sum(chain, lc, range(1, nc + 1)); chain = np.isin(lc, 1 + np.argsort(sz)[-2:])
    lc, nc = ndi.label(chain, structure=np.ones((3, 3)))
    inner = lum[chain]; med = np.median(inner[inner > 60]) if (inner > 60).any() else 100
    out = np.zeros_like(t)
    for y, x in zip(*np.nonzero(chain)):
        l = lum[y, x]
        out[y, x, :3] = EDGE if l < 55 else (REDL if l > med * 1.15 else (REDD if l < med * 0.85 else RED)); out[y, x, 3] = 255
    for k in range(1, nc + 1):                                    # each strand runs on to the medal's edge
        ys, xs = np.nonzero(lc == k); i = int(np.argmin(np.hypot(xs - cx, ys - cy))); x0, y0 = float(xs[i]), float(ys[i])
        for s in np.linspace(0, 1, int(np.hypot(cx - x0, cy - y0) * 3) + 2):
            x, y = x0 + (cx - x0) * s, y0 + (cy - y0) * s
            if np.hypot(x - cx, y - cy) <= R:
                break
            out[int(round(y)), int(round(x)), :3] = RED; out[int(round(y)), int(round(x)), 3] = 255
    disc(out, cx, cy, R)
    Image.fromarray(out).save(os.path.join(OUT, "gump_%s.png" % gender))
    if not CHECK:
        print(gender, "pendant of the original at", round(cx, 1), round(cy, 1)); return
    os.makedirs(CHECK, exist_ok=True)
    body = Image.fromarray(gump_rgba(bid)).convert("RGBA")
    bg = Image.new("RGBA", body.size, (60, 70, 60, 255)); bg.alpha_composite(body); bg.alpha_composite(Image.fromarray(out))
    bg.crop((60, 60, 125, 115)).resize((390, 330), Image.NEAREST).save(os.path.join(CHECK, "check_%s.png" % gender))
    print(gender, "pendant of the original at", round(cx, 1), round(cy, 1))


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
