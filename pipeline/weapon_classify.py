"""Which weapon class (bone) fits each original weapon animation best? For every weapon animation of anim..anim5 (list: item_animations.json, layers
OneHanded / TwoHanded) the sprite is fitted with the class line + class motion of every weapon bone of weapon_motion.json (weapon_fit.py `cross`:
the ends along the line are fitted per weapon). Reports the mean chamfer (px) per class and the best class.

    python weapon_classify.py WP.npz VDROOT META.json OUT.json [--procs 4]
VDROOT/<file>/anim_<local id>.vd (vdtool/mul2vd.py); META.json: {animation id: {file, local, name, layers, frames, complete}}
"""
import os, sys, json
import numpy as np
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import weapon_fit as WF                                                  # noqa: E402

WM = json.load(open(os.path.join(HERE, "weapon_motion.json")))
BONE_OF = {"polearm.L": "hand.L", "axe2h.L": "hand.L", "bow.L": "hand.L", "weapon1h.R": "hand.R"}


def one(args):
    wp, vdroot, aid, m = args
    path = os.path.join(vdroot, m["file"], "anim_%04d.vd" % m["local"])
    V = WF.Views(wp, path)
    res = {}
    for cls, C in WM.items():
        poses = {tuple(int(x) for x in k.split(",")): (v[:3], v[3:]) for k, v in C["poses"].items()}
        line = {"p0": C["pivot"], "u": C["dir"], "piv": (np.array(C["pivot"]) - np.array(C["dir"]) * (np.array(C["pivot"]) @ np.array(C["dir"]))).tolist()}
        per, x = WF.apply_class(V, BONE_OF[cls], line, poses)
        per0, _ = WF.apply_class(V, BONE_OF[cls], line, {})
        res[cls] = dict(chamfer=float(per.mean()), rigid=float(per0.mean()), extent=[float(x[0]), float(x[1])])
    best = min(res, key=lambda c: res[c]["chamfer"])
    print(aid, m["name"], best, {c: round(r["chamfer"], 2) for c, r in res.items()}, flush=True)
    return aid, dict(name=m["name"], file=m["file"], local=m["local"], views=V.n, classes=res, best=best)


if __name__ == "__main__":
    wp, vdroot, meta, out = sys.argv[1:5]
    procs = int(sys.argv[sys.argv.index("--procs") + 1]) if "--procs" in sys.argv else 4
    meta = json.load(open(meta))
    jobs = [(wp, vdroot, aid, m) for aid, m in sorted(meta.items(), key=lambda kv: int(kv[0]))]
    with Pool(procs) as p:
        res = dict(p.imap_unordered(one, jobs))
    json.dump(res, open(out, "w"), indent=1)
