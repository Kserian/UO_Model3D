"""A wedge above a jaw plane, rigid on the head when rendered: its silhouette in each frame is the part of the face above the jaw line (the zone that uo_hybrid_beard.py takes from the original beard).

    python uo_jaw_zone.py OUT.glb [Z_FRONT 1.64] [Z_BACK 1.74]      (metres, Z up, face to -Y; the plane rises from the chin to the ear)
"""
import sys
import bpy

out = sys.argv[sys.argv.index("--") + 1 if "--" in sys.argv else 1]
rest = [float(x) for x in sys.argv[(sys.argv.index("--") + 2 if "--" in sys.argv else 2):]]
zf, zb = (rest + [1.64, 1.74])[:2]
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
xf, yf, yb, zt = 0.24, -0.27, 0.13, 1.99
V = [(-xf, yf, zf), (xf, yf, zf), (xf, yb, zb), (-xf, yb, zb), (-xf, yf, zt), (xf, yf, zt), (xf, yb, zt), (-xf, yb, zt)]
F = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
me = bpy.data.meshes.new("zone"); me.from_pydata(V, [], F); me.update()
ob = bpy.data.objects.new("zone", me); bpy.context.collection.objects.link(ob)
mat = bpy.data.materials.new("g"); mat.use_nodes = True; me.materials.append(mat)
bpy.ops.export_scene.gltf(filepath=out, export_format="GLB")
