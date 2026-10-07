"""Scale and stretch the meshes of a model file and write a new .glb (a model made in other units or on a mannequin with other proportions than the UO body), before uo_make_item.py.

    python -I stretch_glb.py IN.glb OUT.glb SCALE [SX,SY,SZ]        (bpy 4.2)

SCALE = uniform factor (0.3: the file is 3.3 times too big), SX,SY,SZ = then width, depth, height factors about the centre of the model (0.8,1.25,1.0). The normals are kept smooth.
"""
import sys
import bpy
import numpy as np
from mathutils import Matrix

a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
src, out, k = a[0], a[1], float(a[2])
st = [float(x) for x in a[3].split(",")] if len(a) > 3 else [1.0, 1.0, 1.0]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
obs = [o for o in bpy.data.objects if o.type == "MESH"]
P = np.concatenate([np.array([(o.matrix_world @ v.co)[:] for v in o.data.vertices]) for o in obs])
c = (P.min(0) + P.max(0)) / 2
M = Matrix.Scale(k, 4) @ Matrix.Translation(c) @ Matrix.Diagonal((*st, 1.0)) @ Matrix.Translation(-c)
for o in obs:
    o.data.transform(o.matrix_world); o.matrix_world.identity(); o.data.transform(M)
    o.parent = None
bpy.ops.export_scene.gltf(filepath=out, export_format="GLB")
print("wrote", out, "size", np.round((P.max(0) - P.min(0)) * k * np.array(st), 3))
