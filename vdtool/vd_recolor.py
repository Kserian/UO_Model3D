#!/usr/bin/env python3
"""vd_recolor - recolour the red pixels of a .vd item (e.g. the ribbon of a medal); every other pixel stays untouched.

A pixel is "red" when its red channel exceeds both other channels by >= 8 (grey and bluish-grey pixels are never red).
The red pixels are shaded: the darkest and the brightest red found in the file become the two ends of a ramp, and
every red pixel is mapped onto the new ramp by its brightness, so the light/dark structure of the drawing is kept.

Usage:  python vd_recolor.py in.vd out.vd --dark R,G,B --light R,G,B
        --dark / --light : the new colour of the darkest / the brightest red pixels (0-255 each)
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


def red_mask(im):
    a = im[..., 3] > 0
    return a & ((im[..., 0].astype(int) - np.maximum(im[..., 1], im[..., 2]).astype(int)) >= 8)


def lum(rgb):
    rgb = rgb.astype(float)
    return 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]


def parse_rgb(s):
    v = [int(x) for x in s.split(",")]
    if len(v) != 3 or not all(0 <= x <= 255 for x in v):
        raise SystemExit(f"bad colour '{s}', expected R,G,B")
    return np.array(v, float)


def recolor(src, dst, dark, light):
    with tempfile.TemporaryDirectory() as tmp:
        vdtool.cmd_extract(src, tmp)
        meta = json.load(open(os.path.join(tmp, "meta.json")))
        files, ys = [], []
        for blk in meta["blocks"]:
            d = os.path.join(tmp, "frames", f"{blk['action']:02d}_{blk['name']}", f"dir{blk['dir']}")
            for f in blk["frames"]:
                p = os.path.join(d, f["file"])
                im = np.array(Image.open(p).convert("RGBA"))
                m = red_mask(im)
                files.append((p, im, m))
                if m.any():
                    ys.append(lum(im[m][:, :3]))
        allY = np.concatenate(ys)
        y0, y1 = float(allY.min()), float(allY.max())
        changed = 0
        for p, im, m in files:
            if not m.any():
                continue
            t = np.zeros(m.sum()) if y1 == y0 else np.clip((lum(im[m][:, :3]) - y0) / (y1 - y0), 0, 1)
            new = dark[None, :] * (1 - t[:, None]) + light[None, :] * t[:, None]
            im[m, :3] = np.clip(np.round(new), 0, 255).astype(np.uint8)
            Image.fromarray(im).save(p)
            changed += int(m.sum())
        vdtool.cmd_pack(tmp, dst)
    return changed, (y0, y1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--dark", required=True, help="new colour of the darkest red pixels, R,G,B")
    ap.add_argument("--light", required=True, help="new colour of the brightest red pixels, R,G,B")
    a = ap.parse_args()
    n, (y0, y1) = recolor(a.src, a.dst, parse_rgb(a.dark), parse_rgb(a.light))
    print(f"recoloured {n} red pixels (brightness range {y0:.0f}..{y1:.0f}) -> {a.dst}")


if __name__ == "__main__":
    main()
