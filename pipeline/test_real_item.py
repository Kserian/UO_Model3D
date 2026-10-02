"""QA of a REAL item already bound in the .blend (collection Clothing, e.g. Example_Shirt) against the original sprite of the item it imitates.

    python test_real_item.py --anim 434 [--actions 04_stand,...] [--tmp DIR] [--out qa.json] [--img overlay.png] [--set NAME=VALUE]
Same metrics as test_items.py (IoU, outside, missing, strips, specks, colours), but no replica is built: the render of the Clothing collection is used
as it is. Sprites come from pipeline/body13/mul/anim_NNNN.vd (same bytes as the client).
"""
import argparse, json, os, subprocess, sys, tempfile

import numpy as np
from PIL import Image

import test_items as ti

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", default=os.path.join(ti.HERE, "..", "model", "UO_Body_0x190.blend"))
    ap.add_argument("--anim", type=int, required=True)
    ap.add_argument("--actions", default=ti.DEFAULT_ACTIONS)
    ap.add_argument("--canvas", default="256,256"); ap.add_argument("--anchor", default="128,192")
    ap.add_argument("--tmp"); ap.add_argument("--out"); ap.add_argument("--img")
    ap.add_argument("--set", action="append", default=[])
    a = ap.parse_args()
    tmp = os.path.abspath(a.tmp) if a.tmp else tempfile.mkdtemp(prefix="test_real_")
    canvas, anchor = tuple(int(x) for x in a.canvas.split(",")), tuple(int(x) for x in a.anchor.split(","))
    actions = a.actions.split(",")
    cmd = [sys.executable, os.path.join(ti.HERE, "run_render_headless.py"), os.path.abspath(a.blend), tmp, 'LAYER="clothing"', "ONLY=%r" % (actions,),
           "CANVAS=%r" % (canvas,), "ANCHOR=%r" % (anchor,)] + a.set
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit("render failed:\n%s\n%s" % (r.stdout[-2000:], r.stderr[-2000:]))
    ti.ITEMS["real"] = dict(anim=a.anim)
    show = {("04_stand", 0, 0), ("09_attack_1h_slash", 3, 1), ("16_spell_directed", 3, 0), ("21_die_forward", 3, 2), ("00_walk_unarmed", 3, 1)}
    rows, blocks, imgs = ti.measure(os.path.join(tmp, "clothing", "frames"), "real", canvas, anchor, show)
    s = ti.summarize(rows, blocks)
    print("anim %d: frames %d IoU %.3f outside %.1f missing %.1f strip %.1f pieces %.2f clipped %d colors %d | %s" % (
        a.anim, s["frames"], s["iou"], s["outside"], s["missing"], s["strip"], s["pieces"], s["clipped"], s["colors_max"],
        " ".join("%s:%.2f" % (k, v) for k, v in s["by_action"].items())))
    if a.out:
        json.dump(dict(anim=a.anim, canvas=canvas, anchor=anchor, actions=actions, result=s), open(a.out, "w"), indent=1)
    if a.img and imgs:
        im = np.concatenate([np.pad(i[max(anchor[1] - 90, 0):anchor[1] + 36, max(anchor[0] - 45, 0):anchor[0] + 45], ((1, 1), (1, 1), (0, 0)), constant_values=90) for i in imgs], 1)
        Image.fromarray(im).resize((im.shape[1] * 2, im.shape[0] * 2), Image.NEAREST).save(a.img)
