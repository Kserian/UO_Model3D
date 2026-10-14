"""The metal of an item's animation frames made exactly grey (R = G = B in 15 bits), so that a dye with the tiledata flag PartialHue (0x00040000) takes all of it.

    python uo_grey_metal.py IN_DIR OUT_DIR [--chroma 0.25]

IN_DIR: a frame folder of render_uo_layer.py / vdtool.py extract (meta.json + frames/<action>/dir<d>/NN.png); OUT_DIR gets a copy with every pixel whose
chroma (max - min of RGB) is <= CHROMA x its luma set to that luma (a grey of the same level), the rest (wood, coloured parts) unchanged; pack it with
vdtool.py pack OUT_DIR OUT.vd. The client dyes only the pixels with R = G = B in 15 bits when PartialHue is set: a metal pixel with a slight tint stays undyed (a speck;
the client's mace has 6% such pixels). Flail v9: 26% of the metal pixels had a tint up to 8/255.
"""
import os, shutil, sys
import numpy as np
from PIL import Image


def grey_metal(a, k):
    """RGBA uint8 -> the same with the metal (chroma <= k x luma) as the grey of its luma, quantised to 15 bits; returns (image, changed pixels)"""
    q = a[..., :3].astype(np.int32); m = a[..., 3] > 0
    y = 0.299 * q[..., 0] + 0.587 * q[..., 1] + 0.114 * q[..., 2]
    met = m & ((q.max(-1) - q.min(-1)) <= k * np.maximum(y, 1.0))
    g = (np.clip(np.round(y), 8, 255).astype(np.int32) >> 3) << 3
    out = a.copy()
    for c in range(3):
        out[..., c] = np.where(met, g, a[..., c])
    changed = int((met & np.any(out[..., :3] != a[..., :3], -1)).sum())
    return out, changed


def main(src, dst, k):
    if os.path.exists(dst):
        raise SystemExit("uo_grey_metal: %s exists" % dst)
    shutil.copytree(src, dst)
    n = ch = 0
    for root, _, files in os.walk(os.path.join(dst, "frames")):
        for f in files:
            if f.endswith(".png"):
                p = os.path.join(root, f); a = np.array(Image.open(p).convert("RGBA"))
                b, c = grey_metal(a, k); Image.fromarray(b).save(p); n += 1; ch += c
    print("uo_grey_metal: %d frames, %d pixels made grey -> %s" % (n, ch, dst))


if __name__ == "__main__":
    a = sys.argv[1:]; k = 0.25
    if "--chroma" in a:
        i = a.index("--chroma"); k = float(a[i + 1]); del a[i:i + 2]
    main(a[0], a[1], k)
