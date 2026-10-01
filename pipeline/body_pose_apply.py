"""Write fitted pose corrections (corr.npz of body_pose_fit.py) into the keyframes of the actions of model/UO_Body_0x190.blend.

    python body_pose_apply.py ../model/UO_Body_0x190.blend corr.npz [--out OTHER.blend]

Only the keyframe VALUES of rotation_quaternion / location / scale of the bones that differ are changed (handles move with their key), at frame 1+3*i of the
pose (action, i). Nothing else in the file changes. Bones without a curve for the changed channel are skipped with a warning.
"""
import sys, argparse, os
import numpy as np
import bpy


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("blend"); ap.add_argument("corr"); ap.add_argument("--out"); a = ap.parse_args()
    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(a.blend))
    c = np.load(a.corr); bones = [str(b) for b in c["bones"]]; key = c["key"]
    rig = bpy.data.objects["UO_Rig"]
    acts = {int(x["uo_action"]): x for x in bpy.data.actions if "uo_action" in x}
    chan = {"rotation_quaternion": (c["quat"], 4), "location": (c["loc"], 3), "scale": (c["scl"], 3)}
    nset = nskip = 0; skipped = set()
    for p, (act, i) in enumerate(key):
        A = acts[int(act)]; fr = 1 + int(i) * 3
        for dp, (arr, n) in chan.items():
            for j, bn in enumerate(bones):
                new = arr[p, j]
                if dp == "rotation_quaternion":                       # keep the sign convention of the old key (q and -q are the same rotation)
                    old = np.array([A.fcurves.find('pose.bones["%s"].%s' % (bn, dp), index=k).evaluate(fr) if A.fcurves.find('pose.bones["%s"].%s' % (bn, dp), index=k) else np.nan for k in range(4)])
                    if not np.isnan(old).any() and (old * new).sum() < 0:
                        new = -new
                for k in range(n):
                    fc = A.fcurves.find('pose.bones["%s"].%s' % (bn, dp), index=k)
                    if fc is None:
                        skipped.add((bn, dp)); continue
                    kp = [q for q in fc.keyframe_points if abs(q.co[0] - fr) < 1e-6]
                    if not kp:
                        skipped.add((bn, dp, "nokey")); continue
                    v = float(new[k]); q = kp[0]
                    if abs(q.co[1] - v) > 1e-7:
                        d = v - q.co[1]; q.co[1] = v; q.handle_left[1] += d; q.handle_right[1] += d; nset += 1
    for A in acts.values():
        for fc in A.fcurves:
            fc.update()
    print("keyframe values changed: %d; skipped channels: %s" % (nset, sorted(skipped)[:10]))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a.out or a.blend))


if __name__ == "__main__":
    main()
