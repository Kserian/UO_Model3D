# Re-key a weapon bone (polearm.L ...) per action so that the weapon sits in the hand(s) of the fitted body. The keys of the repo rig follow the ORIGINAL weapons, which in many
# actions do not match the body fitted to the silhouettes: the weapon drifts off the hand, the head spins about the shaft, flips by 300 deg, lies across the neck.
# Per action (MOTION[action] = {"mode": ..., ...}; MOTION["default"] for the rest; "orig" = keep the keys of the rig):
#   "two":    both hands are on the shaft: the axis passes through the grip of hand.L and of hand.R (the head on the side of the upper hand, the one that was nearer the head
#             in the first frame / the original key), the upper hand A m below the top of the weapon; smoothed in time, the roll carried by parallel transport.
#   "side":   one hand (hand.L), the shaft in a fixed direction `dir` of the armature (X = left of the character, -Y front, Z up), the hand A m below the top: the weapon
#             stands at the side and goes where the hand goes (walk, run, stand, riding); "damp" < 1 = only that share of the hand's travel about its mean.
#   "chest":  one hand; the direction is `dir` (or the original key of the first frame) at the first frame and then turns with the chest bone only: the hand may flail
#             (deaths, hit, bow, salute, drink) without screwing the weapon about its shaft.
#   "follow": the grip follows the hand joint, the shaft turns with the hand but without the twist about the shaft (swing-twist split).
# Run on the item's .blend after uo_bind_item.py (the rig keys of the item's .blend change; the repo model does not). Run with bpy 4.2.
import bpy
import json
import numpy as np
from mathutils import Matrix, Quaternion, Vector

BONE = "polearm.L"
HAND = "hand.L"
OTHER_HAND = "hand.R"
OTHER_BONE = "weapon1h.R"          # its calibration holds the grip point of the right hand
CHEST = "chest"
LENGTH = 1.62
BUTT = None
MOTION = {}                        # {"default": {...}, "01_walk_armed": {"mode": "side", "dir": [0.2, -0.05, 1], "A": 0.8}, ...}
SMOOTH = 2                         # passes of the [1 2 1] smoothing of the two-hand axis

rig = bpy.data.objects["UO_Rig"]
rig.data.pose_position = "POSE"
pb = rig.pose.bones[BONE]
pb.rotation_mode = "QUATERNION"
ad = rig.animation_data
WMall = json.loads(bpy.data.texts["weapon_motion.json"].as_string())
WM = WMall[BONE]
Hrest = rig.data.bones[HAND].matrix_local.copy()
Orest = rig.data.bones[OTHER_HAND].matrix_local.copy()
Brest = rig.data.bones[BONE].matrix_local.copy()
g0 = Hrest @ Vector(WM["pivot"])                                   # grip point of the left hand at rest, on the shaft line
d0 = (Hrest.to_3x3() @ Vector(WM["dir"])).normalized()           # shaft line, head towards +d0
butt = float(WM["butt"] if BUTT is None else BUTT)
TOP = butt + float(LENGTH)                                         # line parameter of the top of the weapon (u = 0 at g0)
o0 = Orest @ Vector(WMall[OTHER_BONE]["pivot"])                    # grip point of the right hand at rest


def pose_at(act, f):
    ad.action = act
    bpy.context.scene.frame_set(f)
    bpy.context.view_layer.update()


def grips():
    """the grip points of the left and of the right hand in the current pose (armature space)"""
    L = rig.pose.bones[HAND].matrix @ Hrest.inverted() @ g0
    R = rig.pose.bones[OTHER_HAND].matrix @ Orest.inverted() @ o0
    return L, R


def rot_between(a, b):
    return a.rotation_difference(b).to_matrix().to_4x4() if (a - b).length > 1e-9 else Matrix.Identity(4)


def place(Rm, G, u):
    """W (rest mesh -> posed): the weapon point at line parameter u goes to G, turned by Rm (a 4x4 rotation)"""
    return Matrix.Translation(G) @ Rm @ Matrix.Translation(-(g0 + d0 * u))


def smooth_axes(ds, n):
    ds = [d.copy() for d in ds]
    for _ in range(n):
        out = []
        for i, d in enumerate(ds):
            a = ds[max(i - 1, 0)]; c = ds[min(i + 1, len(ds) - 1)]
            out.append((a + 2 * d + c).normalized())
        ds = out
    return ds


def remove_twist(q, axis):
    v = Vector((q.x, q.y, q.z)); p = axis * axis.dot(v)
    tw = Quaternion((q.w, p.x, p.y, p.z))
    if tw.magnitude < 1e-9:
        return q
    tw.normalize()
    return q @ tw.inverted()


def key_all(act, f0, Ws):
    for fc in [fc for fc in act.fcurves if 'pose.bones["%s"]' % BONE in fc.data_path]:
        act.fcurves.remove(fc)
    prev = None
    for k, W in enumerate(Ws):
        f = f0 + k
        pose_at(act, f)
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


for act in sorted(bpy.data.actions, key=lambda a: a.name):
    cfg = MOTION.get(act.name, MOTION.get("default"))
    if not cfg or cfg.get("mode", "orig") == "orig":
        continue
    mode = cfg["mode"]
    f0, f1 = int(round(act.frame_range[0])), int(round(act.frame_range[1]))
    frames = list(range(f0, f1 + 1))
    A = float(cfg.get("A", 0.57)); u = TOP - A                      # the point of the weapon that sits in the (upper) hand
    # the original key of the first frame: where the weapon is now, its roll and the sense of the head
    pose_at(act, f0)
    W_orig = pb.matrix @ Brest.inverted()
    a_orig = (W_orig.to_3x3() @ d0).normalized()
    R_orig = W_orig.to_3x3().to_4x4()
    Ws = []
    if mode == "two":
        ds, Ps, Us = [], [], []
        prev = a_orig
        for f in frames:
            pose_at(act, f)
            L, R = grips()
            v = L - R
            if v.length < float(cfg.get("min_hands", 0.10)):
                d = prev
            else:
                d = v.normalized()
                if d.dot(prev) < 0:
                    d = -d                                          # the head stays on the side it was
                if cfg.get("flip") and not ds:
                    d = -d; prev = d                                # "flip": the head on the other hand's side (the original key points the other way)
            ds.append(d); prev = d
        ds = smooth_axes(ds, int(cfg.get("smooth", SMOOTH)))
        Rm = rot_between(a_orig, ds[0]) @ R_orig
        for k, f in enumerate(frames):
            pose_at(act, f)
            L, R = grips()
            if k:
                Rm = rot_between(ds[k - 1], ds[k]) @ Rm
            up = L if (L - R).dot(ds[k]) >= 0 else R                # the upper hand: the one further along the head direction
            Ws.append(place(Rm, up, u))
    elif mode in ("side", "chest"):
        D = Vector(cfg["dir"]).normalized() if "dir" in cfg else a_orig
        Rm0 = rot_between(a_orig, D) @ R_orig if "dir" in cfg else R_orig
        if mode == "side" and "dir" in cfg:
            Rm0 = rot_between(d0, D)
        pose_at(act, f0); C1 = rig.pose.bones[CHEST].matrix.to_3x3().to_4x4()
        Ls = []
        for f in frames:
            pose_at(act, f); Ls.append(grips()[0])
        mean = sum(Ls, Vector()) / len(Ls); damp = float(cfg.get("damp", 1.0))        # damp < 1: the weapon follows the hand but moves only that share of the hand's travel
        for k, f in enumerate(frames):
            pose_at(act, f)
            L = mean + damp * (Ls[k] - mean)
            if mode == "side":
                Rm = Rm0
            else:
                Cn = rig.pose.bones[CHEST].matrix.to_3x3().to_4x4()
                Rm = (Cn @ C1.inverted()) @ Rm0
            Ws.append(place(Rm, L, u))
    elif mode == "strike":                                          # a blow: the shaft direction (armature space) is interpolated through `keys` = [[uo_frame, [x, y, z]], ...] (scene frame = 1 + 3 * uo_frame), the hand A m below the top follows the hand
        keys = sorted((float(k), Vector(v).normalized()) for k, v in cfg["keys"])
        for f in frames:
            pose_at(act, f)
            t = (f - 1) / 3.0
            lo = max([k for k in keys if k[0] <= t], key=lambda k: k[0], default=keys[0]); hi = min([k for k in keys if k[0] >= t], key=lambda k: k[0], default=keys[-1])
            w = 0.0 if hi[0] == lo[0] else (t - lo[0]) / (hi[0] - lo[0])
            D = (lo[1] * (1 - w) + hi[1] * w).normalized()
            Ws.append(place(rot_between(d0, D), grips()[0], u))
    elif mode == "follow":
        pose_at(act, f0); Hp1 = rig.pose.bones[HAND].matrix.copy(); P1 = Hp1.translation.copy(); Hinv = Hp1.inverted()
        W1 = W_orig; a1 = a_orig
        if "dir" in cfg:                                           # start in the hand with the shaft along `dir` (the original key of a mounted action is 10-50 cm off the hand)
            D = Vector(cfg["dir"]).normalized()
            W1 = place(rot_between(d0, D), grips()[0], u); a1 = D
        for f in frames:
            pose_at(act, f)
            Hr = rig.pose.bones[HAND].matrix @ Hinv
            S = remove_twist(Hr.to_quaternion(), a1).to_matrix().to_4x4()
            P = Hr @ P1
            Ws.append(Matrix.Translation(P) @ S @ Matrix.Translation(-P1) @ W1)
    else:
        raise ValueError(mode)
    key_all(act, f0, Ws)
    print("uo_weapon_motion: %s: %s, %d frames, hand %.2f m below the top" % (act.name, mode, len(frames), A))
