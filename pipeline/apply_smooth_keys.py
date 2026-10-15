"""Writes the local rotation keys of action_smooth_fit.py (JSON per action) into a .blend (same key frames, 1 + 3 * frame).

    python apply_smooth_keys.py IN.blend OUT.blend a.json,b.json,...      (save with bpy 4.2)
"""
import sys, os, json
import bpy

STEP = 3


def main():
    blend, out = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    bpy.ops.wm.open_mainfile(filepath=blend)
    for path in sys.argv[3].split(","):
        d = json.load(open(path))
        act = next(x for x in bpy.data.actions if x.get("uo_action") == d["action"])
        for b, qs in d["keys"].items():
            for k in range(4):
                fc = act.fcurves.find('pose.bones["%s"].rotation_quaternion' % b, index=k)
                assert fc is not None and len(fc.keyframe_points) == len(qs), (b, k)
                for i, q in enumerate(qs):
                    kp = fc.keyframe_points[i]; assert abs(kp.co[0] - (1 + STEP * i)) < 1e-6
                    kp.co[1] = q[k]
                fc.update()
    bpy.ops.wm.save_as_mainfile(filepath=out)


if __name__ == "__main__":
    main()
