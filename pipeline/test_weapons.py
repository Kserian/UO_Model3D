"""Weapon QA: a thin shaft (replica of a weapon) rendered through the whole pipeline (uo_bind_item + render_uo_layer) against the original weapon sprite.

    python test_weapons.py --anim 648 --mode polearm|rigid --vd VDDIR [--rigid RIGID.json] [--actions 04_stand,12_attack_2h_bash,...] [--tmp DIR] [--out qa.json]

mode polearm (or axe2h, bow): the shaft lies on the class line of weapon_motion.json (extent of that weapon) and is bound to the weapon bone (calibrated motion).
mode rigid: the shaft lies on the rigid line fitted for this weapon (weapon_fit.py rigid --out) and is bound to hand.L (what was possible before).
Per frame: IoU and the symmetric chamfer distance (px) of the rendered shaft pixels and the sprite pixels (capped at 15 px).
"""
import argparse, json, os, subprocess, sys, tempfile
import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "vdtool"))
import vdtool                                                       # noqa: E402

BONE = dict(polearm="polearm.L", axe2h="axe2h.L", bow="bow.L")
CLASS_BONE = {"polearm": "polearm.L", "axe2h": "axe2h.L", "bow": "bow.L"}
DEFAULT_ACTIONS = "04_stand,03_run_armed,08_combat_idle_2h,12_attack_2h_bash,13_attack_2h_slash,14_attack_2h_pierce,21_die_forward,30_block"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--anim", type=int, required=True); ap.add_argument("--mode", required=True); ap.add_argument("--vd", required=True)
    ap.add_argument("--rigid"); ap.add_argument("--actions", default=DEFAULT_ACTIONS); ap.add_argument("--radius", type=float, default=0.03)
    ap.add_argument("--blend", default=os.path.join(HERE, "..", "model", "UO_Body_0x190.blend"))
    ap.add_argument("--motion", default=os.path.join(HERE, "weapon_motion.json")); ap.add_argument("--tmp"); ap.add_argument("--out"); ap.add_argument("--reuse", action="store_true", help="measure frames already rendered in --tmp")
    a = ap.parse_args()
    tmp = os.path.abspath(a.tmp or tempfile.mkdtemp(prefix="test_weapons_"))
    if a.mode == "rigid":
        R = json.load(open(a.rigid))["rigid"]; p, u = np.array(R["p0"]), np.array(R["u"])
        spec = dict(p=p.tolist(), u=u.tolist(), s0=0.0, s1=R["length"], part="weapon.L")
    else:
        C = json.load(open(a.motion))[CLASS_BONE[a.mode]]; ex = C["anims"][str(a.anim)]
        spec = dict(p=C["pivot"], u=C["dir"], s0=ex[0], s1=ex[1], part=a.mode)
    spec["radius"] = a.radius
    env = dict(os.environ, UO_TW_SPEC=json.dumps(spec), UO_TW_SCRIPTS=HERE)
    out = os.path.join(tmp, "%d_%s" % (a.anim, a.mode))
    only = [x for x in a.actions.split(",")]
    cmd = [sys.executable, os.path.join(HERE, "run_render_headless.py"), os.path.abspath(a.blend), out, "--pre", os.path.join(HERE, "test_weapons_pre.py"),
           'LAYER="clothing"', "ONLY=%r" % only, "EXACT_BODY=False", "EXACT_COLORS=False", "CANVAS=(256,256)", "ANCHOR=(128,192)"]
    cmd = [c.replace('LAYER="clothing"', "LAYER='clothing'") for c in cmd]
    if not a.reuse:
        subprocess.run(cmd, env=env, check=True)
    _, blocks = vdtool.read_vd(os.path.join(a.vd, "anim_%04d.vd" % a.anim)); blk = {(b["action"], b["dir"]): b for b in blocks}
    rows = []
    for act in only:
        ai = int(act[:2])
        for d in range(5):
            fdir = os.path.join(out, "clothing", "frames", act, "dir%d" % d)
            if not os.path.isdir(fdir):
                continue
            for fn in sorted(os.listdir(fdir)):
                i = int(fn[:2]); Rm = np.array(Image.open(os.path.join(fdir, fn)).convert("RGBA"))[..., 3] > 0
                b = blk.get((ai, d)); G = np.zeros((256, 256), bool)
                if b is not None and i < len(b["frames"]):
                    f = b["frames"][i]; rgba = vdtool.frame_rgba(f, b["palette"]); h, w = rgba.shape[:2]; x0, y0 = 128 - f["cx"], 192 - f["cy"] - f["h"]
                    ys, xs = slice(max(y0, 0), min(y0 + h, 256)), slice(max(x0, 0), min(x0 + w, 256))
                    if ys.stop > ys.start and xs.stop > xs.start:
                        G[ys, xs] = rgba[ys.start - y0:ys.stop - y0, xs.start - x0:xs.stop - x0, 3] > 0
                if G.sum() < 4:
                    continue
                if Rm.sum() < 1:
                    ch = 15.0
                else:
                    dg = ndimage.distance_transform_edt(~G); dr = ndimage.distance_transform_edt(~Rm)
                    ch = 0.5 * (min(dg[Rm].mean(), 15) + min(dr[G].mean(), 15))
                rows.append(dict(a=ai, d=d, i=i, iou=float((Rm & G).sum() / max((Rm | G).sum(), 1)), chamfer=float(ch)))
    f = lambda k: float(np.mean([r[k] for r in rows]))
    res = dict(anim=a.anim, mode=a.mode, frames=len(rows), iou=f("iou"), chamfer=f("chamfer"), chamfer_median=float(np.median([r["chamfer"] for r in rows])),
               by_action={str(x): float(np.mean([r["chamfer"] for r in rows if r["a"] == x])) for x in sorted({r["a"] for r in rows})})
    print("anim %d %-8s frames %d  IoU %.3f  chamfer mean %.2f median %.2f px | per action: %s" % (
        a.anim, a.mode, res["frames"], res["iou"], res["chamfer"], res["chamfer_median"], " ".join("%s:%.1f" % kv for kv in res["by_action"].items())))
    if a.out:
        json.dump(res, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
