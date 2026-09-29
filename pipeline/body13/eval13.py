"""IoU of UO_Body (v13 blend) vs original frames: eval13.py blend out.json [--frames a,i;a,i] [--mounted]"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
import bpy, sys, json, base64, zlib, numpy as np
blend, out = sys.argv[1], sys.argv[2]
FR = [tuple(map(int, s.split(","))) for s in sys.argv[sys.argv.index("--frames") + 1].split(";")] if "--frames" in sys.argv else None
MOUNTED = "--mounted" in sys.argv
bpy.ops.wm.open_mainfile(filepath=blend)
exec(open(os.path.join(HERE, "eval_iou.py")).read().split("body = bpy.data.objects")[0].split("bpy.ops.wm.open_mainfile(filepath=blend)")[1])
body = bpy.data.objects["UO_Body"]
res = {}
acts = sorted([a for a in bpy.data.actions if "uo_action" in a], key=lambda a: int(a["uo_action"]))
for act in acts:
    a = int(act["uo_action"])
    if FR is None and (23 <= a <= 29) != MOUNTED: continue
    rig.animation_data.action = act
    for i in range(int(act["uo_frames"])):
        if FR is not None and (a, i) not in FR: continue
        sc.frame_set(1 + 3 * i)
        for d in range(5):
            rig["uo_direction"] = d; rig.update_tag(); bpy.context.view_layer.update()
            dg = bpy.context.evaluated_depsgraph_get(); o = orig(a, i, d); m = raster(body, dg)
            res["%d,%d,%d" % (a, i, d)] = [int((m & o).sum()), int((m | o).sum()), int((m & ~o).sum()), int((o & ~m).sum())]
json.dump(res, open(out, "w"))
vv = np.array(list(res.values())); iou = vv[:, 0] / np.maximum(vv[:, 1], 1)
print("views %d | IoU mean %.4f p10 %.4f min %.4f | outside %.1f missing %.1f" % (len(vv), iou.mean(), np.percentile(iou, 10), iou.min(), vv[:, 2].mean(), vv[:, 3].mean()))
