"""horse proxy meshes (rig space) per mounted frame -> horse.npz"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
import bpy, numpy as np
bpy.ops.wm.open_mainfile(filepath=os.path.join(HERE, "..", "..", "model", "UO_Body_0x190.blend"))
rig = bpy.data.objects["UO_Rig"]; rig["uo_direction"] = 0; rig.update_tag(); bpy.context.view_layer.update()
out = {}
for o in bpy.data.objects:
    if o.name.startswith("Horse_a"):
        a, f = o.name[7:].split("_f"); M = np.array(rig.matrix_world.inverted() @ o.matrix_world)
        co = np.array([M[:3, :3] @ np.array(v.co) + M[:3, 3] for v in o.data.vertices])
        o.data.calc_loop_triangles(); tri = np.array([t.vertices[:] for t in o.data.loop_triangles])
        out["v_%s_%s" % (a, f)] = co; out["t_%s_%s" % (a, f)] = tri
np.savez_compressed("horse.npz", **out); print(len(out) // 2, "horse meshes")
