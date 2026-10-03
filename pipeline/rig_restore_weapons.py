"""One-off: put the item-motion bones back into the rig (rig_simplify.py had removed them): polearm.L, axe2h.L, bow.L (children of hand.L), weapon1h.R (child of hand.R)
and shield.L (child of forearm.L), with their per-frame keys of all 35 actions.

    git show b86c314:model/UO_Body_0x190.blend > old.blend
    python rig_restore_weapons.py old.blend ../model/UO_Body_0x190.blend OUT.blend
    python sync_blend_scripts.py OUT.blend uo_place_weapon.py uo_weapon_bones.py uo_place_shield.py weapon_motion.json uo_bind_item.py

The bones depend only on the transform of hand.L / hand.R / forearm.L, which the finger bones do not change, so the calibration (docs/qa/weapons_*.json,
weapon_roll.md) is still valid with the fingers. Everything else in the file stays as it is. Run with bpy 4.2.
"""
import re, sys
import bpy

old_path, cur_path, out_path = sys.argv[-3:]
NAMES = ["polearm.L", "axe2h.L", "bow.L", "weapon1h.R", "shield.L"]

bpy.ops.wm.open_mainfile(filepath=old_path)
orig = bpy.data.objects["UO_Rig"]
bones, keys, shield_col = [], {}, False
for n in NAMES:
    b = orig.data.bones[n]
    bones.append(dict(name=n, parent=b.parent.name, head=list(b.head_local), tail=list(b.tail_local), deform=b.use_deform,
                      inherit_scale=b.inherit_scale, inherit_rot=b.use_inherit_rotation, connect=b.use_connect))
bpy.context.view_layer.objects.active = orig
bpy.ops.object.mode_set(mode="EDIT")
for d in bones:
    d["roll"] = orig.data.edit_bones[d["name"]].roll
bpy.ops.object.mode_set(mode="OBJECT")
shield_col = any(c.name == "Shield" and "shield.L" in c.bones for c in orig.data.collections_all)
for a in bpy.data.actions:
    for fc in a.fcurves:
        m = re.match(r'pose\.bones\["(.+?)"\]', fc.data_path)
        if m and m.group(1) in NAMES:
            keys.setdefault(a.name, []).append((fc.data_path, fc.array_index, fc.extrapolation,
                [(kp.co[0], kp.co[1], kp.interpolation, list(kp.handle_left), list(kp.handle_right), kp.handle_left_type, kp.handle_right_type) for kp in fc.keyframe_points]))

bpy.ops.wm.open_mainfile(filepath=cur_path)
rig = bpy.data.objects["UO_Rig"]
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode="EDIT")
for d in bones:
    b = rig.data.edit_bones.new(d["name"])
    b.head, b.tail, b.roll = d["head"], d["tail"], d["roll"]
    b.parent = rig.data.edit_bones[d["parent"]]; b.use_connect = d["connect"]
    b.use_deform = d["deform"]; b.inherit_scale = d["inherit_scale"]; b.use_inherit_rotation = d["inherit_rot"]
bpy.ops.object.mode_set(mode="OBJECT")
if shield_col:
    rig.data.collections.new("Shield").assign(rig.data.bones["shield.L"])
for n in NAMES:
    rig.pose.bones[n].rotation_mode = "QUATERNION"
n_fc = 0
for a in bpy.data.actions:
    for path, idx, extra, pts in keys.get(a.name, []):
        fc = a.fcurves.new(path, index=idx)
        fc.extrapolation = extra
        fc.keyframe_points.add(len(pts))
        for kp, (f, v, ip, hl, hr, hlt, hrt) in zip(fc.keyframe_points, pts):
            kp.co = (f, v); kp.interpolation = ip
            kp.handle_left_type, kp.handle_right_type = hlt, hrt
            kp.handle_left, kp.handle_right = hl, hr
        fc.update(); n_fc += 1
print("bones %d, fcurves %d" % (len(bones), n_fc))
bpy.ops.wm.save_as_mainfile(filepath=out_path)
