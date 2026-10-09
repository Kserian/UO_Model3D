"""Refit one arm (upper arm + forearm rotation) in some frames of a UO action to the original body frames, all 5 directions at once.

    python pose_refit_arm.py IN.blend OUT.blend --action 17 --frames 1,2,3,4 --side L [--wrist-up] [--maxfev 300] [--starts 6]

Why: in the area spell (action 17) frames 1-4 the left elbow of the rig went up over the head and the forearm hung down from it (wrist 30 cm below the elbow), while in
the original frames both hands are up; the silhouette of one direction can be matched by either, the five together cannot (docs/qa/jedi_tunic.md).
The rotations are changed on top of the keyed ones (rotation vectors in the bone's own space) to get the best mean silhouette IoU against the original frames
(pixel-centre raster of the 3D body, body_part_raster.py set-up), started from the keyed pose and from the mirror of the other arm; --wrist-up adds a penalty while the
wrist is below the elbow. Prints the IoU per frame before / after; only the given frames' keys of this arm change.
"""
import sys, os, argparse
import numpy as np
import bpy
from mathutils import Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import body_part_qa                                                 # noqa: E402  (originals())

CW, CH, CANCH = 145, 133, (75, 92)
STEP = 3


def raster_mask(co, tri, Pm, Vm):
    """pixel-centre coverage of the triangles (world co) through the camera (Pm, Vm)"""
    hv = np.c_[co, np.ones(len(co))] @ Vm.T
    h = hv @ Pm.T; ndc = h[:, :2] / h[:, 3:4]
    P = np.stack([(ndc[:, 0] + 1) * 0.5 * CW, (1 - ndc[:, 1]) * 0.5 * CH], 1)[tri]
    img = np.zeros((CH, CW), bool)
    mn = np.floor(P.min(1)).astype(int); mx = np.ceil(P.max(1)).astype(int)
    A, B, C = P[:, 0], P[:, 1], P[:, 2]
    den = (B[:, 1] - C[:, 1]) * (A[:, 0] - C[:, 0]) + (C[:, 0] - B[:, 0]) * (A[:, 1] - C[:, 1])
    ok = np.abs(den) > 1e-12; size = np.clip(mx - mn, 0, 16)
    for dy in range(int(size[:, 1].max(initial=0)) + 1):
        for dx in range(int(size[:, 0].max(initial=0)) + 1):
            t = np.nonzero(ok & (dx <= size[:, 0]) & (dy <= size[:, 1]))[0]
            px_ = mn[t, 0] + dx; py_ = mn[t, 1] + dy; cx, cy = px_ + 0.5, py_ + 0.5
            l0 = ((B[t, 1] - C[t, 1]) * (cx - C[t, 0]) + (C[t, 0] - B[t, 0]) * (cy - C[t, 1])) / den[t]
            l1 = ((C[t, 1] - A[t, 1]) * (cx - C[t, 0]) + (A[t, 0] - C[t, 0]) * (cy - C[t, 1])) / den[t]
            k = (l0 >= -1e-4) & (l1 >= -1e-4) & (1 - l0 - l1 >= -1e-4) & (px_ >= 0) & (py_ >= 0) & (px_ < CW) & (py_ < CH)
            img[py_[k], px_[k]] = True
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst"); ap.add_argument("--action", type=int, required=True); ap.add_argument("--frames", required=True)
    ap.add_argument("--side", default="L"); ap.add_argument("--wrist-up", action="store_true"); ap.add_argument("--maxfev", type=int, default=300); ap.add_argument("--starts", type=int, default=6)
    a = ap.parse_args(sys.argv[sys.argv.index(next(x for x in sys.argv if x.endswith(".py"))) + 1:])
    from scipy.optimize import minimize
    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(a.src))
    sc = bpy.context.scene
    rig, body = bpy.data.objects["UO_Rig"], bpy.data.objects["UO_Body"]
    sc.camera = bpy.data.objects["UO_Camera"]; cd = sc.camera.data
    cd.sensor_fit = "HORIZONTAL"; cd.ortho_scale = CW / sc.get("uo_px_per_m", 36.0); cd.shift_x = cd.shift_y = 0.0
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = CW, CH, 100

    def anchor_px():
        bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get(); cam = sc.camera.evaluated_get(dg)
        P = np.array(cam.calc_matrix_camera(dg, x=CW, y=CH)) @ np.array(cam.matrix_world.inverted()) @ np.array([0.0, 0.0, sc.get("uo_anchor_height", 0.07), 1.0])
        return np.array([(P[0] / P[3] + 1) * 0.5 * CW, (1 - P[1] / P[3]) * 0.5 * CH])

    p0 = anchor_px(); cd.shift_x = cd.shift_y = 0.01; p1 = anchor_px(); k = (p1 - p0) / 0.01
    want = np.array(CANCH, float) + (np.array(sc.get("uo_anchor_px", (68.5, 86.0))) - np.array((68, 86)))
    sh = (want - p0) / k; cd.shift_x, cd.shift_y = float(sh[0]), float(sh[1])
    bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get(); cam = sc.camera.evaluated_get(dg)
    Pm = np.array(cam.calc_matrix_camera(dg, x=CW, y=CH)); Vm = np.array(cam.matrix_world.inverted())

    act = next(x for x in bpy.data.actions if "uo_action" in x and int(x["uo_action"]) == a.action)
    rig.animation_data.action = act; rig.data.pose_position = "POSE"
    Md = []
    for d in range(5):                                              # the turn of each direction (a driver on the rig), applied to the direction-0 body in numpy
        rig["uo_direction"] = d; rig.update_tag(); bpy.context.view_layer.update()
        Md.append(np.array(rig.evaluated_get(bpy.context.evaluated_depsgraph_get()).matrix_world))
    rig["uo_direction"] = 0
    Md = [m @ np.linalg.inv(Md[0]) for m in Md]
    me = body.data; me.calc_loop_triangles()
    tri = np.array([t.vertices[:] for t in me.loop_triangles])
    O = body_part_qa.originals()
    side, other = a.side, ("R" if a.side == "L" else "L")
    bones = ("upper_arm." + side, "forearm." + side)
    fc = {(bn, i): act.fcurves.find('pose.bones["%s"].rotation_quaternion' % bn, index=i) for bn in bones + ("upper_arm." + other, "forearm." + other) for i in range(4)}

    def body_world():
        bpy.context.view_layer.update()
        ev = body.evaluated_get(bpy.context.evaluated_depsgraph_get()); m2 = ev.to_mesh()
        co = np.empty(len(m2.vertices) * 3, np.float32); m2.vertices.foreach_get("co", co)
        Mw = np.array(ev.matrix_world); ev.to_mesh_clear()
        return co.reshape(-1, 3).astype(np.float64) @ Mw[:3, :3].T + Mw[:3, 3]

    gi = [g.index for g in body.vertex_groups if g.name.split(".")[0] in ("upper_arm", "forearm", "hand") or g.name.startswith("finger")]
    gi = [i for i in gi if body.vertex_groups[i].name.endswith("." + side)]
    moving = np.zeros(len(me.vertices), bool)
    for v in me.vertices:
        if any(g.group in gi and g.weight > 0 for g in v.groups):
            moving[v.index] = True
    arm_t = moving[tri].any(1)                                          # triangles the arm moves: rastered per try; the rest of the body once per frame
    static = {}

    def score(fi):
        co = body_world(); ious = []
        for d in range(5):
            cd_ = co @ Md[d][:3, :3].T + Md[d][:3, 3]
            if (fi, d) not in static:
                static[(fi, d)] = raster_mask(cd_, tri[~arm_t], Pm, Vm)
            m = static[(fi, d)] | raster_mask(cd_, tri[arm_t], Pm, Vm); o = O[(a.action, d, fi)]
            ious.append((m & o).sum() / max((m | o).sum(), 1))
        return float(np.mean(ious))

    def set_pose(base, x):
        for j, bn in enumerate(bones):
            rv = Vector(x[3 * j:3 * j + 3]); q = base[j] @ (Quaternion(rv.normalized(), rv.length) if rv.length > 1e-9 else Quaternion())
            rig.pose.bones[bn].rotation_quaternion = q

    def wrist_drop():
        ev = rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
        return float(ev.pose.bones["forearm." + side].head.z - ev.pose.bones["hand." + side].head.z)

    for fi in [int(x) for x in a.frames.split(",")]:
        f = 1 + STEP * fi
        sc.frame_set(f); bpy.context.view_layer.update()
        base = [Quaternion([fc[(bn, i)].evaluate(f) for i in range(4)]) for bn in bones]
        mirror = [Quaternion([fc[(bn.replace("." + side, "." + other), i)].evaluate(f) * (1 if i < 2 else -1) for i in range(4)]) for bn in bones]
        x_m = np.concatenate([np.array((base[j].inverted() @ mirror[j]).to_axis_angle()[0]) * (base[j].inverted() @ mirror[j]).to_axis_angle()[1] for j in range(2)])
        act_backup = rig.animation_data.action; rig.animation_data.action = None    # the pose is set by hand while fitting
        set_pose(base, np.zeros(6)); iou0 = score(fi); drop0 = wrist_drop()

        def cost(x):
            set_pose(base, x); c = 1 - score(fi)
            if a.wrist_up:
                c += 0.5 * max(wrist_drop(), 0.0)                       # 0.05 per 10 cm of the wrist below the elbow
            return c + 0.002 * float(np.linalg.norm(x))

        best = None
        rng = np.random.default_rng(fi)
        starts = [np.zeros(6), x_m] + [x_m + rng.normal(0, 0.35, 6) for _ in range(a.starts)]   # the keyed pose, the mirror of the other arm, and tries around the mirror
        for x0 in starts:
            r = minimize(cost, x0, method="Powell", options=dict(maxfev=a.maxfev, xtol=1e-3, ftol=1e-4))
            if best is None or r.fun < best.fun:
                best = r
        set_pose(base, best.x); iou1 = score(fi); drop1 = wrist_drop()
        rig.animation_data.action = act_backup
        for j, bn in enumerate(bones):                                  # write the fitted rotation into this frame's keys
            q = rig.pose.bones[bn].rotation_quaternion.copy()
            for i in range(4):
                c = fc[(bn, i)]
                kp = next((kp for kp in c.keyframe_points if abs(kp.co[0] - f) < 0.01), None)
                if kp is None:
                    c.keyframe_points.insert(f, q[i])
                else:
                    kp.co[1] = q[i]; kp.handle_left[1] = q[i]; kp.handle_right[1] = q[i]
            for i in range(4):
                fc[(bn, i)].update()
        print("frame %d: mean IoU of 5 directions %.4f -> %.4f, wrist below the elbow %.2f -> %.2f m (%d evaluations)" % (fi, iou0, iou1, drop0, drop1, best.nfev), flush=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a.dst))
    print("saved", a.dst)
    sys.stdout.flush(); os._exit(0)


if __name__ == "__main__":
    main()
