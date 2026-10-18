# Put the SELECTED weapon on the shaft line of its class the way UO holds it (2H weapons, staffs, bows: left hand; 1H weapons: right hand), ready for uo_bind_item.py.
# 1. Model the weapon upright: shaft along +Z, head / tip UP (+Z), butt at the lowest point, object origin anywhere (apply scale first).
# 2. Select it, set PART below (polearm = staff, spear, halberd, bardiche, crook; axe2h = 2H axes; bow = bow, crossbow; weapon1h = sword, mace, hammer, 1H axe, dagger, kryss, club), run this (Alt+P).
# 3. Then uo_bind_item.py with the same PART (the weapon follows the bone polearm.L / axe2h.L / bow.L / weapon1h.R, calibrated on the original weapons).
# The shaft goes along the class line (WEAPON_MOTION in weapon_motion.json: point PIVOT, direction DIR in hand.L space, head towards +DIR) with the butt at
# the class's usual butt position (`butt`, m along the line; bows: their middle sits at 0).
# The roll about the shaft (weapon_roll_fit.py): model the head as a flat plate in the XZ plane of the weapon: its wide side along +X (the blade's flat, the
# bit / cutting edge of an axe towards +X), thin along Y. The script turns the weapon about its shaft so that +X lies in the plane the original weapon REF_ANIM
# has at roll 0 of the class (weapon_motion.json: roll.offsets; default the reference weapon of the class); the bone then turns it with the roll per pose
# (uo_weapon_bones.py). A class without "roll" (bows) keeps the turn of the shortest rotation +Z -> DIR. ROLL_DEG overrides the offset (degrees).
# PART = "weapon.L": a one-handed thing in the LEFT hand (a horn, a lantern: no original to calibrate on). It takes the grip of weapon1h.R mirrored across the sagittal plane
# (X of hand.R -> -X of hand.L, the same grip line, the same roll turned the mirror way), so the left version is the mirror image of the right one; uo_bind_item.py with PART =
# "weapon.L" then makes it rigid on hand.L (the hand bone itself, as the original left-hand items follow it).
# Running it again places the weapon again.
import bpy, json, math
import numpy as np
from mathutils import Vector, Matrix

PART = "polearm"      # "polearm", "axe2h", "bow", "weapon1h" or "weapon.L" (1H in the left hand, mirror of weapon1h)
REF_ANIM = None       # original weapon whose head orientation to copy (anim id, e.g. 624 halberd, 613 executioner's axe, 623 cutlass); None = the reference of the class
ROLL_DEG = None       # or: offset of the head about the shaft in degrees (overrides REF_ANIM)
BUTT = None           # m along the class line where the butt goes (the hand pivot is at 0): None = the class's usual `butt`; e.g. -0.06 = held close to the butt end (a flail's short haft)
BONE = {"polearm": "polearm.L", "axe2h": "axe2h.L", "bow": "bow.L", "weapon1h": "weapon1h.R", "weapon.L": "weapon1h.R"}[PART]
MIRROR = PART == "weapon.L"                                                    # the grip of the right hand mirrored onto hand.L

WM = json.loads(bpy.data.texts["weapon_motion.json"].as_string())[BONE]
rig = bpy.data.objects["UO_Rig"]
mx = (lambda v: Vector((-v[0], v[1], v[2]))) if MIRROR else (lambda v: Vector(v))   # mirror of a vector in the hand's own axes
HAND = "hand.L" if MIRROR else WM["parent"]
H = rig.matrix_world @ rig.data.bones[HAND].matrix_local                        # the hand bone (hand.L, hand.R) at rest -> world
dloc = mx(WM["dir"])
piv = H @ mx(WM["pivot"]); d = (H.to_3x3() @ dloc).normalized()
RO = WM.get("roll")
ru = None
if RO:                                                                         # where +X of the weapon must point (perpendicular to the shaft)
    delta = math.radians(ROLL_DEG) if ROLL_DEG is not None else RO["offsets"].get(str(REF_ANIM if REF_ANIM is not None else RO["ref"]), 0.0)
    ruloc = mx(Matrix.Rotation(delta, 3, Vector(WM["dir"]).normalized()) @ Vector(RO["e1"]))
    ru = (H.to_3x3() @ ruloc).normalized()
for ob in [o for o in bpy.context.selected_objects if o.type == "MESH"]:
    co = np.array([ob.matrix_world @ v.co for v in ob.data.vertices])
    z0, ctr = co[:, 2].min(), co[:, :2].mean(0)                                # butt height, shaft axis (middle of the bounds in XY)
    R = Vector((0, 0, 1)).rotation_difference(d).to_matrix().to_4x4()
    start = piv + d * (WM["butt"] if BUTT is None else BUTT)                  # where the butt goes
    Rr = Matrix.Identity(4)
    if ru is not None:
        x1 = R.to_3x3() @ Vector((1, 0, 0))
        Rr = Matrix.Rotation(math.atan2(d.dot(x1.cross(ru)), x1.dot(ru)), 4, d)
    T = Matrix.Translation(start) @ Rr @ R @ Matrix.Translation(-Vector((ctr[0], ctr[1], z0)))
    ob.matrix_world = T @ ob.matrix_world
    print("uo_place_weapon: %s on the line of %s, butt at %.2f m along it" % (ob.name, BONE, WM["butt"] if BUTT is None else BUTT))
