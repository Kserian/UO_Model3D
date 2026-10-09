"""Hand and finger pose shared by several frames of one UO action, fitted to the ORIGINAL body frames (5 directions x all given frames at once); the left hand = mirror of the right.

    python hand_fit_joint.py IN.blend OUT_PREFIX --action 17 --frames 1,2,3,4      (env NRAND, SIG, MAXFEV, HAND_R)
    python arm_sym_fit.py IN.blend OUT.blend --action 17 --apply OUT_PREFIX_f1.json,OUT_PREFIX_f2.json,...

The finger silhouette of one frame is almost flat in the finger parameters (hand_fit.py: the per-frame fits stay within a few degrees and change sign from finger to finger, i.e. noise),
so the deltas of the finger joints (flexion / spread of fingers 2-5, thumb, wrist rotation, hand scale) are one set for all the frames given; each frame keeps its own key as the base.
Objective: mean over frames and 5 directions of 1 - IoU of the body silhouette vs the sprite inside discs (HAND_R px) around both hands. Writes one JSON per frame (same layout as hand_fit.py).
Needs: pip install numpy scipy pillow "bpy==4.2.*".
"""
import sys, os, json
import numpy as np
import bpy
from mathutils import Quaternion, Vector
from scipy.optimize import minimize
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from body_part_raster import raster, CW, CH, CANCH, STEP
from arm_refit import setup, ROOT, rotvec

NRAND, MAXFEV, SIG = int(os.environ.get("NRAND", 2)), int(os.environ.get("MAXFEV", 800)), float(os.environ.get("SIG", 0.4))
HAND_R = float(os.environ.get("HAND_R", 11))
JW = (1.0, 1.0, 0.8)


def mirror_q(q): return Quaternion((q[0], q[1], -q[2], -q[3]))


def main():
    a = sys.argv[1:]
    blend, prefix = os.path.abspath(a.pop(0)), os.path.abspath(a.pop(0))
    o = {"--action": "17", "--frames": "1,2,3,4"}
    while a: k = a.pop(0); o[k] = a.pop(0)
    aid, frames = int(o["--action"]), [int(x) for x in o["--frames"].split(",")]
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc = bpy.context.scene
    rig, body = bpy.data.objects["UO_Rig"], bpy.data.objects["UO_Body"]; P = rig.pose.bones
    sc.camera = bpy.data.objects["UO_Camera"]; setup(sc)
    act = next(x for x in bpy.data.actions if x.get("uo_action") == aid); rig.animation_data.action = act
    names = ["hand"] + ["finger%d-%d" % (k, j) for k in range(1, 6) for j in (1, 2, 3)]
    ORIG, KEY, SC0 = {}, {}, {}
    for fr in frames:
        for d in range(5):
            ORIG[(fr, d)] = np.array(Image.open(os.path.join(ROOT, "client/body_0x190_frames/frames/%s/dir%d/%02d.png" % (act.name, d, fr))).convert("RGBA"))[..., 3] > 0
        sc.frame_set(1 + fr * STEP); rig.update_tag(); bpy.context.view_layer.update()
        KEY[fr] = {n: Quaternion(P[n + ".R"].rotation_quaternion) for n in names}; SC0[fr] = Vector(P["hand.R"].scale)
    yy, xx = np.mgrid[0:CH, 0:CW]

    def region():
        m = np.zeros((CH, CW), bool)
        mw = np.array(rig.matrix_world); dg = bpy.context.evaluated_depsgraph_get(); cam = sc.camera.evaluated_get(dg)
        Pm = np.array(cam.calc_matrix_camera(dg, x=CW, y=CH)); Vm = np.array(cam.matrix_world.inverted())
        for s in ".L", ".R":
            for p in (P["hand" + s].head, P["hand" + s].tail):
                h = Pm @ Vm @ (mw @ np.array([*p, 1.0]))
                px, py = (h[0] / h[3] + 1) * 0.5 * CW, (1 - h[1] / h[3]) * 0.5 * CH
                m |= (xx + 0.5 - px) ** 2 + (yy + 0.5 - py) ** 2 <= HAND_R ** 2
        return m

    def setpose(fr, x):
        key = KEY[fr]
        q = {"hand": key["hand"] @ rotvec(x[0:3])}
        q["finger1-1"] = key["finger1-1"] @ rotvec(x[3:6])
        q["finger1-2"] = key["finger1-2"] @ Quaternion((1, 0, 0), x[6])
        q["finger1-3"] = key["finger1-3"] @ Quaternion((1, 0, 0), x[7])
        for i, k in enumerate(range(2, 6)):
            fl, sp = x[8 + 2 * i], x[9 + 2 * i]
            q["finger%d-1" % k] = key["finger%d-1" % k] @ Quaternion((1, 0, 0), fl * JW[0]) @ Quaternion((0, 0, 1), sp)
            q["finger%d-2" % k] = key["finger%d-2" % k] @ Quaternion((1, 0, 0), fl * JW[1])
            q["finger%d-3" % k] = key["finger%d-3" % k] @ Quaternion((1, 0, 0), fl * JW[2])
        for n, v in q.items():
            P[n + ".R"].rotation_quaternion = v; P[n + ".L"].rotation_quaternion = mirror_q(v)
        s0 = SC0[fr]; sv = Vector((s0.x * np.exp(x[16]), s0.y * np.exp(x[16] + x[17]), s0.z * np.exp(x[16])))
        P["hand.R"].scale = sv; P["hand.L"].scale = sv

    def cost_frame(fr, x):
        sc.frame_set(1 + fr * STEP); setpose(fr, x); c = 0.0
        for d in range(5):
            rig["uo_direction"] = d; rig.update_tag(); body.update_tag(); bpy.context.view_layer.update()
            dg = bpy.context.evaluated_depsgraph_get(); cam = sc.camera.evaluated_get(dg)
            lab, _ = raster(body, dg, np.array(cam.calc_matrix_camera(dg, x=CW, y=CH)), np.array(cam.matrix_world.inverted()), None)
            r = region(); A, B = (lab >= 0) & r, ORIG[(fr, d)] & r
            c += 1 - (A & B).sum() / max((A | B).sum(), 1)
        return c / 5

    n = 18
    def total(x): return float(np.mean([cost_frame(fr, x) for fr in frames]))
    def f(x):
        pen = 0.6 * float(np.sum(np.square(x[16:18]))) + 0.01 * float(np.sum(np.square(x[:8]))) + 0.002 * float(np.sum(np.square(x[8:16:2]))) + 0.03 * float(np.sum(np.square(x[9:16:2])))
        pen += 3 * float(np.sum(np.maximum(0, np.abs(x[6:8]) - 1.6))) + 3 * float(np.sum(np.maximum(0, np.abs(x[8:16:2]) - 1.7))) + 3 * float(np.sum(np.maximum(0, np.abs(x[9:16:2]) - 0.7)))
        return total(x) + pen

    c_old = {fr: cost_frame(fr, np.zeros(n)) for fr in frames}
    print("old cost per frame", {k: round(v, 4) for k, v in c_old.items()}, "mean %.4f" % np.mean(list(c_old.values())), flush=True)
    rng = np.random.default_rng(1); starts = [np.zeros(n)]
    for f0 in (0.7, 1.2):
        x = np.zeros(n); x[8:16:2] = f0; x[6:8] = (0.5 * f0, 0.7 * f0); starts.append(x)
    claw = np.zeros(n); claw[9:16:2] = [-0.25, -0.1, 0.1, 0.25]; starts.append(claw)
    for _ in range(NRAND): starts.append(rng.normal(0, SIG, n) * np.r_[np.ones(16), 0.1, 0.1])
    if os.environ.get("X0"):                              # no search: write a given parameter vector (e.g. a hand-made fist) for every frame
        starts = [np.array([float(v) for v in os.environ["X0"].split(",")])]; os.environ["STARTS"] = "0"; MAXFEV_ = 1
    best = None
    only = os.environ.get("STARTS")
    for k, xs in enumerate(starts):
        if only is not None and str(k) not in only.split(","): continue
        r = minimize(f, xs, method="Powell", options={"xtol": 1e-2, "ftol": 1e-4, "maxfev": (1 if os.environ.get("X0") else MAXFEV)})
        print(" start", k, "cost %.4f" % r.fun, "flex2-5", np.degrees(r.x[8:16:2]).round(0), flush=True)
        if best is None or r.fun < best.fun: best = r
    x = best.x
    for fr in frames:
        c_new = cost_frame(fr, x)
        chg = {}
        for nme in names:
            for s in ".L", ".R": chg[nme + s] = {"rotation_quaternion": list(P[nme + s].rotation_quaternion)}
        for s in ".L", ".R": chg["hand" + s]["scale"] = list(P["hand" + s].scale)
        json.dump({"action": aid, "frame": fr, "cost_old": c_old[fr], "cost_fit": c_new, "x": list(map(float, x)), "channels": chg}, open("%s_f%d.json" % (prefix, fr), "w"), indent=1)
        print("FRAME", fr, "hand-region IoU-cost: old %.4f -> fitted %.4f" % (c_old[fr], c_new), flush=True)


if __name__ == "__main__":
    main()
