"""Roll QA: a flat plate shaped like the head of an original weapon (learned from its sprites by weapon_roll_fit.py), bound to the class weapon bone and
rendered through the whole pipeline (uo_bind_item + render_uo_layer) against the original weapon sprite, with the roll of the class per pose (mode class)
or one fixed roll (mode const) or no roll at all (mode none).

    python test_weapon_roll.py --anim 613 --roll ROLLDIR --vd VDDIR/anim [--mode class|const|none] [--actions 04_stand,...] [--tmp DIR] [--out qa.json]

ROLLDIR holds roll_<class>.json and cells_<anim>.npy (weapon_roll_fit.py). Per frame: IoU, symmetric chamfer (px, capped at 15) and the tolerant mismatch
(px further than 1 px from the other mask) of the rendered plate and the sprite.
"""
import argparse, json, os, subprocess, sys, tempfile
import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "vdtool"))
import vdtool                                                       # noqa: E402

BONE_PART = {"polearm.L": "polearm", "axe2h.L": "axe2h", "bow.L": "bow", "weapon1h.R": "weapon1h"}
DEFAULT_ACTIONS = "04_stand,03_run_armed,08_combat_idle_2h,09_attack_1h_slash,12_attack_2h_bash,13_attack_2h_slash,14_attack_2h_pierce,21_die_forward,30_block"


def sprite_mask(blk, ai, d, i):
    G = np.zeros((256, 256), bool); b = blk.get((ai, d))
    if b is not None and i < len(b["frames"]):
        f = b["frames"][i]; rgba = vdtool.frame_rgba(f, b["palette"]); h, w = rgba.shape[:2]; x0, y0 = 128 - f["cx"], 192 - f["cy"] - f["h"]
        ys, xs = slice(max(y0, 0), min(y0 + h, 256)), slice(max(x0, 0), min(x0 + w, 256))
        if ys.stop > ys.start and xs.stop > xs.start:
            G[ys, xs] = rgba[ys.start - y0:ys.stop - y0, xs.start - x0:xs.stop - x0, 3] > 0
    return G


def measure(out, blk, only):
    rows = []
    box = np.ones((3, 3), bool)
    for act in only:
        ai = int(act[:2])
        for d in range(5):
            fdir = os.path.join(out, "clothing", "frames", act, "dir%d" % d)
            if not os.path.isdir(fdir):
                continue
            for fn in sorted(os.listdir(fdir)):
                i = int(fn[:2]); R = np.array(Image.open(os.path.join(fdir, fn)).convert("RGBA"))[..., 3] > 0
                G = sprite_mask(blk, ai, d, i)
                if G.sum() < 4:
                    continue
                if R.sum() < 1:
                    ch, mm = 15.0, float(G.sum())
                else:
                    dg = ndimage.distance_transform_edt(~G); dr = ndimage.distance_transform_edt(~R)
                    ch = 0.5 * (min(dg[R].mean(), 15) + min(dr[G].mean(), 15))
                    mm = float((R & ~ndimage.binary_dilation(G, box)).sum() + (G & ~ndimage.binary_dilation(R, box)).sum())
                rows.append(dict(a=ai, d=d, i=i, iou=float((R & G).sum() / max((R | G).sum(), 1)), chamfer=float(ch), mismatch=mm))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--anim", type=int, required=True); ap.add_argument("--roll", required=True); ap.add_argument("--vd", required=True)
    ap.add_argument("--mode", default="class"); ap.add_argument("--actions", default=DEFAULT_ACTIONS); ap.add_argument("--thick", type=float, default=0.012)
    ap.add_argument("--blend", default=os.path.join(HERE, "..", "model", "UO_Body_0x190.blend")); ap.add_argument("--tmp"); ap.add_argument("--out")
    ap.add_argument("--reuse", action="store_true")
    a = ap.parse_args()
    tmp = os.path.abspath(a.tmp or tempfile.mkdtemp(prefix="test_weapon_roll_"))
    cls = None
    for fn in os.listdir(a.roll):
        if fn.startswith("roll_") and fn.endswith(".json"):
            R = json.load(open(os.path.join(a.roll, fn)))
            if str(a.anim) in R["weapons"]:
                cls, RJ = R["cls"], R
    W = RJ["weapons"][str(a.anim)]
    cells = np.load(os.path.join(a.roll, "cells_%d.npy" % a.anim))
    WM = json.load(open(os.path.join(HERE, "weapon_motion.json")))[cls]
    spec = dict(cls=cls, parent=WM["parent"], part=BONE_PART[cls], cells=cells.tolist(), step=0.015, thick=a.thick, delta=float(np.deg2rad(W["delta_deg"])), mode=a.mode,
                phi=RJ["phi"] if a.mode == "class" else None, const=(W["const_abs_deg"] - W["delta_deg"]) if a.mode == "const" else 0.0)
    env = dict(os.environ, UO_TR_SPEC=json.dumps(spec), UO_TR_SCRIPTS=HERE)
    out = os.path.join(tmp, "%d_%s" % (a.anim, a.mode)); only = a.actions.split(",")
    cmd = [sys.executable, os.path.join(HERE, "run_render_headless.py"), os.path.abspath(a.blend), out, "--pre", os.path.join(HERE, "test_weapon_roll_pre.py"),
           "LAYER='clothing'", "ONLY=%r" % only, "EXACT_BODY=False", "EXACT_COLORS=False", "CANVAS=(256,256)", "ANCHOR=(128,192)"]
    if not a.reuse:
        subprocess.run(cmd, env=env, check=True)
    meta = json.load(open(os.path.join(a.roll, "..", "..", "weapons_meta.json"))) if os.path.exists(os.path.join(a.roll, "..", "..", "weapons_meta.json")) else None
    _, blocks = vdtool.read_vd(a.vd); blk = {(b["action"], b["dir"]): b for b in blocks}
    rows = measure(out, blk, only)
    f = lambda k: float(np.mean([r[k] for r in rows]))
    res = dict(anim=a.anim, mode=a.mode, cls=cls, frames=len(rows), iou=f("iou"), chamfer=f("chamfer"), mismatch=f("mismatch"),
               by_action={str(x): float(np.mean([r["mismatch"] for r in rows if r["a"] == x])) for x in sorted({r["a"] for r in rows})})
    print("anim %d %-5s frames %d  IoU %.3f  chamfer %.2f px  tolerant mismatch %.1f px | per action: %s" % (
        a.anim, a.mode, res["frames"], res["iou"], res["chamfer"], res["mismatch"], " ".join("%s:%.0f" % kv for kv in res["by_action"].items())))
    if a.out:
        json.dump(res, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
