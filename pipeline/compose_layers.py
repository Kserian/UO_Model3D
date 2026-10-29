"""Put an ORIGINAL item animation (from a .vd made with vdtool/mul2vd.py, e.g. the body sash anim 490) under a rendered item layer into one .vd.

    python compose_layers.py ORIGINAL.vd RENDER_DIR OUT.vd [--layer clothing] [--alt 0,1,2,3=DIR ...] [--preview PREVIEW.png] [--body pipeline/body400.vd] [--over]

RENDER_DIR/LAYER/frames/NN_action/dirK/NN.png is what render_uo_layer.py writes (canvas 256x256, anchor (128, 192)). Every frame of the original is pasted on the same canvas by its centre
(left = anchor_x - cx, top = anchor_y - cy - h, the rule of uo_vd_writer.crop_frame) and the rendered frame is laid over it (--over: the original over the rendered one); --alt ACTIONS=DIR (several times): the frames of those actions (numbers, comma separated) come from another render (a drum put further forward for the actions in which the torso bends into it: separate renders of the poses that need it, put together here); the frame counts of the two must
match (they do: both follow the 35 actions of the body). The result is written like every other layer (15-bit colours, one 256-colour palette per block, median cut when more are used).
--preview: a sheet of a few actions over the original body frames (body, original item, rendered item), to look at the join.
"""
import argparse, glob, os, sys
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import vd as vdread
import uo_vd_writer as writer

CANVAS, ANCHOR = 256, (128, 192)


def to_canvas(img, cx, cy):
    """a cropped frame of a .vd (image, centre) -> RGBA on the CANVAS, anchor (128, 192): left = anchor_x - cx, top = anchor_y - cy - h"""
    c = np.zeros((CANVAS, CANVAS, 4), np.uint8)
    h, w = img.shape[:2]
    x0, y0 = ANCHOR[0] - cx, ANCHOR[1] - cy - h
    sx0, sy0 = max(0, -x0), max(0, -y0)
    ex, ey = min(w, CANVAS - x0), min(h, CANVAS - y0)
    if ex > sx0 and ey > sy0:
        c[y0 + sy0:y0 + ey, x0 + sx0:x0 + ex] = img[sy0:ey, sx0:ex]
    return c


def over(top, bottom):
    """RGBA uint8 `top` laid over `bottom` (same size)"""
    ta = top[..., 3:4].astype(np.float32) / 255.0; ba = bottom[..., 3:4].astype(np.float32) / 255.0
    na = ta + ba * (1 - ta)
    rgb = (top[..., :3] * ta + bottom[..., :3] * ba * (1 - ta)) / np.maximum(na, 1e-6)
    return np.dstack([np.round(rgb), np.round(na * 255)]).astype(np.uint8)


def compose(orig, render, layer, over_=False, alt=None):
    alt = alt or {}
    _, _, an = vdread.read_vd(orig)
    blocks = {}
    for (a, d), frames in sorted(an.items()):
        dirs = glob.glob(os.path.join(alt.get(a, render), layer, "frames", "%02d_*" % a, "dir%d" % d))
        pngs = sorted(glob.glob(os.path.join(dirs[0], "*.png"))) if dirs else []
        if len(pngs) != len(frames):
            raise SystemExit("action %d dir %d: %d original frames, %d rendered" % (a, d, len(frames), len(pngs)))
        out = []
        for fr, p in zip(frames, pngs):
            item = to_canvas(fr["img"], fr["cx"], fr["cy"])
            top = np.array(Image.open(p).convert("RGBA"))
            out.append(over(item, top) if over_ else over(top, item))
        blocks[(a, d)] = out
    return blocks


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("original"); ap.add_argument("render"); ap.add_argument("out")
    ap.add_argument("--layer", default="clothing"); ap.add_argument("--over", action="store_true"); ap.add_argument("--alt", action="append", default=[]); ap.add_argument("--preview"); ap.add_argument("--body", default=os.path.join(HERE, "body400.vd"))
    a = ap.parse_args()
    alt = {int(x): os.path.abspath(spec.split("=", 1)[1]) for spec in a.alt for x in spec.split("=", 1)[0].split(",")}
    blocks = compose(a.original, a.render, a.layer, a.over, alt)
    writer.write_vd(a.out, blocks, anim_type=2, anchor=ANCHOR)
    if a.preview:
        _, _, body = vdread.read_vd(a.body)
        acts, dirs, fracs, crop, sc = [4, 0, 2, 9, 16, 21], [0, 2, 4], [0, 0.33, 0.66], (88, 100, 168, 200), 3
        tiles = []
        for act in acts:
            row = []
            for d in dirs:
                for f in fracs:
                    n = len(blocks[(act, d)]); i = min(n - 1, int(f * n))
                    b = body[(act, d)][min(i, len(body[(act, d)]) - 1)]
                    c = over(blocks[(act, d)][i], to_canvas(b["img"], b["cx"], b["cy"]))
                    bg = np.zeros_like(c); bg[...] = (90, 110, 90, 255)
                    im = Image.fromarray(over(c, bg)).crop(crop).resize(((crop[2] - crop[0]) * sc, (crop[3] - crop[1]) * sc), Image.NEAREST)
                    row.append(np.array(im))
            tiles.append(np.concatenate(row, 1))
        Image.fromarray(np.concatenate(tiles, 0)).convert("RGB").save(a.preview); print("preview:", a.preview)
    print("composed %d blocks, %d frames -> %s" % (len(blocks), sum(len(v) for v in blocks.values()), a.out))
