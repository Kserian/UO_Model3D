"""Write the measured roll of the weapon classes into weapon_motion.json (field "roll" of every class):

    python weapon_roll_apply.py ROLLDIR [--motion weapon_motion.json]

roll = { "e1": reference vector in the hand frame (hand X without its part along the class line), "phi": {"action,frame": rad}, "ref": anim id of the
reference weapon, "offsets": {anim id: rad} } -- the head of a weapon lies in the plane spanned by the class line and Rot_line(phi + offset) e1 (the wide
side of the blade, the bit of an axe at +). uo_weapon_bones.py composes phi into the keyed turn of the weapon bone; uo_place_weapon.py turns a new weapon
about its shaft by the offset of the original weapon it should look like (REF_ANIM). Only weapons with a trustworthy offset are listed (class roll fits the
sprite clearly better than one fixed roll).
"""
import os, sys, json, glob
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))


def e1_of(u):
    u = np.array(u, float); u /= np.linalg.norm(u)
    for x in ([1.0, 0, 0], [0, 1.0, 0]):
        e = np.array(x) - (np.array(x) @ u) * u
        if np.linalg.norm(e) > 0.3:
            return (e / np.linalg.norm(e)).tolist()


def main():
    rolldir = sys.argv[1]; motion = os.path.join(HERE, "weapon_motion.json")
    if "--motion" in sys.argv:
        motion = sys.argv[sys.argv.index("--motion") + 1]
    WM = json.load(open(motion))
    for f in sorted(glob.glob(os.path.join(rolldir, "roll_*.json"))):
        R = json.load(open(f)); cls = R["cls"]
        if len(R["core"]) < 3:                                                    # bows: no weapon with a measurable roll, the class roll fits worse than none
            print(cls, "skipped: only", len(R["core"]), "weapon(s) with a measurable roll"); continue
        offs = {}
        for a, w in R["weapons"].items():
            if w.get("cls_mismatch") is None:
                continue
            gain = (w["class_const"] - w["cls_mismatch"]) / max(w["class_const"], 1e-9)
            if gain >= 0.1 and w["chamfer"] <= 2.2:
                offs[a] = round(float(np.deg2rad(w["delta_deg"])), 4)
        WM[cls]["roll"] = dict(e1=[round(x, 5) for x in e1_of(WM[cls]["dir"])], ref=R["core"][0],
                               phi={k: round(float(np.deg2rad(v)), 4) for k, v in R["phi"].items()}, offsets=offs)
        print(cls, "ref", R["core"][0], "roll for", len(R["phi"]), "poses, offsets for", len(offs), "weapons")
    json.dump(WM, open(motion, "w"))


if __name__ == "__main__":
    main()
