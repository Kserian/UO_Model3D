"""How much of a held item goes through the body, not counting the grip: share of the item's vertices more than 2 mm inside the posed body skin, only vertices farther than GRIP_R from
the palms (hand.R, hand.L), per action over every frame (the fingers close around the neck, that overlap is wanted).

    python item_collision.py ITEM.blend --actions 07_combat_idle_1h,20_get_hit [--grip-r 0.14]

With --outward also the position of the bowl relative to the gripping hand, seen from above, along the line pelvis -> palm (positive = the bowl is on the outer side of the hand, negative = towards the body): worst and mean frame, cm.
Prints per action: mean share, worst frame share, deepest vertex (mm). Used to compare placements of a lute (docs: model/example_clothing/lute/README.md).
"""
import sys, os
import numpy as np
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

STEP_SCENE = 3


def main():
    args = sys.argv[1:]
    blend = os.path.abspath(args.pop(0)); outward = False; actions = "04_stand"; grip_r = 0.14; step = 1
    while args:
        f = args.pop(0)
        if f == "--actions":
            actions = args.pop(0)
        elif f == "--outward":
            outward = True
        elif f == "--grip-r":
            grip_r = float(args.pop(0))
        elif f == "--step":
            step = int(args.pop(0))
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc = bpy.context.scene
    rig, body = bpy.data.objects["UO_Rig"], bpy.data.objects["UO_Body"]
    items = [o for o in bpy.data.collections["Clothing"].all_objects if o.type == "MESH" and not o.hide_render]
    acts = {int(a["uo_action"]): a for a in bpy.data.actions if "uo_action" in a}
    ends = None
    if outward:                                              # the two ends of the item (its long axis, narrower end = tip) at rest, to follow them through the pose
        rig.data.pose_position = "REST"; bpy.context.view_layer.update()
        o = items[0]; co = np.array([o.matrix_world @ v.co for v in o.data.vertices])
        c0 = co.mean(0); ax = np.linalg.svd(co - c0, full_matrices=False)[2][0]; t = (co - c0) @ ax
        lo, hi = int(np.argmin(t)), int(np.argmax(t))
        w = lambda m: np.ptp(co[m][:, [i for i in range(3) if abs(ax[i]) < 0.9][:2] or [0, 1]], axis=0).prod()
        tipi, buti = (hi, lo) if w(t > t.max() - 0.04 * np.ptp(t)) < w(t < t.min() + 0.04 * np.ptp(t)) else (lo, hi)
        ends = (tipi, buti)
    rig.data.pose_position = "POSE"
    for a in [int(x[:2]) for x in actions.split(",")]:
        act = acts[a]; rig.animation_data.action = act
        per, deep, outs, gaps = [], 0.0, [], []
        for i in range(0, int(act["uo_frames"]), step):
            sc.frame_set(1 + i * STEP_SCENE); rig.update_tag(); bpy.context.view_layer.update()
            dg = bpy.context.evaluated_depsgraph_get()
            eb = body.evaluated_get(dg); mb = eb.to_mesh(); mb.calc_loop_triangles(); M = eb.matrix_world
            bvh = BVHTree.FromPolygons([M @ v.co for v in mb.vertices], [t.vertices[:] for t in mb.loop_triangles]); eb.to_mesh_clear()
            palms = [rig.matrix_world @ (rig.pose.bones[b].head * 0.6 + rig.pose.bones[b].tail * 0.4) for b in ("hand.R", "hand.L")]
            n_in = n_all = 0; sd = []
            if ends:
                eo = items[0].evaluated_get(dg); mo = eo.to_mesh(); Mo = eo.matrix_world
                tip, but = Mo @ mo.vertices[ends[0]].co, Mo @ mo.vertices[ends[1]].co; eo.to_mesh_clear()
                boxc = but + (tip - but) * 0.24; pel = rig.matrix_world @ rig.pose.bones["pelvis"].head
                sdir = Vector((palms[0].x - pel.x, palms[0].y - pel.y, 0)).normalized()
                outs.append(100 * (Vector((boxc.x - palms[0].x, boxc.y - palms[0].y, 0))).dot(sdir))
            for o in items:
                eo = o.evaluated_get(dg); mo = eo.to_mesh(); Mo = eo.matrix_world
                n = len(mo.vertices)
                for k in range(0, n, max(n // 3000, 1)):
                    p = Mo @ mo.vertices[k].co
                    if min((p - q).length for q in palms) < grip_r:
                        continue
                    loc, nrm, fi, d = bvh.find_nearest(p, 0.4)
                    if loc is None:
                        continue
                    s = (p - loc).dot(nrm); n_all += 1; sd.append(s)
                    if s < -0.002:
                        n_in += 1; deep = max(deep, -s)
                eo.to_mesh_clear()
            per.append(n_in / max(n_all, 1))
            if sd:
                gaps.append(float(np.percentile(sd, 5)))
        print("%-26s outside the grip: inside mean %5.1f%%  worst frame %5.1f%%  deepest %5.1f mm  nearest 5%% of the item %+5.1f cm from the skin%s" % (act.name, 100 * np.mean(per), 100 * max(per), 1000 * deep, 100 * np.mean(gaps) if gaps else 0.0,
              ("   bowl outward of the hand: worst %5.1f mean %5.1f cm" % (min(outs), np.mean(outs))) if outs else ""), flush=True)
    sys.stdout.flush(); os._exit(0)


if __name__ == "__main__":
    main()
