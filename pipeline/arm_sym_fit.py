"""Symmetric fit of the arms of a UO action against the ORIGINAL body frames (5 directions at once): L arm = mirror of the R arm (arm_mirror_action.py convention), optionally the
torso: sym = spine / chest only pitch about the local X free, free = spine / chest any rotation with a small prior, keep = as in the key, upper = pelvis, spine, chest, neck, head pure pitch (no twist, no side lean), legs keep their world orientation. One frame at a time, Powell from the key and a few perturbed starts.

    python arm_sym_fit.py IN.blend OUT.json --action 17 --frame 2 [--torso keep|sym|free|upper] [--from R]   (env NRAND, MAXFEV)
    python arm_sym_fit.py IN.blend OUT.blend --action 17 --apply a.json,b.json,...                (writes the keys of the fitted frames; save with bpy 4.2)

Objective: 1 - IoU of the pure-3D body silhouette vs the sprite over 5 directions + the same above TOP rows + a small prior; so the numbers can be compared with
`body_part_qa.py`-style IoU (whole silhouette). OUT.json: per frame the values of every changed channel and the cost before / after.
Needs: pip install numpy scipy pillow "bpy==4.2.*". See docs/qa/elbow_spell.md.
"""
import sys, os, json
import numpy as np
import bpy
from mathutils import Quaternion, Vector
from scipy.optimize import minimize
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from body_part_raster import raster, CW, CH, CANCH, STEP
from arm_refit import setup, ROOT, TOP, TOP_W, rotvec

NRAND, MAXFEV = int(os.environ.get("NRAND", 3)), int(os.environ.get("MAXFEV", 900))
CHAIN = ["clavicle", "upper_arm", "forearm", "hand"]


def find_action(aid):
    return next(a for a in bpy.data.actions if a.get("uo_action") == aid)


def mirror_q(q): return Quaternion((q[0], q[1], -q[2], -q[3]))


def fit(blend, out, aid, frame, torso, s_from):
    s_to = "L" if s_from == "R" else "R"
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc = bpy.context.scene
    rig, body = bpy.data.objects["UO_Rig"], bpy.data.objects["UO_Body"]; P = rig.pose.bones
    sc.camera = bpy.data.objects["UO_Camera"]; setup(sc)
    act = find_action(aid); rig.animation_data.action = act
    ORIG = {d: np.array(Image.open(os.path.join(ROOT, "client/body_0x190_frames/frames/%s/dir%d/%02d.png" % (act.name, d, frame))).convert("RGBA"))[..., 3] > 0 for d in range(5)}
    fingers = [n[:-2] for n in P.keys() if n.startswith("finger") and n.endswith("." + s_from)]
    sc.frame_set(1 + frame * STEP); rig.update_tag(); bpy.context.view_layer.update()

    def cost():
        c = 0.0
        for d in range(5):
            rig["uo_direction"] = d; rig.update_tag(); body.update_tag(); bpy.context.view_layer.update()
            dg = bpy.context.evaluated_depsgraph_get(); cam = sc.camera.evaluated_get(dg)
            lab, _ = raster(body, dg, np.array(cam.calc_matrix_camera(dg, x=CW, y=CH)), np.array(cam.matrix_world.inverted()), None)
            a, b = lab >= 0, ORIG[d]
            c += 1 - (a & b).sum() / max((a | b).sum(), 1)
            a, b = a[:TOP], b[:TOP]; c += TOP_W * (1 - (a & b).sum() / max((a | b).sum(), 1))
        return c / 5

    # key of the source side (rotation, scale, location) and of the torso
    src = {b: {"q": Quaternion(P["%s.%s" % (b, s_from)].rotation_quaternion), "s": Vector(P["%s.%s" % (b, s_from)].scale), "l": Vector(P["%s.%s" % (b, s_from)].location)} for b in CHAIN}
    srcf = {f: Quaternion(P["%s.%s" % (f, s_from)].rotation_quaternion) for f in fingers}
    tk = {b: Quaternion(P[b].rotation_quaternion) for b in ("spine", "chest")}
    old = {n: [list(P[n].rotation_quaternion), list(P[n].scale), list(P[n].location)] for n in P.keys()}
    EXTRA = bool(int(os.environ.get("EXTRA", 0))); pel_loc0 = Vector(P["pelvis"].location)
    TORSO = ("pelvis", "spine", "chest", "neck", "head")
    legs0 = {t: (P[t].matrix.copy(), Vector(P[t].location)) for t in ("thigh.L", "thigh.R")}      # world orientation of the legs, kept when the pelvis changes
    pitch0 = np.array([tk_q.to_euler("XYZ").x for tk_q in (Quaternion(P[b].rotation_quaternion) for b in TORSO)])

    def setfrom(x):
        # x: 3 clavicle, 3 upper arm, 3 forearm, 3 hand (rotation vectors on the key of the source arm), torso pitch spine / chest
        for k, b in enumerate(CHAIN):
            q = src[b]["q"] @ rotvec(x[3 * k:3 * k + 3])
            pf = P["%s.%s" % (b, s_from)]; pt = P["%s.%s" % (b, s_to)]
            pf.rotation_quaternion = q; pt.rotation_quaternion = mirror_q(q)
            pt.scale = src[b]["s"]; pf.scale = src[b]["s"]
            pt.location = Vector((-src[b]["l"].x, src[b]["l"].y, src[b]["l"].z)); pf.location = src[b]["l"]
        for f, q in srcf.items():
            P["%s.%s" % (f, s_from)].rotation_quaternion = q; P["%s.%s" % (f, s_to)].rotation_quaternion = mirror_q(q)
        if torso == "sym":
            for k, b in enumerate(("spine", "chest")):
                e = tk[b].to_euler("XYZ"); P[b].rotation_quaternion = Quaternion((1, 0, 0), e.x + x[12 + k])
        if EXTRA:
            P["pelvis"].location = pel_loc0 + Vector(x[17:20])
            for k, b in enumerate(("upper_arm", "forearm")):
                sc_ = src[b]["s"].copy(); sc_.y *= float(np.exp(x[20 + k]))
                P["%s.%s" % (b, s_from)].scale = sc_; P["%s.%s" % (b, s_to)].scale = sc_
        if torso == "upper":
            for k, b in enumerate(TORSO):
                P[b].rotation_quaternion = Quaternion((1, 0, 0), x[12 + k])         # local X of these bones = lateral axis: pure pitch, no twist, no side lean
            bpy.context.view_layer.update()
            for t, (m0, l0) in legs0.items():
                m = m0.copy(); m.translation = P[t].head
                P[t].matrix = m; P[t].location = l0
        elif torso == "free":
            for k, b in enumerate(("spine", "chest")):
                P[b].rotation_quaternion = tk[b] @ rotvec(x[12 + 3 * k:15 + 3 * k])

    def f(x):
        setfrom(x); return cost() + 0.003 * float(np.sum(np.square(x[:12]))) + (1.0 * float(np.sum(np.square(x[17:20]))) + 0.5 * float(np.sum(np.square(x[20:22]))) if EXTRA else 0.0) + (0.0 if torso == "upper" else (0.02 if torso == "sym" else 0.01)) * float(np.sum(np.square(x[12:]))) + (float(os.environ.get("NECK_PRIOR", 0.0)) * float(np.sum(np.square(x[15:17] - 0.5 * pitch0[3:5] * 0))) if torso == "upper" else 0.0)

    n = 18 if torso == "free" else (17 if torso == "upper" else 14)
    if EXTRA: n += 5
    x0 = np.zeros(n)
    if torso == "upper": x0[12:17] = pitch0
    c_old = cost()
    setfrom(x0); c_mir = cost()
    rng = np.random.default_rng(frame)
    best = None
    for k in range(1 + NRAND):
        xs = x0.copy() if k == 0 else rng.normal(0, float(os.environ.get("SIG", 0.35)), n) * np.r_[np.ones(12), np.full(5, 0.3), np.full(n - 17, 0.05)] + (x0 * np.r_[np.zeros(12), np.ones(n - 12)])
        r = minimize(f, xs, method="Powell", options={"xtol": 1e-2, "ftol": 1e-4, "maxfev": MAXFEV})
        print(" frame", frame, "start", k, "cost %.4f" % r.fun, flush=True)
        if best is None or r.fun < best.fun: best = r
    setfrom(best.x); c_new = cost()
    chg = {}
    for n_, (q, s, l) in old.items():
        qn, sn, ln = list(P[n_].rotation_quaternion), list(P[n_].scale), list(P[n_].location)
        if np.abs(np.array(qn) - q).max() > 1e-9 or np.abs(np.array(sn) - s).max() > 1e-9 or np.abs(np.array(ln) - l).max() > 1e-9:
            chg[n_] = {"rotation_quaternion": qn, "scale": sn, "location": ln}
    print("FRAME", frame, "torso", torso, "IoU-cost: old %.4f, mirror only %.4f, fitted %.4f" % (c_old, c_mir, c_new), flush=True)
    json.dump({"action": aid, "frame": frame, "torso": torso, "cost_old": c_old, "cost_mirror": c_mir, "cost_fit": c_new, "channels": chg}, open(out, "w"), indent=1)


def apply(blend, out, aid, jsons):
    bpy.ops.wm.open_mainfile(filepath=blend)
    act = find_action(aid)
    fc = {(c.data_path.split('"')[1], c.data_path.rsplit(".", 1)[1], c.array_index): c for c in act.fcurves if c.data_path.startswith('pose.bones["')}
    for j in jsons:
        d = json.load(open(j)); i = d["frame"]
        for name, props in d["channels"].items():
            for prop, vals in props.items():
                for k, v in enumerate(vals):
                    c = fc.get((name, prop, k))
                    if c is None: continue
                    kp = next(p for p in c.keyframe_points if abs(p.co[0] - (1 + 3 * i)) < 1e-6)
                    dv = v - kp.co[1]; kp.co[1] = v; kp.handle_left[1] += dv; kp.handle_right[1] += dv
    bpy.ops.wm.save_as_mainfile(filepath=out)
    print("saved", out)


if __name__ == "__main__":
    a = sys.argv[1:]
    blend, out = os.path.abspath(a.pop(0)), os.path.abspath(a.pop(0))
    o = {"--action": "17", "--frame": "0", "--torso": "keep", "--from": "R", "--apply": None}
    while a: k = a.pop(0); o[k] = a.pop(0)
    if o["--apply"]: apply(blend, out, int(o["--action"]), [os.path.abspath(x) for x in o["--apply"].split(",")])
    else: fit(blend, out, int(o["--action"]), int(o["--frame"]), o["--torso"], o["--from"])
