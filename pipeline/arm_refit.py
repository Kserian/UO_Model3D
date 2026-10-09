"""Local refit (Powell, random starts) of one arm of the UO rig against the ORIGINAL body frames, 5 directions at once. Experimental, see docs/qa/elbow_spell.md.

    python arm_refit.py ../model/UO_Body_0x190.blend OUT.json --action 17 --side L --frames 1,2 [--apply]   (env FLEX_MAX, NRAND, MAXFEV)

Free: clavicle, upper_arm, hand (rotation vectors on top of the key), forearm = hinge about the local X (flexion 0..FLEX_MAX) + a little twist. Objective = 1 - IoU of the
pure-3D body silhouette vs the sprite, summed over 5 directions, + the same above the shoulder line (TOP rows) + a prior. OUT.json: old / new quaternions and costs.
The .blend is only read. (Gets stuck in forearms curling over the head: arm_grid.py searches the whole sphere first.)
Needs: pip install numpy scipy pillow "bpy==4.2.*".
"""
import sys, os, json, glob
import numpy as np
import bpy
from mathutils import Quaternion, Vector
from scipy.optimize import minimize
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from body_part_raster import raster, CW, CH, CANCH, STEP

FLEX_MAX = np.radians(float(os.environ.get("FLEX_MAX", 145)))
TOP, TOP_W = 50, 1.0                    # rows above the shoulder line (px of the 145x133 canvas) weigh extra: the raised forearm / fist show there
NRAND, MAXFEV = int(os.environ.get('NRAND', 5)), int(os.environ.get('MAXFEV', 500))
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def setup(sc):
    cd = sc.camera.data
    cd.sensor_fit = "HORIZONTAL"; cd.ortho_scale = CW / sc.get("uo_px_per_m", 36.0); cd.shift_x = cd.shift_y = 0.0
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = CW, CH, 100

    def anchor_px():
        bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get(); cam = sc.camera.evaluated_get(dg)
        P = np.array(cam.calc_matrix_camera(dg, x=CW, y=CH)) @ np.array(cam.matrix_world.inverted()) @ np.array([0.0, 0.0, sc.get("uo_anchor_height", 0.07), 1.0])
        return np.array([(P[0] / P[3] + 1) * 0.5 * CW, (1 - P[1] / P[3]) * 0.5 * CH])
    p0 = anchor_px(); cd.shift_x = cd.shift_y = 0.01; p1 = anchor_px(); k = (p1 - p0) / 0.01
    want = np.array(CANCH, float) + (np.array(sc.get("uo_anchor_px", (68.5, 86.0))) - np.array((68, 86)))
    sh = (want - p0) / k; cd.shift_x, cd.shift_y = float(sh[0]), float(sh[1])
    assert np.abs(anchor_px() - want).max() < 1e-3


def rotvec(v):
    v = np.asarray(v, float); a = np.linalg.norm(v)
    return Quaternion((1, 0, 0, 0)) if a < 1e-9 else Quaternion(Vector(v / a), a)


def main():
    args = sys.argv[1:]
    blend, out = os.path.abspath(args.pop(0)), os.path.abspath(args.pop(0))
    opt = {"--action": "17", "--side": "L", "--frames": "0"}; apply = False
    while args:
        f = args.pop(0)
        if f == "--apply": apply = True          # reserved, nothing is written to the .blend
        else: opt[f] = args.pop(0)
    act_id, side, frames = int(opt["--action"]), opt["--side"], [int(x) for x in opt["--frames"].split(",")]
    other = "R" if side == "L" else "L"
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc = bpy.context.scene
    rig, body = bpy.data.objects["UO_Rig"], bpy.data.objects["UO_Body"]
    sc.camera = bpy.data.objects["UO_Camera"]; setup(sc)
    act = next(a for a in bpy.data.actions if a.get("uo_action") == act_id)
    rig.animation_data.action = act
    name = act.name
    ORIG = {}
    for d in range(5):
        for i in frames:
            p = os.path.join(ROOT, "client/body_0x190_frames/frames/%s/dir%d/%02d.png" % (name, d, i))
            ORIG[(d, i)] = np.array(Image.open(p).convert("RGBA"))[..., 3] > 0
    chain = ["clavicle", "upper_arm", "forearm", "hand"]
    pb = {c: rig.pose.bones["%s.%s" % (c, side)] for c in chain}

    def sil(i):
        res = {}
        for d in range(5):
            rig["uo_direction"] = d; rig.update_tag(); body.update_tag(); bpy.context.view_layer.update()
            dg = bpy.context.evaluated_depsgraph_get(); cam = sc.camera.evaluated_get(dg)
            lab, _ = raster(body, dg, np.array(cam.calc_matrix_camera(dg, x=CW, y=CH)), np.array(cam.matrix_world.inverted()), None)
            res[d] = lab >= 0
        return res

    def iou_cost(i):
        s = sil(i); c = 0.0
        for d in range(5):
            a, b = s[d], ORIG[(d, i)]; c += 1 - (a & b).sum() / max((a | b).sum(), 1)
            a, b = a[:TOP], b[:TOP]; c += TOP_W * (1 - (a & b).sum() / max((a | b).sum(), 1))
        return c / 5

    def flex(qf):
        q = Quaternion(qf); return 2 * np.arctan2(abs(q.x), abs(q.w))      # rotation about the local X of the forearm = elbow bend

    results = {}
    for i in frames:
        sc.frame_set(1 + i * STEP); rig.update_tag(); bpy.context.view_layer.update()
        key = {c: Quaternion(pb[c].rotation_quaternion) for c in chain}

        def apply_x(x, base):
            # x: 3 rotation vector of the upper arm (in its own frame), flexion, twist of the forearm, 3 rotation vector of the hand
            pb["clavicle"].rotation_quaternion = base["clavicle"] @ rotvec(x[8:11])
            pb["upper_arm"].rotation_quaternion = base["upper_arm"] @ rotvec(x[0:3])
            pb["forearm"].rotation_quaternion = Quaternion((1, 0, 0), x[3]) @ Quaternion((0, 1, 0), x[4])
            pb["hand"].rotation_quaternion = base["hand"] @ rotvec(x[5:8])

        def cost(x, base, ref):
            apply_x(x, base)
            fl = x[3]
            pen = 0.0
            if fl > FLEX_MAX: pen += 5 * (fl - FLEX_MAX)
            if fl < 0: pen += 5 * (-fl)
            pen += 0.004 * np.sum(np.square(x[[0, 1, 2, 5, 6, 7]])) + 0.01 * x[4] ** 2 + 0.02 * np.sum(np.square(x[8:11]))
            return iou_cost(i) + pen

        starts = []
        rng = np.random.default_rng(i)
        for f0 in (0.7, 1.2, 1.8):
            starts.append(("key", key, np.array([0, 0, 0, f0, 0, 0, 0, 0, 0, 0, 0.0])))
        for k in range(NRAND):
            x0 = np.zeros(11); x0[0:3] = rng.normal(0, 0.7, 3); x0[3] = rng.uniform(0.6, 1.9); x0[8:11] = rng.normal(0, 0.15, 3)
            starts.append(("rand%d" % k, key, x0))
        best = None
        for nm, base, x0 in starts:
            r = minimize(cost, x0, args=(base, None), method="Powell", options={"xtol": 1e-2, "ftol": 1e-3, "maxfev": MAXFEV})
            print(" frame", i, nm, "flex0 %.1f" % np.degrees(x0[3]), "->", "cost %.4f flex %.0f" % (r.fun, np.degrees(r.x[3])), flush=True)
            if best is None or r.fun < best[0]: best = (r.fun, nm, base, r.x)
        fun, nm, base, x = best
        apply_x(x, base)
        res = {c: [round(v, 5) for v in pb[c].rotation_quaternion] for c in chain}
        old = {c: [round(v, 5) for v in key[c]] for c in chain}
        # cost of the old key, for the record
        for c in chain: pb[c].rotation_quaternion = key[c]
        c_old = iou_cost(i); apply_x(x, base)
        results[i] = {"new": res, "old": old, "cost_new": float(fun), "cost_old": float(c_old), "flex_new_deg": float(np.degrees(x[3])), "start": nm}
        print("FRAME", i, "old iou-cost %.4f -> new %.4f (flex %.0f deg, start %s)" % (c_old, fun, np.degrees(x[3]), nm), flush=True)
    json.dump({"action": act_id, "side": side, "frames": results}, open(out, "w"), indent=1)


if __name__ == "__main__":
    main()
