"""Silhouette of the holding hand (hand.L + its fingers) for every frame of some actions, in the pixels of the render (bpy):
the UO camera of render_uo_layer.py is rebuilt (36 px/m, anchor on ANCHOR), the triangles of the body whose vertices belong to the hand are projected and filled.
vd_hand_cut.py --mask uses it to cut the bow where the fist is in front of the grip.

    python hand_mask.py item.blend out.npz action_name ...      (keys "<action>_<dir>_<frame>", bool arrays CANVAS-sized, row 0 = top)
"""
import os, sys
import numpy as np
import bpy

blend, out = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2]); names = sys.argv[3:]
W, H, ANCHOR, OANCHOR, STEP = 256, 256, (128, 192), (68, 86), 3
HAND = ("hand.L", "finger")
bpy.ops.wm.open_mainfile(filepath=blend)
sc = bpy.context.scene; rig = bpy.data.objects["UO_Rig"]; body = bpy.data.objects["UO_Body"]
rig.data.pose_position = "POSE"


def anchor_px():
    bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get(); cam = sc.camera.evaluated_get(dg)
    P = np.array(cam.calc_matrix_camera(dg, x=W, y=H)) @ np.array(cam.matrix_world.inverted()) @ np.array([0.0, 0.0, sc.get("uo_anchor_height", 0.07), 1.0])
    return np.array([(P[0] / P[3] + 1) * 0.5 * W, (1 - P[1] / P[3]) * 0.5 * H])


cd = sc.camera.data                                                    # place_camera() of render_uo_layer.py
cd.sensor_fit = "HORIZONTAL"; cd.ortho_scale = W / sc.get("uo_px_per_m", 36.0); cd.shift_x = cd.shift_y = 0.0
p0 = anchor_px(); cd.shift_x = cd.shift_y = 0.01; p1 = anchor_px(); k = (p1 - p0) / 0.01
off = np.array(sc.get("uo_anchor_px", (OANCHOR[0] + 0.5, OANCHOR[1] + 0.0))) - np.array(OANCHOR)
sh = (np.array(ANCHOR, float) + off - p0) / k
cd.shift_x, cd.shift_y = [0.0 if abs(s * kk) < 1e-3 else float(s) for s, kk in zip(sh, k)]

gidx = [g.index for g in body.vertex_groups if g.name == HAND[0] or (g.name.startswith(HAND[1]) and g.name.endswith(".L"))]
wsum = np.zeros(len(body.data.vertices))
for v in body.data.vertices:
    wsum[v.index] = sum(g.weight for g in v.groups if g.group in gidx)
hand_v = wsum > 0.5
tris = np.array([p.vertices[:] for p in body.data.polygons if len(p.vertices) == 3] + [q for p in body.data.polygons if len(p.vertices) == 4 for q in ((p.vertices[0], p.vertices[1], p.vertices[2]), (p.vertices[0], p.vertices[2], p.vertices[3]))])
all_tris = tris
tris = tris[hand_v[tris].all(1)]
print("hand_mask: %d hand vertices, %d triangles" % (hand_v.sum(), len(tris)))
res = {}
for act in [a for a in bpy.data.actions if "uo_action" in a and a.name in names]:
    rig.animation_data.action = act
    for d in range(5):
        rig["uo_direction"] = d; rig.update_tag()
        for i in range(int(act["uo_frames"])):
            sc.frame_set(1 + STEP * i); bpy.context.view_layer.update()
            dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh()
            P = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", P); P = P.reshape(-1, 3)
            Pw = (np.array(ev.matrix_world) @ np.c_[P, np.ones(len(P))].T).T; ev.to_mesh_clear()
            cam = sc.camera.evaluated_get(dg); Mc = np.array(cam.calc_matrix_camera(dg, x=W, y=H)) @ np.array(cam.matrix_world.inverted())
            Q = (Mc @ Pw.T).T; px = np.c_[(Q[:, 0] / Q[:, 3] + 1) * 0.5 * W, (1 - Q[:, 1] / Q[:, 3]) * 0.5 * H]
            def fill(tt):
                mask = np.zeros((H, W), bool)
                for t in tt:
                  a_, b_, c_ = px[t]
                  x0, x1 = int(np.floor(min(a_[0], b_[0], c_[0]))), int(np.ceil(max(a_[0], b_[0], c_[0])))
                  y0, y1 = int(np.floor(min(a_[1], b_[1], c_[1]))), int(np.ceil(max(a_[1], b_[1], c_[1])))
                  xs, ys = np.meshgrid(np.arange(max(x0, 0), min(x1 + 1, W)) + 0.5, np.arange(max(y0, 0), min(y1 + 1, H)) + 0.5)
                  den = (b_[1] - c_[1]) * (a_[0] - c_[0]) + (c_[0] - b_[0]) * (a_[1] - c_[1])
                  if abs(den) < 1e-9 or xs.size == 0:
                      continue
                  l1 = ((b_[1] - c_[1]) * (xs - c_[0]) + (c_[0] - b_[0]) * (ys - c_[1])) / den
                  l2 = ((c_[1] - a_[1]) * (xs - c_[0]) + (a_[0] - c_[0]) * (ys - c_[1])) / den
                  ins = (l1 >= -0.02) & (l2 >= -0.02) & (1 - l1 - l2 >= -0.02)
                  mask[(ys[ins] - 0.5).astype(int), (xs[ins] - 0.5).astype(int)] = True
                return mask
            mask = fill(tris)
            if os.environ.get("FULL") and i == 0:                           # whole body, to check the mapping on the sprites
                res["full_%s_%d_%d" % (act.name, d, i)] = fill(all_tris)
            res["%s_%d_%d" % (act.name, d, i)] = mask
    print("hand_mask:", act.name)
np.savez_compressed(out, **res)
