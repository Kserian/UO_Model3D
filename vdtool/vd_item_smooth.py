#!/usr/bin/env python3
"""vd_item_smooth - temporal clean-up of a hanging neck item (medal on a ribbon) in a .vd file.

The ribbon lies on the body and stays exactly where it is (it must keep fitting the original body).
Only the free-hanging pendant (every non-red pixel of the item) is touched:

  1. isolated 1-2 px specks are removed,
  2. 1-frame gaps (and 2-frame gaps between similar sizes) of the pendant are filled from the neighbours,
  3. the pendant becomes one rigid sprite (the most typical real frame, so its shape and brightness no longer flicker) placed on a smooth trajectory: position in canvas coordinates (the body is fixed there),
     low-passed in time (2 Fourier harmonics for walk/run loops, binomial filter otherwise). A frame keeps its original
     place if the move would put the pendant further from the ribbon than it was, cover more ribbon, or push it off the body.

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


def flicker(frames, cyclic):
    """mean frame-to-frame change of the pendant: pixel count (px) and brightness (0-255), over visible neighbours."""
    st = []
    for im in frames:
        m = (~red_mask(im)) & (im[..., 3] > 0)
        st.append((int(m.sum()), float(im[m][:, :3].mean()) if m.sum() >= MIN_PENDANT_PX else None))
    n = len(st)
    dc, dl = [], []
    for i in range(0 if cyclic else 1, n):
        a, b = st[i - 1], st[i]
        if a[1] is not None and b[1] is not None:
            dc.append(abs(a[0] - b[0]))
            dl.append(abs(a[1] - b[1]))
    return (float(np.mean(dc)) if dc else 0.0, float(np.mean(dl)) if dl else 0.0)


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


def fourier_lowpass(arr, keep):
    """keep the first `keep` harmonics of a closed loop of (n,2) samples."""
    f = np.fft.rfft(arr, axis=0)
    f[keep + 1:] = 0
    return np.fft.irfft(f, n=len(arr), axis=0)


def consensus(pend, frames, idxs):
    """the most typical real pendant sprite among the frames (size closest to the median): (rgba, centroid)."""
    cnts = [int(pend[i].sum()) for i in idxs]
    med = float(np.median(cnts))
    best = min(idxs, key=lambda i: (abs(int(pend[i].sum()) - med), -int(pend[i].sum())))
    ys, xs = np.nonzero(pend[best])
    y0, x0 = ys.min(), xs.min()
    rgba = np.zeros((ys.max() - y0 + 1, xs.max() - x0 + 1, 4), np.uint8)
    rgba[ys - y0, xs - x0] = frames[best][ys, xs]
    return rgba, np.array([xs.mean() - x0, ys.mean() - y0])


def stamp(mask, template, tc, pos):
    """set mask where the template lands when its centroid is at pos; False if it leaves the canvas."""
    ys, xs = np.nonzero(template[..., 3] > 0)
    oy, ox = int(round(pos[1] - tc[1])), int(round(pos[0] - tc[0]))
    ny, nx = ys + oy, xs + ox
    if ((ny < 0) | (ny >= mask.shape[0]) | (nx < 0) | (nx >= mask.shape[1])).any():
        return False
    mask[ny, nx] = True
    return True


def stamp_rgba(im, template, tc, pos):
    ys, xs = np.nonzero(template[..., 3] > 0)
    oy, ox = int(round(pos[1] - tc[1])), int(round(pos[0] - tc[0]))
    im[ys + oy, xs + ox] = template[ys, xs]


def gap_to(mask, ribbon):
    """smallest Chebyshev distance between the pendant and the ribbon (0 = overlap); large if there is no ribbon."""
    ys, xs = np.nonzero(mask)
    rys, rxs = np.nonzero(ribbon)
    if len(ys) == 0 or len(rys) == 0:
        return 99
    return int(np.min(np.maximum(np.abs(ys[:, None] - rys[None, :]), np.abs(xs[:, None] - rxs[None, :]))))


def body_cover(mask, body):
    return float(body[mask].mean()) if mask.any() else 0.0


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
    log["flicker_before"] = flicker(frames, cyclic)

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

    # --- 3. rigid pendant on a smooth trajectory ----------------------------------------------------------------
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
    if cyclic and len(runs) == 1 and len(runs[0]) == n:
        runs[0] = list(range(n))
    placed = {}
    for run in runs:
        med = float(np.median([cnt[i] for i in run]))
        limit = 0.3 if cyclic else 0.5                          # below this the pendant is hidden by an arm / the torso
        good = [cnt[i] >= limit * med for i in run]
        sub, cur = [], []
        for i, g in zip(run, good):
            if g:
                cur.append(i)
            elif cur:
                sub.append(cur)
                cur = []
        if cur:
            sub.append(cur)
        if cyclic and len(sub) > 1 and sub[0][0] == run[0] and sub[-1][-1] == run[-1] and good[0] and good[-1] \
                and (run[0] - run[-1]) % n == 1:
            sub[0] = sub.pop() + sub[0]
        gframes = [i for s in sub for i in s]
        if len(gframes) < 3:
            continue
        template, tc = consensus(pend, frames, gframes)
        for s in sub:
            if len(s) < 3:
                continue
            full_cycle = cyclic and len(s) == n
            arr = np.array([off[i] for i in s])
            sm = fourier_lowpass(arr, 2) if full_cycle else lowpass(arr, False, max(strength, 3))
            for k, i in enumerate(s):
                placed[i] = (template, tc, arr[k] + np.clip(sm[k] - arr[k], -max_shift, max_shift) + heads[i], arr[k] + heads[i])
    applied = {}
    for i, (template, tc, target, orig) in placed.items():
        rib = red_mask(frames[i])
        gap0 = gap_to(pend[i], rib)
        cover0 = body_cover(pend[i], bodies[i])
        pos = None
        for f in (1.0, 0.67, 0.33, 0.0):                         # back off towards the original place
            cand = orig + (target - orig) * f
            new = np.zeros_like(pend[i])
            if not stamp(new, template, tc, cand):
                continue
            ok = (body_cover(new, bodies[i]) >= min(0.9, cover0)
                  and gap_to(new, rib) <= max(gap0, 1)
                  and int((new & rib).sum()) <= int((pend[i] & rib).sum()) + 1)
            if ok:
                pos = cand
                break
        if pos is None:                                          # the template at the original place (always allowed)
            pos = orig
            new = np.zeros_like(pend[i])
            if not stamp(new, template, tc, pos):
                continue
        frames[i][pend[i]] = 0
        stamp_rgba(frames[i], template, tc, pos)
        applied[i] = tuple(np.round(pos - orig, 1))
    shifts = applied
    pend = [(~red_mask(im)) & (im[..., 3] > 0) for im in frames]
    new_off = [centroid(p) - heads[i] if p.sum() >= MIN_PENDANT_PX else None for i, p in enumerate(pend)]
    log["d2_after"] = d2_stat(new_off, cyclic)
    log["flicker_after"] = flicker(frames, cyclic)
    log["shifted"] = {int(i): list(map(int, s)) for i, s in shifts.items() if s != (0, 0)}
    return frames


def parse_only(spec):
    """'0-3:1,17:1,26:1' -> {(action, dir), ...}; 'A:D1+D2' selects several directions of one action."""
    out = set()
    for part in spec.split(","):
        acts, dirs = part.split(":")
        a0, _, a1 = acts.partition("-")
        for a in range(int(a0), int(a1 or a0) + 1):
            for d in dirs.split("+"):
                out.add((a, int(d)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--body", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "client", "body_0x190_frames"))
    ap.add_argument("--strength", type=int, default=2, help="low-pass passes (1 = light, 2 = default, 3 = strong)")
    ap.add_argument("--max-shift", type=int, default=3)
    ap.add_argument("--only", help="process only these blocks, e.g. 0-3:1,17:1,26:1 (action[-action]:dir[+dir]); all others stay byte-identical")
    ap.add_argument("--report")
    a = ap.parse_args()
    bmeta = json.load(open(os.path.join(a.body, "meta.json")))
    banchor = bmeta["anchor"]
    with tempfile.TemporaryDirectory() as tmp:
        vdtool.cmd_extract(a.src, tmp)
        meta = json.load(open(os.path.join(tmp, "meta.json")))
        report = {}
        only = parse_only(a.only) if a.only else None
        for blk in meta["blocks"]:
            A, D, name = blk["action"], blk["dir"], blk["name"]
            if only is not None and (A, D) not in only:
                continue
            d = os.path.join(tmp, "frames", f"{A:02d}_{name}", f"dir{D}")
            frames = [np.array(Image.open(os.path.join(d, f["file"])).convert("RGBA")) for f in blk["frames"]]
            heads = [np.zeros(2) for _ in blk["frames"]]          # trajectories are smoothed in canvas coordinates
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
    if b:
        print("mean 2nd difference of pendant position: %.2f px -> %.2f px (%d blocks)"
              % (np.mean([x[0] for x in b]), np.mean([x[1] for x in b]), len(b)))
    fb = np.mean([v["flicker_before"] for v in report.values()], axis=0)
    fa = np.mean([v["flicker_after"] for v in report.values()], axis=0)
    print("frame-to-frame change of pendant size / brightness: %.1f px, %.1f -> %.1f px, %.1f" % (fb[0], fb[1], fa[0], fa[1]))
    print("pendant frames filled:", sum(len(v["filled"]) for v in report.values()),
          "| shifted:", sum(len(v["shifted"]) for v in report.values()),
          "| specks removed:", sum(v["specks"] for v in report.values()))


if __name__ == "__main__":
    main()
