"""Look of an item against the original UO sprites: how much shading (large-scale light/dark) and how much pixel noise it has, per frame, inside the item (outline eroded).

    python item_look.py FRAMES_ROOT [--actions 0,4] [--originals 449,469,527]

FRAMES_ROOT is a render folder (`.../clothing` with `frames/<action>/dir*/NN.png`). Numbers (grey value 0-255):
  shade  std of the 5-px smoothed value: the large-scale shading (folds, form); a flat shell has little of it
  noise  mean |value - 5-px mean|: the pixel noise / texture grain
  mean   mean value
Originals (pipeline/body13/mul/anim_*.vd, stand and walk): robe 449 shade 25 noise 26, robe 469 21 / 18, plate 527 22 / 15, trousers 431 12 / 12.
"""
import argparse, glob, os, re, sys
import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "vdtool")); sys.path.insert(0, os.path.join(HERE, "body13"))


def stats(img):
    a = img[..., :3].astype(float).mean(2); m = img[..., 3] > 0
    mi = ndimage.binary_erosion(m, iterations=2)
    if mi.sum() < 50:
        return None
    sm = ndimage.uniform_filter(a, 5)
    return sm[mi].std(), np.abs(a - sm)[mi].mean(), a[mi].mean()


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("root"); ap.add_argument("--actions", default="0,4"); ap.add_argument("--originals", default="449,469,527,431")
    a = ap.parse_args(); acts = {int(x) for x in a.actions.split(",")}
    r = []
    for f in glob.glob(os.path.join(a.root, "frames", "*", "dir*", "*.png")):
        if int(re.search(r"(\d+)_", os.path.basename(os.path.dirname(os.path.dirname(f)))).group(1)) in acts:
            s = stats(np.array(Image.open(f).convert("RGBA")))
            if s: r.append(s)
    print("%-12s shade %5.1f  noise %5.1f  mean %5.0f   (%d frames)" % ((os.path.basename(os.path.dirname(a.root.rstrip("/"))) or "item",) + tuple(np.mean(r, 0)) + (len(r),)))
    if a.originals:
        import vdtool
        from itemframes import canvas
        for n in (int(x) for x in a.originals.split(",")):
            _, bl = vdtool.read_vd(os.path.join(HERE, "body13", "mul", "anim_%04d.vd" % n)); q = []
            for b in bl:
                if b["action"] in acts:
                    for i in range(len(b["frames"])):
                        s = stats(canvas(b, i, anchor=(75, 92), size=(145, 133)))
                        if s: q.append(s)
            if q:
                print("%-12s shade %5.1f  noise %5.1f  mean %5.0f   (original)" % (n, *np.mean(q, 0)))


if __name__ == "__main__":
    main()
