"""Checks the hand poles of an item.blend made with the recipe field "hand_pole" (uo_hand_pole.py).

    python test_hand_pole.py ITEM.blend [--actions 04_stand,00_walk_unarmed,01_walk_armed] [--max-lateral 3.0] [--max-fore-aft 45] [--fist-tol 0.005]

For every pose of the actions and each pole bone it measures, in armature space (the world of the rig):
  lateral    the sideways tilt of the pole (deg, out / in): at most --max-lateral (the user's limit: a few degrees);
  fore_aft   the tilt forwards / backwards (deg): at most --max-fore-aft;
  spike      the spike must point down (z < 0 of the axis towards the spike);
  grip       distance of the pole's axis from the centre of the fist of its hand (m): at most --fist-tol (the pole goes through the hand).
Prints a table (min / max per action and pole) and a line POLE_TEST OK | FAIL; the exit code is 1 on FAIL.
"""
import argparse, math, os, subprocess, sys

if "--inside" not in sys.argv:
    ap = argparse.ArgumentParser()
    ap.add_argument("blend"); ap.add_argument("--actions", default="04_stand,00_walk_unarmed,01_walk_armed")
    ap.add_argument("--max-lateral", type=float, default=3.0); ap.add_argument("--max-fore-aft", type=float, default=45.0); ap.add_argument("--fist-tol", type=float, default=0.005)
    a = ap.parse_args()
    here = os.path.dirname(os.path.abspath(__file__))
    r = subprocess.run([sys.executable, os.path.join(here, "test_hand_pole.py"), "--inside", os.path.abspath(a.blend), a.actions, str(a.max_lateral), str(a.max_fore_aft), str(a.fist_tol)], capture_output=True, text=True)
    out = [l for l in r.stdout.splitlines() if l.startswith(("POLE", "  "))]
    print("\n".join(out) or (r.stdout + r.stderr)[-1500:])
    sys.exit(0 if any(l.startswith("POLE_TEST OK") for l in out) else 1)

import bpy
from mathutils import Vector
blend, acts, max_lat, max_fa, tol = sys.argv[sys.argv.index("--inside") + 1:][:5]
acts = acts.split(","); max_lat, max_fa, tol = float(max_lat), float(max_fa), float(tol)
bpy.ops.wm.open_mainfile(filepath=blend)
rig = bpy.data.objects["UO_Rig"]; sc = bpy.context.scene
rig.data.pose_position = "POSE"
FIST = (0.019, 0.084, 0.012)
ok = True
print("POLE %-16s %-7s %17s %17s %10s %10s" % ("action", "pole", "lateral deg", "fore-aft deg", "spike z", "grip m"))
for act_name in acts:
    act = bpy.data.actions[act_name]; rig.animation_data.action = act
    for side in "RL":
        bn = "pole." + side
        if bn not in rig.data.bones:
            continue
        lat, fa, sz, gr = [], [], [], []
        for i in range(int(act["uo_frames"])):
            sc.frame_set(1 + 3 * i); bpy.context.view_layer.update()
            B = rig.pose.bones[bn].matrix @ rig.data.bones[bn].matrix_local.inverted()
            up = B.to_3x3() @ Vector((0, 0, 1))                       # handle up (the axis of the shaft)
            s = -up.normalized()                                      # towards the spike
            sign = -1.0 if side == "R" else 1.0                       # outward
            lat.append(math.degrees(math.asin(max(-1, min(1, s.x * sign))))); fa.append(math.degrees(math.atan2(s.y, -s.z))); sz.append(s.z)
            hand = rig.pose.bones["hand." + side].matrix
            c = hand @ Vector((FIST[0] * (1 if side == "R" else -1), FIST[1], FIST[2]))
            p = B.translation + Vector((0, 0, 0)); rest = rig.data.bones[bn].head_local; g = B @ rest      # the grip point of the pole now
            d = up.normalized(); v = c - g; gr.append((v - d * v.dot(d)).length)  # distance of the fist centre from the axis
        bad = max(abs(x) for x in lat) > max_lat + 1e-6 or max(abs(x) for x in fa) > max_fa or max(sz) >= 0 or max(gr) > tol
        ok &= not bad
        print("POLE %-16s %-7s %7.1f..%-7.1f   %7.1f..%-7.1f %10.2f %10.4f %s" % (act_name, bn, min(lat), max(lat), min(fa), max(fa), max(sz), max(gr), "FAIL" if bad else ""))
print("POLE_TEST " + ("OK" if ok else "FAIL"))
sys.stdout.flush(); os._exit(0)
