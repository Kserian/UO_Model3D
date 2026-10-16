# A bow in the shooting action: keep it upright in the left hand. The calibrated keys of bow.L (weapon_motion.json) come from silhouettes of a thin line, which leave the bow's
# tilt towards / away from the camera undetermined: in 18_attack_bow the shaft jumps by ~87 degrees between two frames while the hand hardly moves. Here the keys of ACTIONS are replaced:
# per frame the bone turns the SELECTED bow so that its shaft is along UP (about vertical, a little forward) and its string side (the side the limb tips curve to) faces the archer (BACK),
# the grip stays in the fist (location 0). Run on a bow that is bound to bow.L (uo_bind_item.py, PART = "bow"); other actions and crossbows keep their calibration.
import bpy, json
import numpy as np
from mathutils import Matrix, Quaternion, Vector

ACTIONS = [18]                       # UO action numbers whose keys are replaced
UP = (0.0, -0.12, 1.0)               # armature space: Y is forward (-Y), Z up; the shaft's direction (tip up)
BACK = (0.0, 1.0, 0.0)               # armature space: towards the archer (the string side of the bow)

rig = bpy.data.objects["UO_Rig"]
WM = json.loads(bpy.data.texts["weapon_motion.json"].as_string())["bow.L"]
item = [o for o in bpy.context.selected_objects if o.type == "MESH"][0]
sc = bpy.context.scene


def frame(a, b):
    """right-handed orthonormal frame (columns) with the first column along a, the second towards b"""
    a = np.asarray(a, float); a /= np.linalg.norm(a)
    b = np.asarray(b, float); b = b - (b @ a) * a; b /= np.linalg.norm(b)
    return np.c_[a, b, np.cross(a, b)]


rig.data.pose_position = "REST"
bpy.context.view_layer.update()
M = np.array(rig.matrix_world)[:3, :3]
H0 = M @ np.array((Matrix(rig.data.bones[WM["parent"]].matrix_local).to_3x3()))      # hand.L axes at rest -> world
P = np.array([item.matrix_world @ v.co for v in item.data.vertices])
d = H0 @ np.asarray(WM["dir"], float); d /= np.linalg.norm(d)                           # the class line (shaft, tip up) at rest
t = (P - P.mean(0)) @ d
L = np.ptp(t)
mid = P[np.abs(t - np.median(t)) < 0.1 * L].mean(0)
ends = P[(t > t.min() + 0.8 * L) | (t < t.min() + 0.2 * L)].mean(0)
c = (ends - mid); c -= (c @ d) * d
u_src = frame(np.asarray(WM["dir"], float), H0.T @ c)                                    # shaft and string side in hand axes
print("uo_bow_upright: string side %s (hand axes), shaft %.2f m" % (np.round(H0.T @ c / np.linalg.norm(c), 2), L))

up, back = np.asarray(UP, float), np.asarray(BACK, float)
pb = rig.pose.bones["bow.L"]; pb.rotation_mode = "QUATERNION"
rig.data.pose_position = "POSE"
acts = {int(a["uo_action"]): a for a in bpy.data.actions if "uo_action" in a}
keep = rig.animation_data.action
for an in ACTIONS:
    act = acts[an]; rig.animation_data.action = act
    prev = None
    for i in range(int(act["uo_frames"])):
        pb.rotation_quaternion = Quaternion(); pb.location = (0, 0, 0)
        sc.frame_set(1 + 3 * i); bpy.context.view_layer.update()
        Hw = M @ np.array(rig.pose.bones[WM["parent"]].matrix.to_3x3())                    # hand.L axes posed -> world
        Hw = Hw / np.linalg.norm(Hw, axis=0)
        u_dst = frame(Hw.T @ up, Hw.T @ back)
        Q = u_dst @ u_src.T                                                                   # turn of the bone in hand axes: shaft -> up, string side -> back
        q = Matrix(Q.tolist()).to_quaternion()
        if prev is not None and q.dot(prev) < 0:
            q.negate()
        prev = q
        pb.rotation_quaternion = q; pb.location = (0, 0, 0)
        pb.keyframe_insert("location", frame=1 + 3 * i, group="bow.L")
        pb.keyframe_insert("rotation_quaternion", frame=1 + 3 * i, group="bow.L")
    print("uo_bow_upright: action %d: %d frames re-keyed" % (an, int(act["uo_frames"])))
rig.animation_data.action = keep
