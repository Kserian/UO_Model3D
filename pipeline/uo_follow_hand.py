# A weapon bone that follows its hand rigidly in the listed actions. The item bones (polearm.L, axe2h.L, ...) carry per-frame keys fitted to the ORIGINAL weapons;
# in the mounted actions the original weapon was drawn in a different grip than the rider's fitted hand, so the weapon drifts 10-50 cm off the hand and turns about
# (measured: bone head to hand 0.02 m in 01_walk_armed, 0.1-0.5 m in 23-29). Here the bone is re-keyed in each listed action, every frame, to the hand-relative transform
# it has on average in REFERENCE (an unmounted action in which the weapon is carried in the hand): the weapon then moves with the hand wherever the hand goes.
# Run on the item's .blend after uo_bind_item.py (the rig keys are then the item's own; the repo model is not touched). Run with bpy 4.2.
import bpy
import numpy as np
from mathutils import Matrix, Quaternion

BONE = "polearm.L"
HAND = "hand.L"
ACTIONS = []                       # action names to re-key, e.g. ["23_mounted_walk", ...]
REFERENCE = "01_walk_armed"        # action whose mean hand-relative transform of the bone is used

rig = bpy.data.objects["UO_Rig"]
rig.data.pose_position = "POSE"
pb, hb = rig.pose.bones[BONE], rig.pose.bones[HAND]
pb.rotation_mode = "QUATERNION"
ad = rig.animation_data


def frame_range(act):
    return int(round(act.frame_range[0])), int(round(act.frame_range[1]))


def pose_at(act, f):
    ad.action = act
    bpy.context.scene.frame_set(f)
    bpy.context.view_layer.update()


ref = bpy.data.actions[REFERENCE]
f0, f1 = frame_range(ref)
Ms = []
for f in range(f0, f1 + 1):
    pose_at(ref, f)
    Ms.append(hb.matrix.inverted() @ pb.matrix)
T = np.mean([np.array(M.translation) for M in Ms], axis=0)
q0 = Ms[0].to_quaternion()
Q = np.zeros(4)
for M in Ms:
    q = M.to_quaternion()
    if q.dot(q0) < 0:
        q.negate()
    Q += np.array(q)
Qn = Quaternion(tuple(Q / np.linalg.norm(Q)))
M_REF = Matrix.Translation(T.tolist()) @ Qn.to_matrix().to_4x4()
print("uo_follow_hand: %s in %s = mean over %d frames of %s: %.3f %.3f %.3f m from the hand" % (BONE, HAND, len(Ms), REFERENCE, *T))

for name in ACTIONS:
    act = bpy.data.actions[name]
    for fc in [fc for fc in act.fcurves if 'pose.bones["%s"]' % BONE in fc.data_path]:
        act.fcurves.remove(fc)
    a0, a1 = frame_range(act)
    for f in range(a0, a1 + 1):
        pose_at(act, f)
        pb.matrix = hb.matrix @ M_REF
        bpy.context.view_layer.update()
        pb.keyframe_insert("location", frame=f, group=BONE)
        pb.keyframe_insert("rotation_quaternion", frame=f, group=BONE)
        pb.keyframe_insert("scale", frame=f, group=BONE)
    for fc in [fc for fc in act.fcurves if 'pose.bones["%s"]' % BONE in fc.data_path]:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
    print("uo_follow_hand: %s re-keyed %d frames on the hand (%s)" % (name, a1 - a0 + 1, BONE))
ad.action = bpy.data.actions[REFERENCE]
