# Put the SELECTED weapon on the shaft line of its class the way UO holds it in the left hand, ready for uo_bind_item.py.
# 1. Model the weapon upright: shaft along +Z, head / tip UP (+Z), butt at the lowest point, object origin anywhere (apply scale first).
# 2. Select it, set PART below (polearm = staff, spear, halberd, bardiche, crook; axe2h = 2H axes; bow = bow, crossbow), run this (Alt+P).
# 3. Then uo_bind_item.py with the same PART (the weapon follows the bone polearm.L / axe2h.L / bow.L, calibrated on the original weapons).
# The shaft goes along the class line (WEAPON_MOTION in weapon_motion.json: point PIVOT, direction DIR in hand.L space, head towards +DIR) with the butt at
# the class's usual butt position (`butt`, m along the line; bows: their middle sits at 0). The roll about the shaft is not calibrated: the weapon keeps the
# turn it gets from the shortest rotation +Z -> DIR; turn it about the shaft by hand if its head must face another way.
# Running it again places the weapon again.
import bpy, json
import numpy as np
from mathutils import Vector, Matrix

PART = "polearm"      # "polearm", "axe2h" or "bow"
BONE = {"polearm": "polearm.L", "axe2h": "axe2h.L", "bow": "bow.L"}[PART]

WM = json.loads(bpy.data.texts["weapon_motion.json"].as_string())[BONE]
rig = bpy.data.objects["UO_Rig"]
H = rig.matrix_world @ rig.data.bones[WM["parent"]].matrix_local              # hand.L at rest -> world
piv = H @ Vector(WM["pivot"]); d = (H.to_3x3() @ Vector(WM["dir"])).normalized()
for ob in [o for o in bpy.context.selected_objects if o.type == "MESH"]:
    co = np.array([ob.matrix_world @ v.co for v in ob.data.vertices])
    z0, ctr = co[:, 2].min(), co[:, :2].mean(0)                                # butt height, shaft axis (middle of the bounds in XY)
    R = Vector((0, 0, 1)).rotation_difference(d).to_matrix().to_4x4()
    start = piv + d * WM["butt"]                                               # where the butt goes
    T = Matrix.Translation(start) @ R @ Matrix.Translation(-Vector((ctr[0], ctr[1], z0)))
    ob.matrix_world = T @ ob.matrix_world
    print("uo_place_weapon: %s on the line of %s, butt at %.2f m along it" % (ob.name, BONE, WM["butt"]))
