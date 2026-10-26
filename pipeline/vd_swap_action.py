"""Replace the frames of single actions in a finished .vd with freshly rendered ones, without rendering the whole file again.

    python vd_swap_action.py init  ITEM.vd WORK                          # unpack ITEM.vd into WORK on the render canvas (256x256, anchor (128, 192)), one folder per action
    python vd_swap_action.py swap  WORK RENDER_DIR 12_attack_2h_bash,... [--out NEW.vd]
                                                                         # copy the frames of these actions from RENDER_DIR/clothing/frames, pack WORK into NEW.vd (default WORK/new.vd)
    python vd_swap_action.py check WORK                                  # pack WORK unchanged and compare it with the .vd it came from (pixels)

RENDER_DIR = the --out folder of run_render_headless.py (RENDER_DIR/clothing/frames/NN_action/dirK/NN.png; render_uo_layer.py writes 256x256 frames, anchor (128, 192)), made with
ONLY=["12_attack_2h_bash"], i.e. one action rendered from the item.blend. Every direction of the action must have the same number of frames as in the .vd. WORK keeps the
unpacked frames, so a later swap starts from the .vd with every earlier swap already in it; WORK/source.vd is the .vd it was unpacked from, WORK/new.vd the last result.
"""
import glob, json, os, shutil, subprocess, sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
VDTOOL = os.path.join(HERE, "..", "vdtool", "vdtool.py")
CANVAS, ANCHOR = (256, 256), (128, 192)


def run(*args):
    r = subprocess.run([sys.executable, VDTOOL] + [str(a) for a in args], capture_output=True, text=True)
    if r.returncode:
        sys.exit("vdtool %s failed:\n%s%s" % (args[0], r.stdout, r.stderr))
    return r.stdout


def init(vd, work):
    if os.path.exists(work):
        sys.exit("%s exists: remove it to unpack again" % work)
    os.makedirs(work)
    shutil.copy(vd, os.path.join(work, "source.vd"))
    run("extract", vd, os.path.join(work, "vd"))
    meta_p = os.path.join(work, "vd", "meta.json")
    meta = json.load(open(meta_p))
    cw, ch = meta["canvas"]; ax, ay = meta["anchor"]
    dx, dy = ANCHOR[0] - ax, ANCHOR[1] - ay
    n = 0
    for f in glob.glob(os.path.join(work, "vd", "frames", "*", "dir*", "*.png")):
        im = Image.open(f).convert("RGBA")
        big = Image.new("RGBA", CANVAS, (0, 0, 0, 0)); big.paste(im, (dx, dy))
        big.save(f); n += 1
    meta["canvas"], meta["anchor"] = list(CANVAS), list(ANCHOR)
    json.dump(meta, open(meta_p, "w"), indent=1)
    print("unpacked %d frames of %s into %s (canvas %dx%d, anchor %s)" % (n, vd, work, *CANVAS, ANCHOR))


def pack(work, out):
    run("pack", os.path.join(work, "vd"), out)
    return out


def swap(work, render, actions, out):
    meta = json.load(open(os.path.join(work, "vd", "meta.json")))
    for act in actions:
        src = glob.glob(os.path.join(render, "clothing", "frames", act))
        dst = glob.glob(os.path.join(work, "vd", "frames", act))
        if not src or not dst:
            sys.exit("action %s: %s" % (act, "not rendered in " + render if not src else "not in the .vd"))
        for d in range(5):
            new = sorted(glob.glob(os.path.join(src[0], "dir%d" % d, "*.png")))
            old = sorted(glob.glob(os.path.join(dst[0], "dir%d" % d, "*.png")))
            if len(new) != len(old):
                sys.exit("%s dir%d: %d rendered frames, %d in the .vd" % (act, d, len(new), len(old)))
            for o, nw in zip(old, new):
                if Image.open(nw).size != CANVAS:
                    sys.exit("%s is not %dx%d (render with CANVAS=(256,256) ANCHOR=(128,192))" % (nw, *CANVAS))
                shutil.copy(nw, o)
        print("swapped %s (%d frames x 5 directions)" % (act, len(new)))
    pack(work, out)
    print("wrote", out)


def check(work):
    out = pack(work, os.path.join(work, "check.vd"))
    print(run("verify", os.path.join(work, "source.vd"), out).strip())


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["init"] and len(a) == 3:
        init(a[1], a[2])
    elif a[:1] == ["swap"] and len(a) >= 4:
        o = a[a.index("--out") + 1] if "--out" in a else os.path.join(a[1], "new.vd")
        swap(a[1], a[2], a[3].split(","), o)
    elif a[:1] == ["check"] and len(a) == 2:
        check(a[1])
    else:
        sys.exit(__doc__)
