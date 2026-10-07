"""Prepare cinto_de_armas.glb for belt_swords_recipe.json: Object_20 (guard) also holds the gold rings that sit on the blade at the mouth of the scabbard. They are split off
(loose parts whose position along the sword axis is > T_RING) as Object_20b, so that the recipe can make them grey together with the blade; the rest stays Object_20a.

    python -I belt_swords_prep.py IN.glb OUT.glb          (bpy 4.2)
"""
import sys
import bpy
import numpy as np

T_RING = -0.47      # m along the axis of the scabbard (Object_24), measured from its centre, file units: the rings are at -0.46..-0.45, the guard at -0.69..-0.51
src, out = sys.argv[-2], sys.argv[-1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
O = bpy.data.objects
V24 = np.array([(O["Object_24"].matrix_world @ v.co)[:] for v in O["Object_24"].data.vertices])
c = V24.mean(0); u = np.linalg.svd(V24 - c, full_matrices=False)[2][0]
u = u if u[1] > 0 else -u
for o in bpy.context.selected_objects:
    o.select_set(False)
g = O["Object_20"]; g.select_set(True); bpy.context.view_layer.objects.active = g
bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.select_all(action="SELECT"); bpy.ops.mesh.separate(type="LOOSE"); bpy.ops.object.mode_set(mode="OBJECT")
pieces = [o for o in O if o.type == "MESH" and o.name.startswith("Object_20")]
ring, rest = [], []
for o in pieces:
    V = np.array([(o.matrix_world @ v.co)[:] for v in o.data.vertices])
    (ring if float(((V - c) @ u).mean()) > T_RING else rest).append(o)
print("pieces", len(pieces), "ring", len(ring), "guard", len(rest))
for name, group in (("Object_20b", ring), ("Object_20a", rest)):
    for o in bpy.context.selected_objects:
        o.select_set(False)
    for o in group:
        o.select_set(True)
    bpy.context.view_layer.objects.active = group[0]; bpy.ops.object.join()
    bpy.context.view_layer.objects.active.name = name
bpy.ops.export_scene.gltf(filepath=out, export_format="GLB")
print("wrote", out)
