"""Export the posed-body data of all 1050 UO frames, so shape work can run offline (numpy only, no Blender).

    python body_pose_export.py ../model/UO_Body_0x190.blend OUT.npz

Writes: rest (N,3) rest vertices, wi (N,K) / ww (N,K) bone indices and weights (K influences, padded with weight 0), tris (T,3) triangles of
the quads, tpart-less; bones (list), M (F,B,4,4) armature-space skinning matrices per frame (pose @ rest^-1), MW (F,4,4) body matrix_world,
key (F,3) = (action, dir, frame), cam (3,4,4)= [Pm, Vm, (CW, CH, 0, 0)], horse_depth (F,CH,CW) float32 (inf = none) and horse_mask (F,CH,CW)
bool for mounted frames. Canvas is the one of the original frames: 145x133, anchor (75,92). resid_idx / resid_val / resid_frame: where plain LBS of rest with M differs from Blender's evaluated mesh by > 0.1 mm (shoulders:
bendy-bone / twist bones), as sparse vertex offsets per frame; Scene.posed adds them.
"""
import sys, os, json
import numpy as np
import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
CW, CH, CANCH = 145, 133, (75, 92)
STEP = 3


def main():
    blend, out = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
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
    rig.data.pose_position = "POSE"
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get(); cam = sc.camera.evaluated_get(dg)
    Pm = np.array(cam.calc_matrix_camera(dg, x=CW, y=CH)); Vm = np.array(cam.matrix_world.inverted())

    names = [g.name for g in body.vertex_groups]
    rest = np.array([v.co[:] for v in body.data.vertices])
    Wm = np.zeros((len(rest), len(names)))
    for v in body.data.vertices:
        for g in v.groups:
            Wm[v.index, g.group] = g.weight
    for j, n in enumerate(names):                         # Blender ignores the groups of bones with Deform off (the clavicles) and renormalises
        if not rig.data.bones[n].use_deform:
            Wm[:, j] = 0.0
    Wm /= np.maximum(Wm.sum(1, keepdims=True), 1e-9)
    K = int((Wm > 0).sum(1).max())
    wi = np.argsort(-Wm, 1)[:, :K]; ww = np.take_along_axis(Wm, wi, 1)
    body.data.calc_loop_triangles()
    tris = np.array([t.vertices[:] for t in body.data.loop_triangles], np.int32)
    horses = {o.name: o for o in bpy.data.objects if o.name.startswith("Horse_")}
    for o in horses.values():
        o.hide_viewport = o.hide_render = False
    HM = {}
    if "uo_horse_masks.json" in bpy.data.texts:
        import base64, zlib
        for kk, v in json.loads(bpy.data.texts["uo_horse_masks.json"].as_string())["masks"].items():
            bits = np.unpackbits(np.frombuffer(zlib.decompress(base64.b64decode(v)), np.uint8))[:120 * 136].reshape(120, 136).astype(bool)
            m = np.zeros((CH, CW), bool); m[CANCH[1] - 86:CANCH[1] - 86 + 120, CANCH[0] - 68:CANCH[0] - 68 + 136] = bits
            HM[tuple(int(x) for x in kk.split(","))] = m

    Ms, MWs, keys, hd, hm = [], [], [], [], []
    R4 = np.c_[rest, np.ones(len(rest))]; RI, RV, RF = [], [], []        # residual: Blender's evaluated mesh minus the plain LBS below
    from body_part_raster import raster                       # horse proxies are rasterised with the same code
    acts = sorted([a for a in bpy.data.actions if "uo_action" in a], key=lambda a: int(a["uo_action"]))
    for act in acts:
        a = int(act["uo_action"]); rig.animation_data.action = act
        for d in range(5):
            rig["uo_direction"] = d
            for i in range(int(act["uo_frames"])):
                sc.frame_set(1 + i * STEP); rig.update_tag(); bpy.context.view_layer.update()
                M = np.zeros((len(names), 4, 4))
                for j, n in enumerate(names):
                    pb = rig.pose.bones[n]; M[j] = np.array(pb.matrix @ pb.bone.matrix_local.inverted())
                Ms.append(M); MWs.append(np.array(body.matrix_world)); keys.append((a, d, i))
                ev = body.evaluated_get(bpy.context.evaluated_depsgraph_get()); me = ev.to_mesh()
                co = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", co); ev.to_mesh_clear()
                lbs = (np.einsum("nkij,nj->nki", M[wi], R4)[..., :3] * ww[..., None]).sum(1)
                r = co.reshape(-1, 3) - lbs; bad = np.nonzero(np.linalg.norm(r, axis=1) > 1e-4)[0]
                RI.append(bad); RV.append(r[bad].astype(np.float32)); RF.append(np.full(len(bad), len(Ms) - 1))
                h = horses.get("Horse_a%d_f%d" % (a, i)); m = HM.get((a, i, d))
                if h is not None and m is not None:
                    dg = bpy.context.evaluated_depsgraph_get()
                    hl, depth = raster(h, dg, Pm, Vm, None)
                    hd.append(np.where(hl >= 0, depth, np.inf).astype(np.float32)); hm.append(m)
                else:
                    hd.append(np.full((CH, CW), np.inf, np.float32)); hm.append(np.zeros((CH, CW), bool))
        print("action", a, flush=True)
    np.savez_compressed(out, rest=rest, wi=wi, ww=ww, tris=tris, bones=np.array(names), M=np.array(Ms, np.float32), MW=np.array(MWs),
                        key=np.array(keys), resid_idx=np.concatenate(RI), resid_val=np.concatenate(RV), resid_frame=np.concatenate(RF), Pm=Pm, Vm=Vm, canvas=np.array([CW, CH]), horse_depth=np.array(hd), horse_mask=np.array(hm))


if __name__ == "__main__":
    main()
