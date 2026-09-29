"""random outfit on the v13 body: procedural items built from the body skin (shells), the cloth templates and simple
props, each fitted + bound with the user scripts (uo_fit_item / uo_bind_item presets), then rendered.
usage: gen_items.py v13.blend out_dir seed actions(comma names) [--layers]
  --layers: also render every item as its own UO layer (clothing), else only the preview (LAYER = "all")"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
import bpy, bmesh, sys, os, json, random, re
import numpy as np
from mathutils import Vector, Matrix

args = [a for a in sys.argv[sys.argv.index("--") + 1:]] if "--" in sys.argv else sys.argv[-4:]
blend, out_dir, seed, only = args[0], os.path.abspath(args[1]), int(args[2]), args[3].split(",")
LAYERS = "--layers" in sys.argv
os.makedirs(out_dir, exist_ok=True)
rnd = random.Random(seed)
bpy.ops.wm.open_mainfile(filepath=blend)
sc = bpy.context.scene; rig = bpy.data.objects["UO_Rig"]; body = bpy.data.objects["UO_Body"]
rig.animation_data.action = None; rig["uo_direction"] = 0; rig.data.pose_position = "REST"; bpy.context.view_layer.update()
cl = bpy.data.collections["Clothing"]
for o in list(cl.objects):
    cl.objects.unlink(o)
    if not o.users_collection: sc.collection.objects.link(o)
    o.hide_render = True; o.hide_viewport = True

SUB = {"upper_arm_twist": "upper_arm", "forearm_twist": "forearm", "toe": "foot"}
def group_of(n):
    s = n[-2:] if n.endswith((".L", ".R")) else ""
    b = n[:-2] if s else n
    return ("hand" if b.startswith("finger") else SUB.get(b, b)), s

me = body.data
gnames = [g.name for g in body.vertex_groups]
W = np.zeros((len(me.vertices), len(gnames)))
for v in me.vertices:
    for g in v.groups: W[v.index, g.group] = g.weight
dom_base = np.array([group_of(gnames[j])[0] for j in W.argmax(1)])
dom_side = np.array([group_of(gnames[j])[1] for j in W.argmax(1)])
CO = np.array([v.co[:] for v in me.vertices]); NO = np.array([v.normal[:] for v in me.vertices])
bone = lambda n: rig.data.bones[n]
def bone_t(name, X):
    b = bone(name); h = np.array(b.head_local); t = np.array(b.tail_local)
    return ((X - h) @ (t - h)) / ((t - h) @ (t - h))

def uo_material(name, rgb, metal=False):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    for n in [n for n in nt.nodes if n.type != "OUTPUT_MATERIAL"]: nt.nodes.remove(n)
    grp = nt.nodes.new("ShaderNodeGroup"); grp.node_tree = bpy.data.node_groups["UO_Look"]
    alb = next((i for i in grp.inputs if i.name.lower().startswith("albedo")), grp.inputs[0])
    alb.default_value = (*rgb, 1.0)
    nt.links.new(grp.outputs[0], out.inputs["Surface"])
    return m

def shell(name, keep, thick, rgb):
    """item from the body skin: faces whose vertices are all kept, pushed out along the normals"""
    idx = np.nonzero(keep)[0]; remap = -np.ones(len(CO), int); remap[idx] = np.arange(len(idx))
    faces = [[remap[i] for i in p.vertices] for p in me.polygons if keep[list(p.vertices)].all()]
    V = CO[idx] + NO[idx] * thick
    m = bpy.data.meshes.new(name); m.from_pydata(V.tolist(), [], faces); m.update()
    for p in m.polygons: p.use_smooth = True
    ob = bpy.data.objects.new(name, m); cl.objects.link(ob); m.materials.append(uo_material(name + "_mat", rgb))
    return ob

def part(*bases, side=None):
    k = np.isin(dom_base, bases)
    if side: k &= dom_side == side
    return k

def fit_bind(ob, PART, fit=True):
    for o in bpy.context.selected_objects: o.select_set(False)
    ob.select_set(True); bpy.context.view_layer.objects.active = ob
    if fit:
        exec(compile(bpy.data.texts["uo_fit_item.py"].as_string(), "uo_fit_item.py", "exec"), {"__name__": "__main__"})
    src = bpy.data.texts["uo_bind_item.py"].as_string().replace('PART = "all"', 'PART = %r' % PART, 1)
    exec(compile(src, "uo_bind_item.py", "exec"), {"__name__": "__main__"})

PAL = {"steel": (0.62, 0.64, 0.68), "dark": (0.22, 0.22, 0.25), "gold": (0.78, 0.6, 0.25), "red": (0.55, 0.12, 0.1),
       "green": (0.18, 0.38, 0.18), "blue": (0.15, 0.25, 0.55), "leather": (0.42, 0.27, 0.15), "cloth": (0.75, 0.7, 0.58),
       "purple": (0.4, 0.18, 0.45), "black": (0.08, 0.08, 0.09)}
pick = lambda *k: PAL[rnd.choice(k)]
items = []

# ---------------------------------------------------------------- torso
if rnd.random() < 0.6:
    k = part("pelvis", "spine", "chest", "clavicle", "neck") & (CO[:, 2] < 1.62)
    ob = shell("Item_ChestPlate", k, 0.03, pick("steel", "dark", "gold")); fit_bind(ob, "chest", fit=False); items.append(ob)
    for s in (".L", ".R"):                                            # pauldrons
        h = np.array(bone("upper_arm" + s).head_local)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.11, location=Vector(h + np.array([0, 0, 0.03])))
        pd = bpy.context.active_object; pd.name = "Item_Pauldron" + s; pd.scale = (1.15, 1.0, 0.75)
        for c in pd.users_collection: c.objects.unlink(pd)
        cl.objects.link(pd); pd.data.materials.append(ob.data.materials[0])
        bpy.ops.object.select_all(action="DESELECT"); pd.select_set(True); bpy.context.view_layer.objects.active = pd
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        fit_bind(pd, "shoulders"); items.append(pd)
else:
    sleeve = rnd.choice(["short", "elbow", "long"])
    k = part("pelvis", "spine", "chest", "clavicle", "neck") & (CO[:, 2] < 1.6)
    ka = np.zeros(len(CO), bool)
    for s in (".L", ".R"):
        ua = (dom_side == s) & (dom_base == "upper_arm"); fa = (dom_side == s) & (dom_base == "forearm")
        ka |= ua & (bone_t("upper_arm" + s, CO) < (0.55 if sleeve == "short" else 2))
        if sleeve == "long": ka |= fa & (bone_t("forearm" + s, CO) < 0.85)
    ob = shell("Item_Shirt", k | ka, 0.012, pick("cloth", "red", "green", "blue", "purple")); fit_bind(ob, "chest", fit=False); items.append(ob)
# ---------------------------------------------------------------- legs
lower = rnd.choice(["pants", "pants", "skirt"])
if lower == "pants":
    k = part("pelvis", "thigh", "shin") & (CO[:, 2] < 1.08)
    ob = shell("Item_Pants", k, 0.012, pick("leather", "cloth", "dark", "blue")); fit_bind(ob, "legs", fit=False); items.append(ob)
else:
    tpl = bpy.data.objects["UO_Template_Skirt"]
    ob = bpy.data.objects.new("Item_Skirt", tpl.data.copy()); cl.objects.link(ob); ob.matrix_world = tpl.matrix_world.copy()
    ob.vertex_groups.clear(); ob.data.materials.clear(); ob.data.materials.append(uo_material("skirt_mat", pick("red", "green", "blue", "purple")))
    fit_bind(ob, "skirt", fit=False); items.append(ob)
# ---------------------------------------------------------------- boots, gloves
tb = np.zeros(len(CO), bool)
for s in (".L", ".R"):
    tb |= (dom_side == s) & (((dom_base == "shin") & (bone_t("shin" + s, CO) > 0.45)) | (dom_base == "foot"))
ob = shell("Item_Boots", tb, 0.015, pick("leather", "dark", "black")); fit_bind(ob, "boots", fit=False); items.append(ob)
if rnd.random() < 0.6:
    tg = np.zeros(len(CO), bool)
    for s in (".L", ".R"):
        tg |= (dom_side == s) & (((dom_base == "forearm") & (bone_t("forearm" + s, CO) > 0.55)) | (dom_base == "hand"))
    ob = shell("Item_Gloves", tg, 0.01, pick("leather", "dark", "steel")); fit_bind(ob, "gloves", fit=False); items.append(ob)
# ---------------------------------------------------------------- head: helmet or hair (+ beard)
top = CO[:, 2].max()
if rnd.random() < 0.5:
    k = part("head") & (CO[:, 2] > top - 0.13)
    ob = shell("Item_Helm", k, 0.022, pick("steel", "dark", "gold")); fit_bind(ob, "helm", fit=False); items.append(ob)
else:
    face = (CO[:, 1] < np.percentile(CO[part("head"), 1], 35)) & (CO[:, 2] < top - 0.05)
    long_ = rnd.random() < 0.5
    k = part("head") & (CO[:, 2] > top - (0.2 if long_ else 0.11)) & ~face
    if long_: k |= part("neck") & (CO[:, 1] > np.median(CO[part("neck"), 1]))
    ob = shell("Item_Hair", k, 0.02, pick("black", "leather", "gold")); fit_bind(ob, "hair", fit=False); items.append(ob)
# ---------------------------------------------------------------- cloak
if rnd.random() < 0.5:
    tpl = bpy.data.objects["UO_Template_Cloak"]
    ob = bpy.data.objects.new("Item_Cloak", tpl.data.copy()); cl.objects.link(ob); ob.matrix_world = tpl.matrix_world.copy()
    ob.vertex_groups.clear(); ob.data.materials.clear(); ob.data.materials.append(uo_material("cloak_mat", pick("red", "green", "blue", "black", "purple")))
    fit_bind(ob, "cloak", fit=False); items.append(ob)
# ---------------------------------------------------------------- weapon + shield (rigid)
if rnd.random() < 0.8:
    g = json.load(open(os.path.join(HERE, "grip_katana2.json")))                  # grip calibrated on the UO katana frames
    Mb = np.array(bone(g["bone"]).matrix_local)
    grip = (Mb @ np.r_[g["grip"], 1])[:3]; ax = Mb[:3, :3] @ np.array(g["dir"]); ax /= np.linalg.norm(ax)
    pz = np.cross(ax, Mb[:3, 0]); pz /= np.linalg.norm(pz)
    L = rnd.choice([0.7, 0.85, 1.0])
    bm = bmesh.new()
    def box(c, size, R):
        vs = []
        for dx in (-0.5, 0.5):
            for dy in (-0.5, 0.5):
                for dz in (-0.5, 0.5):
                    vs.append(bm.verts.new(Vector(c + R @ (np.array([dx, dy, dz]) * size))))
        for f in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
            bm.faces.new([vs[i] for i in f])
    y = np.cross(pz, ax); R = np.stack([ax, y, pz], 1)
    box(grip + ax * (0.12 + L / 2), np.array([L, 0.05, 0.012]), R)             # blade
    box(grip + ax * 0.1, np.array([0.03, 0.22, 0.035]), R)                      # cross guard
    box(grip + ax * 0.02, np.array([0.16, 0.035, 0.035]), R)                     # grip
    m = bpy.data.meshes.new("Item_Sword"); bm.to_mesh(m); bm.free()
    ob = bpy.data.objects.new("Item_Sword", m); cl.objects.link(ob); m.materials.append(uo_material("sword_mat", PAL["steel"]))
    fit_bind(ob, "weapon", fit=False); items.append(ob)
    if rnd.random() < 0.6:
        sh_ = json.load(open(os.path.join(HERE, "shield_heater.json")))                  # calibrated on the UO heater shield frames
        Mf = np.array(bone(sh_["bone"]).matrix_local)
        c = (Mf @ np.r_[sh_["centre"], 1])[:3]; nrm = Mf[:3, :3] @ np.array(sh_["normal"]); nrm /= np.linalg.norm(nrm)
        bpy.ops.mesh.primitive_cylinder_add(radius=sh_["radius"] * rnd.choice([0.8, 0.95]), depth=0.03, vertices=24, location=Vector(c))
        sh = bpy.context.active_object; sh.name = "Item_Shield"
        sh.rotation_mode = "QUATERNION"; sh.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(Vector(nrm))
        for cc in sh.users_collection: cc.objects.unlink(sh)
        cl.objects.link(sh); sh.data.materials.append(uo_material("shield_mat", pick("red", "blue", "gold", "leather")))
        bpy.ops.object.select_all(action="DESELECT"); sh.select_set(True); bpy.context.view_layer.objects.active = sh
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        fit_bind(sh, "shield", fit=False); items.append(sh)

rig.data.pose_position = "POSE"
print("ITEMS", [o.name for o in items])
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, "outfit_%d.blend" % seed), compress=True)

def render(layer, sub, objs=None):
    if objs is not None:
        for o in cl.objects: o.hide_render = o not in objs
    r = bpy.data.texts["render_uo_layer.py"].as_string()
    r = re.sub(r'(?m)^LAYER = "clothing"', 'LAYER = %r' % layer, r, count=1)
    r = re.sub(r'(?m)^ONLY = \[\]', 'ONLY = %r' % only, r, count=1)
    r = r.replace('OUT_DIR = "//uo_render/"', 'OUT_DIR = %r' % (os.path.join(out_dir, sub) + "/"), 1)
    r = r.replace('VD_FILE = "//uo_render/%s.vd"', 'VD_FILE = %r' % (os.path.join(out_dir, sub, "%s.vd")), 1)
    exec(compile(r, "render_uo_layer.py", "exec"), {"__name__": "__main__"})

render("all", "preview")
if LAYERS:
    for o in items:
        render("clothing", "layer_" + o.name[5:], [o])
print("GEN_DONE")
