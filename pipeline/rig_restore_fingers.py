"""One-off: put the 30 finger bones back into the 19-bone UO_Rig (rig_simplify.py had removed them), with their weights and their UO-fitted poses.

    git show b86c314:model/UO_Body_0x190.blend > old.blend           # the file before the simplification: finger bones, weights, per-frame keys
    python rig_restore_fingers.py old.blend ../model/UO_Body_0x190.blend OUT.blend

Takes from the old file: the 15 finger bones per hand (head, tail, roll, parent, flags), their rotation keys in all 35 actions (the curl of the fingers and
the thumb was fitted to the original UO frames, so the hand is clenched as in the original) and the body weights of the finger groups. Twist and toe weights
stay merged (limb / foot), the clavicle groups stay on UO_Body (Deform off), other bones and the rest of the file are not touched. Run with bpy 4.2.
"""
import json, re, sys
import numpy as np
import bpy

old_path, cur_path, out_path = sys.argv[-3:]
FIN = re.compile(r"^finger\d-\d\.[LR]$")

# --- 1. read the old file
bpy.ops.wm.open_mainfile(filepath=old_path)
orig = bpy.data.objects["UO_Rig"]
bones = []
for b in orig.data.bones:
    if FIN.match(b.name):
        bones.append(dict(name=b.name, parent=b.parent.name, head=list(b.head_local), tail=list(b.tail_local), roll=None,
                          deform=b.use_deform, inherit_scale=b.inherit_scale, inherit_rot=b.use_inherit_rotation, connect=b.use_connect))
bpy.context.view_layer.objects.active = orig
bpy.ops.object.mode_set(mode="EDIT")
for d in bones:
    d["roll"] = orig.data.edit_bones[d["name"]].roll
bpy.ops.object.mode_set(mode="OBJECT")
body = bpy.data.objects["UO_Body"]
gname = {g.index: g.name for g in body.vertex_groups}
fw = {}                                                   # finger group -> {vertex: weight}
for v in body.data.vertices:
    for g in v.groups:
        if FIN.match(gname[g.group]):
            fw.setdefault(gname[g.group], {})[v.index] = g.weight
nv = len(body.data.vertices)
keys = {}                                                 # action -> [(path, index, [(frame, value, interp, hl, hr, hlt, hrt)])]
for a in bpy.data.actions:
    for fc in a.fcurves:
        if FIN.match(re.match(r'pose\.bones\["(.+?)"\]', fc.data_path).group(1)) if fc.data_path.startswith("pose.bones") else False:
            keys.setdefault(a.name, []).append((fc.data_path, fc.array_index, fc.extrapolation,
                [(kp.co[0], kp.co[1], kp.interpolation, list(kp.handle_left), list(kp.handle_right), kp.handle_left_type, kp.handle_right_type) for kp in fc.keyframe_points]))

# --- 2. apply to the current file
bpy.ops.wm.open_mainfile(filepath=cur_path)
rig = bpy.data.objects["UO_Rig"]
body = bpy.data.objects["UO_Body"]
assert len(body.data.vertices) == nv, "the body mesh changed since the old file"
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode="EDIT")
eb = rig.data.edit_bones
for d in bones:
    b = eb.new(d["name"])
    b.head, b.tail, b.roll = d["head"], d["tail"], d["roll"]
    b.parent = eb[d["parent"]]; b.use_connect = d["connect"]
    b.use_deform = d["deform"]; b.inherit_scale = d["inherit_scale"]; b.use_inherit_rotation = d["inherit_rot"]
bpy.ops.object.mode_set(mode="OBJECT")
col = rig.data.collections.new("Fingers")
for d in bones:
    col.assign(rig.data.bones[d["name"]])
for pb in rig.pose.bones:
    if FIN.match(pb.name):
        pb.rotation_mode = "QUATERNION"

# weights: finger groups from the old file, taken from the hand group (hand keeps what the fingers do not carry)
vg = body.vertex_groups
hand = {s: np.zeros(nv) for s in "LR"}
for s in "LR":
    g = vg["hand." + s]
    for v in body.data.vertices:
        for e in v.groups:
            if e.group == g.index:
                hand[s][v.index] = e.weight
for name, w in fw.items():
    s = name[-1]
    g = vg.new(name=name)
    for i, x in w.items():
        g.add([i], x, "REPLACE")
        hand[s][i] -= x
for s in "LR":
    assert hand[s].min() > -1e-4, "finger weight larger than the hand weight"
    g = vg["hand." + s]
    for i in np.nonzero(hand[s] > 1e-5)[0]:
        g.add([int(i)], float(hand[s][i]), "REPLACE")
    for i in np.nonzero(hand[s] <= 1e-5)[0]:
        g.remove([int(i)])

# keys
n = 0
for a in bpy.data.actions:
    for path, idx, extra, pts in keys.get(a.name, []):
        fc = a.fcurves.new(path, index=idx)
        fc.extrapolation = extra
        fc.keyframe_points.add(len(pts))
        for kp, (f, v, ip, hl, hr, hlt, hrt) in zip(fc.keyframe_points, pts):
            kp.co = (f, v); kp.interpolation = ip
            kp.handle_left_type, kp.handle_right_type = hlt, hrt
            kp.handle_left, kp.handle_right = hl, hr
        fc.update(); n += 1
print("finger bones %d, groups %d, fcurves %d" % (len(bones), len(fw), n))
bpy.ops.wm.save_as_mainfile(filepath=out_path)
