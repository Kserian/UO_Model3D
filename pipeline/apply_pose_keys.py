"""Writes the pose keys of pose_natural_fit.py (OUT_DIR/a<aid>.json) into a .blend and saves a copy.

    python apply_pose_keys.py IN.blend OUT.blend OUT_DIR [--actions 0,1,2] [--bones all|fit]      (bpy 4.2; the .blend is saved with it)

Per action: every key of rotation_quaternion / location / scale of the bones in the JSON is set to the new value at its UO frame (scene frame
1 + 3 i; a loop that repeats its first key at the end gets the first frame's value again). Quaternion keys are written sign-continuous
(dot with the previous key >= 0, the repeated loop key too): Blender interpolates the four components separately, and a sign flip between
two keys spins the bone through the in-between frames. Channels keep their fcurves even when all keys become 0 (a channel without keys in one action keeps the value of the action played before).
The item bones (weapon1h.R, polearm.L, axe2h.L, bow.L, shield.L) are then checked: their armature-space matrices must be the ORIGINAL
ones (they were fitted to the original weapons); a frame that differs by more than 1e-4 gets them set through pose_bone.matrix.
Needs: numpy "bpy==4.2.*".
"""
import sys, os, json, glob
import numpy as np
import bpy
from mathutils import Matrix, Quaternion

STEP = 3
ITEM_BONES = ["weapon1h.R", "polearm.L", "axe2h.L", "bow.L", "shield.L"]
FIT_BONES = ["spine", "chest", "neck", "head", "clavicle.R", "upper_arm.R", "forearm.R", "hand.R", "clavicle.L", "upper_arm.L", "forearm.L", "hand.L"]


def fix_quat_signs(act):
    """every quaternion key gets the sign that keeps dot(previous key, key) >= 0 (same rotation, no spin between the keys)"""
    groups = {}
    for fc in act.fcurves:
        if fc.data_path.endswith("rotation_quaternion"):
            groups.setdefault(fc.data_path, {})[fc.array_index] = fc
    flips = 0
    for dp, g in groups.items():
        if len(g) != 4: continue
        fcs = [g[c] for c in range(4)]
        m = min(len(fc.keyframe_points) for fc in fcs)
        Q = np.array([[fc.keyframe_points[i].co[1] for fc in fcs] for i in range(m)])
        for i in range(1, m):
            if np.dot(Q[i], Q[i - 1]) < 0:
                Q[i] = -Q[i]; flips += 1
                for c in range(4): fcs[c].keyframe_points[i].co[1] = float(Q[i, c])
        for fc in fcs: fc.update()
    return flips


def main():
    a = sys.argv[1:]
    src, dst, d = os.path.abspath(a.pop(0)), os.path.abspath(a.pop(0)), os.path.abspath(a.pop(0))
    o = {"--actions": "", "--bones": "all"}
    while a: k = a.pop(0); o[k] = a.pop(0)
    want = {int(x) for x in o["--actions"].split(",")} if o["--actions"] else None
    bpy.ops.wm.open_mainfile(filepath=src)
    sc = bpy.context.scene
    rig = bpy.data.objects["UO_Rig"]; P = rig.pose.bones
    acts = {int(x["uo_action"]): x for x in bpy.data.actions if "uo_action" in x}
    for path in sorted(glob.glob(os.path.join(d, "a*.json"))):
        J = json.load(open(path)); aid = J["action"]
        if want is not None and aid not in want: continue
        act = acts[aid]; n = int(act["uo_frames"]); bones = J["bones"]
        q, loc, scl = np.array(J["q"]), np.array(J["loc"]), np.array(J["scale"])
        assert len(q) == n
        rig.animation_data.action = act
        # original armature-space matrices of the item bones
        T0 = []
        for i in range(n):
            sc.frame_set(1 + STEP * i); bpy.context.view_layer.update()
            T0.append({b: P[b].matrix.copy() for b in ITEM_BONES if b in P})
        sel = set(bones) if o["--bones"] == "all" else set(FIT_BONES) | set(ITEM_BONES)
        for k, b in enumerate(bones):
            if b not in sel: continue
            qs = q[:, k].copy()
            for i in range(1, n):
                if np.dot(qs[i], qs[i - 1]) < 0: qs[i] = -qs[i]
            for prop, vals, nc in (("rotation_quaternion", qs, 4), ("location", loc[:, k], 3), ("scale", scl[:, k], 3)):
                for c in range(nc):
                    fc = act.fcurves.find('pose.bones["%s"].%s' % (b, prop), index=c)
                    if fc is None:
                        if b in ITEM_BONES: continue                     # unkeyed channel of an item bone: the exported value is whatever the previous action left; the matrix check below decides
                        neutral = (1.0 if c == 0 else 0.0) if prop == "rotation_quaternion" else (1.0 if prop == "scale" else 0.0)
                        assert np.abs(vals[:, c] - neutral).max() < 1e-6, (aid, b, prop, c, "new keys on a channel without an fcurve")
                        continue
                    kps = fc.keyframe_points
                    assert len(kps) in (n, n + 1), (aid, b, prop, len(kps), n)
                    for i in range(n):
                        assert abs(kps[i].co[0] - (1 + STEP * i)) < 1e-6
                        kps[i].co[1] = float(vals[i, c])
                    if len(kps) == n + 1:                                # loop closure: the first frame again, sign continuous with the last
                        v0 = vals[0].copy()
                        if prop == "rotation_quaternion" and np.dot(vals[0], vals[n - 1]) < 0: v0 = -v0
                        kps[n].co[1] = float(v0[c])
                    fc.update()
        # items: armature-space matrices as before
        worst, fixed = 0.0, 0
        for i in range(n):
            sc.frame_set(1 + STEP * i); bpy.context.view_layer.update()
            for b, T in T0[i].items():
                e = max(abs(x - y) for r1, r2 in zip(P[b].matrix, T) for x, y in zip(r1, r2))
                worst = max(worst, e)
                if e > 1e-4:
                    P[b].matrix = T; bpy.context.view_layer.update()
                    for prop, nc in (("rotation_quaternion", 4), ("location", 3)):
                        val = getattr(P[b], prop)
                        for c in range(nc):
                            fc = act.fcurves.find('pose.bones["%s"].%s' % (b, prop), index=c)
                            if fc is not None:
                                fc.keyframe_points[i].co[1] = val[c]; fc.update()
                    fixed += 1
        flips = fix_quat_signs(act)
        print("action %2d %-26s written; item bones: max matrix difference %.1e, %d frame-bones re-solved; %d quaternion sign flips removed" %
              (aid, act.name, worst, fixed, flips), flush=True)
    bpy.ops.wm.save_as_mainfile(filepath=dst)
    print("saved", dst)


if __name__ == "__main__":
    main()
