"""Pre-script of test_weapon_roll.py (run inside Blender by run_render_headless.py --pre): a flat plate (the head learned by weapon_roll_fit.py, cells
(s, u) in m along the class line and across it) in Rest Position on the class line of the weapon bone, turned about the shaft by the offset of this weapon,
bound with uo_bind_item.py; the class bone is re-keyed with the roll per pose (roll composed into the pose turn: R' = R * Rot_u(phi)).
Spec in the env var UO_TR_SPEC = json {cls, parent, part, cells, step, thick, delta, phi: {"a,i": deg} or null, const: deg}."""
import bpy, json, os, re, math
import numpy as np
from mathutils import Vector, Matrix

spec = json.loads(os.environ["UO_TR_SPEC"]); scripts = os.environ["UO_TR_SCRIPTS"]
cls = spec["cls"]
WM = json.loads(bpy.data.texts["weapon_motion.json"].as_string())
C = WM[cls]; u = np.array(C["dir"], float); u /= np.linalg.norm(u); piv = np.array(C["pivot"], float)


def rot(axis, ang):
    return Matrix.Rotation(ang, 3, Vector(axis))


x = np.array([1.0, 0, 0]); e1 = x - (x @ u) * u
if np.linalg.norm(e1) < 0.3:
    x = np.array([0, 1.0, 0]); e1 = x - (x @ u) * u
e1 /= np.linalg.norm(e1)

# 1. the roll per pose through the "roll" field of the class (what uo_weapon_bones.py keys), re-keyed with the uo_weapon_bones.py of this repo
phi = spec.get("phi"); const = math.radians(spec.get("const", 0.0)); mode = spec["mode"]
C.pop("roll", None)
if mode == "class":
    C["roll"] = dict(phi={k: math.radians(v) for k, v in phi.items()})
elif mode == "const":
    C["roll"] = dict(phi={k: const for k in C["poses"]})
t = bpy.data.texts["weapon_motion.json"]; t.clear(); t.write(json.dumps(WM))
src = open(os.path.join(scripts, "uo_weapon_bones.py")).read()
exec(compile(src, "uo_weapon_bones.py", "exec"), {"__name__": "__main__"})

# 2. the plate
rig = bpy.data.objects["UO_Rig"]
H = rig.matrix_world @ rig.data.bones[spec["parent"]].matrix_local
ru = np.array(rot(u, spec["delta"]) @ Vector(e1)); rv = np.cross(u, ru)
step, th = spec["step"], spec["thick"]
verts, faces = [], []
for s, uu in spec["cells"]:
    c = piv + u * s + ru * uu; b = len(verts)
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                q = c + u * sx * step / 2 + ru * sy * step / 2 + rv * sz * th / 2
                verts.append((H @ Vector(q))[:])
    faces += [(b + 0, b + 1, b + 3, b + 2), (b + 4, b + 6, b + 7, b + 5), (b + 0, b + 4, b + 5, b + 1), (b + 2, b + 3, b + 7, b + 6),
              (b + 0, b + 2, b + 6, b + 4), (b + 1, b + 5, b + 7, b + 3)]
me = bpy.data.meshes.new("TestPlate"); me.from_pydata(verts, [], faces); me.update()
ob = bpy.data.objects.new("TestPlate", me)
if "Clothing" not in bpy.data.collections:
    bpy.context.scene.collection.children.link(bpy.data.collections.new("Clothing"))
for o in list(bpy.data.collections["Clothing"].objects):
    bpy.data.objects.remove(o)
bpy.data.collections["Clothing"].objects.link(ob)
mat = bpy.data.materials.get("UO_Look") or bpy.data.materials.get("UO_Skin")
if mat: me.materials.append(mat)
bpy.ops.object.select_all(action="DESELECT"); ob.select_set(True); bpy.context.view_layer.objects.active = ob
text = open(os.path.join(scripts, "uo_bind_item.py")).read()
text, k = re.subn(r"^PART\s*=.*$", "PART = %r" % spec["part"], text, count=1, flags=re.M); assert k == 1
exec(compile(text, "uo_bind_item.py", "exec"), {"__name__": "__main__"})
