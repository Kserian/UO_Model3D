"""Original sideburns + our beard: per frame, the pixels of an original facial-hair animation above a jaw line, joined to a rendered beard with a softened seam.

    python uo_hybrid_beard.py ORIG_FRAMES BEARD_FRAMES ZONE_FRAMES OUT_FRAMES [--actions 04_stand,...]

ORIG_FRAMES: folder of `vdtool.py extract` of the original animation (e.g. anim 801: meta.json + frames/); BEARD_FRAMES: the beard rendered by uo_make_item.py / run_render_headless.py
(LAYER = clothing, canvas 256x256, anchor 128,192); ZONE_FRAMES: a wedge above the jaw rendered the same way (rigid on the head: its silhouette is, in every frame, the part of the face above
the jaw line). Frames are laid on the common anchor. Result in OUT_FRAMES (same layout as BEARD_FRAMES: meta.json + frames/ACTION/dirN/NN.png), pack with `vdtool.py pack`.
  sideburn S = original pixels inside the zone;  beard B = rendered pixels, without the zone's silhouette shrunk by `--margin` px (a beard never covers the sideburn);
  seam: dark outline pixels of S or B that sit between the two (opaque neighbours on both sides) take the colour of their light neighbours, a 1-2 px gap between S and B is filled by blending
  the colours above and below, and the tone of B is matched to that of S along the seam.
"""
import argparse, json, os, sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

ap = argparse.ArgumentParser()
ap.add_argument("orig"); ap.add_argument("beard"); ap.add_argument("zone"); ap.add_argument("out")
ap.add_argument("--actions", default="")
ap.add_argument("--margin", type=float, default=0.0)
ap.add_argument("--dark", type=int, default=75)           # luminance below which a pixel counts as an outline pixel
ap.add_argument("--fade", type=float, default=5.0)        # px over which the tone of the beard is matched to the sideburn along the seam
ap.add_argument("--gap", type=int, default=2)
ap.add_argument("--damp", type=float, nargs=2, default=[1.0, 1.0], metavar=("KX", "KY"), help="share of the sway of the beard against the head that is kept (1 = all, 0.5 = half); the sway is the centroid of the beard minus the centroid of the zone, per action and direction, damped towards its mean by whole pixels")
ap.add_argument("--max-shift", type=int, default=2)
ap.add_argument("--align", type=int, default=0, metavar="MAX_PX", help="per frame, the top of the beard is moved onto the top of the original beard (the part of the original below the zone) of the same frame: the original follows the real head, so the beard sits where the original one sat; the offset is median-filtered over 3 frames, at most MAX_PX; 0 = off; replaces --damp")
ap.add_argument("--align-window", type=int, default=3, help="frames of the median filter of the --align offset (1 = none)")
ap.add_argument("--straight", type=float, default=0.0, help="share (0-1) of the sideways drift of the beard along its length that is removed: every row of the beard is moved so that its centre lies over the centre of the top of the beard (a hanging beard is straight; a rigid one leans with the roll of the head); only when the drift stays within --max-bend px")
ap.add_argument("--max-bend", type=int, default=4)
ap.add_argument("--max-light", type=int, default=200, help="no pixel of the rendered beard lighter than this (the original beards peak at 197)")
a = ap.parse_args()


def lum(rgb):
    return rgb[..., :3].astype(float).mean(-1)


def load(root, action, d, i):
    meta = json.load(open(os.path.join(root, "meta.json")))
    blk = next((b for b in meta["blocks"] if b["action"] == action and b["dir"] == d), None)
    if blk is None or i >= len(blk["frames"]):
        return None, meta
    names = sorted(os.listdir(os.path.join(root, "frames")))
    ad = next(n for n in names if n.startswith("%02d_" % action))
    return np.array(Image.open(os.path.join(root, "frames", ad, "dir%d" % d, blk["frames"][i]["file"])).convert("RGBA")), meta


def on_canvas(im, meta, W, H, ax, ay):
    out = np.zeros((H, W, 4), np.uint8)
    if im is None:
        return out
    ox, oy = ax - meta["anchor"][0], ay - meta["anchor"][1]
    h, w = im.shape[:2]
    y0, x0 = max(oy, 0), max(ox, 0); y1, x1 = min(oy + h, H), min(ox + w, W)
    if y1 > y0 and x1 > x0:
        out[y0:y1, x0:x1] = im[y0 - oy:y1 - oy, x0 - ox:x1 - ox]
    return out


def shift(im, dx, dy):
    out = np.zeros_like(im)
    H, W = im.shape[:2]
    ys, xs = slice(max(dy, 0), H + min(dy, 0)), slice(max(dx, 0), W + min(dx, 0))
    yd, xd = slice(max(-dy, 0), H + min(-dy, 0)), slice(max(-dx, 0), W + min(-dx, 0))
    out[ys, xs] = im[yd, xd]
    return out


def top_anchor(m, n=3):
    """(x, y) of the top n rows of a boolean mask: mean column, first row"""
    rows = np.nonzero(m.any(1))[0]
    if len(rows) < 2:
        return None
    return np.array([np.mean([np.nonzero(m[r])[0].mean() for r in rows[:n]]), float(rows[0])])


def median3(vals, win=3):
    out = []
    h = win // 2
    for i in range(len(vals)):
        w = [v for v in vals[max(0, i - h):i + h + 1] if v is not None]
        out.append(np.median(w, 0) if w else None)
    return out


def straighten(B, k, max_bend):
    """rows of the beard shifted sideways so that their centres lie over the centre of its top rows"""
    al = B[..., 3] > 0
    rows = np.nonzero(al.any(1))[0]
    if k <= 0 or len(rows) < 4:
        return B
    cen = {r: np.nonzero(al[r])[0].mean() for r in rows}
    ref = np.mean([cen[r] for r in rows[:3]])
    if max(abs(cen[r] - ref) for r in rows) > max_bend:
        return B
    out = np.zeros_like(B)
    for r in rows:
        dx = int(np.rint(-k * (cen[r] - ref)))
        out[r] = np.roll(B[r], dx, axis=0)
        if dx > 0:
            out[r, :dx] = 0
        elif dx < 0:
            out[r, dx:] = 0
    return out


def merge(O, B, Z):
    """O, B: RGBA on the same canvas, Z: bool zone. Returns RGBA."""
    zone = Z
    if a.margin:
        zone = ndi.binary_erosion(Z, iterations=int(round(a.margin)))
    So = (O[..., 3] > 0) & Z
    Bo = (B[..., 3] > 0)
    out = np.zeros_like(O)
    # tone of the beard matched to the sideburn along the seam
    seam = ndi.binary_dilation(So, iterations=2) & ndi.binary_dilation(Bo, iterations=2)
    Bc = B.astype(float)
    if seam.any() and (So & seam).any() and (Bo & seam).any():
        gain = lum(O)[So & seam].mean() / max(lum(B)[Bo & seam].mean(), 1.0)
        gain = min(max(gain, 0.8), 1.25)
        dist = ndi.distance_transform_edt(~ndi.binary_dilation(So, iterations=1))      # px from the sideburn
        wgt = np.clip(1.0 - dist / a.fade, 0.0, 1.0)
        Bc[..., :3] *= (1.0 + (gain - 1.0) * wgt)[..., None]
    out[Bo] = np.clip(Bc[Bo], 0, a.max_light).astype(np.uint8)
    out[So] = O[So]
    alpha = out[..., 3] > 0
    # 1-2 px gaps between S and B: filled with the mean of the colours above and below
    for _ in range(a.gap):
        empty = ~alpha
        up = np.roll(alpha, 1, 0); dn = np.roll(alpha, -1, 0); lf = np.roll(alpha, 1, 1); rt = np.roll(alpha, -1, 1)
        close = empty & ((up & dn) | (lf & rt))
        close &= ndi.binary_dilation(So, iterations=3) & ndi.binary_dilation(Bo, iterations=3)
        if not close.any():
            break
        col = (np.roll(out, 1, 0).astype(float) * up[..., None] + np.roll(out, -1, 0) * dn[..., None] + np.roll(out, 1, 1) * lf[..., None] + np.roll(out, -1, 1) * rt[..., None])
        n = (up.astype(int) + dn + lf + rt)[..., None]
        out[close] = (col[close] / np.maximum(n[close], 1)).astype(np.uint8); out[close, 3] = 255
        alpha = out[..., 3] > 0
    # outline pixels of the seam: dark, opaque neighbours on both sides in the union, near the boundary of S and B
    L = lum(out)
    nb = lambda m, dy, dx: np.roll(np.roll(m, dy, 0), dx, 1)
    inner = alpha & nb(alpha, 1, 0) & nb(alpha, -1, 0) & nb(alpha, 0, 1) & nb(alpha, 0, -1)
    near = ndi.binary_dilation(So, iterations=2) & ndi.binary_dilation(Bo, iterations=2)
    fix = inner & near & (L < a.dark)
    if fix.any():
        light = alpha & (L >= a.dark)
        acc = np.zeros(out.shape[:2] + (3,)); cnt = np.zeros(out.shape[:2])
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy or dx:
                    m = nb(light, dy, dx); acc += nb(out[..., :3], dy, dx) * m[..., None]; cnt += m
        ok = fix & (cnt > 0)
        out[ok, :3] = (acc[ok] / cnt[ok, None]).astype(np.uint8)
    g = np.rint(out[..., :3].astype(float).mean(-1)).astype(np.uint8)       # exactly grey (R = G = B): the client dyes by the red channel
    out[..., :3] = g[..., None]
    return out


def main():
    mo = json.load(open(os.path.join(a.orig, "meta.json"))); mb = json.load(open(os.path.join(a.beard, "meta.json"))); mz = json.load(open(os.path.join(a.zone, "meta.json")))
    W, H = mb["canvas"]; ax, ay = mb["anchor"]
    sel = [x for x in a.actions.split(",") if x]
    out_meta = json.loads(json.dumps(mb))
    stats = []
    for blk in out_meta["blocks"]:
        name = blk["name"]
        if sel and name not in sel:
            continue
        action, d = blk["action"], blk["dir"]
        frames = []
        for i, fr in enumerate(blk["frames"]):
            B, _ = load(a.beard, action, d, i)
            O, _ = load(a.orig, action, d, i)
            Zim, _ = load(a.zone, action, d, i)
            frames.append((fr, on_canvas(O, mo, W, H, ax, ay), on_canvas(B, mb, W, H, ax, ay), on_canvas(Zim, mz, W, H, ax, ay)[..., 3] > 0))
        # sway of the beard against the head: damped towards its mean by whole pixels
        rel = []
        for fr, Oc, Bc, Zc in frames:
            ys, xs = np.nonzero(Bc[..., 3] > 0); zy, zx = np.nonzero(Zc)
            rel.append(np.array([xs.mean() - zx.mean(), ys.mean() - zy.mean()]) if len(xs) and len(zx) else None)
        ok = [r for r in rel if r is not None]
        mean = np.mean(ok, 0) if ok else None
        k = np.array(a.damp)
        if a.align:                                              # the top of the beard onto the top of the original beard of the same frame
            diffs = []
            for fr, Oc, Bc, Zc in frames:
                ao = top_anchor((Oc[..., 3] > 0) & ~Zc); ab = top_anchor(Bc[..., 3] > 0)
                diffs.append(ao - ab if ao is not None and ab is not None else None)
            sm = median3(diffs, a.align_window)
            known = [x for x in sm if x is not None]
            fill = np.median(known, 0) if known else np.zeros(2)
            aligned = []
            for (fr, Oc, Bc, Zc), dv in zip(frames, sm):
                dv = fill if dv is None else dv
                dv = np.clip(np.rint(dv), -a.align, a.align).astype(int)
                aligned.append((fr, Oc, shift(Bc, int(dv[0]), int(dv[1])) if (Bc[..., 3] > 0).any() else Bc, Zc))
            frames = aligned
            rel = []
            for fr, Oc, Bc, Zc in frames:
                ys, xs = np.nonzero(Bc[..., 3] > 0); zy, zx = np.nonzero(Zc)
                rel.append(np.array([xs.mean() - zx.mean(), ys.mean() - zy.mean()]) if len(xs) and len(zx) else None)
            ok = [r for r in rel if r is not None]
            mean = np.mean(ok, 0) if ok else None
        shifted = []
        for (fr, Oc, Bc, Zc), r in zip(frames, rel):
            if r is not None and len(ok) > 2 and (k < 1).any():
                sh = np.clip(np.rint(-(1.0 - k) * (r - mean)), -a.max_shift, a.max_shift).astype(int)
                Bc = shift(Bc, sh[0], sh[1])
            shifted.append(straighten(Bc, a.straight, a.max_bend))
        if len(ok) > 2:
            after = [np.array([np.nonzero(Bc[..., 3] > 0)[1].mean() - np.nonzero(Zc)[1].mean(), np.nonzero(Bc[..., 3] > 0)[0].mean() - np.nonzero(Zc)[0].mean()]) for (fr, Oc, _, Zc), Bc in zip(frames, shifted) if (Bc[..., 3] > 0).any() and Zc.any()]
            stats.append((np.std(ok, 0), np.std(after, 0)))
        for (fr, Oc, _, Zc), Bc in zip(frames, shifted):
            res = merge(Oc, Bc, Zc)
            p = os.path.join(a.out, "frames", "%s" % name, "dir%d" % d); os.makedirs(p, exist_ok=True)
            Image.fromarray(res).save(os.path.join(p, fr["file"]))
    if stats:
        b4 = np.mean([s_[0] for s_ in stats], 0); af = np.mean([s_[1] for s_ in stats], 0)
        print("sway of the beard against the head (std over the frames of a block, px, mean over the blocks): x %.2f -> %.2f, y %.2f -> %.2f" % (b4[0], af[0], b4[1], af[1]))
    json.dump(out_meta, open(os.path.join(a.out, "meta.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
