#!/usr/bin/env python3
"""vd_item_smooth - temporal clean-up of a hanging neck item (medal on a ribbon) in a .vd file.

The ribbon lies on the body and stays exactly where it is (it must keep fitting the original body).
Only the free-hanging pendant (every non-red pixel of the item) is touched:

  1. isolated 1-2 px specks are removed,
  2. 1-frame gaps (and 2-frame gaps between similar sizes) of the pendant are filled from the neighbours,
  3. the pendant position, measured relative to the original body's head top, is low-pass filtered in time
     (binomial 5-tap, cyclic for walk/run loops) and the pendant pixels are shifted by whole pixels.

Usage:  python vd_item_smooth.py in.vd out.vd [--body client/body_0x190_frames] [--strength 2] [--max-shift 3]
        [--report report.json]
Requires: numpy, pillow.  Works on a copy; the input file is never modified.
"""
import argparse
import json
import os
import sys
import tempfile

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vdtool  # noqa: E402

CYCLIC_ACTIONS = {0, 1, 2, 3, 15, 23, 24}      # walk / run / advance loops: last frame leads into the first
MIN_PENDANT_PX = 3


def red_mask(im):
    a = im[..., 3] > 0
    return a & (im[..., 0].astype(int) > im[..., 1].astype(int) + 50)


def components(mask):
    h, w = mask.shape
    seen = np.zeros_like(mask)
    out = []
    for y in range(h):
        for x in range(w):
            if mask[y, x] and not seen[y, x]:
                st, pts = [(y, x)], []
                seen[y, x] = True
                while st:
                    cy, cx = st.pop()
                    pts.append((cy, cx))
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = cy + dy, cx + dx
                            if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                                seen[ny, nx] = True
                                st.append((ny, nx))
                out.append(pts)
    return out


def despeckle(im, log):
    a = im[..., 3] > 0
    removed = 0
    for pts in components(a):
        if len(pts) <= 2:
            for y, x in pts:
                im[y, x] = 0
            removed += len(pts)
    log["specks"] = log.get("specks", 0) + removed
    return removed


def centroid(mask):
    ys, xs = np.nonzero(mask)
    return np.array([xs.mean(), ys.mean()]) if len(xs) else None


def head_top(body_png, body_anchor):
    a = np.array(Image.open(body_png).convert("RGBA"))[..., 3] > 0
    ys, xs = np.nonzero(a)
    return np.array([xs[ys == ys.min()].mean() - body_anchor[0], ys.min() - body_anchor[1]])


def d2_stat(series, cyclic):
    """max / mean second difference (px) of a list of 2-vectors (None = hidden)."""
    n = len(series)
    vals = []
    for i in range(0 if cyclic else 1, n if cyclic else n - 1):
        p, c, q = series[(i - 1) % n], series[i], series[(i + 1) % n]
        if p is not None and c is not None and q is not None:
            vals.append(float(np.hypot(*(p - 2 * c + q))))
    return (max(vals), float(np.mean(vals))) if vals else (0.0, 0.0)


def lowpass(run, cyclic_full, strength):
    """binomial [1,2,1]/4 repeated `strength` times; run = (k,2) array."""
    x = run.astype(float)
    for _ in range(strength):
        if cyclic_full:
            x = (np.roll(x, 1, 0) + 2 * x + np.roll(x, -1, 0)) / 4
        else:
            p = np.vstack([x[:1], x, x[-1:]])
            x = (p[:-2] + 2 * p[1:-1] + p[2:]) / 4
    return x


def body_mask_in_item_canvas(body_png, body_anchor, item_anchor, shape):
    """body silhouette resampled into the item canvas (both anchored at the body origin)."""
    b = np.array(Image.open(body_png).convert("RGBA"))[..., 3] > 0
    out = np.zeros(shape, bool)
    ox, oy = body_anchor[0] - item_anchor[0], body_anchor[1] - item_anchor[1]     # item (x,y) -> body (x+ox, y+oy)
    ys, xs = np.mgrid[0:shape[0], 0:shape[1]]
    bx, by = xs + ox, ys + oy
    ok = (bx >= 0) & (bx < b.shape[1]) & (by >= 0) & (by < b.shape[0])
    out[ok] = b[by[ok], bx[ok]]
    return out


def placement_ok(pend, ribbon, body, dx, dy, touch_required):
    """pendant moved by (dx, dy) stays on the body (>= 90 % of pixels) and keeps touching the ribbon."""
    h, w = pend.shape
    ys, xs = np.nonzero(pend)
    ny, nx = ys + dy, xs + dx
    if ((ny < 0) | (ny >= h) | (nx < 0) | (nx >= w)).any():
        return False
    if body[ny, nx].mean() < 0.9:
        return False
    if touch_required:
        rys, rxs = np.nonzero(ribbon)
        if len(rys) == 0:
            return False
        dmin = np.min(np.maximum(np.abs(ny[:, None] - rys[None, :]), np.abs(nx[:, None] - rxs[None, :])))
        if dmin > 1:
            return False
    return True


def touches(pend, ribbon):
    ys, xs = np.nonzero(pend)
    rys, rxs = np.nonzero(ribbon)
    if len(ys) == 0 or len(rys) == 0:
        return False
    return np.min(np.maximum(np.abs(ys[:, None] - rys[None, :]), np.abs(xs[:, None] - rxs[None, :]))) <= 1


def shift_pendant(im, pendant, dx, dy):
    """move the pendant pixels of im by (dx, dy); they are drawn over the ribbon."""
    h, w = pendant.shape
    ys, xs = np.nonzero(pendant)
    px = im[ys, xs].copy()
    im[ys, xs] = 0
    ny, nx = ys + dy, xs + dx
    ok = (ny >= 0) & (ny < h) & (nx >= 0) & (nx < w)
    im[ny[ok], nx[ok]] = px[ok]


def process_block(frames, heads, bodies, cyclic, strength, max_shift, log):
    n = len(frames)
    for im in frames:
        despeckle(im, log)
    pend = [(~red_mask(im)) & (im[..., 3] > 0) for im in frames]
    cnt = [int(p.sum()) for p in pend]
    vis = [c >= MIN_PENDANT_PX for c in cnt]
    off = [centroid(p) - heads[i] if vis[i] else None for i, p in enumerate(pend)]
    log["d2_before"] = d2_stat(off, cyclic)

    # --- 2. fill short gaps -------------------------------------------------------------------------------------
    filled = []
    i = 0
    idx = list(range(n))
    while i < n:
        if vis[i]:
            i += 1
            continue
        j = i
        while j < n and not vis[j]:
            j += 1
        gap = list(range(i, j))
        a, b = i - 1, j % n if cyclic else j
        if (a >= 0 or cyclic) and (b < n) and len(gap) < n - 1:
            a %= n
            if vis[a] and vis[b] and a != b:
                ca, cb = cnt[a], cnt[b]
                similar = max(ca, cb) <= 1.4 * min(ca, cb)
                if len(gap) == 1 or (len(gap) == 2 and similar):
                    src = a if ca <= cb else b                 # the smaller sprite is the conservative choice
                    for k, g in enumerate(gap):
                        t = (k + 1) / (len(gap) + 1)
                        target = off[a] * (1 - t) + off[b] * t + heads[g]
                        sp = pend[src]
                        ys, xs = np.nonzero(sp)
                        c0 = np.array([xs.mean(), ys.mean()])
                        dx0, dy0 = int(round(target[0] - c0[0])), int(round(target[1] - c0[1]))
                        rib_g = red_mask(frames[g])
                        best = None
                        for ddx, ddy in sorted(((u, v) for u in range(-2, 3) for v in range(-2, 3)), key=lambda s: abs(s[0]) + abs(s[1])):
                            hangs = np.nonzero(rib_g)[0].size > 0 and ys.mean() + dy0 + ddy >= np.nonzero(rib_g)[0].max() - 1
                            if hangs and placement_ok(sp, rib_g, bodies[g], dx0 + ddx, dy0 + ddy, True):
                                best = (dx0 + ddx, dy0 + ddy)
                                break
                        if best is None:
                            continue
                        dx, dy = best
                        h, w = sp.shape
                        ny, nx = ys + dy, xs + dx
                        ok = (ny >= 0) & (ny < h) & (nx >= 0) & (nx < w)
                        frames[g][ny[ok], nx[ok]] = frames[src][ys[ok], xs[ok]]
                        filled.append(g)
        i = j
    log["filled"] = filled
    if filled:
        pend = [(~red_mask(im)) & (im[..., 3] > 0) for im in frames]
        cnt = [int(p.sum()) for p in pend]
        vis = [c >= MIN_PENDANT_PX for c in cnt]
        off = [centroid(p) - heads[i] if vis[i] else None for i, p in enumerate(pend)]

    # --- 3. smooth position over each visible run ---------------------------------------------------------------
    runs, cur = [], []
    for i in range(n):
        if vis[i]:
            cur.append(i)
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    if cyclic and len(runs) > 1 and runs[0][0] == 0 and runs[-1][-1] == n - 1:
        runs[0] = runs.pop() + runs[0]                          # a run that wraps around the loop
    shifts = {}
    for run in runs:
        if len(run) < 3:
            continue
        full_cycle = cyclic and len(run) == n
        arr = np.array([off[i] for i in run])
        sm = lowpass(arr, full_cycle, strength)
        d = np.clip(np.round(sm - arr), -max_shift, max_shift)
        # accept the run only if it really gets smoother (second difference inside the run)
        before = d2_stat(list(arr), full_cycle)[1] if len(arr) >= 3 else 0
        after = d2_stat(list(arr + d), full_cycle)[1]
        if after >= before:
            continue
        for k, i in enumerate(run):
            shifts[i] = (int(d[k][0]), int(d[k][1]))
    applied = {}
    for i, (dx, dy) in shifts.items():
        rib = red_mask(frames[i])
        need_touch = touches(pend[i], rib)
        for f in (1.0, 0.67, 0.33, 0.0):                         # back off until the constraints hold
            sx, sy = int(round(dx * f)), int(round(dy * f))
            if (sx == 0 and sy == 0) or placement_ok(pend[i], rib, bodies[i], sx, sy, need_touch):
                break
        if sx or sy:
            shift_pendant(frames[i], pend[i], sx, sy)
            applied[i] = (sx, sy)
    shifts = applied
    pend = [(~red_mask(im)) & (im[..., 3] > 0) for im in frames]
    new_off = [centroid(p) - heads[i] if p.sum() >= MIN_PENDANT_PX else None for i, p in enumerate(pend)]
    log["d2_after"] = d2_stat(new_off, cyclic)
    log["shifted"] = {int(i): list(map(int, s)) for i, s in shifts.items() if s != (0, 0)}
    return frames


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--body", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "client", "body_0x190_frames"))
    ap.add_argument("--strength", type=int, default=2, help="low-pass passes (1 = light, 2 = default, 3 = strong)")
    ap.add_argument("--max-shift", type=int, default=3)
    ap.add_argument("--report")
    a = ap.parse_args()
    bmeta = json.load(open(os.path.join(a.body, "meta.json")))
    banchor = bmeta["anchor"]
    with tempfile.TemporaryDirectory() as tmp:
        vdtool.cmd_extract(a.src, tmp)
        meta = json.load(open(os.path.join(tmp, "meta.json")))
        report = {}
        for blk in meta["blocks"]:
            A, D, name = blk["action"], blk["dir"], blk["name"]
            d = os.path.join(tmp, "frames", f"{A:02d}_{name}", f"dir{D}")
            frames = [np.array(Image.open(os.path.join(d, f["file"])).convert("RGBA")) for f in blk["frames"]]
            heads = [head_top(os.path.join(a.body, "frames", f"{A:02d}_{name}", f"dir{D}", f["file"]), banchor)
                     + np.array(meta["anchor"]) for f in blk["frames"]]
            # item frames and body frames have different canvases; offsets are taken in item-canvas pixels
            bodies = [body_mask_in_item_canvas(os.path.join(a.body, "frames", f"{A:02d}_{name}", f"dir{D}", f["file"]),
                                               banchor, meta["anchor"], frames[0].shape[:2]) for f in blk["frames"]]
            log = {}
            out = process_block(frames, heads, bodies, A in CYCLIC_ACTIONS, a.strength, a.max_shift, log)
            for im, f in zip(out, blk["frames"]):
                Image.fromarray(im).save(os.path.join(d, f["file"]))
            report[f"{A}_{D}_{name}"] = log
        vdtool.cmd_pack(tmp, a.dst)
    if a.report:
        json.dump(report, open(a.report, "w"), indent=1, default=float)
    b = [(v["d2_before"][1], v["d2_after"][1]) for v in report.values() if v["d2_before"][1] > 0]
    print("mean 2nd difference of pendant position vs head: %.2f px -> %.2f px (%d blocks)"
          % (np.mean([x[0] for x in b]), np.mean([x[1] for x in b]), len(b)))
    print("pendant frames filled:", sum(len(v["filled"]) for v in report.values()),
          "| shifted:", sum(len(v["shifted"]) for v in report.values()),
          "| specks removed:", sum(v["specks"] for v in report.values()))


if __name__ == "__main__":
    main()
