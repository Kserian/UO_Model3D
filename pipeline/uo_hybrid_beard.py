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
    for blk in out_meta["blocks"]:
        name = blk["name"]
        if sel and name not in sel:
            continue
        action, d = blk["action"], blk["dir"]
        for i, fr in enumerate(blk["frames"]):
            B, _ = load(a.beard, action, d, i)
            O, _ = load(a.orig, action, d, i)
            Zim, _ = load(a.zone, action, d, i)
            Bc = on_canvas(B, mb, W, H, ax, ay); Oc = on_canvas(O, mo, W, H, ax, ay); Zc = on_canvas(Zim, mz, W, H, ax, ay)[..., 3] > 0
            res = merge(Oc, Bc, Zc)
            p = os.path.join(a.out, "frames", "%s" % name, "dir%d" % d); os.makedirs(p, exist_ok=True)
            Image.fromarray(res).save(os.path.join(p, fr["file"]))
    json.dump(out_meta, open(os.path.join(a.out, "meta.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
