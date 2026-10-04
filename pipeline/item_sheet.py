"""Contact sheets of rendered item frames (what an item looks like in several actions, directions and moments of the animation).

    python item_sheet.py RENDER_DIR LAYER OUT.png [--actions 04_stand,00_walk_unarmed,...] [--dirs 0,2,4] [--fractions 0,0.33,0.66] [--scale 3] [--ref anim_0527.vd]

RENDER_DIR/LAYER/frames/NN_action/dirK/NN.png is what render_uo_layer.py writes. With --ref (an original item .vd, e.g. pipeline/body13/mul/anim_0527.vd) every row is
followed by the same frames of the original item on the original body, to compare by eye.
"""
import argparse, glob, os, sys
import numpy as np
from PIL import Image

CROP = (88, 100, 168, 200)      # around the character on the 256x256 canvas, anchor (128, 192)


def frames_of(root, layer, action, d):
    dirs = glob.glob(os.path.join(root, layer, "frames", action + "*", "dir%d" % d))
    return sorted(glob.glob(os.path.join(dirs[0], "*.png"))) if dirs else []


def tile(path, crop=CROP, bg=(90, 110, 90, 255)):
    im = Image.open(path).convert("RGBA").crop(crop)
    b = Image.new("RGBA", im.size, bg); b.alpha_composite(im)
    return b


def sheet(root, layer, actions, dirs, fractions, scale=3, ref=None):
    rows = []
    for act in actions:
        row = []
        for d in dirs:
            fr = frames_of(root, layer, act, d)
            for f in fractions:
                if fr:
                    row.append(tile(fr[min(int(f * len(fr)), len(fr) - 1)]))
        if row:
            rows.append((act, row))
    if not rows:
        raise SystemExit("no frames in %s/%s" % (root, layer))
    w = sum(t.width for t in rows[0][1]); h = rows[0][1][0].height
    out = Image.new("RGB", (w, h * len(rows)), (0, 0, 0))
    for i, (act, row) in enumerate(rows):
        x = 0
        for t in row:
            out.paste(t.convert("RGB"), (x, i * h)); x += t.width
    return out.resize((out.width * scale, out.height * scale), Image.NEAREST)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("root"); ap.add_argument("layer"); ap.add_argument("out")
    ap.add_argument("--actions", default="04_stand,00_walk_unarmed,02_run_unarmed,09_attack_1h_slash,16_spell_directed,21_die_forward")
    ap.add_argument("--dirs", default="0,2,4"); ap.add_argument("--fractions", default="0,0.33,0.66"); ap.add_argument("--scale", type=int, default=3)
    a = ap.parse_args()
    im = sheet(a.root, a.layer, a.actions.split(","), [int(x) for x in a.dirs.split(",")], [float(x) for x in a.fractions.split(",")], a.scale)
    im.save(a.out); print(a.out, im.size)
