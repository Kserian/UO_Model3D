"""Does a small item (a medal, a pendant) stay on the skin in every action? Measured on the posed meshes (no render), the way item_qa.py poses them.

    python item_skin_gap.py ITEM.blend [--below Z] [--actions all|04_stand,...] [--step 2] [--json out.json]

Only the vertices of the item whose REST height is below Z (m, default 1.375: the medal under its ring; 99 = all vertices) are measured. For every action and every `step`-th
frame each of them gets its signed distance to the nearest point of the posed skin (negative = inside). Per action: p10 / p50 / p90 of the distance (mm), the share inside (more than
2 mm under the skin) and the deepest one; the summary is the spread of the median over all frames (how far the item drifts off / into the skin relative to the rest pose, mm) and the
worst frames. The render pushes the vertices that are inside the limbs out by BODY_GAP (render_uo_layer.py), not those inside the torso.
"""
import sys, os, json
import numpy as np
import bpy
from mathutils.bvhtree import BVHTree

STEP_SCENE = 3


def main():
    args = sys.argv[1:]
    blend = os.path.abspath(args.pop(0))
    below, actions, step, out = 1.375, "all", 2, None
    while args:
        f = args.pop(0)
        if f == "--below":
            below = float(args.pop(0))
        elif f == "--actions":
            actions = args.pop(0)
        elif f == "--step":
            step = int(args.pop(0))
        elif f == "--json":
            out = args.pop(0)
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc = bpy.context.scene
    rig, body = bpy.data.objects["UO_Rig"], bpy.data.objects["UO_Body"]
    items = [o for o in bpy.data.collections["Clothing"].all_objects if o.type == "MESH" and not o.hide_render]
    acts = {int(a["uo_action"]): a for a in bpy.data.actions if "uo_action" in a}
    want = sorted(acts) if actions == "all" else [int(x[:2]) for x in actions.split(",")]
    rig.data.pose_position = "REST"; bpy.context.view_layer.update()
    sel = {}
    for o in items:
        P = np.array([(o.matrix_world @ v.co)[:] for v in o.data.vertices])
        sel[o.name] = np.flatnonzero(P[:, 2] < below)
    print("measured vertices:", {k: len(v) for k, v in sel.items()})
    rig.data.pose_position = "POSE"
    rows, allmed = [], []
    for a in want:
        act = acts[a]
        rig.animation_data.action = act
        rig["uo_direction"] = 0
        meds, ins, deep, p10, p90 = [], [], [], [], []
        for i in range(0, int(act["uo_frames"]), step):
            sc.frame_set(1 + i * STEP_SCENE); rig.update_tag(); bpy.context.view_layer.update()
            dg = bpy.context.evaluated_depsgraph_get()
            eb = body.evaluated_get(dg); mb = eb.to_mesh(); mb.calc_loop_triangles()
            M = eb.matrix_world
            bvh = BVHTree.FromPolygons([M @ v.co for v in mb.vertices], [t.vertices[:] for t in mb.loop_triangles]); eb.to_mesh_clear()
            S = []
            for o in items:
                eo = o.evaluated_get(dg); mo = eo.to_mesh(); Mo = eo.matrix_world
                for k in sel[o.name]:
                    p = Mo @ mo.vertices[int(k)].co
                    loc, nrm, fi, d = bvh.find_nearest(p, 0.4)
                    if loc is not None:
                        S.append((p - loc).dot(nrm))
                eo.to_mesh_clear()
            if S:
                S = np.array(S) * 1000
                meds.append(np.median(S)); ins.append(np.mean(S < -2)); deep.append(max(0.0, -S.min())); p10.append(np.percentile(S, 10)); p90.append(np.percentile(S, 90))
        if not meds:
            continue
        allmed += meds
        r = dict(action=a, name=act.name, p10=float(np.mean(p10)), p50=float(np.mean(meds)), p90=float(np.mean(p90)), med_min=float(min(meds)), med_max=float(max(meds)),
                 inside=float(np.mean(ins)), deepest=float(max(deep)))
        rows.append(r)
        print("%-26s distance to skin p10 %6.1f  p50 %6.1f  p90 %6.1f mm | median %6.1f..%6.1f | inside %4.1f%%  deepest %5.1f mm" % (r["name"], r["p10"], r["p50"], r["p90"], r["med_min"], r["med_max"], 100 * r["inside"], r["deepest"]), flush=True)
    s = dict(median_all=float(np.median(allmed)), median_min=float(min(allmed)), median_max=float(max(allmed)), inside_mean=float(np.mean([r["inside"] for r in rows])),
             deepest_max=max(r["deepest"] for r in rows))
    print("SKIN_GAP median over all frames %.1f mm (range %.1f .. %.1f), inside %.1f%%, deepest %.1f mm" % (s["median_all"], s["median_min"], s["median_max"], 100 * s["inside_mean"], s["deepest_max"]))
    if out:
        json.dump(dict(blend=blend, summary=s, actions=rows), open(out, "w"), indent=1)
    sys.stdout.flush(); os._exit(0)


if __name__ == "__main__":
    main()
