"""IoU of body meshes (posed by UO_Rig actions) against the original UO frames, all 5 directions.
usage: python eval_iou.py <blend> <out.json> [--step N] [--mounted]
Bodies evaluated: UO_Body with corrections, UO_Body without corrections (shape keys muted), UO_Body_v13 (if present).
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
import bpy, sys, json, base64, zlib, numpy as np
blend, out = sys.argv[1], sys.argv[2]
STEP = int(sys.argv[sys.argv.index("--step") + 1]) if "--step" in sys.argv else 1
MOUNTED = "--mounted" in sys.argv
bpy.ops.wm.open_mainfile(filepath=blend)
sc = bpy.context.scene
rig = bpy.data.objects["UO_Rig"]; rig.data.pose_position = "POSE"
cam = bpy.data.objects["UO_Camera"]; sc.camera = cam
ORIG = json.load(open(os.path.join(HERE, "..", "uo_original_frames.json")))["frames"]
def orig(a, i, d):
    return np.frombuffer(zlib.decompress(base64.b64decode(ORIG["%d,%d,%d" % (a, i, d)])), np.uint8).reshape(120, 136, 4)[..., 3] > 0

def raster(ob, dg):
    ev = ob.evaluated_get(dg); me = ev.to_mesh()
    co = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
    me.calc_loop_triangles()
    tri = np.empty(len(me.loop_triangles) * 3, np.int32); me.loop_triangles.foreach_get("vertices", tri); tri = tri.reshape(-1, 3)
    Mw = np.array(ev.matrix_world); ev.to_mesh_clear()
    c = cam.evaluated_get(dg)
    Mc = np.array(c.calc_matrix_camera(dg, x=136, y=120)) @ np.array(c.matrix_world.inverted()) @ Mw
    h = np.c_[co, np.ones(len(co))] @ Mc.T
    ndc = h[:, :2] / h[:, 3:4]
    P = np.stack([(ndc[:, 0] + 1) * 0.5 * 136, (1 - ndc[:, 1]) * 0.5 * 120], 1)[tri]
    img = np.zeros((120, 136), bool)
    mn = np.floor(P.min(1)).astype(int); mx = np.ceil(P.max(1)).astype(int)
    A, B, C = P[:, 0], P[:, 1], P[:, 2]
    den = (B[:, 1] - C[:, 1]) * (A[:, 0] - C[:, 0]) + (C[:, 0] - B[:, 0]) * (A[:, 1] - C[:, 1])
    ok = np.abs(den) > 1e-12; size = np.clip(mx - mn, 0, 16)
    for dy in range(int(size[:, 1].max(initial=0)) + 1):
        for dx in range(int(size[:, 0].max(initial=0)) + 1):
            t = np.nonzero(ok & (dx <= size[:, 0]) & (dy <= size[:, 1]))[0]
            px = mn[t, 0] + dx; py = mn[t, 1] + dy; cx, cy = px + 0.5, py + 0.5
            l0 = ((B[t, 1] - C[t, 1]) * (cx - C[t, 0]) + (C[t, 0] - B[t, 0]) * (cy - C[t, 1])) / den[t]
            l1 = ((C[t, 1] - A[t, 1]) * (cx - C[t, 0]) + (A[t, 0] - C[t, 0]) * (cy - C[t, 1])) / den[t]
            k = (l0 >= -1e-4) & (l1 >= -1e-4) & (1 - l0 - l1 >= -1e-4) & (px >= 0) & (py >= 0) & (px < 136) & (py < 120)
            img[py[k], px[k]] = True
    return img

body = bpy.data.objects["UO_Body"]
v13 = bpy.data.objects.get("UO_Body_v13")
for o in bpy.data.objects:
    if o.type == "MESH":
        o.hide_viewport = False
keys = body.data.shape_keys.key_blocks
variants = [("v12_corr", body, False), ("v12_pure", body, True)] + ([("v13", v13, None)] if v13 else [])
res = {v[0]: {} for v in variants}
acts = sorted([a for a in bpy.data.actions if "uo_action" in a], key=lambda a: int(a["uo_action"]))
for act in acts:
    a = int(act["uo_action"])
    if (23 <= a <= 29) != MOUNTED:
        continue
    rig.animation_data.action = act
    for i in range(0, int(act["uo_frames"]), STEP):
        sc.frame_set(1 + 3 * i)
        for d in range(5):
            rig["uo_direction"] = d; rig.update_tag(); bpy.context.view_layer.update()
            dg = bpy.context.evaluated_depsgraph_get()
            o = orig(a, i, d)
            for name, ob, mute in variants:
                if mute is not None:
                    for k in keys[1:]:
                        k.mute = mute
                    body.data.update(); bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get()
                m = raster(ob, dg)
                res[name]["%d,%d,%d" % (a, i, d)] = [int((m & o).sum()), int((m | o).sum()), int((m & ~o).sum()), int((o & ~m).sum())]
for k in keys[1:]:
    k.mute = False
json.dump(res, open(out, "w"))
for name in res:
    v = np.array(list(res[name].values()))
    iou = v[:, 0] / np.maximum(v[:, 1], 1)
    print("%-9s views %d | IoU mean %.3f  p10 %.3f  min %.3f | outside px/view %.1f  missing px/view %.1f"
          % (name, len(v), iou.mean(), np.percentile(iou, 10), iou.min(), v[:, 2].mean(), v[:, 3].mean()), flush=True)
