# Copy the per-frame shape corrections of UO_Body onto the SELECTED clothing / armour meshes.
# Use after the item is bound to the rig (Armature modifier + weights, see README). Run with Alt+P in the Text Editor.
# Every vertex takes the correction of the nearest point of the body skin (rest pose), so the item follows the
# corrected body in all 210 UO frames. Run it again after you edit the item's shape.
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform

body = bpy.data.objects["UO_Body"]
rig = bpy.data.objects["UO_Rig"]


def transfer(ob):
    kb = body.data.shape_keys.key_blocks
    basis = np.array([v.co[:] for v in kb["Basis"].data], np.float64)
    body.data.calc_loop_triangles()
    tri = [tuple(t.vertices) for t in body.data.loop_triangles]
    bvh = BVHTree.FromPolygons([Vector(p) for p in basis], tri)
    M = body.matrix_world.inverted() @ ob.matrix_world               # item space -> body space
    R = np.array(M.to_3x3().inverted())                                  # body offsets -> item space
    src = []
    for v in ob.data.vertices:
        p = M @ v.co
        loc, nrm, fi, dist = bvh.find_nearest(p)
        a, b, c = tri[fi]
        A, B, C = (Vector(basis[k]) for k in (a, b, c))
        w = barycentric_transform(loc, A, B, C, Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)))
        src.append((a, b, c, w[0], w[1], w[2]))
    src = np.array(src)
    idx = src[:, :3].astype(int); wts = src[:, 3:]
    if ob.data.shape_keys is None:
        ob.shape_key_add(name="Basis", from_mix=False)
    for k in [k for k in ob.data.shape_keys.key_blocks if k.name.startswith("uo_")]:
        ob.shape_key_remove(k)
    obasis = np.array([v.co[:] for v in ob.data.shape_keys.key_blocks["Basis"].data], np.float64)
    drivers = {d.data_path: d for d in body.data.shape_keys.animation_data.drivers}
    for k in [k for k in kb if k.name.startswith("uo_")]:
        off = np.array([v.co[:] for v in k.data], np.float64) - basis
        o = (off[idx] * wts[..., None]).sum(1) @ R.T
        sk = ob.shape_key_add(name=k.name, from_mix=False)
        sk.data.foreach_set("co", (obasis + o).ravel().astype(np.float32))
        src_d = drivers['key_blocks["%s"].value' % k.name].driver
        d = sk.driver_add("value").driver; d.type = "SCRIPTED"
        for sv in src_d.variables:
            v = d.variables.new(); v.name = sv.name; v.type = sv.type
            v.targets[0].id_type = sv.targets[0].id_type; v.targets[0].id = sv.targets[0].id
            v.targets[0].data_path = sv.targets[0].data_path
        d.expression = src_d.expression
    print("corrections copied to", ob.name, len([k for k in kb if k.name.startswith("uo_")]))


pose = rig.data.pose_position
rig.data.pose_position = "REST"
bpy.context.view_layer.update()
for ob in [o for o in bpy.context.selected_objects if o.type == "MESH" and o != body]:
    transfer(ob)
rig.data.pose_position = pose
