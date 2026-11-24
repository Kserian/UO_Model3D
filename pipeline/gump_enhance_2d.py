#!/usr/bin/env python3
"""gump_enhance_2d - 2D clean-up of a paperdoll body gump (260 x 237, e.g. 0xC male, 0xD female): more form and detail, same silhouette.

    python gump_enhance_2d.py in.png out.png [--hires out_x4.png] [--detail 1.35] [--clarity 0.75] [--micro 2.2]

The silhouette (alpha) is NOT changed (items made on the original body keep fitting) and neither are the hues: only the brightness of each
pixel is processed.  Steps, all on the brightness at 4 x resolution inside the exact silhouette (no halo from the transparent border):
detail boost (unsharp mask at 0.55 px), "clarity" (the difference between 0.55 px and 2.2 px blur gives muscle and fold definition),
a mild S-curve, then the mean brightness of the skin is restored to that of the original.  --hires also writes the 4 x image with a fine
skin micro-texture (invisible at 1 x, hence not part of the game file).  Garment pixels (coloured) get no micro-texture.
Requires: numpy, pillow.
"""
import argparse
import numpy as np
from PIL import Image


def blur(a, s):
    """gaussian blur (FFT, reflected borders) of a float image."""
    a = np.asarray(a, np.float32)
    pad = int(4 * s) + 2
    p = np.pad(a, pad, mode='reflect')
    fy = np.fft.fftfreq(p.shape[0])[:, None]
    fx = np.fft.rfftfreq(p.shape[1])[None, :]
    g = np.exp(-2 * (np.pi * s) ** 2 * (fx ** 2 + fy ** 2)).astype(np.float32)
    return np.fft.irfft2(np.fft.rfft2(p) * g, s=p.shape).astype(np.float32)[pad:-pad, pad:-pad]


def nblur(a, m, s):
    return blur(a * m, s) / np.maximum(blur(m.astype(np.float32), s), 1e-4)


def floor15(rgb):
    """a 15-bit colour of 0 is transparent in the client: a pixel that would quantise to black becomes (8, 8, 8)."""
    rgb = rgb.copy()
    dead = rgb.max(-1) < 8
    rgb[dead] = 8
    return rgb.astype(np.uint8)


def enhance(src, K=4, detail=1.35, clarity=0.75, micro=2.2, seed=1):
    a = np.asarray(Image.open(src).convert('RGBA')).astype(np.float32)
    H, W = a.shape[:2]
    al = a[..., 3] > 0
    rgb = a[..., :3]
    lum = rgb.mean(-1)
    chroma = rgb - lum[..., None]
    garment = (rgb.max(-1) - rgb.min(-1)) > 12
    up = lambda x: np.asarray(Image.fromarray(x.astype(np.float32), mode='F').resize((W * K, H * K), Image.BICUBIC))
    nn = lambda x: np.asarray(Image.fromarray((x * 255).astype(np.uint8)).resize((W * K, H * K), Image.NEAREST)) > 0
    mk, gm = nn(al), nn(garment)
    alf = al.astype(np.float32)
    L = up(lum * alf) / np.maximum(up(alf), 1e-3)                          # interpolate inside the silhouette only (no halo)
    L = np.where(up(alf) > 0.02, L, 0)
    m = mk.astype(np.float32)
    base, mid = nblur(L, m, K * 0.55), nblur(L, m, K * 2.2)
    out = base + detail * (L - base) + clarity * (base - mid)
    t = np.clip(out / 255.0, 0, 1)
    out = (t + 0.18 * (t - 0.5) * (1 - np.abs(2 * t - 1))) * 255
    hires = out.copy()
    rng = np.random.default_rng(seed)
    n = sum(blur(rng.standard_normal(L.shape).astype(np.float32), K * s) * (s ** 0.5 * K * 0.6) for s in (0.25, 0.5, 1.0)) / 3
    hires = np.clip(hires + micro * n * np.clip(L / 200.0, 0.2, 1.0) * (mk & ~gm), 0, 255)
    # back to 1 x: area average inside the exact silhouette
    def down(x):
        return (x * m).reshape(H, K, W, K).sum((1, 3)) / np.maximum(m.reshape(H, K, W, K).sum((1, 3)), 1)
    lo = np.where(al, down(out), 0)
    sk = al & ~garment
    lo = lo + np.where(al, (lum[sk].mean() - lo[sk].mean()), 0)             # keep the mean brightness of the skin
    pa = np.pad(al, 1)
    ring = al & ~(pa[:-2, 1:-1] & pa[2:, 1:-1] & pa[1:-1, :-2] & pa[1:-1, 2:])   # the 1 px outline of the silhouette
    lo = np.where(ring, np.maximum(lo, 0.9 * lum), lo)                      # sharpening must not make it heavier than the original
    res = np.zeros((H, W, 4), np.uint8)
    res[..., :3] = floor15(np.clip(np.round(lo[..., None] + chroma), 0, 255))
    res[..., 3] = np.where(al, 255, 0)
    res[~al, :3] = 0
    hi = np.zeros((H * K, W * K, 4), np.uint8)
    hl = hires + (lum[sk].mean() - down(hires)[sk].mean())
    ringK = nn(ring)
    lumK = np.asarray(Image.fromarray(lum.astype(np.float32), mode='F').resize((W * K, H * K), Image.NEAREST))
    hl = np.where(ringK, np.maximum(hl, 0.9 * lumK), hl)
    gch = np.asarray(Image.fromarray(np.clip(chroma + 128, 0, 255).astype(np.uint8)).resize((W * K, H * K), Image.NEAREST)).astype(np.float32) - 128
    hi[..., :3] = floor15(np.clip(np.round(hl[..., None] + gch), 0, 255))
    hi[..., 3] = np.where(mk, 255, 0)
    hi[~mk, :3] = 0
    return res, hi


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('src'); ap.add_argument('dst')
    ap.add_argument('--hires'); ap.add_argument('--detail', type=float, default=1.35)
    ap.add_argument('--clarity', type=float, default=0.75); ap.add_argument('--micro', type=float, default=2.2)
    o = ap.parse_args()
    lo, hi = enhance(o.src, detail=o.detail, clarity=o.clarity, micro=o.micro)
    Image.fromarray(lo).save(o.dst)
    if o.hires:
        Image.fromarray(hi).save(o.hires)
