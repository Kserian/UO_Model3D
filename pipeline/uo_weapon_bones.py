# Add the weapon bones of the left hand (polearm.L, axe2h.L, bow.L; children of hand.L) and key their motion in every UO action of THIS file.
# UO holds 2H weapons, staffs, bows and crossbows in the LEFT hand and moves them differently from the hand bone: the calibration
# (weapon_fit.py, from the original weapon animations, 0.6-2 px instead of 5-6 px with the weapon rigid in hand.L) is in WEAPON_MOTION below
# (pipeline/weapon_motion.json). Run it once from Blender's Text Editor (Alt+P); running it again replaces the keys.
# The roll of the weapon about its own shaft (the flat of a blade, the bit of an axe) is keyed too: c["roll"]["phi"] per pose, measured from the original sprites.
# A bone sits at the grip point of its class (PIVOT, hand.L space) with the axes of hand.L. A weapon is modelled in Rest Position with its shaft along
# the class line (through PIVOT, direction DIR in hand.L space), then bound with uo_bind_item.py: PART = "polearm" (staff, spear, halberd,
# bardiche, crook), "axe2h" (2H axes), "bow" (bow, crossbow, heavy crossbow). The bone moves by (turn R, shift T) in hand.L axes per frame.
import bpy, json
from mathutils import Matrix, Quaternion, Vector

WEAPON_MOTION = json.loads(bpy.data.texts["weapon_motion.json"].as_string()) if "weapon_motion.json" in bpy.data.texts else None
if WEAPON_MOTION is None:
    import os
    WEAPON_MOTION = json.load(open(os.path.join(os.path.dirname(bpy.data.filepath), "..", "pipeline", "weapon_motion.json")))
ROLL = True                                                   # key the roll about the shaft too (field "roll" of the class in weapon_motion.json)
LEN = 0.12                                                    # m, drawn length of the (non-deforming role) bone

rig = bpy.data.objects["UO_Rig"]
assert rig.mode == "OBJECT" or bpy.ops.object.mode_set(mode="OBJECT")
bpy.context.view_layer.objects.active = rig
for b, c in WEAPON_MOTION.items():
    if b not in rig.data.bones:
        bpy.ops.object.mode_set(mode="EDIT")
        hand = rig.data.edit_bones[c["parent"]]
        M = hand.matrix.copy()                                # armature-space frame of hand.L at rest
        eb = rig.data.edit_bones.new(b)
        eb.parent = hand; eb.use_connect = False
        M2 = Matrix.Translation(M @ Vector(c["pivot"])) @ M.to_3x3().normalized().to_4x4()
        eb.length = LEN; eb.matrix = M2
        bpy.ops.object.mode_set(mode="OBJECT")
    bone = rig.data.bones[b]
    bone.inherit_scale = "NONE"; bone.use_deform = True
rig.data.pose_position = rig.data.pose_position
keep = rig.animation_data.action
for b, c in WEAPON_MOTION.items():
    pb = rig.pose.bones[b]; pb.rotation_mode = "QUATERNION"; n = 0; roll = c.get("roll")
    for act in [a for a in bpy.data.actions if "uo_action" in a]:
        for i in range(int(act["uo_frames"])):
            p = c["poses"].get("%d,%d" % (int(act["uo_action"]), i))
            if p is None:
                continue
            r = Vector(p[:3]); ang = r.length
            rig.animation_data.action = act
            q = Quaternion(r / ang, ang) if ang > 1e-9 else Quaternion()
            if ROLL and roll is not None:                                 # the turn of the weapon about its own axis (weapon_roll_fit.py): R' = R * Rot_line(phi)
                q = q @ Quaternion(Vector(c["dir"]).normalized(), roll["phi"].get("%d,%d" % (int(act["uo_action"]), i), 0.0))
            pb.rotation_quaternion = q
            pb.location = p[3:]
            pb.keyframe_insert("location", frame=1 + 3 * i, group=b)
            pb.keyframe_insert("rotation_quaternion", frame=1 + 3 * i, group=b)
            n += 1
    print("uo_weapon_bones: %s keyed on %d poses" % (b, n))
rig.animation_data.action = keep
