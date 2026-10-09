"""Joint fit of BOTH arms (clavicle, upper arm, forearm hinge + twist, hand) and optionally the upper torso (spine / chest free rotation) of one frame of a UO action against the
ORIGINAL body frames, 5 directions at once. Unlike arm_sym_fit.py the arms are independent (death / fall actions are not symmetric) and unlike arm_grid.py / arm_refit.py the
other arm is fitted too (a fit of one arm with the other one wrong only moves the error).

    python arm_joint_fit.py IN.blend OUT.json --action 21 --frame 4 [--torso 0|1] [--flex 145] (env NRAND, MAXFEV, TORSO_PRIOR, TOP_W); mounted frames: the horse hides the body as in body_part_raster.py
    python arm_sym_fit.py IN.blend OUT.blend --action 21 --apply a.json,b.json                 (writes the keys, same layout; save with bpy 4.2)

Objective: as arm_sym_fit.py (1 - IoU whole + above TOP rows, mean of 5 directions) + small priors (elbow flex 0..FLEX, rotations near the key); starts: the key, the key with
the elbows bent differently, random arm directions. See docs/qa/arm_poses.md.  Needs: numpy scipy pillow "bpy==4.2.*".
"""
import sys, os, json
import numpy as np
import bpy
from mathutils import Quaternion, Vector, Matrix
from scipy.optimize import minimize
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from body_part_raster import raster, CW, CH, CANCH, STEP
from arm_refit import setup, ROOT, TOP, rotvec

NRAND, MAXFEV = int(os.environ.get("NRAND", 6)), int(os.environ.get("MAXFEV", 1500))
TOP_W = float(os.environ.get("TOP_W", 1.0))           # weight of the rows above the shoulder line (arm_refit.py: 1.0)
CHAIN = ["clavicle", "upper_arm", "forearm", "hand"]


def horse_masks(aid, frame):
    """horse object of a mounted frame and its sprite masks per direction (same data as body_part_raster.py); (None, {}) when not mounted"""
    import base64, zlib
    h = bpy.data.objects.get("Horse_a%d_f%d" % (aid, frame))
    if h is None or "uo_horse_masks.json" not in bpy.data.texts:
        return None, {}
    h.hide_viewport = h.hide_render = False
    HM = {}
    for k, v in json.loads(bpy.data.texts["uo_horse_masks.json"].as_string())["masks"].items():
        a, f, d = (int(x) for x in k.split(","))
        if (a, f) != (aid, frame): continue
        bits = np.unpackbits(np.frombuffer(zlib.decompress(base64.b64decode(v)), np.uint8))[:120 * 136].reshape(120, 136).astype(bool)
        m = np.zeros((CH, CW), bool); m[CANCH[1] - 86:CANCH[1] - 86 + 120, CANCH[0] - 68:CANCH[0] - 68 + 136] = bits
        HM[d] = m
    return h, HM


def main():
    a = sys.argv[1:]
    blend, out = os.path.abspath(a.pop(0)), os.path.abspath(a.pop(0))
    o = {"--action": "21", "--frame": "4", "--torso": "0", "--flex": "145"}
    while a: k = a.pop(0); o[k] = a.pop(0)
    aid, frame, torso, FLEX = int(o["--action"]), int(o["--frame"]), int(o["--torso"]), np.radians(float(o["--flex"]))
    tprior = float(os.environ.get("TORSO_PRIOR", 0.05))
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc = bpy.context.scene
    rig, body = bpy.data.objects["UO_Rig"], bpy.data.objects["UO_Body"]; P = rig.pose.bones
    sc.camera = bpy.data.objects["UO_Camera"]; setup(sc)
    act = next(x for x in bpy.data.actions if x.get("uo_action") == aid); rig.animation_data.action = act
    ORIG = {d: np.array(Image.open(os.path.join(ROOT, "client/body_0x190_frames/frames/%s/dir%d/%02d.png" % (act.name, d, frame))).convert("RGBA"))[..., 3] > 0 for d in range(5)}
    sc.frame_set(1 + frame * STEP); rig.update_tag(); bpy.context.view_layer.update()

    horse, HM = horse_masks(aid, frame)

    def cost():
        c = 0.0
        for d in range(5):
            rig["uo_direction"] = d; rig.update_tag(); body.update_tag(); bpy.context.view_layer.update()
            dg = bpy.context.evaluated_depsgraph_get(); cam = sc.camera.evaluated_get(dg)
            Pm, Vm = np.array(cam.calc_matrix_camera(dg, x=CW, y=CH)), np.array(cam.matrix_world.inverted())
            lab, depth = raster(body, dg, Pm, Vm, None)
            if horse is not None and d in HM:           # mounted: the horse hides what is behind it, clipped to its sprite (as body_part_raster.py)
                hl, hd = raster(horse, dg, Pm, Vm, None)
                lab[(hl >= 0) & (hd < depth) & HM[d]] = -1
            s, b = lab >= 0, ORIG[d]
            c += 1 - (s & b).sum() / max((s | b).sum(), 1)
            s, b = s[:TOP], b[:TOP]; c += TOP_W * (1 - (s & b).sum() / max((s | b).sum(), 1))
        return c / 5

    key = {(b, s): Quaternion(P["%s.%s" % (b, s)].rotation_quaternion) for b in CHAIN for s in "LR"}
    tkey = {b: Quaternion(P[b].rotation_quaternion) for b in ("spine", "chest")}
    old = {n: [list(P[n].rotation_quaternion), list(P[n].scale), list(P[n].location)] for n in P.keys()}
    NA = 11

    def setarm(s, x):
        # x: 3 upper arm rotvec, flex, twist, 3 hand rotvec, 3 clavicle rotvec
        P["clavicle." + s].rotation_quaternion = key[("clavicle", s)] @ rotvec(x[8:11])
        P["upper_arm." + s].rotation_quaternion = key[("upper_arm", s)] @ rotvec(x[0:3])
        P["forearm." + s].rotation_quaternion = Quaternion((1, 0, 0), x[3]) @ Quaternion((0, 1, 0), x[4])
        P["hand." + s].rotation_quaternion = key[("hand", s)] @ rotvec(x[5:8])

    def pen_arm(x):
        return 5 * max(0, x[3] - FLEX) + 5 * max(0, -x[3]) + 0.004 * float(np.sum(np.square(x[[0, 1, 2, 5, 6, 7]]))) + 0.01 * x[4] ** 2 + 0.02 * float(np.sum(np.square(x[8:11])))

    def settorso(x):
        for k, b in enumerate(("spine", "chest")): P[b].rotation_quaternion = tkey[b] @ rotvec(x[3 * k:3 * k + 3])

    def f_side(x, s):
        setarm(s, x); return cost() + pen_arm(x)

    def f_all(x):
        setarm("L", x[:NA]); setarm("R", x[NA:2 * NA])
        pen = pen_arm(x[:NA]) + pen_arm(x[NA:2 * NA])
        if torso: settorso(x[2 * NA:]); pen += tprior * float(np.sum(np.square(x[2 * NA:])))
        return cost() + pen

    def x_key(fl):
        x = np.zeros(NA); x[3] = fl; return x
    rng = np.random.default_rng(frame + 100 * aid)
    xs = {}
    c_old = cost()
    print(" key cost %.4f" % c_old, flush=True)
    for s in "LR":
        other = "R" if s == "L" else "L"
        starts = [np.zeros(NA)] + [x_key(f) for f in (0.7, 1.2, 1.8)]
        for k in range(NRAND):
            x0 = np.zeros(NA); x0[0:3] = rng.normal(0, 0.9, 3); x0[3] = rng.uniform(0.3, 2.2); x0[8:11] = rng.normal(0, 0.15, 3); starts.append(x0)
        res = []
        for x0 in starts:
            r = minimize(f_side, x0, args=(s,), method="Powell", options={"xtol": 1e-2, "ftol": 1e-3, "maxfev": MAXFEV})
            res.append((r.fun, r.x))
        res.sort(key=lambda t: t[0]); xs[s] = res
        print(" side", s, "best", [round(t[0], 4) for t in res[:4]], "flex", [round(float(np.degrees(t[1][3]))) for t in res[:4]], flush=True)
        setarm(s, res[0][1])             # the next side is fitted with this one in place
    # joint polish from the best 2 x 2 combinations
    best = None
    for i in range(2):
        for j in range(2):
            x0 = np.r_[xs["L"][i][1], xs["R"][j][1], np.zeros(6 if torso else 0)]
            r = minimize(f_all, x0, method="Powell", options={"xtol": 1e-2, "ftol": 1e-4, "maxfev": 2 * MAXFEV})
            print(" joint", i, j, "cost %.4f" % r.fun, flush=True)
            if best is None or r.fun < best.fun: best = r
    f_all(best.x)
    if best.fun > c_old:                 # never worse than the key: keep it (x = 0 is not the key: the forearm is set absolutely)
        for n_, (q, s_, l) in old.items(): P[n_].rotation_quaternion = q
    c_new = cost()
    chg = {}
    for n_, (q, s_, l) in old.items():
        qn, sn, ln = list(P[n_].rotation_quaternion), list(P[n_].scale), list(P[n_].location)
        if np.abs(np.array(qn) - q).max() > 1e-9: chg[n_] = {"rotation_quaternion": qn}
    el = {s: float(np.degrees(best.x[k * NA + 3])) for k, s in enumerate("LR")}
    print("FRAME", frame, "cost old %.4f -> fitted %.4f, elbows L %.0f R %.0f" % (c_old, c_new, el["L"], el["R"]), flush=True)
    json.dump({"action": aid, "frame": frame, "torso": torso, "cost_old": c_old, "cost_fit": c_new, "elbow_deg": el, "channels": chg}, open(out, "w"), indent=1)


if __name__ == "__main__":
    main()
