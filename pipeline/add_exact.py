"""Blender step: per-frame corrective shape keys (driven by the rig's action + frame), packed original UO frames
(atlas for the shader projection + JSON for the render script), exact-colour projection in the body material,
clothing bound with Surface Deform, new render_uo_layer.py.
usage: python add_exact.py --src out_v10/UO_Body_0x190.blend --out out_v11 --corr corr_all.pkl"""
import bpy, sys, os, pickle, json
import numpy as np
arg = lambda k: sys.argv[sys.argv.index(k) + 1]
SRC, OUT, CORR = arg("--src"), arg("--out"), arg("--corr")
os.makedirs(OUT, exist_ok=True)
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.open_mainfile(filepath=os.path.abspath(SRC))
sc = bpy.context.scene
rig = bpy.data.objects["UO_Rig"]; body = bpy.data.objects["UO_Body"]
corr = pickle.load(open(CORR, "rb"))
acts = {int(a["uo_action"]): a for a in bpy.data.actions if "uo_action" in a}
CYC = {0, 1, 2, 3, 23, 24}
STEP = 3

# ---------------------------------------------------------------- 0) split the few concave quads (Surface Deform needs
#     convex polygons); the split follows Blender's own tessellation, so renders do not change
import bmesh
rig.animation_data.action = None
me = body.data
if me.shape_keys is None:
    me.calc_loop_triangles()
    lt = {}
    for t in me.loop_triangles:
        lt.setdefault(t.polygon_index, []).append(tuple(t.vertices))
    conc = []
    for p in me.polygons:
        if len(p.vertices) != 4:
            continue
        v = [me.vertices[k].co for k in p.vertices]
        sg = [((v[(k + 1) % 4] - v[k]).cross(v[(k + 2) % 4] - v[(k + 1) % 4])).dot(p.normal) > 0 for k in range(4)]
        if not all(sg):
            conc.append(p.index)
    bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table(); bm.verts.ensure_lookup_table()
    uvl = bm.loops.layers.uv.active
    for pi, f in [(pi, bm.faces[pi]) for pi in conc]:
        uv = {l.vert.index: l[uvl].uv.copy() for l in f.loops} if uvl else {}
        smooth, mi = f.smooth, f.material_index
        new_faces = []
        for tri in lt[pi]:
            nf = bm.faces.new([bm.verts[k] for k in tri]); nf.smooth = smooth; nf.material_index = mi
            if uvl:
                for l in nf.loops: l[uvl].uv = uv[l.vert.index]
            new_faces.append(nf)
        bm.faces.remove(f)
    bm.normal_update(); bm.to_mesh(me); bm.free(); me.update()
    print("split concave quads:", len(conc))

# ---------------------------------------------------------------- 1) corrective shape keys
# every UO action keys the rig property "uo_action_id" (constant), so the shape-key drivers know the current action
rig["uo_action_id"] = -1
for a_, act_ in acts.items():
    for fc in [fc for fc in act_.fcurves if fc.data_path == '["uo_action_id"]']:
        act_.fcurves.remove(fc)
    fc = act_.fcurves.new('["uo_action_id"]')
    kp = fc.keyframe_points.insert(1, float(a_)); kp.interpolation = "CONSTANT"
me = body.data
if me.shape_keys is None:
    body.shape_key_add(name="Basis", from_mix=False)
kb = me.shape_keys.key_blocks
base = np.zeros(len(me.vertices) * 3, np.float32); kb["Basis"].data.foreach_get("co", base); base = base.reshape(-1, 3)
for k in [k for k in kb if k.name.startswith("uo_")]:
    body.shape_key_remove(k)
n = 0
for (a, i), r in sorted(corr.items()):
    F = int(acts[a]["uo_frames"])
    sk = body.shape_key_add(name="uo_%02d_%02d" % (a, i), from_mix=False)
    sk.data.foreach_set("co", (base + r["D"]).ravel())
    sk.slider_min, sk.slider_max = 0.0, 1.0
    d = sk.driver_add("value").driver
    d.type = "SCRIPTED"
    v = d.variables.new(); v.name = "ua"; v.type = "SINGLE_PROP"
    v.targets[0].id_type = "OBJECT"; v.targets[0].id = rig; v.targets[0].data_path = '["uo_action_id"]'
    f0 = 1 + STEP * i
    e = "(ua == %d) * max(0, 1 - abs(frame - %d) / %d)" % (a, f0, STEP)
    if a in CYC and i == 0 and F > 1:
        e = "(ua == %d) * max(0, 1 - abs(frame - %d) / %d, 1 - abs(frame - %d) / %d)" % (a, f0, STEP, f0 + STEP * F, STEP)
    d.expression = e
    n += 1
    for dk, E in sorted((r.get("Ed") or {}).items()):     # per-direction correction: only in UO direction dk
        if float(np.abs(E).max()) < 1e-5:
            continue
        sk2 = body.shape_key_add(name="uo_%02d_%02d_d%d" % (a, i, dk), from_mix=False)
        sk2.data.foreach_set("co", (base + E).ravel())
        sk2.slider_min, sk2.slider_max = 0.0, 1.0
        d2 = sk2.driver_add("value").driver; d2.type = "SCRIPTED"
        for nm, path in (("ua", '["uo_action_id"]'), ("dd", '["uo_direction"]')):
            v2 = d2.variables.new(); v2.name = nm; v2.type = "SINGLE_PROP"
            v2.targets[0].id_type = "OBJECT"; v2.targets[0].id = rig; v2.targets[0].data_path = path
        d2.expression = e.replace("(ua == %d)" % a, "(ua == %d) * (dd == %d)" % (a, dk), 1)
        n += 1
me.shape_keys.use_relative = True
print("shape keys", n, "simple expressions:", all(k.driver.is_simple_expression for k in me.shape_keys.animation_data.drivers))
rig.animation_data.action = acts[4]; sc.frame_set(1)
print("check: driver valid", all(k.driver.is_valid for k in me.shape_keys.animation_data.drivers),
      "stand key value", me.shape_keys.key_blocks.get("uo_04_00").value if me.shape_keys.key_blocks.get("uo_04_00") else None)
rig.animation_data.action = None

# ---------------------------------------------------------------- 2) original frames
old = bpy.data.images.get("UO_Original_Atlas")
if old:
    bpy.data.images.remove(old)
img = bpy.data.images.load(os.path.abspath("UO_Original_Atlas.png")); img.name = "UO_Original_Atlas"
img.colorspace_settings.name = "sRGB"; img.alpha_mode = "STRAIGHT"; img.pack()
meta = json.load(open("uo_original_frames.json"))
t = bpy.data.texts.get("uo_original_frames.json") or bpy.data.texts.new("uo_original_frames.json")
t.from_string(json.dumps(meta))
sc["uo_tile_col"] = 0; sc["uo_tile_row"] = 0; sc["uo_exact"] = 1.0

# ---------------------------------------------------------------- 3) projection in the body material
mat = body.data.materials[0]; nt = mat.node_tree; N = nt.nodes.new; L = nt.links.new
for nd in [nd for nd in nt.nodes if nd.name.startswith("UOX_")]:
    nt.nodes.remove(nd)
out = next(nd for nd in nt.nodes if nd.type == "OUTPUT_MATERIAL")
grp = next(nd for nd in nt.nodes if nd.type == "GROUP" and nd.node_tree and nd.node_tree.name == "UO_Look")


def node(kind, name, loc, label=None):
    nd = N(kind); nd.name = "UOX_" + name; nd.location = loc; nd.label = label or name; return nd


def driven_value(name, prop, loc):
    nd = node("ShaderNodeValue", name, loc, "scene['%s'] (driver)" % prop)
    dr = nd.outputs[0].driver_add("default_value").driver; dr.type = "SCRIPTED"
    v = dr.variables.new(); v.name = "p"; v.type = "SINGLE_PROP"; v.targets[0].id_type = "SCENE"; v.targets[0].id = sc
    v.targets[0].data_path = '["%s"]' % prop; dr.expression = "p"
    return nd


def math(op, name, loc, a=None, b=None):
    nd = node("ShaderNodeMath", name, loc); nd.operation = op
    for k_, x in enumerate((a, b)):
        if x is None: continue
        if isinstance(x, (int, float)): nd.inputs[k_].default_value = x
        else: L(x, nd.inputs[k_])
    return nd


X0, Y0 = 400, -900
tc = node("ShaderNodeTexCoord", "texco", (X0 - 1400, Y0))
sep = node("ShaderNodeSeparateXYZ", "sep", (X0 - 1200, Y0)); L(tc.outputs["Window"], sep.inputs[0])
col = driven_value("col", "uo_tile_col", (X0 - 1200, Y0 - 200)); row = driven_value("row", "uo_tile_row", (X0 - 1200, Y0 - 300))
ex = driven_value("exact", "uo_exact", (X0 - 400, Y0 - 350)); lk = driven_value("look", "uo_look", (X0 - 400, Y0 - 450))
C, R = meta["cols"], meta["rows"]
u = math("MULTIPLY", "u", (X0 - 800, Y0), math("ADD", "u0", (X0 - 1000, Y0), col.outputs[0], sep.outputs["X"]).outputs[0], 1.0 / C)
v1 = math("SUBTRACT", "v0", (X0 - 1000, Y0 - 150), sep.outputs["Y"], row.outputs[0])
v = math("MULTIPLY", "v", (X0 - 800, Y0 - 150), math("ADD", "v1", (X0 - 900, Y0 - 150), v1.outputs[0], float(R - 1)).outputs[0], 1.0 / R)
cmb = node("ShaderNodeCombineXYZ", "uv", (X0 - 600, Y0)); L(u.outputs[0], cmb.inputs[0]); L(v.outputs[0], cmb.inputs[1])
tex = node("ShaderNodeTexImage", "atlas", (X0 - 400, Y0), "original UO frame (projected from the UO camera)")
tex.image = img; tex.interpolation = "Closest"; tex.extension = "CLIP"; L(cmb.outputs[0], tex.inputs[0])
em = node("ShaderNodeEmission", "emit", (X0 - 100, Y0)); L(tex.outputs["Color"], em.inputs["Color"])
fac = math("MULTIPLY", "fac", (X0 - 100, Y0 - 300), math("MULTIPLY", "fac0", (X0 - 250, Y0 - 300), tex.outputs["Alpha"], ex.outputs[0]).outputs[0], lk.outputs[0])
mix = node("ShaderNodeMixShader", "mix", (X0 + 150, Y0 + 300), "exact UO colours (original frames) / model")
L(fac.outputs[0], mix.inputs[0]); L(grp.outputs[0], mix.inputs[1]); L(em.outputs[0], mix.inputs[2])
L(mix.outputs[0], out.inputs["Surface"])

# ---------------------------------------------------------------- 4) clothing follows the corrected body:
#     Armature (as before) + the body's corrections copied onto the item (text block uo_transfer_corrections.py)
tt = bpy.data.texts.get("uo_transfer_corrections.py") or bpy.data.texts.new("uo_transfer_corrections.py")
tt.from_string(open("uo_transfer_corrections.py").read())
tb = bpy.data.texts.get("uo_bind_item.py") or bpy.data.texts.new("uo_bind_item.py")   # one-click bind (weights per body part)
tb.from_string(open("uo_bind_item.py").read())
tf = bpy.data.texts.get("uo_fit_item.py") or bpy.data.texts.new("uo_fit_item.py")      # push the item out of the skin
tf.from_string(open("uo_fit_item.py").read())
bpy.ops.object.select_all(action="DESELECT")
for ob in (bpy.data.collections["Clothing"].all_objects if "Clothing" in bpy.data.collections else []):
    if ob.type == "MESH":
        for m_ in [m_ for m_ in ob.modifiers if m_.type == "SURFACE_DEFORM"]:
            ob.modifiers.remove(m_)
        if not any(m_.type == "ARMATURE" for m_ in ob.modifiers):
            am = ob.modifiers.new("Armature", "ARMATURE"); am.object = rig
        ob.select_set(True)
rig.animation_data.action = None
exec(compile(tt.as_string(), "uo_transfer_corrections.py", "exec"), {"__name__": "__main__"})
rig.animation_data.action = acts[4]

# ---------------------------------------------------------------- 5) render script
txt = bpy.data.texts.get("render_uo_layer.py") or bpy.data.texts.new("render_uo_layer.py")
txt.from_string(open("render_uo_layer.py").read())
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(os.path.join(OUT, "UO_Body_0x190.blend")))
print("saved")
