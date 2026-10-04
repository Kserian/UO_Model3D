"""Does an item go through the body, and is it too thick? Measured on the posed meshes, every action (no render).

    python item_qa.py ITEM.blend [--actions 04_stand,00_walk_unarmed,...|all] [--step 2] [--json out.json]

For every UO action and every `step`-th frame the body skin and the items of the collection Clothing are posed (the Armature modifier, the way the render sees them before
BODY_GAP and the cloth push of render_uo_layer.py) and every item vertex gets its distance to the nearest skin (negative = inside the body):
  inside    share of the vertices more than 2 mm inside the skin (the render pushes these out by BODY_GAP, but a lot of them means bad weights or a shell that is too tight),
  depth     the deepest vertex (mm),
  stand-off the distance from the skin of the vertices that are outside, p50 / p90 / max (cm): the "thickness". The original items stand 5.6-8.1 cm (plate) / 5.6 (shirt) from the
            silhouette at p90 (docs/qa/layer_analysis.md); LIMIT_BY_KIND of uo_fit_item.py keeps the item under its slot's limit in the rest pose.
Prints the worst actions. Items of a loose garment (custom property uo_cloth) are measured before the legs push them out, so their `inside` counts the legs poking through.
"""
import sys, os, json
import numpy as np
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

STEP_SCENE = 3


def main():
    args = sys.argv[1:]
    blend = os.path.abspath(args.pop(0))
    actions, step, out = "04_stand,00_walk_unarmed,02_run_unarmed,09_attack_1h_slash,13_attack_2h_slash,16_spell_directed,17_spell_area,20_get_hit,21_die_forward,30_block", 2, None
    while args:
        f = args.pop(0)
        if f == "--actions":
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
    rig.data.pose_position = "POSE"
    rows = []
    for a in want:
        act = acts[a]
        rig.animation_data.action = act
        rig["uo_direction"] = 0
        ins, dep, so = [], [], []
        for i in range(0, int(act["uo_frames"]), step):
            sc.frame_set(1 + i * STEP_SCENE); rig.update_tag(); bpy.context.view_layer.update()
            dg = bpy.context.evaluated_depsgraph_get()
            eb = body.evaluated_get(dg); mb = eb.to_mesh(); mb.calc_loop_triangles()
            M = eb.matrix_world
            co = [M @ v.co for v in mb.vertices]; tri = [t.vertices[:] for t in mb.loop_triangles]
            bvh = BVHTree.FromPolygons(co, tri); eb.to_mesh_clear()
            for o in items:
                eo = o.evaluated_get(dg); mo = eo.to_mesh(); Mo = eo.matrix_world
                n = len(mo.vertices); sel = range(0, n, max(n // 3000, 1))
                for k in sel:
                    p = Mo @ mo.vertices[k].co
                    loc, nrm, fi, d = bvh.find_nearest(p, 0.4)
                    if loc is None:
                        continue
                    s = (p - loc).dot(nrm)
                    if s < 0:
                        dep.append(-s)
                    (ins if s < -0.002 else so).append(1 if s < -0.002 else s)
                eo.to_mesh_clear()
        tot = len(ins) + len(so)
        rows.append(dict(action=a, name=acts[a].name, inside=len(ins) / max(tot, 1), depth_mm=1000 * (max(dep) if dep else 0.0),
                         p50_cm=100 * float(np.percentile(so, 50)) if so else 0.0, p90_cm=100 * float(np.percentile(so, 90)) if so else 0.0, max_cm=100 * (max(so) if so else 0.0)))
        r = rows[-1]
        print("%-26s inside %5.1f%%  deepest %5.1f mm | stand-off p50 %.1f  p90 %.1f  max %.1f cm" % (r["name"], 100 * r["inside"], r["depth_mm"], r["p50_cm"], r["p90_cm"], r["max_cm"]), flush=True)
    s = dict(inside_mean=float(np.mean([r["inside"] for r in rows])), inside_worst=max(rows, key=lambda r: r["inside"])["name"], depth_max_mm=max(r["depth_mm"] for r in rows),
             p90_max_cm=max(r["p90_cm"] for r in rows))
    print("ITEM_QA mean inside %.1f%% (worst: %s), deepest %.1f mm, stand-off p90 at most %.1f cm" % (100 * s["inside_mean"], s["inside_worst"], s["depth_max_mm"], s["p90_max_cm"]))
    if out:
        json.dump(dict(blend=blend, summary=s, actions=rows), open(out, "w"), indent=1)
    sys.stdout.flush(); os._exit(0)


if __name__ == "__main__":
    main()
