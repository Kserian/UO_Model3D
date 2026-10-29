"""A heavy sculpt (millions of vertices, authored large) -> a small solid glb at UO size, placed in the model's coordinates (metres, Z up, face to -Y).

    python uo_scale_remesh.py IN.glb OUT.glb --scale 0.23 [--voxel 0.0035] [--tris 40000] [--move X Y Z] [--cut-z Z] [--stretch SX SY SZ] [--taper TOP_W END_W POWER] [--tuck Z0 Z1 DY]

Scale first (the voxel size is then in metres of the result), a voxel remesh (the surface detail below the voxel size goes, the lobes of curls stay), triangulate,
decimate to --tris, a plain grey material (the game dyes hair with a hue; uo_materials.py sets the brightness), then move by X Y Z; --cut-z removes everything above that height (after the move; the cut is closed by a flat cap).
--tuck Z0 Z1 DY: above Z0 the beard is pushed backwards (+y) by up to DY m (smoothstep, full at Z1): its top goes into the head, so the head hides it and no flat top edge shows under the chin.
--taper: the width (x) of the result is brought to a profile that is TOP_W m at the top (the jaw), END_W m at the tip, TOP_W..END_W falling as (1 - t) ** POWER along the height t: a beard whose widest part is in the middle (a sculpt of a diamond shape) becomes widest at the chin like the original beards. The model is not otherwise changed
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
ap.add_argument("--taper", type=float, nargs=3, default=None, metavar=("TOP_W", "END_W", "POWER"))
ap.add_argument("--tuck", type=float, nargs=3, default=None, metavar=("Z0", "Z1", "DY"))
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
if a.tuck:
    z0_, z1_, dy_ = a.tuck
    for v in me.vertices:
        t_ = min(max((v.co.z - z0_) / max(z1_ - z0_, 1e-6), 0.0), 1.0); v.co.y += dy_ * t_ * t_ * (3 - 2 * t_)
    me.update()
if a.cut_z is not None:
    bm = bmesh.new(); bm.from_mesh(me)
    res = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, a.cut_z), plane_no=(0, 0, 1), clear_outer=True)
    border = [e for e in bm.edges if e.is_boundary]
    if border:
        bmesh.ops.holes_fill(bm, edges=border, sides=0)
    bm.to_mesh(me); bm.free()
if a.taper:
    top_w, end_w, pw = a.taper
    co = np.array([v.co[:] for v in me.vertices])
    z0, z1 = co[:, 2].max(), co[:, 2].min()
    bins = np.linspace(z1, z0, 31)
    lo_x, hi_x = [], []
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (co[:, 2] >= lo) & (co[:, 2] <= hi)
        lo_x.append(np.percentile(co[m, 0], 4) if m.any() else np.nan); hi_x.append(np.percentile(co[m, 0], 96) if m.any() else np.nan)      # percentiles: single strands that stick out do not set the width
    lo_x, hi_x = np.array(lo_x), np.array(hi_x)
    mid = (bins[:-1] + bins[1:]) / 2; ok = ~np.isnan(lo_x)
    smooth = lambda v: np.convolve(np.pad(v[ok], 1, mode="edge"), np.ones(3) / 3, mode="valid")
    centre = np.interp(co[:, 2], mid[ok], smooth((lo_x + hi_x) / 2))       # the sculpt is not exactly symmetric: the beard is centred on x = 0
    cur = np.interp(co[:, 2], mid[ok], smooth((hi_x - lo_x) / 2))
    t = (z0 - co[:, 2]) / max(z0 - z1, 1e-6)
    want = ((top_w - end_w) * (1 - t) ** pw + end_w) / 2
    f = np.clip(want / np.maximum(cur, 1e-6), 0.3, 5.0)
    for v, c, k in zip(me.vertices, centre, f):
        v.co.x = (v.co.x - c) * k
    me.update()
    print("uo_scale_remesh: taper: width %.3f at the top, %.3f in the middle, %.3f at the tip; factors %.2f .. %.2f" % (top_w, (top_w - end_w) * 0.5 ** pw + end_w, end_w, f.min(), f.max()))
me.materials.clear()
mat = bpy.data.materials.new("grey"); mat.use_nodes = True
mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.7, 0.7, 0.7, 1)
me.materials.append(mat)
c = np.array([v.co[:] for v in me.vertices])
print("uo_scale_remesh: %d vertices, %d faces, bbox %s .. %s" % (len(me.vertices), len(me.polygons), c.min(0).round(3), c.max(0).round(3)))
bpy.ops.export_scene.gltf(filepath=a.out, export_format="GLB")
