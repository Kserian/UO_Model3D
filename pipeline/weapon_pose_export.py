"""Export what the weapon calibration needs from the .blend: for each of the 210 UO poses and 5 directions, the world matrix of the hand
bones and the camera (world -> canvas pixels). Offline fits (weapon_fit.py) then run in numpy only.

    python weapon_pose_export.py ../model/UO_Body_0x190.blend OUT.npz [--canvas 256,256 --anchor 128,192]

Writes: key (N,3) = (action, dir, frame); bones (names); BW (N,nb,4,4) world matrix of the pose bones in `bones`; PX (N,3,4) world -> pixels:
(x, y, depth) = PX @ (X, Y, Z, 1), x to the right and y down in canvas pixels (pixel (i, j) covers [i, i+1) x [j, j+1)).
"""
import sys, os
import numpy as np
import bpy

STEP = 3
BONES = ["hand.L", "hand.R", "forearm.L", "forearm.R", "shield.L"]


def main():
    args = sys.argv[1:]
    blend, out = os.path.abspath(args.pop(0)), os.path.abspath(args.pop(0))
    CW, CH, CANCH = 256, 256, (128, 192)
    while args:
        a = args.pop(0)
        if a == "--canvas": CW, CH = (int(x) for x in args.pop(0).split(","))
        elif a == "--anchor": CANCH = tuple(int(x) for x in args.pop(0).split(","))
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc = bpy.context.scene
    rig = bpy.data.objects["UO_Rig"]
    sc.camera = bpy.data.objects["UO_Camera"]; cd = sc.camera.data
    cd.sensor_fit = "HORIZONTAL"; cd.ortho_scale = CW / sc.get("uo_px_per_m", 36.0); cd.shift_x = cd.shift_y = 0.0
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = CW, CH, 100

    def cam_matrix():
        bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get(); cam = sc.camera.evaluated_get(dg)
        return np.array(cam.calc_matrix_camera(dg, x=CW, y=CH)) @ np.array(cam.matrix_world.inverted())

    def anchor_px():
        P = cam_matrix() @ np.array([0.0, 0.0, sc.get("uo_anchor_height", 0.07), 1.0])
        return np.array([(P[0] / P[3] + 1) * 0.5 * CW, (1 - P[1] / P[3]) * 0.5 * CH])

    p0 = anchor_px(); cd.shift_x = cd.shift_y = 0.01; p1 = anchor_px(); k = (p1 - p0) / 0.01
    want = np.array(CANCH, float) + (np.array(sc.get("uo_anchor_px", (68.5, 86.0))) - np.array((68, 86)))
    sh = (want - p0) / k; cd.shift_x, cd.shift_y = float(sh[0]), float(sh[1])
    assert np.abs(anchor_px() - want).max() < 1e-3
    bones = [b for b in BONES if b in rig.pose.bones]
    acts = sorted([a for a in bpy.data.actions if "uo_action" in a], key=lambda a: int(a["uo_action"]))
    keys, BW, PX = [], [], []
    for act in acts:
        rig.animation_data.action = act
        for d in range(5):
            rig["uo_direction"] = d
            for i in range(int(act["uo_frames"])):
                sc.frame_set(1 + i * STEP); rig.update_tag(); bpy.context.view_layer.update()
                M = cam_matrix(); Rw = np.array(rig.matrix_world)
                assert np.abs(M[3] - [0, 0, 0, 1]).max() < 1e-9          # orthographic
                # orthographic: w stays 1; pixel x = (ndc_x + 1) / 2 * CW, y = (1 - ndc_y) / 2 * CH, depth = -view z
                V = np.array(sc.camera.evaluated_get(bpy.context.evaluated_depsgraph_get()).matrix_world.inverted())
                px = np.stack([(M[0] + M[3]) * 0.5 * CW, (M[3] - M[1]) * 0.5 * CH, -V[2]])
                keys.append((int(act["uo_action"]), d, i)); PX.append(px)
                BW.append([Rw @ np.array(rig.pose.bones[b].matrix) for b in bones])
        print("action", act["uo_action"], "done", flush=True)
    np.savez_compressed(out, key=np.array(keys), bones=np.array(bones), BW=np.array(BW), PX=np.array(PX), canvas=np.array([CW, CH]), anchor=np.array(CANCH))


if __name__ == "__main__":
    main()
