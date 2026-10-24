# A weapon bone that follows its hand in the listed actions. The item bones (polearm.L, axe2h.L, ...) carry per-frame keys fitted to the ORIGINAL weapons; in some actions the
# original weapon art does not match the rider / body fitted to the silhouettes (mounted actions: 10-50 cm off the hand; deaths, block, drink: the head spins about the
# shaft, flips by 300 deg between two frames). Here the bone is re-keyed in each listed action, every frame:
#   - the grip follows the hand joint rigidly (the weapon never leaves the hand),
#   - the shaft turns with the hand, but the TWIST about the shaft axis is removed (swing-twist split): no wrist screw, no spinning head, no flips,
#   - the pose at the first frame of the action is either the ORIGINAL key of that frame (ORIGINAL_ACTIONS: the weapon keeps its direction and sense), or a chosen one
#     (UPRIGHT_ACTIONS: the head up and out, the hand GRIP_FROM_BUTT m from the butt: a rider holds a mace upright beside the horse, the lower end does not go into the horse).
# Run on the item's .blend after uo_bind_item.py (the keys of the item's rig are changed; the repo model is not touched). Run with bpy 4.2.
import bpy
import json
import numpy as np
from mathutils import Matrix, Quaternion, Vector

BONE = "polearm.L"
HAND = "hand.L"
ORIGINAL_ACTIONS = []              # first frame = the original key of the action
UPRIGHT_ACTIONS = []               # first frame = UPRIGHT_DIR at the grip GRIP_FROM_BUTT
UPRIGHT_DIR = (0.30, -0.10, 1.0)   # armature space (X = the character's left, -Y = front, Z up): shaft direction towards the head
GRIP_FROM_BUTT = 0.50              # m
BUTT = None                        # m: where the weapon was placed on its line (None = the class's butt)

rig = bpy.data.objects["UO_Rig"]
rig.data.pose_position = "POSE"
pb, hb = rig.pose.bones[BONE], rig.pose.bones[HAND]
pb.rotation_mode = "QUATERNION"
ad = rig.animation_data
WM = json.loads(bpy.data.texts["weapon_motion.json"].as_string())[BONE]
Hrest = rig.data.bones[HAND].matrix_local.copy()
Brest = rig.data.bones[BONE].matrix_local.copy()
g0 = Hrest @ Vector(WM["pivot"])                                  # the grip point on the hand at rest
d0 = (Hrest.to_3x3() @ Vector(WM["dir"])).normalized()           # the shaft line through it, head towards +d0
butt = float(WM["butt"] if BUTT is None else BUTT)


def pose_at(act, f):
    ad.action = act
    bpy.context.scene.frame_set(f)
    bpy.context.view_layer.update()


def frame_range(act):
    return int(round(act.frame_range[0])), int(round(act.frame_range[1]))


def remove_twist(q, axis):
    """q = swing * twist (twist about `axis`): the swing, which sends the axis where q sends it and does not screw about it"""
    v = Vector((q.x, q.y, q.z)); p = axis * axis.dot(v)
    tw = Quaternion((q.w, p.x, p.y, p.z))
    if tw.magnitude < 1e-9:
        return q
    tw.normalize()
    return q @ tw.inverted()


for name in list(ORIGINAL_ACTIONS) + list(UPRIGHT_ACTIONS):
    act = bpy.data.actions[name]
    f0, f1 = frame_range(act)
    pose_at(act, f0)
    Hp1 = hb.matrix.copy()
    if name in UPRIGHT_ACTIONS:
        D = Vector(UPRIGHT_DIR).normalized()
        u0 = butt + GRIP_FROM_BUTT                                # the point of the weapon that sits in the hand (u along the line from the grip point)
        g1 = Hp1 @ Hrest.inverted() @ g0
        Rd = d0.rotation_difference(D).to_matrix().to_4x4()
        W1 = Matrix.Translation(g1) @ Rd @ Matrix.Translation(-(g0 + d0 * u0))
    else:
        W1 = pb.matrix @ Brest.inverted()                          # the original key of the first frame: where the rest mesh is now
    a1 = (W1.to_3x3() @ d0).normalized()                           # the shaft axis at the first frame
    P1 = Hp1.translation.copy()                                    # the hand joint at the first frame
    for fc in [fc for fc in act.fcurves if 'pose.bones["%s"]' % BONE in fc.data_path]:
        act.fcurves.remove(fc)
    Hinv = Hp1.inverted()
    prev = None
    for f in range(f0, f1 + 1):
        pose_at(act, f)
        Hr = hb.matrix @ Hinv                                      # the hand's move since the first frame
        S = remove_twist(Hr.to_quaternion(), a1).to_matrix().to_4x4()
        P = Hr @ P1                                                # the hand joint now
        W = Matrix.Translation(P) @ S @ Matrix.Translation(-P1) @ W1
        pb.matrix = W @ Brest
        bpy.context.view_layer.update()
        q = pb.rotation_quaternion.copy()
        if prev is not None and q.dot(prev) < 0:
            q.negate()
        pb.rotation_quaternion = q; prev = q
        pb.keyframe_insert("location", frame=f, group=BONE)
        pb.keyframe_insert("rotation_quaternion", frame=f, group=BONE)
        pb.keyframe_insert("scale", frame=f, group=BONE)
    for fc in [fc for fc in act.fcurves if 'pose.bones["%s"]' % BONE in fc.data_path]:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
    print("uo_follow_hand: %s: %s on %s, %d frames, %s" % (name, BONE, HAND, f1 - f0 + 1, "upright %s grip %.2f m from the butt" % (tuple(round(x, 2) for x in UPRIGHT_DIR), GRIP_FROM_BUTT) if name in UPRIGHT_ACTIONS else "original first frame"))
