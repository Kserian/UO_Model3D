"""Per-frame distance of a rigid item to the ORIGINAL body in a side view: the item is moved along its parent's local y (towards the body) so that the visible gap between it and the original body sprite is the target one.

    python fit_item_contact.py ITEM.blend RENDER_DIR --action 00_walk_unarmed [--action 01_walk_armed ...] [--parent pelvis] [--target 1.0] [--dir 2] [--body pipeline/body400.vd] [--out item_motion.npz]

ITEM.blend: an item with a "rigid" recipe with "motion": true (property uo_motion) bound to the bone --parent, rendered once as it is: RENDER_DIR/clothing/frames/NN_action/dirK/NN.png (render_uo_layer.py, LAYER clothing).
The gap of a frame: for every row of the item sprite the distance in pixels between its back edge and the nearest pixel of the original body (frames of --body, anchored like the sprites) on that row (a hand in front of the
item gives a negative number, which counts as 0); the mean over the rows of the item. The item's own geometry is fitted to OUR body, which follows the original silhouettes to ~0.9 IoU: in some frames of a walk the original
body is further from the item than ours, and the item hangs in front of it. The shift of a frame is (gap - target) px / 36 px per m, never negative (an item that is closer than the target stays), (--smooth: mixed with the neighbouring frames of a looping action). The matrix of a frame, item_motion.npz "ACTION_i": the parent's pose against its rest pose, then the shift along the parent's local +y. render_uo_layer.py motion_fix applies it (same file as uo_make_item.py
\"rigid\" \"motion\"); render the action again with it. Prints the gaps before, so that a second run on the new render shows what is left.
"""
import argparse, glob, os, sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
STEP = 3
LOOP = {0, 1, 2, 3, 4, 5, 6, 7, 8, 15, 23, 24, 25}


def gap_px(render, act, d, i, body):
    import compose_layers as cl
    p = sorted(glob.glob(os.path.join(render, "clothing", "frames", act + "*", "dir%d" % d, "*.png")))[i]
    dr = np.array(Image.open(p).convert("RGBA"))[..., 3] >= 128
    a = int(act[:2]); b = body[(a, d)][min(i, len(body[(a, d)]) - 1)]; bm = cl.to_canvas(b["img"], b["cx"], b["cy"])[..., 3] >= 128
    gl, gr = [], []
    for y in np.nonzero(dr.any(1))[0]:
        xs = np.nonzero(dr[y])[0]; bx = np.nonzero(bm[y])[0]
        if len(bx):
            gl.append(bx.min() - xs.max()); gr.append(xs.min() - bx.max())
    if not gl:
        return 0.0
    gl, gr = np.array(gl), np.array(gr)
    g = gl if abs(np.median(gl)) < abs(np.median(gr)) else gr                 # the body is on the left or on the right of the item
    return float(np.mean(np.maximum(g, 0)))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("blend"); ap.add_argument("render"); ap.add_argument("--action", action="append", required=True)
    ap.add_argument("--parent", default="pelvis"); ap.add_argument("--target", type=float, default=1.0); ap.add_argument("--dir", type=int, default=2)
    ap.add_argument("--body", default=os.path.join(HERE, "body400.vd")); ap.add_argument("--out"); ap.add_argument("--merge", action="store_true", help="keep the frames already in the npz"); ap.add_argument("--smooth", type=float, default=0.0, help="share of the neighbours in a looping action (0 = the raw shifts: the gaps of a walk change slowly)")
    a = ap.parse_args()
    import vd, bpy
    _, _, body = vd.read_vd(a.body)
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(a.blend)), "item_motion.npz")
    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(a.blend))
    sc = bpy.context.scene; rig = bpy.data.objects["UO_Rig"]
    rig.data.pose_position = "REST"; rig.animation_data.action = None; bpy.context.view_layer.update()
    rest = np.array([list(r) for r in rig.data.bones[a.parent].matrix_local])
    res = dict(np.load(out)) if a.merge and os.path.exists(out) else {}
    rig.data.pose_position = "POSE"
    for act in a.action:
        action = bpy.data.actions[act]; rig.animation_data.action = action; n = int(action["uo_frames"]); num = int(act[:2])
        g = np.array([gap_px(a.render, act, a.dir, i, body) for i in range(n)])
        sh = np.maximum(g - a.target, 0.0)
        if num in LOOP and n > 2:
            sh = a.smooth / 2 * np.roll(sh, 1) + (1 - a.smooth) * sh + a.smooth / 2 * np.roll(sh, -1)
        print("%s: gap px %s -> shift px %s" % (act, " ".join("%.1f" % x for x in g), " ".join("%.1f" % x for x in sh)))
        for i in range(n):
            sc.frame_set(1 + i * STEP); bpy.context.view_layer.update()
            P = np.array([list(r) for r in rig.pose.bones[a.parent].matrix])
            T = np.eye(4); T[1, 3] = sh[i] / 36.0                                # towards the body: the parent's local +y
            res["%d_%d" % (num, i)] = P @ np.linalg.inv(rest) @ T
    np.savez(out, **res)
    print("fit_item_contact: saved", out, "(%d frames)" % len(res))
