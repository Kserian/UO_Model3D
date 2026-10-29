"""Recolour a .vd (and gump / art PNGs) without rendering: the hue of the reddish colours is turned to another hue, the rest (the grey sash, the cream head, black) stays.

    python recolor_vd.py IN.vd OUT.vd [--to-hue 215] [--from-hue 0] [--range 28] [--min-sat 0.30]
    python recolor_vd.py IN.png OUT.png [...]            # the same for a PNG (gump, art)

A .vd frame stores indices into the palette of its block (256 colours, 15 bit, the first 512 bytes of every block of an action and direction): only the palette entries are rewritten, the pixels
and the sizes stay, so the file keeps its layout and every frame of every action is recoloured at once. A colour is recoloured when its hue lies within +-RANGE degrees of FROM_HUE and its
saturation is at least MIN_SAT (or, for the DARK outline of the red parts: hue within +-DARK_RANGE, saturation >= DARK_SAT, value < DARK_VAL: after the darkening of the rim the saturation of a dark red falls to 0.12-0.25 and the old threshold left it red); hue goes to TO_HUE, saturation and the luminance (0.299 R + 0.587 G + 0.114 B) are kept (a blue of the same value is much darker than a red). 15-bit 0 is transparent: a result of 0 becomes 1.
"""
import argparse, colorsys, struct, sys
import numpy as np


def make_map(to_hue, from_hue, rng, min_sat, dark_rng=18.0, dark_sat=0.08, dark_val=0.5):
    def f(rgb):
        r, g, b = [c / 255.0 for c in rgb]
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        d = abs(((h * 360.0 - from_hue) + 180.0) % 360.0 - 180.0)
        dark = d <= dark_rng and s >= dark_sat and v < dark_val              # the dark outline of the red parts: low saturation after the darkening, still the same hue
        if not dark and (s < min_sat or d > rng):
            return rgb
        lum = 0.299 * r + 0.587 * g + 0.114 * b
        r2, g2, b2 = colorsys.hsv_to_rgb(to_hue / 360.0, s, v)
        l2 = 0.299 * r2 + 0.587 * g2 + 0.114 * b2
        k = lum / max(l2, 1e-6)
        return tuple(int(round(min(1.0, c * k) * 255)) for c in (r2, g2, b2))
    return f


def recolor_vd(src, dst, f):
    d = bytearray(open(src, "rb").read())
    ft, at = struct.unpack_from("<hh", d, 0)
    n = {0: 22, 1: 13, 2: 35}[at] * 5
    done = set(); changed = 0
    for i in range(n):
        off, ln, ex = struct.unpack_from("<iii", d, 4 + 12 * i)
        if off <= 0 or ln <= 0 or off in done:
            continue
        done.add(off)
        for k in range(256):
            c = struct.unpack_from("<H", d, off + 2 * k)[0]
            if c == 0:
                continue
            rgb = (((c >> 10) & 31) * 255 // 31, ((c >> 5) & 31) * 255 // 31, (c & 31) * 255 // 31)
            n2 = f(rgb)
            if n2 != rgb:
                c2 = ((n2[0] * 31 + 127) // 255 << 10) | ((n2[1] * 31 + 127) // 255 << 5) | ((n2[2] * 31 + 127) // 255)
                struct.pack_into("<H", d, off + 2 * k, c2 if c2 else 1); changed += 1
    open(dst, "wb").write(bytes(d))
    return len(done), changed


def recolor_png(src, dst, f):
    from PIL import Image
    a = np.array(Image.open(src).convert("RGBA")); m = a[..., 3] > 0
    cols = np.unique(a[m][:, :3], axis=0); lut = {tuple(c): f(tuple(int(x) for x in c)) for c in cols}
    for c, n2 in lut.items():
        if n2 != c:
            sel = m & (a[..., :3] == np.array(c)).all(-1); a[sel, :3] = n2
    Image.fromarray(a).save(dst)
    return len(cols), sum(1 for c, n2 in lut.items() if n2 != c)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--to-hue", type=float, default=215.0); ap.add_argument("--from-hue", type=float, default=0.0)
    ap.add_argument("--range", type=float, default=28.0); ap.add_argument("--min-sat", type=float, default=0.30)
    ap.add_argument("--dark-range", type=float, default=18.0); ap.add_argument("--dark-sat", type=float, default=0.08); ap.add_argument("--dark-val", type=float, default=0.5)
    a = ap.parse_args()
    f = make_map(a.to_hue, a.from_hue, a.range, a.min_sat, a.dark_range, a.dark_sat, a.dark_val)
    if a.src.lower().endswith(".png"):
        n, c = recolor_png(a.src, a.dst, f); print("%d colours, %d recoloured -> %s" % (n, c, a.dst))
    else:
        b, c = recolor_vd(a.src, a.dst, f); print("%d palettes, %d palette entries recoloured -> %s" % (b, c, a.dst))
