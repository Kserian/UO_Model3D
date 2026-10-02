"""Put a class fitted by `weapon_fit.py class` into weapon_motion.json (the calibration the weapon bones of uo_weapon_bones.py are keyed from).

    python weapon_motion_add.py CLASS.json weapon_motion.json BONE PARENT
e.g. python weapon_motion_add.py class1h.json weapon_motion.json weapon1h.R hand.R
Entry: the bone sits at `pivot` (point of the class line nearest to the origin of the hand bone, hand space) and `dir` is the line; `anims` = extent (m along the
line, from the pivot) of every fitted weapon, `butt` = their median butt end (where uo_place_weapon.py puts the butt), `poses` = turn (rotation vector, rad) +
shift (m) in the hand axes for each (action, frame).
"""
import json, sys
import numpy as np

cls, out, bone, parent = sys.argv[1:5]
C = json.load(open(cls)); R = C["rigid"]
p0 = np.array(R["p0"]); u = np.array(R["u"]); piv = p0 - u * (p0 @ u)
ex = {str(a): [round(float(x), 3) for x in e] for a, e in C["extents"].items()}
entry = dict(parent=parent, pivot=[round(float(x), 4) for x in piv], dir=[round(float(x), 4) for x in u], anims=ex,
             chamfer={str(a): round(float(v), 2) for a, v in C["chamfer"].items()},
             poses={k: [round(float(x), 4) for x in v[0] + v[1]] for k, v in C["poses"].items()}, butt=round(float(np.median([e[0] for e in ex.values()])), 3))
M = json.load(open(out)); M[bone] = entry
json.dump(M, open(out, "w"), separators=(",", ": "))
print("%s: %d poses, butt %.3f m, chamfer %s" % (bone, len(entry["poses"]), entry["butt"], entry["chamfer"]))
