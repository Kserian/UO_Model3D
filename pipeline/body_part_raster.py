"""Per-part label images of the pure 3D body, for every UO action / direction / frame (no Cycles: pixel-centre rasteriser).

    python body_part_raster.py ../model/UO_Body_0x190.blend OUT.npz [--offset dx,dy] [--actions 0,1,2]

Writes `lab` (N, 133, 145) int8 in the canvas of the ORIGINAL body frames (145x133, anchor (75,92), 36 px/m): part index per pixel,
-1 = empty or hidden by the horse (mounted actions); `key` (N, 3) = (action, dir, frame); `parts` = part names. Parts: dominant bone group of a triangle's vertices, merged
(fingers -> hand, twist bones -> limb, toe -> foot), left / right kept apart. `body_part_qa.py` compares it with the original frames.
Needs: pip install numpy "bpy==4.2.*".
"""
import sys, os
import numpy as np
import bpy

CW, CH, CANCH = 145, 133, (75, 92)     # canvas and anchor of the original UO body frames
STEP = 3                               # scene frames between two UO frames


def part_of(name):
    base, _, side = name.partition(".")
    if base.startswith("finger"):
        base = "hand"
    base = {"upper_arm_twist": "upper_arm", "forearm_twist": "forearm", "toe": "foot"}.get(base, base)
    return base + ("." + side if side else "")


def raster(ob, dg, Pm, Vm, tlab, off=(0.0, 0.0)):
    """label (tlab[triangle], or 0 when tlab is None) and camera depth of the nearest triangle per pixel, pixel-centre rule"""
    ev = ob.evaluated_get(dg); m2 = ev.to_mesh()
    co = np.empty(len(m2.vertices) * 3, np.float32); m2.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
    m2.calc_loop_triangles()
    tri = np.empty(len(m2.loop_triangles) * 3, np.int32); m2.loop_triangles.foreach_get("vertices", tri); tri = tri.reshape(-1, 3)
    Mw = np.array(ev.matrix_world); ev.to_mesh_clear()
    lt = np.zeros(len(tri), np.int8) if tlab is None else tlab
    assert len(tri) == len(lt)
    hv = np.c_[co, np.ones(len(co))] @ (Vm @ Mw).T
    h = hv @ Pm.T; ndc = h[:, :2] / h[:, 3:4]
    P = np.stack([(ndc[:, 0] + 1) * 0.5 * CW, (1 - ndc[:, 1]) * 0.5 * CH], 1)[tri] + np.array(off)
    Z = -hv[:, 2][tri]
    lab = np.full((CH, CW), -1, np.int8); depth = np.full((CH, CW), np.inf)
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
            kk = (l0 >= -1e-4) & (l1 >= -1e-4) & (1 - l0 - l1 >= -1e-4) & (px_ >= 0) & (py_ >= 0) & (px_ < CW) & (py_ < CH)
            z = l0[kk] * Z[t[kk], 0] + l1[kk] * Z[t[kk], 1] + (1 - l0[kk] - l1[kk]) * Z[t[kk], 2]
            tt, yy, xx = t[kk], py_[kk], px_[kk]
            o = np.argsort(-z)                              # far first: the nearest triangle is written last
            o = o[z[o] < depth[yy[o], xx[o]]]
            depth[yy[o], xx[o]] = z[o]; lab[yy[o], xx[o]] = lt[tt[o]]
    return lab, depth


def main():
    args = sys.argv[1:]
    blend, out = os.path.abspath(args.pop(0)), os.path.abspath(args.pop(0))
    only, OFF = None, (0.0, 0.0)
    if args and args[0] == "--offset":                      # test: shift the whole render by (dx, dy) px
        args.pop(0); OFF = tuple(float(x) for x in args.pop(0).split(","))
    if args and args[0] == "--actions":
        args.pop(0); only = {int(x) for x in args.pop(0).split(",")}
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc = bpy.context.scene
    rig, body = bpy.data.objects["UO_Rig"], bpy.data.objects["UO_Body"]
    sc.camera = bpy.data.objects["UO_Camera"]; cd = sc.camera.data
    cd.sensor_fit = "HORIZONTAL"; cd.ortho_scale = CW / sc.get("uo_px_per_m", 36.0); cd.shift_x = cd.shift_y = 0.0
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = CW, CH, 100

    def anchor_px():
        bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get(); cam = sc.camera.evaluated_get(dg)
        P = np.array(cam.calc_matrix_camera(dg, x=CW, y=CH)) @ np.array(cam.matrix_world.inverted()) @ \
            np.array([0.0, 0.0, sc.get("uo_anchor_height", 0.07), 1.0])
        return np.array([(P[0] / P[3] + 1) * 0.5 * CW, (1 - P[1] / P[3]) * 0.5 * CH])

    p0 = anchor_px(); cd.shift_x = cd.shift_y = 0.01; p1 = anchor_px(); k = (p1 - p0) / 0.01
    want = np.array(CANCH, float) + (np.array(sc.get("uo_anchor_px", (68.5, 86.0))) - np.array((68, 86)))
    sh = (want - p0) / k; cd.shift_x, cd.shift_y = float(sh[0]), float(sh[1])
    assert np.abs(anchor_px() - want).max() < 1e-3

    names = [g.name for g in body.vertex_groups]
    parts = sorted({part_of(n) for n in names}); pid = {p: i for i, p in enumerate(parts)}
    gpart = np.array([pid[part_of(n)] for n in names])
    me = body.data
    Wv = np.zeros((len(me.vertices), len(parts)))
    for v in me.vertices:
        for g in v.groups:
            Wv[v.index, gpart[g.group]] += g.weight
    me.calc_loop_triangles()
    tri0 = np.array([t.vertices[:] for t in me.loop_triangles])
    tlab = Wv[tri0].sum(1).argmax(1)

    horses = {o.name: o for o in bpy.data.objects if o.name.startswith("Horse_")}
    for o in horses.values():
        o.hide_viewport = o.hide_render = False                # hidden objects are not evaluated by the depsgraph
    HORSE = {}
    if "uo_horse_masks.json" in bpy.data.texts:
        import base64, zlib, json
        for k, v in json.loads(bpy.data.texts["uo_horse_masks.json"].as_string())["masks"].items():
            bits = np.unpackbits(np.frombuffer(zlib.decompress(base64.b64decode(v)), np.uint8))[:120 * 136].reshape(120, 136).astype(bool)
            m = np.zeros((CH, CW), bool); m[CANCH[1] - 86:CANCH[1] - 86 + 120, CANCH[0] - 68:CANCH[0] - 68 + 136] = bits
            HORSE[tuple(int(x) for x in k.split(","))] = m

    acts = sorted([a for a in bpy.data.actions if "uo_action" in a], key=lambda a: int(a["uo_action"]))
    labs, keys = [], []
    for act in acts:
        a = int(act["uo_action"])
        if only is not None and a not in only:
            continue
        rig.animation_data.action = act
        for d in range(5):
            rig["uo_direction"] = d
            for i in range(int(act["uo_frames"])):
                sc.frame_set(1 + i * STEP); rig.update_tag(); body.update_tag(); bpy.context.view_layer.update()
                dg = bpy.context.evaluated_depsgraph_get(); cam = sc.camera.evaluated_get(dg)
                Pm = np.array(cam.calc_matrix_camera(dg, x=CW, y=CH)); Vm = np.array(cam.matrix_world.inverted())
                lab, depth = raster(body, dg, Pm, Vm, tlab, OFF)
                h_ob = horses.get("Horse_a%d_f%d" % (a, i))
                hm = HORSE.get((a, i, d))
                if h_ob is not None and hm is not None:         # mounted: the horse hides what is behind it, clipped to its sprite
                    hl, hd = raster(h_ob, dg, Pm, Vm, None, OFF)
                    hide = (hl >= 0) & (hd < depth) & hm
                    lab[hide] = -1
                labs.append(lab); keys.append((a, d, i))
        print("action", a, "done", flush=True)
    np.savez_compressed(out, lab=np.array(labs), key=np.array(keys), parts=np.array(parts))


if __name__ == "__main__":
    main()
