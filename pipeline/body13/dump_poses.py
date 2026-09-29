"""rest matrices of UO_Rig + per-frame pose channels of every action + body-in-rig matrix -> rig_poses.npz"""
import bpy, numpy as np, sys
bpy.ops.wm.open_mainfile(filepath=sys.argv[1])
sc = bpy.context.scene; rig = bpy.data.objects["UO_Rig"]; body = bpy.data.objects["UO_Body"]
v13 = bpy.data.objects.get("UO_Body_v13")
bones = [b.name for b in rig.data.bones]
R = np.array([np.array(b.matrix_local) for b in rig.data.bones])
par = np.array([bones.index(b.parent.name) if b.parent else -1 for b in rig.data.bones])
rig["uo_direction"] = 0; rig.update_tag(); bpy.context.view_layer.update()
Brel = np.array(rig.matrix_world.inverted() @ (v13 or body).matrix_world)
rig.data.pose_position = "POSE"
keys, loc, quat, scl = [], [], [], []
acts = sorted([a for a in bpy.data.actions if "uo_action" in a], key=lambda a: int(a["uo_action"]))
for act in acts:
    rig.animation_data.action = act; a = int(act["uo_action"])
    for i in range(int(act["uo_frames"])):
        sc.frame_set(1 + 3 * i)
        keys.append((a, i))
        loc.append([list(rig.pose.bones[b].location) for b in bones]); quat.append([list(rig.pose.bones[b].rotation_quaternion) for b in bones])
        scl.append([list(rig.pose.bones[b].scale) for b in bones])
np.savez(sys.argv[2], bones=np.array(bones), R=R, parent=par, Brel=Brel, keys=np.array(keys), loc=np.array(loc), quat=np.array(quat), scale=np.array(scl))
print("frames", len(keys), "max |scale-1|", np.abs(np.array(scl) - 1).max(), "max |loc|", np.abs(np.array(loc)).max(axis=(0, 2)))
