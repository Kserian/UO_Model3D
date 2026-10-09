"""Make the left arm of a UO action the mirror image of the right arm (the game animates the two arms symmetrically in some actions, e.g. 17_spell_area).

    python arm_mirror_action.py IN.blend OUT.blend --action 17 [--frames 0,1,2,3,4,5,6] [--from R]      (OUT.blend is saved with the running bpy: use bpy 4.2)

Copies, per key of the action, from the chosen side to the other for clavicle, upper_arm, forearm, hand and the finger bones: rotation q = (w, x, -y, -z) (the rest
matrices of the L / R bones are exact mirrors M B M, M = diag(-1, 1, 1), so the local rotation mirrors this way), scale as it is, location (-x, y, z). The torso, head and legs are not touched.
Prints the error of the mirror in the chest frame (m) before saving. See docs/qa/elbow_spell.md.
"""
import sys, os
import numpy as np
import bpy
from mathutils import Quaternion

PARTS = ("clavicle", "upper_arm", "forearm", "hand")


def main():
    args = sys.argv[1:]
    src, dst = os.path.abspath(args.pop(0)), os.path.abspath(args.pop(0))
    opt = {"--action": "17", "--frames": None, "--from": "R"}
    while args:
        f = args.pop(0); opt[f] = args.pop(0)
    bpy.ops.wm.open_mainfile(filepath=src)
    rig = bpy.data.objects["UO_Rig"]; P = rig.pose.bones
    act = next(a for a in bpy.data.actions if a.get("uo_action") == int(opt["--action"]))
    s_from = opt["--from"]; s_to = "L" if s_from == "R" else "R"
    nfr = int(act["uo_frames"]); frames = list(range(nfr)) if opt["--frames"] is None else [int(x) for x in opt["--frames"].split(",")]
    bones = [n[:-2] for n in P.keys() if n.endswith("." + s_from) and (n.split(".")[0] in PARTS or n.startswith("finger"))]
    fc = {}
    for c in act.fcurves:
        if c.data_path.startswith('pose.bones["'):
            fc[(c.data_path.split('"')[1], c.data_path.rsplit(".", 1)[1], c.array_index)] = c

    def value(name, prop, k, frame):
        return fc[(name, prop, k)].evaluate(frame)

    def set_key(name, prop, k, i, v):
        c = fc[(name, prop, k)]
        kp = next(p for p in c.keyframe_points if abs(p.co[0] - (1 + 3 * i)) < 1e-6)
        d = v - kp.co[1]; kp.co[1] = v; kp.handle_left[1] += d; kp.handle_right[1] += d

    for i in frames:
        fr = 1 + 3 * i
        for b in bones:
            a, z = "%s.%s" % (b, s_from), "%s.%s" % (b, s_to)
            if (a, "rotation_quaternion", 0) in fc and (z, "rotation_quaternion", 0) in fc:
                q = [value(a, "rotation_quaternion", k, fr) for k in range(4)]
                for k, v in enumerate((q[0], q[1], -q[2], -q[3])): set_key(z, "rotation_quaternion", k, i, v)
            if (a, "scale", 0) in fc and (z, "scale", 0) in fc:
                for k in range(3): set_key(z, "scale", k, i, value(a, "scale", k, fr))
            if (a, "location", 0) in fc and (z, "location", 0) in fc:
                for k, sg in enumerate((-1, 1, 1)): set_key(z, "location", k, i, sg * value(a, "location", k, fr))
    # check in the chest frame
    rig.animation_data.action = act; rig["uo_direction"] = 0
    def joints(s):
        ch = np.array(P["chest"].matrix.inverted())
        return np.array([(ch @ np.array([*p, 1]))[:3] for p in (P["upper_arm." + s].head, P["upper_arm." + s].tail, P["forearm." + s].tail, P["hand." + s].tail)])
    for i in frames:
        bpy.context.scene.frame_set(1 + 3 * i); rig.update_tag(); bpy.context.view_layer.update()
        e = np.abs(joints("L") - joints("R") * [-1, 1, 1]).max()
        print("frame", i, "mirror error in the chest frame %.4f m" % e)
    bpy.ops.wm.save_as_mainfile(filepath=dst)
    print("saved", dst)


if __name__ == "__main__":
    main()
