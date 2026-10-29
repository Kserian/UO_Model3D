"""A heavy sculpt (millions of vertices, authored large) -> a small solid glb at UO size, placed in the model's coordinates (metres, Z up, face to -Y).

    python uo_scale_remesh.py IN.glb OUT.glb --scale 0.23 [--voxel 0.0035] [--tris 40000] [--move X Y Z] [--cut-z Z] [--stretch SX SY SZ]

Scale first (the voxel size is then in metres of the result), a voxel remesh (the surface detail below the voxel size goes, the lobes of curls stay), triangulate,
decimate to --tris, a plain grey material (the game dyes hair with a hue; uo_materials.py sets the brightness), then move by X Y Z; --cut-z removes everything above that height (after the move; the cut is closed by a flat cap). The model is not otherwise changed
(a model made for the UO head can be placed by hand: --move; recipe "prepare": {"AUTOFIT": false, "FIT": false}). Needs bpy (4.2).
"""
import argparse, sys, time
import bpy, bmesh, numpy as np
from mathutils import Matrix

ap = argparse.ArgumentParser()
ap.add_argument("inp"); ap.add_argument("out")
ap.add_argument("--scale", type=float, required=True)
ap.add_argument("--voxel", type=float, default=0.0035)
ap.add_argument("--tris", type=int, default=40000)
ap.add_argument("--move", type=float, nargs=3, default=[0.0, 0.0, 0.0])
ap.add_argument("--cut-z", type=float, default=None)
ap.add_argument("--stretch", type=float, nargs=3, default=[1.0, 1.0, 1.0], help="extra width / depth / height factors on top of --scale")
a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])

for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
t = time.time()
bpy.ops.import_scene.gltf(filepath=a.inp)
ob = [o for o in bpy.data.objects if o.type == "MESH"][0]
bpy.context.view_layer.objects.active = ob; ob.select_set(True)
me = ob.data
for p in me.polygons:
    p.use_smooth = False
ob.scale = tuple(a.scale * f for f in a.stretch)
bpy.ops.object.transform_apply(scale=True)
print("uo_scale_remesh: imported %d vertices (%.0f s)" % (len(me.vertices), time.time() - t))
me.remesh_voxel_size = a.voxel; me.remesh_voxel_adaptivity = 0.0
bpy.ops.object.voxel_remesh()
bm = bmesh.new(); bm.from_mesh(me)
bmesh.ops.triangulate(bm, faces=bm.faces[:]); bm.to_mesh(me); bm.free()
d = ob.modifiers.new("d", "DECIMATE"); d.ratio = min(1.0, a.tris / len(me.polygons)); bpy.ops.object.modifier_apply(modifier="d")
for p in me.polygons:
    p.use_smooth = True
me.transform(Matrix.Translation(a.move))
if a.cut_z is not None:
    bm = bmesh.new(); bm.from_mesh(me)
    res = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, a.cut_z), plane_no=(0, 0, 1), clear_outer=True)
    border = [e for e in bm.edges if e.is_boundary]
    if border:
        bmesh.ops.holes_fill(bm, edges=border, sides=0)
    bm.to_mesh(me); bm.free()
me.materials.clear()
mat = bpy.data.materials.new("grey"); mat.use_nodes = True
mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.7, 0.7, 0.7, 1)
me.materials.append(mat)
c = np.array([v.co[:] for v in me.vertices])
print("uo_scale_remesh: %d vertices, %d faces, bbox %s .. %s" % (len(me.vertices), len(me.polygons), c.min(0).round(3), c.max(0).round(3)))
bpy.ops.export_scene.gltf(filepath=a.out, export_format="GLB")
