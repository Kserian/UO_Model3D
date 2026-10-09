"""Global search for the pose of one arm of the UO rig against the ORIGINAL body frames (5 directions at once): direction of the upper arm (80 on the sphere),
roll about its axis (6), elbow flexion (20-FLEX_MAX deg, hinge about the local X of the forearm), then a local refinement. Clavicle and hand keep the old key.
Objective: 1 - IoU of the pure-3D body silhouette vs the sprite over 5 directions, + the same above the shoulder line (TOP rows).

    python arm_grid.py ../model/UO_Body_0x190.blend OUT.json --action 17 --side L --frames 1,2,3 [--apply-to NEW.blend]

arm_refit.py (local search) got stuck in the forearm curling over the head; a silhouette does not fix the elbow flexion, so the search is bounded by
FLEX_MAX (default 120, env) and the best of the whole sphere is taken. OUT.json: old / new quaternions and costs per frame (same layout as arm_refit.py).
"""
import sys, os, json
import numpy as np
import bpy
from mathutils import Quaternion, Vector, Matrix
from scipy.optimize import minimize
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from body_part_raster import raster, CW, CH, CANCH, STEP
from arm_refit import setup, ROOT, TOP, TOP_W

FLEX_MAX = float(os.environ.get("FLEX_MAX", 120)); NDIR = int(os.environ.get("NDIR", 80))


def main():
    args = sys.argv[1:]
    blend, out = os.path.abspath(args.pop(0)), os.path.abspath(args.pop(0))
    opt = {"--action": "17", "--side": "L", "--frames": "1"}
    while args:
        f = args.pop(0); opt[f] = args.pop(0)
    act_id, side, frames = int(opt["--action"]), opt["--side"], [int(x) for x in opt["--frames"].split(",")]
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc = bpy.context.scene
    rig, body = bpy.data.objects["UO_Rig"], bpy.data.objects["UO_Body"]
    sc.camera = bpy.data.objects["UO_Camera"]; setup(sc)
    act = next(a for a in bpy.data.actions if a.get("uo_action") == act_id)
    rig.animation_data.action = act
    chain = ["clavicle", "upper_arm", "forearm", "hand"]
    pb = {c: rig.pose.bones["%s.%s" % (c, side)] for c in chain}
    ORIG = {(d, i): np.array(Image.open(os.path.join(ROOT, "client/body_0x190_frames/frames/%s/dir%d/%02d.png" % (act.name, d, i))).convert("RGBA"))[..., 3] > 0
            for d in range(5) for i in frames}

    def cost(i):
        c = 0.0
        for d in range(5):
            rig["uo_direction"] = d; rig.update_tag(); body.update_tag(); bpy.context.view_layer.update()
            dg = bpy.context.evaluated_depsgraph_get(); cam = sc.camera.evaluated_get(dg)
            lab, _ = raster(body, dg, np.array(cam.calc_matrix_camera(dg, x=CW, y=CH)), np.array(cam.matrix_world.inverted()), None)
            a, b = lab >= 0, ORIG[(d, i)]
            c += 1 - (a & b).sum() / max((a | b).sum(), 1)
            a, b = a[:TOP], b[:TOP]; c += TOP_W * (1 - (a & b).sum() / max((a | b).sum(), 1))
        return c / 5

    def set_arm(az, el, roll, flex, head):
        d = Vector((np.cos(el) * np.cos(az), np.cos(el) * np.sin(az), np.sin(el)))
        ref = Vector((0, 0, 1)) if abs(d.z) < 0.95 else Vector((1, 0, 0))
        x = d.cross(ref).normalized(); x = Quaternion(d, roll) @ x
        z = x.cross(d).normalized()
        m = Matrix(((x.x, d.x, z.x, head.x), (x.y, d.y, z.y, head.y), (x.z, d.z, z.z, head.z), (0, 0, 0, 1)))
        pb["upper_arm"].matrix = m                       # armature space
        bpy.context.view_layer.update()
        pb["forearm"].rotation_quaternion = Quaternion((1, 0, 0), flex)

    phi = np.pi * (3 - 5 ** 0.5)
    dirs = [(phi * k % (2 * np.pi), np.arcsin(1 - 2 * (k + 0.5) / NDIR)) for k in range(NDIR)]
    results = {}
    for i in frames:
        sc.frame_set(1 + i * STEP); rig.update_tag(); bpy.context.view_layer.update()
        key = {c: [round(v, 5) for v in pb[c].rotation_quaternion] for c in chain}
        head = Vector(pb["upper_arm"].head)
        c_old = cost(i)
        best = (9, None); grid = []
        for az, el in dirs:
            for roll in np.radians([0, 60, 120, 180, 240, 300]):
                for fl in np.radians([20, 50, 80, 110]):
                    if np.degrees(fl) > FLEX_MAX: continue
                    set_arm(az, el, roll, fl, head); c = cost(i); grid.append((c, az, el, roll, fl))
        grid.sort()
        print(" frame", i, "grid best", [round(g[0], 4) for g in grid[:5]], "old", round(c_old, 4), flush=True)
        fin = []
        for g in grid[:4]:
            f = lambda p: (set_arm(p[0], p[1], p[2], min(max(p[3], 0.0), np.radians(FLEX_MAX)), head), cost(i))[1] + 3 * max(0, p[3] - np.radians(FLEX_MAX)) + 3 * max(0, -p[3])
            r = minimize(f, np.array(g[1:]), method="Powell", options={"xtol": 1e-2, "ftol": 1e-4, "maxfev": 150})
            fin.append((r.fun, r.x))
        fin.sort(key=lambda t: t[0]); fun, p = fin[0]
        set_arm(p[0], p[1], p[2], min(max(p[3], 0.0), np.radians(FLEX_MAX)), head)
        new = {c: [round(v, 5) for v in pb[c].rotation_quaternion] for c in chain}
        results[i] = {"new": new, "old": key, "cost_new": float(fun), "cost_old": float(c_old), "flex_new_deg": float(np.degrees(p[3])), "top": [[round(g[0], 4), round(np.degrees(g[4]))] for g in grid[:8]]}
        print("FRAME", i, "old %.4f -> new %.4f (flex %.0f deg)" % (c_old, fun, np.degrees(p[3])), flush=True)
    json.dump({"action": act_id, "side": side, "frames": results}, open(out, "w"), indent=1)


if __name__ == "__main__":
    main()
