"""Apply a rest-shape displacement D (body_shape_fit.py output, key "D" (N,3) metres) to the body mesh of a .blend and save it.

    python body_shape_apply.py ../model/UO_Body_0x190.blend D.npz OUT.blend [--scale 1.0]

D is added to the vertex coordinates of the rest mesh `UO_Body` (no shape keys, so skinning, UVs, weights and materials stay as they are).
Refuses to run when the mesh already differs from the one D was fitted on (vertex count) or has shape keys.
"""
import sys
import numpy as np
import bpy

blend, dnpz, out = sys.argv[1], sys.argv[2], sys.argv[3]
scale = float(sys.argv[sys.argv.index("--scale") + 1]) if "--scale" in sys.argv else 1.0
bpy.ops.wm.open_mainfile(filepath=blend)
body = bpy.data.objects["UO_Body"]; me = body.data
D = np.load(dnpz)["D"]
assert len(me.vertices) == len(D), "vertex count differs"
assert me.shape_keys is None, "body has shape keys"
co = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", co)
co = co.reshape(-1, 3) + scale * D.astype(np.float32)
me.vertices.foreach_set("co", co.ravel()); me.update()
bpy.ops.wm.save_as_mainfile(filepath=out)
print("saved", out, "mean |D| %.4f m, max %.4f m" % (np.linalg.norm(D, axis=1).mean() * scale, np.linalg.norm(D, axis=1).max() * scale))
