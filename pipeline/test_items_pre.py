"""Runs inside bpy (run_render_headless.py --pre): builds a body-hugging replica of one UO item and binds it with uo_bind_item.py.

The replica is the part of the UO_Body skin that the real item covers (vertices whose dominant bone is in `parts`, optionally
cut along a limb bone), moved out along the vertex normals by `thickness` metres. It replaces everything in the Clothing
collection. Settings come from the environment: UO_TEST_SPEC (json file with the item table of test_items.py), UO_TEST_ITEM,
UO_TEST_FIT (1 = also run uo_fit_item.py), UO_TEST_SCRIPTS (folder with uo_bind_item.py / uo_fit_item.py).
"""
import json, os, re

import bmesh
import numpy as np

spec = json.load(open(os.environ["UO_TEST_SPEC"]))[os.environ["UO_TEST_ITEM"]]
scripts = os.environ["UO_TEST_SCRIPTS"]
body, rig = bpy.data.objects["UO_Body"], bpy.data.objects["UO_Rig"]
me = body.data
assert np.allclose(body.scale, 1.0), "UO_Body is scaled"

SUB = {"upper_arm_twist": "upper_arm", "forearm_twist": "forearm", "toe": "foot"}


def base_of(n):
    s = n[-2:] if n.endswith((".L", ".R")) else ""
    b = n[:-2] if s else n
    return ("hand" if b.startswith("finger") else SUB.get(b, b)), s


groups = [base_of(g.name) for g in body.vertex_groups]
dom = [groups[max(v.groups, key=lambda g: g.weight).group] if v.groups else ("", "") for v in me.vertices]
keep = np.array([d[0] in spec["parts"] for d in dom])
co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
nrm = np.empty_like(co); me.vertices.foreach_get("normal", nrm.ravel())
if spec.get("cut"):                                          # drop the near end of a limb bone: boots start up the shin, gloves on the forearm
    bname, t0 = spec["cut"]
    child = {"shin": "foot", "forearm": "hand"}[bname]
    M = np.array(rig.matrix_world.inverted() @ body.matrix_world)
    ca = co @ M[:3, :3].T + M[:3, 3]
    for s in (".L", ".R"):
        h = np.array(rig.data.bones[bname + s].head_local); ax = np.array(rig.data.bones[child + s].head_local) - h
        L = np.linalg.norm(ax); t = ((ca - h) @ (ax / L)) / L
        keep &= ~(np.array([d == (bname, s) for d in dom]) & (t < t0))

if spec.get("zrange"):                                       # height cut in the rest pose (world z), measured from the sprite extent
    z = (co @ np.array(body.matrix_world)[:3, :3].T + np.array(body.matrix_world)[:3, 3])[:, 2]
    keep &= (z >= spec["zrange"][0]) & (z <= spec["zrange"][1])

if spec.get("cut_far"):                                      # drop the far end of a limb bone (short sleeves): keep t <= t1
    bname, t1 = spec["cut_far"]
    child = {"upper_arm": "forearm", "thigh": "shin"}[bname]
    M = np.array(rig.matrix_world.inverted() @ body.matrix_world)
    ca = co @ M[:3, :3].T + M[:3, 3]
    for s_ in (".L", ".R"):
        h = np.array(rig.data.bones[bname + s_].head_local); ax = np.array(rig.data.bones[child + s_].head_local) - h
        L = np.linalg.norm(ax); t = ((ca - h) @ (ax / L)) / L
        keep &= ~(np.array([d == (bname, s_) for d in dom]) & (t > t1))

bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table()
for v in bm.verts:
    v.co += type(v.co)(nrm[v.index] * spec["thickness"])
for lay in list(bm.verts.layers.deform):                     # the replica must not inherit the body's group indices: uo_bind_item makes its own groups
    bm.verts.layers.deform.remove(lay)
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not keep[v.index]], context="VERTS")
item_me = bpy.data.meshes.new("test_" + os.environ["UO_TEST_ITEM"]); bm.to_mesh(item_me); bm.free()
item = bpy.data.objects.new(item_me.name, item_me); item.matrix_world = body.matrix_world.copy()

clo = bpy.data.collections["Clothing"]
shirt = bpy.data.objects.get("Example_Shirt")
if shirt is not None:
    item_me.materials.append(shirt.active_material)           # the UO look; colours do not matter for the silhouette tests
for o in list(clo.all_objects):
    for c in [c for c in bpy.data.collections if o.name in c.objects]:
        c.objects.unlink(o)
clo.objects.link(item)
bpy.context.view_layer.update()
for o in bpy.context.view_layer.objects:
    o.select_set(False)
item.select_set(True); bpy.context.view_layer.objects.active = item


def run(script, **over):
    text = open(os.path.join(scripts, script)).read()
    for k, v in over.items():
        text, n = re.subn(r"^%s\s*=.*$" % k, "%s = %r" % (k, v), text, count=1, flags=re.M)
        assert n == 1, (script, k)
    exec(compile(text, script, "exec"), {"__name__": "__main__"})


if os.environ.get("UO_TEST_FIT") == "1":
    run("uo_fit_item.py")
run("uo_bind_item.py", PART=spec["part"])
print("test_items_pre: %s -> %d vertices, %d faces, PART=%s" % (item.name, len(item_me.vertices), len(item_me.polygons), spec["part"]))
