"""How much of a held item goes through the body, not counting the grip: share of the item's vertices more than 2 mm inside the posed body skin, only vertices farther than GRIP_R from
the palms (hand.R, hand.L), per action over every frame (the fingers close around the neck, that overlap is wanted).

    python item_collision.py ITEM.blend --actions 07_combat_idle_1h,20_get_hit [--grip-r 0.14]

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
    blend = os.path.abspath(args.pop(0)); actions = "04_stand"; grip_r = 0.14; step = 1
    while args:
        f = args.pop(0)
        if f == "--actions":
            actions = args.pop(0)
        elif f == "--grip-r":
            grip_r = float(args.pop(0))
        elif f == "--step":
            step = int(args.pop(0))
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc = bpy.context.scene
    rig, body = bpy.data.objects["UO_Rig"], bpy.data.objects["UO_Body"]
    items = [o for o in bpy.data.collections["Clothing"].all_objects if o.type == "MESH" and not o.hide_render]
    acts = {int(a["uo_action"]): a for a in bpy.data.actions if "uo_action" in a}
    rig.data.pose_position = "POSE"
    for a in [int(x[:2]) for x in actions.split(",")]:
        act = acts[a]; rig.animation_data.action = act
        per, deep = [], 0.0
        for i in range(0, int(act["uo_frames"]), step):
            sc.frame_set(1 + i * STEP_SCENE); rig.update_tag(); bpy.context.view_layer.update()
            dg = bpy.context.evaluated_depsgraph_get()
            eb = body.evaluated_get(dg); mb = eb.to_mesh(); mb.calc_loop_triangles(); M = eb.matrix_world
            bvh = BVHTree.FromPolygons([M @ v.co for v in mb.vertices], [t.vertices[:] for t in mb.loop_triangles]); eb.to_mesh_clear()
            palms = [rig.matrix_world @ (rig.pose.bones[b].head * 0.6 + rig.pose.bones[b].tail * 0.4) for b in ("hand.R", "hand.L")]
            n_in = n_all = 0
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
                    s = (p - loc).dot(nrm); n_all += 1
                    if s < -0.002:
                        n_in += 1; deep = max(deep, -s)
                eo.to_mesh_clear()
            per.append(n_in / max(n_all, 1))
        print("%-26s outside the grip: inside mean %5.1f%%  worst frame %5.1f%%  deepest %5.1f mm" % (act.name, 100 * np.mean(per), 100 * max(per), 1000 * deep), flush=True)
    sys.stdout.flush(); os._exit(0)


if __name__ == "__main__":
    main()
