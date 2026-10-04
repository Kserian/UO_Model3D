"""Skinning matrices of the UO rig for every action / direction / frame, so that garments can be posed and rasterised in plain numpy (no Blender, no Cycles).

    python pose_capture.py ../model/UO_Body_0x190.blend OUT.npz [--actions 0,1,2,3,4,9] [--bones pelvis,thigh.L,...]

Writes (N = number of (action, direction, frame) poses):
  key    (N, 3)       action, direction, frame
  skin   (N, B, 4, 4) world-space skinning matrix of every bone: a point that was at x in the rest pose is at skin[i, b] @ x in the pose (UO direction included)
  bones  (B,)         bone names
  P, V   (4, 4)       camera: projection and view matrix (the same for all poses); canvas of the original body frames, 145 x 133, anchor (75, 92), 36 px/m
  body_tri / body_rest  the rest-pose skin triangles / vertices (world), for collision tests of the garments
Same camera set-up as body_part_raster.py (the pose does not depend on anything else).
"""
import sys, os
import numpy as np
import bpy

CW, CH, CANCH = 145, 133, (75, 92)
STEP = 3


def main():
    args = sys.argv[1:]
    blend, out = os.path.abspath(args.pop(0)), os.path.abspath(args.pop(0))
    only, names = None, None
    while args:
        f = args.pop(0)
        if f == "--actions":
            only = {int(x) for x in args.pop(0).split(",")}
        elif f == "--bones":
            names = args.pop(0).split(",")
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
    bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get(); cam = sc.camera.evaluated_get(dg)
    P = np.array(cam.calc_matrix_camera(dg, x=CW, y=CH)); V = np.array(cam.matrix_world.inverted())

    rig.data.pose_position = "POSE"
    bones = [b.name for b in rig.data.bones if (names is None or b.name in names)]
    rest = {b: np.array(rig.matrix_world @ rig.data.bones[b].matrix_local) for b in bones}       # bone rest matrix, world
    acts = sorted([a for a in bpy.data.actions if "uo_action" in a], key=lambda a: int(a["uo_action"]))
    keys, skin = [], []
    for act in acts:
        a = int(act["uo_action"])
        if only is not None and a not in only:
            continue
        rig.animation_data.action = act
        for d in range(5):
            rig["uo_direction"] = d
            for i in range(int(act["uo_frames"])):
                sc.frame_set(1 + i * STEP); rig.update_tag(); bpy.context.view_layer.update()
                Mw = np.array(rig.matrix_world)
                skin.append(np.stack([(Mw @ np.array(rig.pose.bones[b].matrix)) @ np.linalg.inv(np.array(rig.data.bones[b].matrix_local)) @ np.linalg.inv(Mw)
                                      for b in bones]))
                keys.append((a, d, i))
        print("action", a, "done", flush=True)
    # skinning matrices above are armature-space; the rest pose is expressed in world coordinates, so conjugate by the armature matrix (done: Mw ... Mw^-1)
    me = body.data
    co = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3).astype(np.float64)
    rig.data.pose_position = "REST"; bpy.context.view_layer.update()
    kb = me.shape_keys.key_blocks["Basis"] if me.shape_keys else None
    if kb is not None:
        kb.data.foreach_get("co", co.ravel()) if False else None
    Mb = np.array(body.matrix_world)
    me.calc_loop_triangles()
    tri = np.array([t.vertices[:] for t in me.loop_triangles])
    np.savez_compressed(out, key=np.array(keys), skin=np.array(skin), bones=np.array(bones), P=P, V=V, body_tri=tri, body_rest=co @ Mb[:3, :3].T + Mb[:3, 3])
    print("wrote", out, len(keys), "poses")


if __name__ == "__main__":
    main()
