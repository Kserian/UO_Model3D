"""Per-pixel geometry of the pure 3D body for every UO frame, for the light / shadow analysis (no Cycles: pixel-centre rasteriser + BVH rays).

    python light_raster.py ../model/UO_Body_0x190.blend OUT.npz [--actions 0,1,2] [--ao-every 3]

Canvas of the ORIGINAL body frames (145x133, anchor (75,92), 36 px/m), as body_part_raster.py. For every covered pixel of every frame (mounted
actions 23-29 are left out: the horse proxy hides parts of the body) it stores, in world space (z up, camera at -y):
  frame   index into `key` (action, direction, frame)           y, x       pixel
  N       smooth normal (3)       P  position (3, m)            uv   texture coordinate (2)       part  dominant bone group (int8, `parts`)
  lit     1 = the ray from P (+ 3 mm along N) towards the UO light leaves the body without hitting it, 0 = the body shadows itself there
  ao      share of 8 hemisphere rays of 0.4 m that leave the body (255 = open); only every --ao-every-th frame, 255 elsewhere
  L       the UO light of the file (node group UO_Look, world space)
`light_data.py` joins this with the original frames.  Needs: pip install numpy "bpy==4.2.*".
"""
import sys, os
import numpy as np
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import body_part_raster as bpr

CW, CH, CANCH, STEP = bpr.CW, bpr.CH, bpr.CANCH, bpr.STEP


def raster_full(ob, dg, Pm, Vm):
    """per pixel: triangle index (-1 none), barycentric weights of corners 0 and 1, plus the evaluated vertex positions / normals / triangles"""
    ev = ob.evaluated_get(dg); m2 = ev.to_mesh()
    co = np.empty(len(m2.vertices) * 3, np.float32); m2.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
    vn = np.empty(len(m2.vertices) * 3, np.float32); m2.vertices.foreach_get("normal", vn); vn = vn.reshape(-1, 3)
    m2.calc_loop_triangles()
    tri = np.empty(len(m2.loop_triangles) * 3, np.int32); m2.loop_triangles.foreach_get("vertices", tri); tri = tri.reshape(-1, 3)
    Mw = np.array(ev.matrix_world); ev.to_mesh_clear()
    cow = (np.c_[co, np.ones(len(co))] @ Mw.T)[:, :3]; vnw = vn @ Mw[:3, :3].T
    hv = np.c_[cow, np.ones(len(co))] @ Vm.T
    h = hv @ Pm.T; ndc = h[:, :2] / h[:, 3:4]
    P = np.stack([(ndc[:, 0] + 1) * 0.5 * CW, (1 - ndc[:, 1]) * 0.5 * CH], 1)[tri]
    Z = -hv[:, 2][tri]
    tid = np.full((CH, CW), -1, np.int32); depth = np.full((CH, CW), np.inf); B0 = np.zeros((CH, CW)); B1 = np.zeros((CH, CW))
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
            tt, yy, xx, a0, a1 = t[kk], py_[kk], px_[kk], l0[kk], l1[kk]
            o = np.argsort(-z)
            o = o[z[o] < depth[yy[o], xx[o]]]
            depth[yy[o], xx[o]] = z[o]; tid[yy[o], xx[o]] = tt[o]; B0[yy[o], xx[o]] = a0[o]; B1[yy[o], xx[o]] = a1[o]
    return tid, B0, B1, cow, vnw, tri


def main():
    args = sys.argv[1:]
    blend, out = os.path.abspath(args.pop(0)), os.path.abspath(args.pop(0))
    only, ao_every = None, 3
    while args:
        f = args.pop(0)
        if f == "--actions":
            only = {int(x) for x in args.pop(0).split(",")}
        elif f == "--ao-every":
            ao_every = int(args.pop(0))
    bpy.ops.wm.open_mainfile(filepath=blend)
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
    assert np.abs(anchor_px() - want).max() < 1e-3

    ng = bpy.data.node_groups["UO_Look"]
    ldir = next(n for n in ng.nodes if n.type == "COMBXYZ")
    L = np.array([ldir.inputs[i].default_value for i in range(3)], float); L /= np.linalg.norm(L)

    names = [g.name for g in body.vertex_groups]
    parts = sorted({bpr.part_of(n) for n in names}); pid = {p: i for i, p in enumerate(parts)}
    gpart = np.array([pid[bpr.part_of(n)] for n in names])
    me = body.data
    Wv = np.zeros((len(me.vertices), len(parts)))
    for v in me.vertices:
        for g in v.groups:
            Wv[v.index, gpart[g.group]] += g.weight
    me.calc_loop_triangles()
    tri0 = np.array([t.vertices[:] for t in me.loop_triangles])
    tlab = Wv[tri0].sum(1).argmax(1).astype(np.int8)
    uvl = me.uv_layers.active.data
    tri_uv = np.array([[uvl[l].uv[:] for l in t.loops] for t in me.loop_triangles], np.float32)       # (T, 3, 2)

    rng = np.random.default_rng(1)
    hemi = rng.normal(size=(8, 3)); hemi[:, 2] = np.abs(hemi[:, 2]); hemi /= np.linalg.norm(hemi, axis=1, keepdims=True)    # +z = the normal

    acts = sorted([a for a in bpy.data.actions if "uo_action" in a], key=lambda a: int(a["uo_action"]))
    cols = {k: [] for k in ("frame", "y", "x", "N", "P", "uv", "part", "lit", "ao")}
    keys = []
    nfr = 0
    for act in acts:
        a = int(act["uo_action"])
        if 23 <= a <= 29 or (only is not None and a not in only):
            continue
        rig.animation_data.action = act
        for d in range(5):
            rig["uo_direction"] = d
            for i in range(int(act["uo_frames"])):
                sc.frame_set(1 + i * STEP); rig.update_tag(); body.update_tag(); bpy.context.view_layer.update()
                dg = bpy.context.evaluated_depsgraph_get(); cam = sc.camera.evaluated_get(dg)
                Pm = np.array(cam.calc_matrix_camera(dg, x=CW, y=CH)); Vm = np.array(cam.matrix_world.inverted())
                tid, B0, B1, cow, vnw, tri = raster_full(body, dg, Pm, Vm)
                Minv = np.array(body.evaluated_get(dg).matrix_world.inverted())           # BVHTree.FromObject works in the object's local space
                Mi = Minv[:3, :3]
                Lloc = Vector(Mi @ L)
                yy, xx = np.nonzero(tid >= 0)
                t = tid[yy, xx]; w0, w1 = B0[yy, xx], B1[yy, xx]; w2 = 1 - w0 - w1
                v = tri[t]
                P = w0[:, None] * cow[v[:, 0]] + w1[:, None] * cow[v[:, 1]] + w2[:, None] * cow[v[:, 2]]
                N = w0[:, None] * vnw[v[:, 0]] + w1[:, None] * vnw[v[:, 1]] + w2[:, None] * vnw[v[:, 2]]
                N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9)
                uv = w0[:, None] * tri_uv[t, 0] + w1[:, None] * tri_uv[t, 1] + w2[:, None] * tri_uv[t, 2]
                bvh = BVHTree.FromObject(body, dg)
                lit = np.zeros(len(t), np.uint8); ao = np.full(len(t), 255, np.uint8)
                Pl = (np.c_[P, np.ones(len(P))] @ Minv.T)[:, :3]; Nl = N @ Mi.T
                do_ao = (nfr % ao_every == 0)
                for j in range(len(t)):
                    o = Vector(Pl[j] + Nl[j] * 0.003)
                    lit[j] = 0 if bvh.ray_cast(o, Lloc, 3.0)[0] is not None else 1
                    if do_ao:
                        n = Vector(Nl[j]).normalized(); tt = n.cross(Vector((0, 0, 1)) if abs(n.z) < 0.9 else Vector((1, 0, 0))).normalized(); bb = n.cross(tt)
                        free = 0
                        for h in hemi:
                            dvec = tt * h[0] + bb * h[1] + n * h[2]
                            if bvh.ray_cast(o, dvec, 0.4)[0] is None:
                                free += 1
                        ao[j] = int(round(255 * free / 8))
                cols["frame"].append(np.full(len(t), len(keys), np.int32)); cols["y"].append(yy.astype(np.uint8)); cols["x"].append(xx.astype(np.uint8))
                cols["N"].append(N.astype(np.float16)); cols["P"].append(P.astype(np.float16)); cols["uv"].append(uv.astype(np.float16))
                cols["part"].append(tlab[t]); cols["lit"].append(lit); cols["ao"].append(ao)
                keys.append((a, d, i)); nfr += 1
        print("action", a, "done", len(keys), "frames", flush=True)
    np.savez_compressed(out, key=np.array(keys), parts=np.array(parts), L=L, **{k: np.concatenate(v) for k, v in cols.items()})


if __name__ == "__main__":
    main()
