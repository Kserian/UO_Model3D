"""Export forward-kinematics data of the 210 UO poses (one per action/frame; the 5 directions share the pose), for offline pose fitting.

    python body_pose_fk_export.py ../model/UO_Body_0x190.blend OUT.npz

Writes: bones (names, same order as body_pose_export.py), parent (B,) index (-1 = root), Lrest (B,4,4) rest matrix of the bone relative to its
parent (armature space for the root), Arest (B,4,4) armature-space rest matrix (bone.matrix_local), key (P,2) = (action, frame), loc (P,B,3), quat (P,B,4)
(w,x,y,z), scl (P,B,3) = local pose basis of every bone at frame 1+3*frame, P (P,B,4,4) armature-space pose matrix (Blender's pose_bone.matrix).
noscale (B,) bool = inherit_scale NONE (the parent's scale is not inherited; the offset still is).
Pose bone matrix = P[parent] @ Lrest @ T(loc) R(quat) S(scl) (checked against P by body_pose_lib.py).
"""
import sys, os
import numpy as np
import bpy

STEP = 3


def main():
    blend, out = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    bpy.ops.wm.open_mainfile(filepath=blend)
    rig, body = bpy.data.objects["UO_Rig"], bpy.data.objects["UO_Body"]
    names = [g.name for g in body.vertex_groups]
    idx = {n: i for i, n in enumerate(names)}
    parent = np.array([idx[rig.data.bones[n].parent.name] if rig.data.bones[n].parent else -1 for n in names])
    assert all(p >= 0 or n == "pelvis" for p, n in zip(parent, names)), "a skinned bone has a parent outside the vertex groups"
    Arest = np.array([np.array(rig.data.bones[n].matrix_local) for n in names])
    Lrest = np.array([Arest[i] if parent[i] < 0 else np.linalg.inv(Arest[parent[i]]) @ Arest[i] for i in range(len(names))])
    rig.data.pose_position = "POSE"
    sc = bpy.context.scene
    acts = sorted([a for a in bpy.data.actions if "uo_action" in a], key=lambda a: int(a["uo_action"]))
    noscale = np.array([rig.data.bones[n].inherit_scale == "NONE" for n in names])
    keys, loc, quat, scl, P = [], [], [], [], []
    for act in acts:
        rig.animation_data.action = act
        for i in range(int(act["uo_frames"])):
            sc.frame_set(1 + i * STEP); bpy.context.view_layer.update()
            keys.append((int(act["uo_action"]), i))
            loc.append([list(rig.pose.bones[n].location) for n in names]); quat.append([list(rig.pose.bones[n].rotation_quaternion) for n in names])
            scl.append([list(rig.pose.bones[n].scale) for n in names]); P.append([np.array(rig.pose.bones[n].matrix) for n in names])
    np.savez_compressed(out, bones=np.array(names), parent=parent, noscale=noscale, Lrest=Lrest, Arest=Arest, key=np.array(keys), loc=np.array(loc), quat=np.array(quat), scl=np.array(scl), P=np.array(P))
    print("poses", len(keys), "bones", len(names))


if __name__ == "__main__":
    main()
