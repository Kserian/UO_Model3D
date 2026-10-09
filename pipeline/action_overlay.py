"""Overlay sheet of the pure 3D body vs the ORIGINAL UO body frames for one action (rows = 5 directions, columns = frames).

    python body_part_raster.py ../model/UO_Body_0x190.blend lab.npz --actions 21
    python action_overlay.py lab.npz OUT.png --action 21 [--scale 3]

Colours: both = light grey, only the sprite = green, only the model = red (so a limb in a wrong place shows as a red / green pair). Needs: numpy pillow.
"""
import sys, os, argparse
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from body_part_qa import originals


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("lab"); ap.add_argument("out")
    ap.add_argument("--action", type=int, required=True); ap.add_argument("--scale", type=int, default=3)
    ap.add_argument("--frames", default=None)
    a = ap.parse_args()
    z = np.load(a.lab); lab, key = z["lab"], z["key"]; O = originals()
    sel = [i for i, k in enumerate(key) if k[0] == a.action]
    nf = 1 + max(key[i][2] for i in sel)
    frames = [int(x) for x in a.frames.split(",")] if a.frames else list(range(nf))
    H, W = lab.shape[1:]; s = a.scale
    sheet = Image.new("RGB", (W * s * len(frames), H * s * 5), (30, 30, 30))
    for i in sel:
        _, d, f = key[i]
        if f not in frames: continue
        m = lab[i] >= 0; o = O[(a.action, d, f)]
        im = np.zeros((H, W, 3), np.uint8)
        im[m & o] = (200, 200, 200); im[o & ~m] = (60, 220, 60); im[m & ~o] = (230, 50, 50)
        t = Image.fromarray(im).resize((W * s, H * s), Image.NEAREST)
        ImageDraw.Draw(t).text((3, 3), "d%d f%d" % (d, f), fill=(255, 255, 0))
        sheet.paste(t, (frames.index(f) * W * s, d * H * s))
    sheet.save(a.out); print("saved", a.out)


if __name__ == "__main__":
    main()
