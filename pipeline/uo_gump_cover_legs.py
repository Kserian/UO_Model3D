"""Paperdoll gump: the side panels follow the legs of the drawn body (a leg must not stick out beside the panel).

    python uo_gump_cover_legs.py RAW_DIR [--margin 1] [--side left|right|both]

RAW_DIR = the output of uo_render_paperdoll.py (gump_male_raw.npy, gump_female_raw.npy); the body gumps are docs/paperdoll/paperdoll_male_0xc.png / female_0xd.png. The skirt of the 3D model hangs
straight down, the drawn bodies stand with the legs apart (the left leg of the body gump 12 goes 15 px outwards over the height of the skirt), so below the hip the leg comes out beside the
outer panel. Per row: the leg's outer edge is the outermost pixel of the body gump, the panel's the outermost pixel of the item; where the leg is further out, the panel (the outermost run of item
pixels, when it is separate from the rest) is moved outwards by the difference + margin px, smoothed along y and eased in over the first rows, so it hangs along the leg. Only the left side is
moved by default (the right leg is inside its panel in both gumps); `--side both` moves the right one too where needed. Overwrites the raw files, prints the largest shift per gump.
"""
import argparse, os
import numpy as np
from PIL import Image
from scipy import ndimage

BODIES = {"male": "paperdoll_male_0xc.png", "female": "paperdoll_female_0xd.png"}
DOCS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "paperdoll")


def runs(row):
    r, s = [], None
    for x, v in enumerate(row):
        if v and s is None:
            s = x
        if not v and s is not None:
            r.append((s, x)); s = None
    if s is not None:
        r.append((s, len(row)))
    return r


def cover(raw, body, margin, side, y_leg=135, max_run=24):
    a = raw[..., 3] > 0.5; B = body[..., 3] > 0
    H, W = a.shape
    ys = np.nonzero(a.any(1))[0]
    sign = -1 if side == "left" else 1
    d = np.zeros(H)
    for y in range(max(ys.min(), y_leg), ys.max() + 1):
        ix = np.nonzero(a[y])[0]; bx = np.nonzero(B[y])[0]
        if not len(ix) or not len(bx):
            continue
        d[y] = max(0.0, (ix.min() - bx.min() + margin) if side == "left" else (bx.max() - ix.max() + margin))
    d = ndimage.gaussian_filter1d(d, 2.0)
    d *= np.clip((np.arange(H) - y_leg) / 6.0, 0, 1)                     # eased in below the hip
    out = raw.copy(); moved = 0
    for y in range(H):
        sh = int(round(d[y]))
        if sh <= 0 or not a[y].any():
            continue
        rs = runs(a[y])
        if len(rs) < 2:
            continue
        s, e = rs[0] if side == "left" else rs[-1]
        if e - s > max_run:
            continue
        seg = raw[y, s:e].copy()
        out[y, s:e] = 0                                                    # the old place of the panel is empty (the body shows)
        ns = s + sign * sh
        if 0 <= ns and ns + (e - s) <= W:
            out[y, ns:ns + (e - s)] = np.where(seg[..., 3:4] > 0.5, seg, out[y, ns:ns + (e - s)])
            moved = max(moved, sh)
    return out, moved, d.max()


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("raw"); ap.add_argument("--margin", type=float, default=1.0); ap.add_argument("--side", default="left")
    a = ap.parse_args()
    for g, f in BODIES.items():
        body = np.array(Image.open(os.path.join(DOCS, f)).convert("RGBA"))
        raw = np.load(os.path.join(a.raw, "gump_%s_raw.npy" % g))
        for side in (["left", "right"] if a.side == "both" else [a.side]):
            raw, moved, dmax = cover(raw, body, a.margin, side)
            print("%s %s: the panel moved outwards by up to %d px (the leg stuck out by %.1f px)" % (g, side, moved, dmax))
        np.save(os.path.join(a.raw, "gump_%s_raw.npy" % g), raw)


if __name__ == "__main__":
    main()
