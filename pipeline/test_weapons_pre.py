"""Pre-script of test_weapons.py (run inside Blender by run_render_headless.py --pre): a thin straight shaft in Rest Position along a line given in the
local frame of the hand bone `parent` (hand.L by default; spec in the env var UO_TW_SPEC = json {p, u, s0, s1, radius, part}), bound with uo_bind_item.py to the bone of `part`."""
import bpy, json, os, re, math
import numpy as np
from mathutils import Vector, Matrix

spec = json.loads(os.environ["UO_TW_SPEC"])
rig = bpy.data.objects["UO_Rig"]
H = rig.matrix_world @ rig.data.bones[spec.get("parent", "hand.L")].matrix_local   # hand frame at rest -> world
p, u = np.array(spec["p"]), np.array(spec["u"])
a, b = H @ Vector(p + u * spec["s0"]), H @ Vector(p + u * spec["s1"])
n, r = 12, spec["radius"]
axis = (b - a).normalized(); ref = Vector((0, 1, 0)) if abs(axis.y) < 0.9 else Vector((1, 0, 0))
e1 = axis.cross(ref).normalized(); e2 = axis.cross(e1).normalized()
verts = [a + (e1 * math.cos(2 * math.pi * k / n) + e2 * math.sin(2 * math.pi * k / n)) * r for k in range(n)] + \
        [b + (e1 * math.cos(2 * math.pi * k / n) + e2 * math.sin(2 * math.pi * k / n)) * r for k in range(n)]
faces = [(k, (k + 1) % n, n + (k + 1) % n, n + k) for k in range(n)] + [tuple(range(n))[::-1], tuple(range(n, 2 * n))]
me = bpy.data.meshes.new("TestShaft"); me.from_pydata([v[:] for v in verts], [], faces); me.update()
ob = bpy.data.objects.new("TestShaft", me)
if "Clothing" not in bpy.data.collections:
    bpy.context.scene.collection.children.link(bpy.data.collections.new("Clothing"))
for o in list(bpy.data.collections["Clothing"].objects):
    bpy.data.objects.remove(o)
bpy.data.collections["Clothing"].objects.link(ob)
mat = bpy.data.materials.get("UO_Look") or bpy.data.materials.get("UO_Skin")
if mat: me.materials.append(mat)
bpy.ops.object.select_all(action="DESELECT"); ob.select_set(True); bpy.context.view_layer.objects.active = ob
scripts = os.path.dirname(os.path.abspath(os.environ["UO_TW_SPEC_FILE"])) if "UO_TW_SPEC_FILE" in os.environ else os.getcwd()
text = open(os.path.join(os.environ["UO_TW_SCRIPTS"], "uo_bind_item.py")).read()
text, k = re.subn(r"^PART\s*=.*$", "PART = %r" % spec["part"], text, count=1, flags=re.M); assert k == 1
exec(compile(text, "uo_bind_item.py", "exec"), {"__name__": "__main__"})
