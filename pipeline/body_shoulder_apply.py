"""Narrow the shoulders / thin the arms of the rest mesh `UO_Body` in a .blend and save it (see body_shoulder_lib.py for the parameters).

    python body_shoulder_apply.py ../model/UO_Body_0x190.blend OUT.blend --shift 0.01 --arm 0.95 [--fore 0.95] [--arm-y 1.0] [--fore-y 1.0]

The edit is applied to the CURRENT rest mesh, so to change the amount start again from the .blend before the edit (git: commit before the
"shoulders" commit) or apply the inverse by hand. No shape keys: skinning, UVs, weights, materials unchanged. Refuses to run on a mesh with shape keys.
"""
import sys, argparse
import numpy as np
import bpy
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
import body_shoulder_lib as L

ap = argparse.ArgumentParser(); ap.add_argument("blend"); ap.add_argument("out")
ap.add_argument("--shift", type=float, default=0.0); ap.add_argument("--arm", type=float, default=1.0); ap.add_argument("--fore", type=float)
ap.add_argument("--arm-y", type=float, default=1.0); ap.add_argument("--fore-y", type=float)
a = ap.parse_args()
bpy.ops.wm.open_mainfile(filepath=a.blend)
rig, body = bpy.data.objects["UO_Rig"], bpy.data.objects["UO_Body"]; me = body.data
assert me.shape_keys is None, "body has shape keys"
names = [g.name for g in body.vertex_groups]; gi = {n: i for i, n in enumerate(names)}
W = L.weights(me, len(names))
bones = {b.name: (np.array(b.head_local), np.array(b.tail_local)) for b in rig.data.bones}
co0 = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", co0); co0 = co0.reshape(-1, 3).astype(np.float64)
co = L.edit(co0, W, gi, bones, shift=a.shift, arm=a.arm, fore=a.fore, arm_y=a.arm_y, fore_y=a.fore_y)
me.vertices.foreach_set("co", co.astype(np.float32).ravel()); me.update()
d = np.linalg.norm(co - co0, axis=1)
print("moved %d of %d vertices, mean %.4f m, max %.4f m" % ((d > 1e-9).sum(), len(d), d.mean(), d.max()))
bpy.ops.wm.save_as_mainfile(filepath=a.out)
print("saved", a.out)
