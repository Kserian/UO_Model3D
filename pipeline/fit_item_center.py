"""Per-frame sideways position of a rigid item against the ORIGINAL body in the front view: the item is moved along x (the width of the body) until its centre is on the centre of the original torso.

    python fit_item_center.py ITEM.blend RENDER_DIR --action 02_run_unarmed [--action ...] [--constant] [--parent pelvis] [--dir 0] [--pxm 30] [--body pipeline/body400.vd] [--target 0.0]

Like fit_item_contact.py (which sets the distance in the side view), for an item bound to --parent with the property uo_motion, rendered once into RENDER_DIR. The offset of a frame: the middle of the item's pixels minus the
mean over its rows of the middle of the run of body pixels (of that row) nearest to the head's axis (the rows of the arms, which swing, make separate runs; the head axis is the middle of the body's first rows),
in px; positive = the item is to the right of the torso. The item goes by (target - offset) / --pxm m along x of the armature (a step along x is --pxm px in the dir 0 view: 30, not 36: that view is turned about 34 deg;
measure it: x +0.05 m moved the drum by 1.5 px). If item_motion.npz already holds the frame (a contact shift of fit_item_contact.py), the shift is added to it; otherwise it starts from the parent's pose. Run it again on the new
render to see what is left (the offsets are printed).
"""
import argparse, glob, os, sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
STEP = 3


def offset_px(render, act, d, i, body):
    import compose_layers as cl
    p = sorted(glob.glob(os.path.join(render, "clothing", "frames", act + "*", "dir%d" % d, "*.png")))[i]
    dr = np.array(Image.open(p).convert("RGBA"))[..., 3] >= 128
    if not dr.any():
        return None
    ys, xs = np.nonzero(dr); cx = (xs.min() + xs.max()) / 2.0
    a = int(act[:2]); b = body[(a, d)][min(i, len(body[(a, d)]) - 1)]; bm = cl.to_canvas(b["img"], b["cx"], b["cy"])[..., 3] >= 128
    top = np.nonzero(bm.any(1))[0].min()
    head = [(np.nonzero(bm[y])[0].min() + np.nonzero(bm[y])[0].max()) / 2.0 for y in range(top + 2, top + 12) if bm[y].any()]
    hc = np.mean(head) if head else None
    rows = []
    for y in range(ys.min(), ys.max() + 1):
        xb = np.nonzero(bm[y])[0]
        if len(xb) == 0:
            continue
        runs = np.split(xb, np.nonzero(np.diff(xb) > 1)[0] + 1)
        h = hc if hc is not None else xb.mean()
        r = min(runs, key=lambda r: abs((r.min() + r.max()) / 2 - h))
        rows.append((r.min() + r.max()) / 2.0)
    return None if not rows else float(cx - np.mean(rows))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("blend"); ap.add_argument("render"); ap.add_argument("--action", action="append", required=True)
    ap.add_argument("--parent", default="pelvis"); ap.add_argument("--dir", type=int, default=0); ap.add_argument("--pxm", type=float, default=30.0); ap.add_argument("--target", type=float, default=0.0)
    ap.add_argument("--body", default=os.path.join(HERE, "body400.vd")); ap.add_argument("--out"); ap.add_argument("--constant", action="store_true", help="ONE shift per action (the mean offset) in the item's own frame, like moving its starting place: the motion of the item stays as it was; without it the item is put on the torso in every frame, which removes its natural swing")
    a = ap.parse_args()
    import vd, bpy
    _, _, body = vd.read_vd(a.body)
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(a.blend)), "item_motion.npz")
    res = dict(np.load(out)) if os.path.exists(out) else {}
    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(a.blend))
    sc = bpy.context.scene; rig = bpy.data.objects["UO_Rig"]
    rig.data.pose_position = "REST"; rig.animation_data.action = None; bpy.context.view_layer.update()
    rest = np.array([list(r) for r in rig.data.bones[a.parent].matrix_local])
    rig.data.pose_position = "POSE"
    for act in a.action:
        action = bpy.data.actions[act]; rig.animation_data.action = action; n = int(action["uo_frames"]); num = int(act[:2])
        off = [offset_px(a.render, act, a.dir, i, body) for i in range(n)]
        print("%s: offset px %s" % (act, " ".join("%+.1f" % o if o is not None else "  n/a" for o in off)))
        valid = [o for o in off if o is not None]
        dx_const = (a.target - float(np.mean(valid))) / a.pxm if valid else 0.0
        if a.constant:
            print("   constant shift %+.1f px = %+.1f cm along the item's own x" % (a.pxm * dx_const, 100 * dx_const))
        for i in range(n):
            key = "%d_%d" % (num, i)
            if key in res:
                M0 = res[key]
            else:
                sc.frame_set(1 + i * STEP); bpy.context.view_layer.update()
                P = np.array([list(r) for r in rig.pose.bones[a.parent].matrix]); M0 = P @ np.linalg.inv(rest)
            T = np.eye(4)
            if a.constant:
                T[0, 3] = dx_const; res[key] = M0 @ T                          # in the rest frame of the item, before the parent's pose: moves with the body, the swing is kept
            else:
                T[0, 3] = 0.0 if off[i] is None else (a.target - off[i]) / a.pxm
                res[key] = T @ M0
    np.savez(out, **res)
    print("fit_item_center: saved", out, "(%d frames)" % len(res))
