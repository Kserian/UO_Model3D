"""Sideburns / cheek hair as a shell of the head skin, cut away from a beard model so that the two never overlap; written together with the beard as one glb.

    python uo_cheek_shell.py BEARD.glb OUT.glb [--base ../model/UO_Body_0x190.blend] [--x-in X] [--y-max Y] [--z-top Z] [--slope S] [--z-bottom Z] [--thick T] [--clear C] [--preview PNG]

BEARD.glb: the beard in the coordinates of the model (metres, Z up, face to -Y), e.g. from uo_scale_remesh.py. The sideburn of each side is a band on the cheek (the original beard 801 has two such strips in the front view and a patch from the front of the face to the ear in profile): outside |x| = `x-in`,
in front of the ear, from the jaw up to an edge that is high at the ear and falls towards the front; copied, moved out along the skin normals by `thick`, smoothed. Where it comes within `clear` m of the beard surface (or would be inside it) the faces are cut away, so
the beard stays as modelled and the sideburn ends at it. Needs bpy 4.2 (the body from the base .blend, rest pose).
"""
import argparse, os, sys
import bpy, bmesh, numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument("beard"); ap.add_argument("out")
ap.add_argument("--base", default=os.path.join(HERE, "..", "model", "UO_Body_0x190.blend"))
ap.add_argument("--x-in", type=float, default=0.055)      # m, |x| of the inner edge of the band: the face between the two bands (nose, mouth) stays free
ap.add_argument("--y-max", type=float, default=-0.06)     # m, the band starts in front of the ear (front is -Y)
ap.add_argument("--z-top", type=float, default=1.765)     # m, height of the top edge at y = --y-max (next to the ear)
ap.add_argument("--slope", type=float, default=0.5)       # the top edge falls by this much per metre towards the front (the sideburn is high at the ear, low at the cheek)
ap.add_argument("--z-bottom", type=float, default=1.62)   # m, lower edge (jaw corner, where the beard proper begins)
ap.add_argument("--thick", type=float, default=0.016)     # m, the shell stands this far off the skin
ap.add_argument("--clear", type=float, default=0.006)     # m, cut away what is closer than this to the beard
ap.add_argument("--smooth", type=int, default=4)
ap.add_argument("--no-beard", action="store_true", help="write the sideburns only")
a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])

bpy.ops.wm.open_mainfile(filepath=a.base)
body = bpy.data.objects["UO_Body"]
rig = bpy.data.objects["UO_Rig"]; rig.data.pose_position = "REST"; bpy.context.view_layer.update()
me = body.data
names = {g.index: g.name for g in body.vertex_groups}
P = np.array([(body.matrix_world @ v.co)[:] for v in me.vertices])
head = np.array([sum(g.weight for g in v.groups if names[g.group] == "head") >= 0.5 for v in me.vertices])
M3 = np.array(body.matrix_world.to_3x3())
N = np.array([(body.matrix_world.to_3x3() @ v.normal).normalized()[:] for v in me.vertices])

# beard: an own BVH (world coordinates = file coordinates)
bpy.ops.import_scene.gltf(filepath=a.beard)
bobs = [o for o in bpy.data.objects if o.type == "MESH" and o.name != "UO_Body" and o.get("uo_is_beard", True) and o.name not in ("UO_Body",) and not o.name.startswith("Horse") and o.name != "Example_Shirt"
        and o.parent is None]
beard = [o for o in bobs if o.data.name not in [m.name for m in bpy.data.meshes if m.users == 0]][-1]
bm = bmesh.new(); bm.from_mesh(beard.data); bm.transform(beard.matrix_world); bmesh.ops.triangulate(bm, faces=bm.faces)
bco = [v.co.copy() for v in bm.verts]; btri = [[v.index for v in f.verts] for f in bm.faces]; bm.free()
bvh = BVHTree.FromPolygons(bco, btri)

# the band on the skin of each cheek: outside |x| = x_in, in front of the ear, between the jaw and a top edge that falls towards the front
sel = head & (np.abs(P[:, 0]) >= a.x_in) & (P[:, 1] <= a.y_max) & (P[:, 2] >= a.z_bottom) & (P[:, 2] <= a.z_top + a.slope * (P[:, 1] - a.y_max)) & (N[:, 1] < 0.85)
print("uo_cheek_shell: %d skin vertices in the bands" % sel.sum())

# faces inside the bands, copied and moved out
bm = bmesh.new(); bm.from_mesh(me); bm.transform(body.matrix_world); bm.verts.ensure_lookup_table()
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
keep = [f for f in bm.faces if all(sel[v.index] for v in f.verts)]
geom = bmesh.ops.duplicate(bm, geom=keep)
nv = [v for v in geom["geom"] if isinstance(v, bmesh.types.BMVert)]
nf = [f for f in geom["geom"] if isinstance(f, bmesh.types.BMFace)]
old_index = {}
# duplicate keeps no link to the source: find by position
src = {tuple(np.round(P[i], 6)): i for i in np.nonzero(sel)[0]}
for v in nv:
    i = src.get(tuple(np.round(np.array(v.co[:]), 6)))
    v.co = v.co + Vector(N[i] * a.thick) if i is not None else v.co
rest = [f for f in bm.faces if f not in nf]
bmesh.ops.delete(bm, geom=rest, context="FACES")
bm.verts.ensure_lookup_table()
orphans = [v for v in bm.verts if not v.link_faces]
bmesh.ops.delete(bm, geom=orphans, context="VERTS")
# smooth the shell a little (the muscle under it is rougher than hair)
for _ in range(a.smooth):
    bmesh.ops.smooth_vert(bm, verts=bm.verts, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
# cut away what is near or inside the beard
bad = set()
for v in bm.verts:
    loc, nrm, fi, d = bvh.find_nearest(v.co, a.clear * 3)
    if loc is not None:
        side_out = (v.co - loc).dot(nrm)
        if d < a.clear or side_out < 0:
            bad.add(v)
fb = [f for f in bm.faces if any(v in bad for v in f.verts)]
bmesh.ops.delete(bm, geom=fb, context="FACES")
orphans = [v for v in bm.verts if not v.link_faces]; bmesh.ops.delete(bm, geom=orphans, context="VERTS")
print("uo_cheek_shell: shell %d faces, %d cut away near the beard" % (len(bm.faces), len(fb)))
sm = bpy.data.meshes.new("sideburns"); bm.to_mesh(sm); bm.free()
so = bpy.data.objects.new("sideburns", sm); bpy.context.collection.objects.link(so)
mat = bpy.data.materials.new("grey"); mat.use_nodes = True
mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.7, 0.7, 0.7, 1)
sm.materials.append(mat)
for p in sm.polygons:
    p.use_smooth = True

# overlap check: triangles of the two meshes that intersect
bm = bmesh.new(); bm.from_mesh(sm); bmesh.ops.triangulate(bm, faces=bm.faces)
sco = [v.co.copy() for v in bm.verts]; stri = [[v.index for v in f.verts] for f in bm.faces]; bm.free()
ov = BVHTree.FromPolygons(sco, stri).overlap(bvh)
dmin = min((bvh.find_nearest(c)[3] for c in sco), default=0)
print("uo_cheek_shell: intersecting triangle pairs %d, closest distance to the beard %.1f mm" % (len(ov), dmin * 1000))

for o in list(bpy.data.objects):
    if o not in (so, beard):
        bpy.data.objects.remove(o)
if a.no_beard:
    bpy.data.objects.remove(beard)
else:
    bpy.ops.object.select_all(action="DESELECT"); so.select_set(True); beard.select_set(True)
    bpy.context.view_layer.objects.active = beard; bpy.ops.object.join()
bpy.ops.export_scene.gltf(filepath=a.out, export_format="GLB")
print("uo_cheek_shell: wrote", a.out)
