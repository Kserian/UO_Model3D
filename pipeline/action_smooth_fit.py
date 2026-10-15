"""Re-fit of the rotation keys of ONE action with a smoothness term in time, against the ORIGINAL body frames (5 directions at once).

    python action_smooth_fit.py IN.blend OUT.json --action 11 [--stages torso,head,armR,armL] [--sweeps 2]   (env LAMBDA, EDGE_W, MAXFEV, TOL)
    python apply_smooth_keys.py IN.blend OUT.blend a.json,b.json,...                                         (writes the keys; save with bpy 4.2)

Why: the poses were fitted frame by frame (arm_joint_fit.py, ...) without any link between neighbouring frames. Parts the silhouette hardly shows (twist of a limb,
rotation of the round head, the hand) then followed the 1-px noise of the sprite outline and zig-zag from frame to frame (10-50 deg); items rigid on the head or
the hand jump. Here every frame is fitted again (Gauss-Seidel sweeps) with   cost = (1 - IoU) + EDGE_W * (>= 2 px errors) + LAMBDA * sum angle(q_i, mid(q_i-1, q_i+1))^2
over the bones of the stage, starting from the current keys; a frame is kept only if its silhouette cost does not rise by more than TOL (no worse fit to the original).
Loops (walk, run, idle, mounted walk / run / stand) wrap, the ends of one-shot actions stay. Output: the new local rotation quaternions per bone and frame.
Needs: numpy scipy pillow "bpy==4.2.*".
"""
import sys, os, json
import numpy as np
import bpy
from mathutils import Quaternion
from scipy.optimize import minimize
from scipy.ndimage import distance_transform_edt
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from body_part_raster import raster, CW, CH, STEP
from arm_refit import setup, ROOT, rotvec
from arm_joint_fit import horse_masks

LOOP = {0, 1, 2, 3, 4, 5, 6, 7, 8, 15, 23, 24, 25}
LAMBDA, EDGE_W = float(os.environ.get("LAMBDA", 0.07)), float(os.environ.get("EDGE_W", 1.0))
MAXFEV, TOL = int(os.environ.get("MAXFEV", 150)), float(os.environ.get("TOL", 0.002))
STAGES = {"torso": ["spine", "chest", "neck"], "head": ["head"],
          "armR": ["clavicle.R", "upper_arm.R", "forearm.R", "hand.R"], "armL": ["clavicle.L", "upper_arm.L", "forearm.L", "hand.L"]}


def angle(a, b):
    d = abs(a.dot(b)); return 2 * np.arccos(min(1.0, d))


def main():
    a = sys.argv[1:]
    blend, out = os.path.abspath(a.pop(0)), os.path.abspath(a.pop(0))
    o = {"--action": "11", "--stages": "torso,head,armR,armL", "--sweeps": "2"}
    while a: k = a.pop(0); o[k] = a.pop(0)
    aid, sweeps, stages = int(o["--action"]), int(o["--sweeps"]), o["--stages"].split(",")
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc = bpy.context.scene
    rig, body = bpy.data.objects["UO_Rig"], bpy.data.objects["UO_Body"]; P = rig.pose.bones
    sc.camera = bpy.data.objects["UO_Camera"]; setup(sc)
    act = next(x for x in bpy.data.actions if x.get("uo_action") == aid); rig.animation_data.action = act
    n = int(act["uo_frames"]); loop = aid in LOOP
    ORIG = [{d: np.array(Image.open(os.path.join(ROOT, "client/body_0x190_frames/frames/%s/dir%d/%02d.png" % (act.name, d, i))).convert("RGBA"))[..., 3] > 0 for d in range(5)} for i in range(n)]
    HORSE = [horse_masks(aid, i) for i in range(n)]
    allb = sorted({b for s in stages for b in STAGES[s]})
    # current keys, read from the pose at each frame
    Q = {b: [] for b in allb}
    for i in range(n):
        sc.frame_set(1 + i * STEP)
        for b in allb: Q[b].append(Quaternion(P[b].rotation_quaternion))
    bpy.context.view_layer.update()

    def sil_cost(i):
        sc.frame_set(1 + i * STEP)
        for b in allb: P[b].rotation_quaternion = Q[b][i]
        horse, HM = HORSE[i]
        c = 0.0
        for d in range(5):
            rig["uo_direction"] = d; rig.update_tag(); body.update_tag(); bpy.context.view_layer.update()
            dg = bpy.context.evaluated_depsgraph_get(); cam = sc.camera.evaluated_get(dg)
            Pm, Vm = np.array(cam.calc_matrix_camera(dg, x=CW, y=CH)), np.array(cam.matrix_world.inverted())
            lab, depth = raster(body, dg, Pm, Vm, None)
            if horse is not None and d in HM:
                hl, hd = raster(horse, dg, Pm, Vm, None); lab[(hl >= 0) & (hd < depth) & HM[d]] = -1
            s, b = lab >= 0, ORIG[i][d]
            u = max((s | b).sum(), 1)
            c += 1 - (s & b).sum() / u
            if EDGE_W:
                dd = np.where(s & ~b, distance_transform_edt(~b), distance_transform_edt(~s))
                c += EDGE_W * ((s ^ b) & (dd >= 2)).sum() / u
        return c / 5

    def prior(i, bones):
        if n < 3 or (not loop and i in (0, n - 1)): return 0.0
        p = 0.0
        for b in bones:
            mid = Q[b][(i - 1) % n].slerp(Q[b][(i + 1) % n], 0.5)
            p += angle(Q[b][i], mid) ** 2
        return LAMBDA * p

    def zigzag(bones):
        idx = range(n) if loop else range(1, n - 1)
        return float(np.degrees(np.mean([angle(Q[b][i], Q[b][(i - 1) % n].slerp(Q[b][(i + 1) % n], 0.5)) for b in bones for i in idx]))) if n >= 3 else 0.0

    log = []
    for sw in range(sweeps):
        for st in stages:
            bones = STAGES[st]
            for i in (range(n) if loop else range(1, n - 1)):
                base = [Quaternion(Q[b][i]) for b in bones]
                c0 = sil_cost(i); f0 = c0 + prior(i, bones)

                def f(x):
                    for k, b in enumerate(bones): Q[b][i] = base[k] @ rotvec(x[3 * k:3 * k + 3])
                    return sil_cost(i) + prior(i, bones)
                r = minimize(f, np.zeros(3 * len(bones)), method="Powell", options={"xtol": 1e-2, "ftol": 1e-4, "maxfev": MAXFEV})
                for k, b in enumerate(bones): Q[b][i] = base[k] @ rotvec(r.x[3 * k:3 * k + 3])
                c1 = sil_cost(i)
                if c1 > c0 + TOL or r.fun >= f0:               # no better overall, or a worse silhouette: keep the old keys
                    for k, b in enumerate(bones): Q[b][i] = base[k]
                    c1 = c0
                log.append((sw, st, i, round(c0, 4), round(c1, 4)))
                print("sweep %d %s frame %d sil %.4f -> %.4f" % (sw, st, i, c0, c1), flush=True)
            print("ZIGZAG after %s: %s" % (st, {b: round(zigzag([b]), 1) for b in bones}), flush=True)
    json.dump({"action": aid, "loop": loop, "lambda": LAMBDA, "keys": {b: [list(q) for q in Q[b]] for b in allb}, "log": log}, open(out, "w"))


if __name__ == "__main__":
    main()
