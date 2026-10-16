# A bow held the same way in every action: grip (the middle of the bow) in the fist, shaft as calibrated, string side towards the body.
# The calibrated keys of bow.L (weapon_motion.json) come from silhouettes of a thin line: the shaft's tilt towards / away from the camera and the roll about the shaft are not determined by
# them (in 18_attack_bow the shaft jumps by ~87 degrees between two frames while the hand hardly moves), and the pivot sits up to 10 cm from the fist. Here, for every pose of bow.L:
#  - the shaft is parallel to the body (pelvis -> neck), straight, in every action (PARALLEL False: the calibrated direction, UPRIGHT actions along UP),
#  - the string side of the bow (the side the limb tips curve to) faces the back of the chest (taken perpendicular to the shaft): the bow stands in the body's own plane in every action
#    (from the front it is seen edge-on; held out in front the string comes to the archer, the limb tips curve away from the leg when the bow hangs at the side),
#  - the handle of the bow (its middle, the belly-most part - the bounds' axis lies a hand's width towards the string) goes to the centre of the fingers of hand.L.
#  - in AIM actions (held out) the string side faces the archer along the arm.
# Run on a bow that is bound to bow.L (uo_bind_item.py, PART = "bow"), the bow selected.
import bpy, json
import numpy as np
from mathutils import Matrix, Quaternion, Vector

PARALLEL = True                      # the shaft stays upright in every action (like in the walk), it follows the body (pelvis -> neck) only once the body leans more than FREE_LEAN (False = the calibrated direction, except UPRIGHT actions)
FACING = "pelvis"                    # bone whose back the string faces (not the chest: in the war stance 7 the torso is turned ~70 deg against the legs and the bow turned with it)
FREE_LEAN = 35.0                     # degrees of lean of the body (crouch, step) the bow does not follow
UPRIGHT = [18]                       # with PARALLEL False: UO action numbers where the shaft is made vertical instead of the calibrated direction
UP = (0.0, -0.12, 1.0)               # world axes at direction 0: Y is forward (-Y), Z up
AIM = [18, 19]                       # actions where the bow is held out along the aim line: the string side faces the archer along the arm (fist -> shoulder), not the back of the chest
FIST_SHIFT = 0.0                     # m along the shaft from the fingers' centre (+ = towards the tip) if the grip should sit higher / lower in the fist

rig = bpy.data.objects["UO_Rig"]
WM = json.loads(bpy.data.texts["weapon_motion.json"].as_string())["bow.L"]
item = [o for o in bpy.context.selected_objects if o.type == "MESH"][0]
sc = bpy.context.scene
FINGERS = [b.name for b in rig.data.bones if b.name.startswith("finger") and b.name.endswith(".L")]


def frame(a, b):
    """right-handed orthonormal frame (columns): first column along a, second towards b"""
    a = np.asarray(a, float); a /= np.linalg.norm(a)
    b = np.asarray(b, float); b = b - (b @ a) * a; b /= np.linalg.norm(b)
    return np.c_[a, b, np.cross(a, b)]


rig.data.pose_position = "REST"
bpy.context.view_layer.update()
M = np.array(rig.matrix_world)[:3, :3]
H0 = M @ np.array(Matrix(rig.data.bones[WM["parent"]].matrix_local).to_3x3())            # hand.L axes at rest -> world
P = np.array([item.matrix_world @ v.co for v in item.data.vertices])
C0 = M @ np.array(Matrix(rig.data.bones[FACING].matrix_local).to_3x3()); C0 = C0 / np.linalg.norm(C0, axis=0)
d = H0 @ np.asarray(WM["dir"], float); d /= np.linalg.norm(d)                             # the class line (shaft, tip up) at rest
t = (P - P.mean(0)) @ d
L = np.ptp(t)
mid = P[np.abs(t - np.median(t)) < 0.1 * L].mean(0)
ends = P[(t > t.min() + 0.8 * L) | (t < t.min() + 0.2 * L)].mean(0)
c = ends - mid; c -= (c @ d) * d
cl = (P - mid) @ (c / np.linalg.norm(c))                                                   # coordinate along the string side
ts = (P - P.mean(0)) @ d
hs = (np.abs(ts - np.median(ts)) < 0.06 * L) & (cl < cl[np.abs(ts - np.median(ts)) < 0.06 * L].min() + 0.06)   # the handle: the belly-most part of the middle (not the string across it)
hc = P[hs].mean(0) + c / np.linalg.norm(c) * 0.025                                         # + half the grip's thickness
head0 = np.array(rig.matrix_world @ rig.data.bones["bow.L"].head_local)
o_h = H0.T @ (hc - head0)                                                                    # handle centre from the bone's head, in hand axes: it goes into the fist, not the axis of the bounds
print("uo_bow_hold: handle %.1f cm along the shaft, %.1f cm towards the string from the bone head" % (100 * (hc - head0) @ d, 100 * (hc - head0) @ (c / np.linalg.norm(c))))
u_src = frame(np.asarray(WM["dir"], float), H0.T @ c)                                      # shaft and string side in hand axes
print("uo_bow_hold: string side %s (hand axes), shaft %.2f m" % (np.round(H0.T @ c / np.linalg.norm(c), 2), L))

pb = rig.pose.bones["bow.L"]; pb.rotation_mode = "QUATERNION"
rig.data.pose_position = "POSE"
keep = rig.animation_data.action
W = lambda p: np.array(rig.matrix_world @ p)
n = 0
for act in [a for a in bpy.data.actions if "uo_action" in a]:
    an = int(act["uo_action"]); rig.animation_data.action = act; prev = None
    for i in range(int(act["uo_frames"])):
        p = WM["poses"].get("%d,%d" % (an, i))
        if p is None:
            continue
        sc.frame_set(1 + 3 * i)                                                                # evaluates the old keys of bow.L; the hand's pose is what is wanted here
        pb.rotation_quaternion = Quaternion(); pb.location = (0, 0, 0); bpy.context.view_layer.update()
        Hw = M @ np.array(rig.pose.bones[WM["parent"]].matrix.to_3x3()); Hw = Hw / np.linalg.norm(Hw, axis=0)   # hand.L axes posed -> world
        r = Vector(p[:3]); ang = r.length
        q0 = Quaternion(r / ang, ang) if ang > 1e-9 else Quaternion()
        body = W(rig.pose.bones["neck"].head) - W(rig.pose.bones["pelvis"].head)
        Cw = M @ np.array(rig.pose.bones[FACING].matrix.to_3x3()); Cw = Cw / np.linalg.norm(Cw, axis=0)
        if PARALLEL:
            bn = body / np.linalg.norm(body); lean = np.degrees(np.arccos(np.clip(bn[2], -1, 1)))
            side = bn - bn[2] * np.array([0.0, 0.0, 1.0])
            a = np.radians(max(0.0, lean - FREE_LEAN))
            body = np.array([0.0, 0.0, 1.0]) * np.cos(a) + (side / np.linalg.norm(side) * np.sin(a) if np.linalg.norm(side) > 1e-6 else 0.0)
        D = body if PARALLEL else np.asarray(UP, float) if an in UPRIGHT else Hw @ (np.array(q0.to_matrix()) @ np.asarray(WM["dir"], float))
        D = D / np.linalg.norm(D)
        F = np.mean([W(rig.pose.bones[b].head) for b in FINGERS] + [W(rig.pose.bones[b].tail) for b in FINGERS], 0) + D * FIST_SHIFT
        to_body = Cw @ C0.T @ np.array([0.0, 1.0, 0.0])                                        # the back of FACING (the body faces -Y at rest)
        if an in AIM:
            to_arm = W(rig.pose.bones["upper_arm.L"].head) - F
            to_arm -= (to_arm @ D) * D
            to_body -= (to_body @ D) * D; to_body /= np.linalg.norm(to_body)
            n_arm = np.linalg.norm(to_arm)                                                      # the arm held out: the string comes to the archer along it; bent: the back of the chest (as in the walk)
            if n_arm > 1e-3:
                w = float(np.clip((n_arm - 0.3) / 0.2, 0.0, 1.0))
                to_body = (1 - w) * to_body + w * to_arm / n_arm
        to_body -= (to_body @ D) * D
        if np.linalg.norm(to_body) < 1e-3:
            to_body = np.array([0.0, 1.0, 0.0])
        Q = frame(Hw.T @ D, Hw.T @ to_body) @ u_src.T                                       # turn of the bone in hand axes: shaft -> D, string side -> the body
        q = Matrix(Q.tolist()).to_quaternion()
        if prev is not None and q.dot(prev) < 0:
            q.negate()
        prev = q
        pb.rotation_quaternion = q
        bpy.context.view_layer.update()
        h = W(pb.head)                                                                         # the bone's head with the location 0
        pb.location = tuple(float(x) for x in Hw.T @ (F - Hw @ (Q @ o_h) - h))                                  # hand axes = the bone's axes: the shift that puts the grip in the fist
        pb.keyframe_insert("location", frame=1 + 3 * i, group="bow.L")
        pb.keyframe_insert("rotation_quaternion", frame=1 + 3 * i, group="bow.L")
        n += 1
print("uo_bow_hold: %d poses re-keyed" % n)
rig.animation_data.action = keep
