"""Paperdoll gump: the side panels follow the legs of the drawn body (a leg must not stick out beside the panel).

    python uo_gump_cover_legs.py RAW_DIR [--margin 1] [--side left|right|both]

RAW_DIR = the output of uo_render_paperdoll.py (gump_male_raw.npy, gump_female_raw.npy); the body gumps are docs/paperdoll/paperdoll_male_0xc.png / female_0xd.png. The skirt of the 3D model hangs
straight down, the drawn bodies stand with the legs apart (the left leg of the body gump 12 goes 15 px outwards over the height of the skirt), so below the hip the leg comes out beside the
outer panel. Per row: the leg's outer edge is the outermost pixel of the body gump, the panel's the outermost pixel of the item; where the leg is further out, the panel (the outermost run of item
pixels, when it is separate from the rest) is moved outwards by the difference + margin px, smoothed along y and the largest need within +-4 rows then smoothed, and the shift may grow by at most 0.5 px per row from the first row that needs it (a slanted start flush with the band, like the right panel; the leg may stick out 2-4 px there); its outer edge smoothed along y (only extended outwards, so the cover stays), so it hangs along the leg. Only the left side is
moved by default (the right leg is inside its panel in both gumps); `--side both` moves the right one too where needed. The inner edges of both panels are then smoothed along y (smooth_inner_edges). Overwrites the raw files, prints the largest shift per gump.
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


def cover(raw, body, margin, side, y_leg=135, max_run=24, panel_x=(None, 86), slope=0.5):
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
    d = ndimage.maximum_filter1d(d, size=9)                              # the cover first (the largest need within +-4 rows), then smooth: the edge is a slanted line, not steps
    d = ndimage.gaussian_filter1d(d, 3.0)
    y_sep = H                                                              # the first row in which the panel is a run of its own (left of the banner): there the shift starts at 0
    for y in range(y_leg, H):
        rs = runs(a[y])
        if len(rs) >= 2:
            s0, e0 = rs[0] if side == "left" else rs[-1]
            if e0 - s0 <= max_run and ((side == "left" and e0 <= panel_x[1]) or (side == "right" and s0 >= 260 - panel_x[1])):
                y_sep = y; break
    d = np.minimum(d, slope * np.maximum(np.arange(H) - y_sep + 1, 0))     # the shift grows by at most `slope` px per row from there: the panel leaves the band along a slanted edge, flush with it, like the other panel
    d = np.minimum(d, 14.0)                                                  # at most 14 px; no easing out at the end: the panel keeps its outer edge on the leg's outer edge down to its own last row (it rests on the leg)
    out = raw.copy(); moved = 0
    for y in range(H):
        sh = int(round(d[y]))
        if sh <= 0 or not a[y].any():
            continue
        rs = runs(a[y])
        if len(rs) < 2:
            continue
        s, e = rs[0] if side == "left" else rs[-1]
        if e - s > max_run or (side == "left" and e > panel_x[1]) or (side == "right" and s < 260 - panel_x[1]):
            continue                                                           # not a panel: wider than one, or already the banner's own ornament
        seg = raw[y, s:e].copy()
        out[y, s:e] = 0                                                    # the old place of the panel is empty (the body shows)
        ns = s + sign * sh
        if 0 <= ns and ns + (e - s) <= W:
            out[y, ns:ns + (e - s)] = np.where(seg[..., 3:4] > 0.5, seg, out[y, ns:ns + (e - s)])
            moved = max(moved, sh)
    # the outer edge of the moved panel is replaced by a smooth curve: a cubic polynomial fitted to its x(y) over the rows of the panel (the waves of the torn border and the plateaus and steps of the integer
    # shifts go; the slanted line along the leg stays), then clamped so that the leg never sticks out by more than 1 px (the cover stays), at most 5 px from where it was; pixels added take the colour of the
    # edge pixel, pixels removed become transparent
    edge = np.full(H, np.nan)
    for y in range(H):
        if d[y] > 0.5 and out[y, :, 3].max() > 0.5:
            rs = runs(out[y, :, 3] > 0.5)
            r0 = rs[0] if side == "left" else rs[-1]
            if len(rs) >= 2 and r0[1] - r0[0] <= max_run and (side != "left" or r0[1] <= panel_x[1]):
                edge[y] = r0[0] if side == "left" else r0[1] - 1
    ok = ~np.isnan(edge); ys_ok = np.nonzero(ok)[0]
    for seg in (np.split(ys_ok, np.nonzero(np.diff(ys_ok) > 1)[0] + 1) if len(ys_ok) else []):
        if len(seg) < 12:
            continue
        coef = np.polyfit(seg - seg[0], edge[seg], 3); fit = np.polyval(coef, seg - seg[0])
        for y, e_old, e_fit in zip(seg, edge[seg], fit):
            e_old = int(e_old)
            bx = np.nonzero(B[y])[0]
            new_e = int(np.clip(round(e_fit), e_old - 5, e_old + 5))
            if side == "left":
                if len(bx):
                    new_e = min(new_e, int(bx.min()))                              # the edge reaches the leg's outermost pixel: no body beside the panel
                if new_e < e_old:
                    out[y, new_e:e_old] = out[y, e_old]
                elif new_e > e_old:
                    out[y, e_old:new_e] = 0
    if side == "left":                                                      # the corner under the band: before the panel leaves it (the shift grows 0.5 px per row) the leg comes out beside the band's lower corner by 2-3 px; the item's edge is
        for y in range(max(y_leg - 4, 0), H):                              # widened to the leg's outer edge (at most 5 px, the colour of the edge pixel; later rows are covered by the fitted edge)
            if not (out[y, :, 3] > 0.5).any() or not B[y].any():
                continue
            lx = int(np.nonzero(B[y])[0].min()); ix = int(np.nonzero(out[y, :, 3] > 0.5)[0].min())
            if lx >= 70 and ix > lx and ix - lx <= 5 and ix <= panel_x[1]:
                out[y, lx:ix] = out[y, ix]
    if side == "left":                                                      # 1-px stubs beside the panel (a tick of the tip) go: a 2 x 2 opening of the panel's region only (the banner's own thin ornaments are not touched)
        reg = np.zeros(out.shape[:2], bool); reg[y_leg:, :panel_x[1]] = True
        al = out[..., 3] > 0.5
        opened = ndimage.binary_opening(al & reg, structure=np.ones((2, 2), bool))
        drop = al & reg & ~opened
        out[drop] = 0
    return out, moved, d.max()


def smooth_inner_edges(raw, y_leg=135, max_run=24, left_end=86, right_start=103, sigma=2.5, max_move=3):
    """the inner edges of both panels (towards the leg and the banner) are smoothed along y: the torn border of the model is ragged and, once the body shows behind it, reads as frayed. Per row the panel is
    the first run left of the banner (its right end is the inner edge) / the last run right of it (its left end); the edge x(y) goes through a median of 5 rows (notches of the torn border) and an average over +-2.5 rows in every stretch of consecutive rows
    and is moved by at most `max_move` (3) px: a pixel added takes the colour of the edge pixel, a pixel removed becomes transparent"""
    out = raw.copy(); a = raw[..., 3] > 0.5; H, W = a.shape
    for side in ("left", "right"):
        edge = np.full(H, np.nan)
        for y in range(y_leg, H):
            rs = runs(a[y])
            if len(rs) < 2:
                continue
            s0, e0 = rs[0] if side == "left" else rs[-1]
            if e0 - s0 > max_run:
                continue
            if side == "left" and e0 <= left_end:
                edge[y] = e0
            elif side == "right" and s0 >= right_start:
                edge[y] = s0
        ok = ~np.isnan(edge); ys = np.nonzero(ok)[0]
        if len(ys) < 5:
            continue
        for seg in np.split(ys, np.nonzero(np.diff(ys) > 1)[0] + 1):               # consecutive rows only
            if len(seg) < 5:
                continue
            e = edge[seg]; sm = ndimage.gaussian_filter1d(ndimage.median_filter(e, size=5, mode="nearest"), sigma, mode="nearest")      # the median first: notches of the torn border go, then the average
            for y, e_old, e_new in zip(seg, e, sm):
                n = int(np.clip(round(e_new) - e_old, -max_move, max_move)); e_old = int(e_old)
                if n == 0:
                    continue
                if side == "left":                                                   # the inner edge is the right end of the run [s0, e_old)
                    if n > 0:
                        out[y, e_old:e_old + n] = out[y, e_old - 1]
                    else:
                        out[y, e_old + n:e_old] = 0
                else:                                                                # the inner edge is the left end s0 = e_old
                    if n < 0:
                        out[y, e_old + n:e_old] = out[y, e_old]
                    else:
                        out[y, e_old:e_old + n] = 0
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("raw"); ap.add_argument("--margin", type=float, default=0.0); ap.add_argument("--side", default="left")
    a = ap.parse_args()
    for g, f in BODIES.items():
        body = np.array(Image.open(os.path.join(DOCS, f)).convert("RGBA"))
        raw = np.load(os.path.join(a.raw, "gump_%s_raw.npy" % g))
        for side in (["left", "right"] if a.side == "both" else [a.side]):
            raw, moved, dmax = cover(raw, body, a.margin, side)
            print("%s %s: the panel moved outwards by up to %d px (the leg stuck out by %.1f px)" % (g, side, moved, dmax))
        raw = smooth_inner_edges(raw)
        lab, n = ndimage.label(raw[..., 3] > 0.5)                              # a bit of the moved tip left on its own (a few pixels) is dropped
        size = ndimage.sum(np.ones(lab.shape), lab, range(1, n + 1))
        for k in np.nonzero(size < 20)[0]:
            raw[lab == k + 1] = 0
        np.save(os.path.join(a.raw, "gump_%s_raw.npy" % g), raw)


if __name__ == "__main__":
    main()
