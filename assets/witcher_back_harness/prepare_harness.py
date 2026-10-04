"""Sword back harness (Jack Bronswijk, CC BY 4.0) -> UO item: only the straps and the sword stay, the strap follows the torso, the sword is rigid on the back.

    python prepare_harness.py MODEL.glb ../../model/UO_Body_0x190.blend OUT.blend        # bpy 4.2; the .blend needs the current embedded scripts (sync_blend_scripts.py)
    python ../../pipeline/run_render_headless.py OUT.blend OUTDIR LAYER='"clothing"'     # frames + clothing.vd (about 30 min)

What it does (measured / chosen on 2026-10-04):
 1. Import, centimetres -> metres. KEPT: Base_01 and Base_02a (the two straps: diagonal over the chest and the one round the waist) and the sword (handle, handle wrap,
    guard, scabbard). DROPPED: the mannequin, the dagger, the knife, buckles, prongs, loops, ring, latches, the wraps round the scabbard, the short strap Base_02b (it only
    holds the knife) and the blade (it sits hidden inside the scabbard).
 2. The mannequin torso is fitted to the UO body (least squares on the front / back depth along y and on the width of the trunk): the straps get a non-uniform scale
    (here sx 1.145, sy 0.985, sz 1.258) and the move, the sword keeps its real size and gets only the move.
 3. Straps: uo_prepare_item.py with KIND "harness" = densify, uo_fit_item (1.5 cm off the skin; 258 vertices were inside the body, moved up to 6.9 cm), uo_bind_item with
    PART "torso" (weights only from pelvis, spine, chest, neck: the strap moves with the trunk and does not follow the arms or legs).
 4. Sword: uo_bind_item PART "quiver" = 100 % on `chest` (rigid: moves like the back, does not bend). Moved SWORD_BACK = 1.5 cm back so that it clears the skin (min 9 mm)
    and the strap. Custom properties: uo_no_body_gap (render_uo_layer.py does not bend it away from limbs) and uo_behind_torso (the chest hides it where it is more than 12 cm
    behind it, so from the front only the strap shows).
 5. uo_materials.py: textures T_Belts and T_Sword in the UO look (no highlight on the straps).
"""
import re, sys
import numpy as np
import bpy, bmesh
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from scipy import optimize

GLB, SRC, DST = sys.argv[-3:]
STRAP = ["defaultMaterial.001", "defaultMaterial.005"]                                       # Base_01, Base_02a
SWORD = ["defaultMaterial.018", "defaultMaterial.019", "defaultMaterial.020", "defaultMaterial.021"]   # Handle, Wrap, Guard, SM_Scabbard
MANNEQUIN = "defaultMaterial"
SWORD_BACK = 0.015      # m

bpy.ops.wm.open_mainfile(filepath=SRC)
for o in list(bpy.data.objects):
    if o.name == "Example_Shirt":
        bpy.data.objects.remove(o)
body, rig = bpy.data.objects["UO_Body"], bpy.data.objects["UO_Rig"]
rig.data.pose_position = "REST"; bpy.context.view_layer.update()

# --- 1. import and clean
before = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=GLB)
new = [o for o in bpy.data.objects if o not in before]
bake = {}
for o in new:
    if o.type == "MESH":
        me = o.data.copy(); me.transform(o.matrix_world); me.transform(Matrix.Scale(0.01, 4))     # cm -> m
        bake[o.name] = me
for o in new:
    bpy.data.objects.remove(o)


def joined(name, keys):
    bm = bmesh.new(); mats = []
    for k in keys:
        src = bake[k]; first = len(mats); mats += list(src.materials)
        tmp = bmesh.new(); tmp.from_mesh(src)
        for f in tmp.faces:
            f.material_index += first
        tmp.to_mesh(src); tmp.free(); bm.from_mesh(src)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for m in mats:
        me.materials.append(m)
    return bpy.data.objects.new(name, me)


belt, sword = joined("Harness_Belt", STRAP), joined("Harness_Sword", SWORD)
man = bpy.data.objects.new("Mannequin", bake[MANNEQUIN])
for o in (belt, sword, man):
    bpy.context.scene.collection.objects.link(o)

# --- 2. fit the mannequin torso to the UO body
def profile(me, zs, mw=None):
    pts = [mw @ v.co if mw is not None else v.co for v in me.vertices]
    me.calc_loop_triangles()
    bvh = BVHTree.FromPolygons([Vector(p) for p in pts], [t.vertices[:] for t in me.loop_triangles])
    f, b = [], []
    for z in zs:
        h1 = bvh.ray_cast(Vector((0, -3, z)), Vector((0, 1, 0))); h2 = bvh.ray_cast(Vector((0, 3, z)), Vector((0, -1, 0)))
        f.append(h1[0].y if h1[0] else np.nan); b.append(h2[0].y if h2[0] else np.nan)
    return np.array(f), np.array(b)


zm = np.linspace(0.04, 0.50, 24)
mf, mb = profile(man.data, zm)
zb = np.linspace(0.5, 1.9, 400)
bf, bb = profile(body.data, zb, body.matrix_world)
ok = ~np.isnan(mf) & ~np.isnan(mb)
names = {g.index: g.name for g in body.vertex_groups}
Mb = np.array(body.matrix_world)
bco = np.array([(Mb @ np.append(np.array(v.co), 1))[:3] for v in body.data.vertices])
torso = np.array([bool(v.groups) and names[max(v.groups, key=lambda g: g.weight).group] in ("pelvis", "spine", "chest") for v in body.data.vertices])
zw = np.arange(0.86, 1.45, 0.01); wb = np.array([np.ptp(bco[torso & (abs(bco[:, 2] - z) < 0.01), 0]) for z in zw])
mco = np.array([v.co[:] for v in man.data.vertices]); zmw = np.arange(0.01, 0.19, 0.03)      # below the sleeves of the mannequin
wm = np.array([np.ptp(mco[abs(mco[:, 2] - z) < 0.01, 0]) for z in zmw])


def residual(p):
    sx, sy, sz, dz, dy = p
    z = sz * zm[ok] + dz
    r1 = np.r_[sy * mf[ok] + dy - np.interp(z, zb, bf), sy * mb[ok] + dy - np.interp(z, zb, bb)]
    r2 = 2 * (sx * wm - np.interp(sz * zmw + dz, zw, wb))
    return np.r_[r1, r2]


r = optimize.least_squares(residual, [1.1, 1.0, 1.0, 0.9, 0.0], bounds=([0.8, 0.8, 0.8, 0.6, -0.2], [1.5, 1.4, 1.4, 1.3, 0.2]))
sx, sy, sz, dz, dy = r.x
print("harness fit: sx %.3f sy %.3f sz %.3f dz %.3f dy %.3f rms %.1f mm" % (sx, sy, sz, dz, dy, np.sqrt((r.fun ** 2).mean()) * 1000))
belt.data.transform(Matrix.Translation((0, dy, dz)) @ Matrix.Diagonal((sx, sy, sz, 1.0)))
sword.data.transform(Matrix.Translation((0, dy + SWORD_BACK, dz)))
bpy.data.objects.remove(man)
clothing = bpy.data.collections["Clothing"]
for ob in (belt, sword):
    bpy.context.scene.collection.objects.unlink(ob); clothing.objects.link(ob)


def select(*obs):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in obs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]


def run_text(name, **over):
    text = bpy.data.texts[name].as_string()
    for k, v in over.items():
        text, n = re.subn(r"^%s\s*=.*$" % k, "%s = %r" % (k, v), text, count=1, flags=re.M)
        assert n == 1, (name, k)
    exec(compile(text, name, "exec"), {"__name__": "__main__"})


# --- 3. straps and 4. sword
select(belt); run_text("uo_prepare_item.py", KIND="harness")
select(sword); run_text("uo_bind_item.py", PART="quiver")
sword["uo_no_body_gap"] = 1; sword["uo_behind_torso"] = 1
# --- 5. materials
select(belt); run_text("uo_materials.py", METAL=False)
select(sword); run_text("uo_materials.py")
rig.data.pose_position = "POSE"
bpy.ops.wm.save_as_mainfile(filepath=DST)
