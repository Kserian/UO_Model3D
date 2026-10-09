"""Fit of the hand and finger pose of one UO action to the ORIGINAL body frames (5 directions at once), left hand = mirror of the right (as arm_sym_fit.py).

    python hand_fit.py IN.blend OUT.json --action 17 --frame 2          (env NRAND, SIG, MAXFEV)
    python arm_sym_fit.py IN.blend OUT.blend --action 17 --apply a.json,b.json,...   (writes the keys; the .blend is saved with bpy 4.2)

Parameters of the right hand (the left one is its mirror, q -> (w, x, -y, -z)): hand rotation (3, rotation vector on the key), hand scale (uniform + along the bone, 2), thumb: base rotation (3) + flexion of the
two outer joints (2), fingers 2-5: flexion (about the local X of the finger bones = the curl axis, joints 1:2:3 = 1:1:0.8) and spread (about the local Z of the first joint) (2 each).
Objective: (1 - IoU of the pure-3D body silhouette vs the sprite) + EDGE_W * (1 - F-score of the outline / depth-jump pixels of the model vs the dark pixels of the sprite), counted only in discs (HAND_R px) around both hands (projected head / tail of the hand bones), summed over
5 directions; small prior on the parameters. Arms, torso and legs are not touched. See docs/qa/elbow_spell.md.
Needs: pip install numpy scipy pillow "bpy==4.2.*".
"""
import sys, os, json
import numpy as np
import bpy
from mathutils import Quaternion, Vector
from scipy.optimize import minimize
from scipy.ndimage import binary_dilation, binary_erosion
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from body_part_raster import raster, CW, CH, CANCH, STEP
from arm_refit import setup, ROOT, rotvec

NRAND, MAXFEV, SIG = int(os.environ.get("NRAND", 3)), int(os.environ.get("MAXFEV", 1500)), float(os.environ.get("SIG", 0.3))
HAND_R = float(os.environ.get("HAND_R", 11))
EDGE_W, DARK, DZ = float(os.environ.get("EDGE_W", 1.0)), float(os.environ.get("DARK", 70)), float(os.environ.get("DZ", 0.03))
JW = (1.0, 1.0, 0.8)


def mirror_q(q): return Quaternion((q[0], q[1], -q[2], -q[3]))


def main():
    a = sys.argv[1:]
    blend, out = os.path.abspath(a.pop(0)), os.path.abspath(a.pop(0))
    o = {"--action": "17", "--frame": "0"}
    while a: k = a.pop(0); o[k] = a.pop(0)
    aid, frame = int(o["--action"]), int(o["--frame"])
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc = bpy.context.scene
    rig, body = bpy.data.objects["UO_Rig"], bpy.data.objects["UO_Body"]; P = rig.pose.bones
    sc.camera = bpy.data.objects["UO_Camera"]; setup(sc)
    act = next(x for x in bpy.data.actions if x.get("uo_action") == aid); rig.animation_data.action = act
    IM = {d: np.array(Image.open(os.path.join(ROOT, "client/body_0x190_frames/frames/%s/dir%d/%02d.png" % (act.name, d, frame))).convert("RGBA")) for d in range(5)}
    ORIG = {d: IM[d][..., 3] > 0 for d in range(5)}
    EDGE0 = {d: ORIG[d] & (IM[d][..., :3].astype(float).mean(2) < DARK) for d in range(5)}          # the dark outline pixels of the sprite (silhouette and the lines between fingers)
    sc.frame_set(1 + frame * STEP); rig.update_tag(); bpy.context.view_layer.update()
    names = ["hand"] + ["finger%d-%d" % (k, j) for k in range(1, 6) for j in (1, 2, 3)]
    key = {n: Quaternion(P[n + ".R"].rotation_quaternion) for n in names}
    sc0 = Vector(P["hand.R"].scale); old_scale = {s_: list(P["hand" + s_].scale) for s_ in (".L", ".R")}
    old = {n + s: list(P[n + s].rotation_quaternion) for n in names for s in (".L", ".R")}
    yy, xx = np.mgrid[0:CH, 0:CW]

    def region(d):
        m = np.zeros((CH, CW), bool); pts = []
        mw = np.array(rig.matrix_world); dg = bpy.context.evaluated_depsgraph_get(); cam = sc.camera.evaluated_get(dg)
        Pm = np.array(cam.calc_matrix_camera(dg, x=CW, y=CH)); Vm = np.array(cam.matrix_world.inverted())
        for s in ".L", ".R":
            for p in (P["hand" + s].head, P["hand" + s].tail):
                h = Pm @ Vm @ (mw @ np.array([*p, 1.0]))
                px, py = (h[0] / h[3] + 1) * 0.5 * CW, (1 - h[1] / h[3]) * 0.5 * CH
                m |= (xx + 0.5 - px) ** 2 + (yy + 0.5 - py) ** 2 <= HAND_R ** 2
        return m

    def cost():
        c = 0.0
        for d in range(5):
            rig["uo_direction"] = d; rig.update_tag(); body.update_tag(); bpy.context.view_layer.update()
            dg = bpy.context.evaluated_depsgraph_get(); cam = sc.camera.evaluated_get(dg)
            lab, depth = raster(body, dg, np.array(cam.calc_matrix_camera(dg, x=CW, y=CH)), np.array(cam.matrix_world.inverted()), None)
            r = region(d); A, B = (lab >= 0) & r, ORIG[d] & r
            c += 1 - (A & B).sum() / max((A | B).sum(), 1)
            if EDGE_W > 0:
                m = lab >= 0; dz = np.zeros(m.shape)
                for ax, sh in ((0, 1), (0, -1), (1, 1), (1, -1)):
                    dd = np.abs(depth - np.roll(depth, sh, ax)); dd[~np.isfinite(dd)] = 0; dz = np.maximum(dz, dd)
                Ea = ((m & ~binary_erosion(m)) | (m & (dz > DZ))) & r; Eb = EDGE0[d] & r
                if Ea.sum() and Eb.sum():
                    P_ = (Ea & binary_dilation(Eb)).sum() / Ea.sum(); R_ = (Eb & binary_dilation(Ea)).sum() / Eb.sum()
                    c += EDGE_W * (1 - 2 * P_ * R_ / max(P_ + R_, 1e-9))
                else: c += EDGE_W
        return c / 5

    def setfrom(x):
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
        sc_ = Vector(sc0)
        sc_ = Vector((sc_.x * np.exp(x[16]), sc_.y * np.exp(x[16] + x[17]), sc_.z * np.exp(x[16])))
        P["hand.R"].scale = sc_; P["hand.L"].scale = sc_

    n = 18
    def f(x):
        pen = 0.6 * float(np.sum(np.square(x[16:18]))) + 0.01 * float(np.sum(np.square(x[:8]))) + 0.002 * float(np.sum(np.square(x[8:16:2]))) + 0.03 * float(np.sum(np.square(x[9:16:2])))
        pen += 3 * float(np.sum(np.maximum(0, np.abs(x[6:8]) - 1.6))) + 3 * float(np.sum(np.maximum(0, np.abs(x[8:16:2]) - 1.7))) + 3 * float(np.sum(np.maximum(0, np.abs(x[9:16:2]) - 0.7)))
        setfrom(x); return cost() + pen

    setfrom(np.zeros(n)); c_old = cost()
    rng = np.random.default_rng(frame); best = None
    starts = [np.zeros(n)]
    # global search of the hand orientation (roll about the forearm axis, wrist flexion, deviation): the local search sits in the key's basin
    def qrv(q):
        ax, an = q.to_axis_angle(); return np.array(ax) * an
    grid = []
    for roll in np.radians([-90, -60, -30, 0, 30, 60, 90]):
        for fl in np.radians([-40, -20, 0, 20, 40]):
            for dev in np.radians([-20, 0, 20]):
                x = np.zeros(n); x[0:3] = qrv(Quaternion((0, 1, 0), roll) @ Quaternion((1, 0, 0), fl) @ Quaternion((0, 0, 1), dev))
                setfrom(x); grid.append((cost(), tuple(x)))
    grid.sort(key=lambda t: t[0])
    print(" frame", frame, "hand-orientation grid best", [round(g[0], 4) for g in grid[:4]], "key", round(c_old, 4), flush=True)
    for g in grid[:1]: starts.append(np.array(g[1]))
    for f0 in (0.7, 1.2):                                  # closed hand: the original casting hands are blocky fists, an open hand tapers to a point
        x = np.zeros(n); x[8:16:2] = f0; x[6:8] = (0.5 * f0, 0.7 * f0); starts.append(x)
    claw = np.zeros(n); claw[9:16:2] = [-0.25, -0.1, 0.1, 0.25]; starts.append(claw)
    for _ in range(NRAND): starts.append(rng.normal(0, SIG, n))
    for k, xs in enumerate(starts):
        r = minimize(f, xs, method="Powell", options={"xtol": 1e-2, "ftol": 1e-4, "maxfev": MAXFEV})
        print(" frame", frame, "start", k, "cost %.4f" % r.fun, flush=True)
        if best is None or r.fun < best.fun: best = r
    setfrom(best.x); c_new = cost()
    chg = {n_: {"rotation_quaternion": list(P[n_].rotation_quaternion)} for n_ in old if np.abs(np.array(P[n_].rotation_quaternion) - old[n_]).max() > 1e-9}
    for s_ in (".L", ".R"): chg.setdefault("hand" + s_, {})["scale"] = list(P["hand" + s_].scale)
    print("FRAME", frame, "hand-region IoU-cost: old %.4f -> fitted %.4f" % (c_old, c_new), flush=True)
    json.dump({"action": aid, "frame": frame, "cost_old": c_old, "cost_fit": c_new, "x": list(map(float, best.x)), "channels": chg}, open(out, "w"), indent=1)


if __name__ == "__main__":
    main()
