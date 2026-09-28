"""Add the clothing-layer workflow to the model .blend: UO_Look node group, Clothing collection, example shirt,
render_uo_layer.py + uo_vd_writer.py text blocks."""
import bpy, sys, os, math, pickle
import numpy as np
from mathutils import Vector

SRC = sys.argv[sys.argv.index("--src") + 1]
OUT = sys.argv[sys.argv.index("--out") + 1]
os.makedirs(OUT, exist_ok=True)
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.open_mainfile(filepath=os.path.abspath(SRC))
sc = bpy.context.scene
body = bpy.data.objects["UO_Body"]; rig = bpy.data.objects["UO_Rig"]
light = pickle.load(open("uo_light.pkl", "rb"))
theta = math.radians(sc["uo_theta_deg"])
right_w = Vector((1, 0, 0)); up_w = Vector((0, math.sin(theta), math.cos(theta))); tow_w = right_w.cross(up_w)
Lc = light["L_camera"]
Lw = (right_w * Lc[0] + up_w * Lc[1] + tow_w * Lc[2]).normalized()
sc["uo_look"] = 1.0

# ---------------------------------------------------------------- node group UO_Look
ng = bpy.data.node_groups.new("UO_Look", "ShaderNodeTree")
ng.interface.new_socket("Albedo", in_out="INPUT", socket_type="NodeSocketColor").default_value = (0.5, 0.5, 0.5, 1)
ng.interface.new_socket("Shader", in_out="OUTPUT", socket_type="NodeSocketShader")
N = ng.nodes.new; L = ng.links.new
gi = N("NodeGroupInput"); gi.location = (-900, 0)
go = N("NodeGroupOutput"); go.location = (600, 0)
bsdf = N("ShaderNodeBsdfPrincipled"); bsdf.location = (-100, 300); bsdf.inputs["Roughness"].default_value = 0.8
geo = N("ShaderNodeNewGeometry"); geo.location = (-900, -300)
ldir = N("ShaderNodeCombineXYZ"); ldir.location = (-900, -550); ldir.label = "UO light direction (world)"
for i, v in enumerate(Lw):
    ldir.inputs[i].default_value = v
dot = N("ShaderNodeVectorMath"); dot.operation = "DOT_PRODUCT"; dot.location = (-650, -350)
mx = N("ShaderNodeMath"); mx.operation = "MAXIMUM"; mx.inputs[1].default_value = 0.0; mx.location = (-450, -350)
mad = N("ShaderNodeMath"); mad.operation = "MULTIPLY_ADD"; mad.location = (-250, -350); mad.label = "ambient + diffuse*cos"
mad.inputs[1].default_value = light["diffuse"]; mad.inputs[2].default_value = light["ambient"]
mul = N("ShaderNodeMix"); mul.data_type = "RGBA"; mul.blend_type = "MULTIPLY"; mul.location = (-50, -150)
mul.inputs["Factor"].default_value = 1.0
emis = N("ShaderNodeEmission"); emis.location = (200, -150)
mix = N("ShaderNodeMixShader"); mix.location = (420, 0)
look = N("ShaderNodeValue"); look.location = (200, 250); look.label = "UO look (driven by scene['uo_look'])"
fc = look.outputs[0].driver_add("default_value")
fc.driver.type = "AVERAGE"
var = fc.driver.variables.new(); var.type = "SINGLE_PROP"
var.targets[0].id_type = "SCENE"; var.targets[0].id = sc; var.targets[0].data_path = '["uo_look"]'
L(gi.outputs["Albedo"], bsdf.inputs["Base Color"])
L(geo.outputs["Normal"], dot.inputs[0]); L(ldir.outputs["Vector"], dot.inputs[1])
L(dot.outputs["Value"], mx.inputs[0]); L(mx.outputs["Value"], mad.inputs[0])
L(gi.outputs["Albedo"], mul.inputs[6]); L(mad.outputs["Value"], mul.inputs[7])
L(mul.outputs[2], emis.inputs["Color"])
L(look.outputs[0], mix.inputs["Fac"])
L(bsdf.outputs["BSDF"], mix.inputs[1]); L(emis.outputs["Emission"], mix.inputs[2])
L(mix.outputs["Shader"], go.inputs["Shader"])

# ---------------------------------------------------------------- body material -> UO_Look group
mat = bpy.data.materials["UO_Skin"]
nt = mat.node_tree
old_mix = next(n for n in nt.nodes if n.type == "MIX_SHADER")
old_mul = next(n for n in nt.nodes if n.type == "MIX" and n.blend_type == "MULTIPLY")
albedo_socket = old_mul.inputs[6].links[0].from_socket          # per-direction albedo selection chain
out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
grp = nt.nodes.new("ShaderNodeGroup"); grp.node_tree = ng; grp.location = (450, -100); grp.label = "UO_Look"
nt.links.new(albedo_socket, grp.inputs["Albedo"])
nt.links.new(grp.outputs["Shader"], out.inputs["Surface"])
for n in list(nt.nodes):
    if n.type in ("MIX_SHADER", "EMISSION", "NEW_GEOMETRY", "COMBXYZ", "VECT_MATH") or n == old_mul \
            or (n.type == "MATH" and n.operation in ("MAXIMUM", "MULTIPLY_ADD")) \
            or (n.type == "VALUE" and n.label.startswith("UO look")):
        nt.nodes.remove(n)
# keep a plain Principled for exporters (export.py links it to the output)
bsdf_b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
tex_global = next(n for n in nt.nodes if n.type == "TEX_IMAGE" and n.image and n.image.name == "UO_Body_Texture")
nt.links.new(tex_global.outputs["Color"], bsdf_b.inputs["Base Color"])

# ---------------------------------------------------------------- Clothing collection + example shirt
col = bpy.data.collections.new("Clothing")
sc.collection.children.link(col)
me = body.data
V = np.array([v.co[:] for v in me.vertices])
nrm = np.array([v.normal[:] for v in me.vertices])
gname = {g.index: g.name for g in body.vertex_groups}
W = {}
for v in me.vertices:
    for g in v.groups:
        W.setdefault(gname[g.group], np.zeros(len(V)))[v.index] = g.weight
shirt_w = sum(W.get(n, 0) for n in ("chest", "spine", "upper_arm.L", "upper_arm.R"))
keepv = shirt_w > 0.5
keepv &= V[:, 2] > (V[:, 2].min() + 0.93)          # not below the belt line
faces = [list(p.vertices) for p in me.polygons if all(keepv[i] for i in p.vertices)]
used = sorted({i for f in faces for i in f})
remap = {o: n for n, o in enumerate(used)}
sv = V[used] + nrm[used] * 0.012                     # 1.2 cm above the skin
sm = bpy.data.meshes.new("Example_Shirt")
sm.from_pydata(sv.tolist(), [], [[remap[i] for i in f] for f in faces])
sm.update()
for p in sm.polygons:
    p.use_smooth = True
shirt = bpy.data.objects.new("Example_Shirt", sm)
col.objects.link(shirt)
for name, w in W.items():
    vg = shirt.vertex_groups.new(name=name)
    for n, o in enumerate(used):
        if w[o] > 0:
            vg.add([n], float(w[o]), "REPLACE")
shirt.parent = rig
mod = shirt.modifiers.new("Armature", "ARMATURE"); mod.object = rig
smat = bpy.data.materials.new("Example_Shirt_Mat"); smat.use_nodes = True
snt = smat.node_tree; snt.nodes.clear()
so = snt.nodes.new("ShaderNodeOutputMaterial"); so.location = (400, 0)
sg = snt.nodes.new("ShaderNodeGroup"); sg.node_tree = ng; sg.location = (150, 0)
sg.inputs["Albedo"].default_value = (0.35, 0.35, 0.35, 1)        # grey = hue-able in UO
sp = snt.nodes.new("ShaderNodeBsdfPrincipled"); sp.location = (150, 300)
sp.inputs["Base Color"].default_value = (0.35, 0.35, 0.35, 1)
snt.links.new(sg.outputs["Shader"], so.inputs["Surface"])
sm.materials.append(smat)
print("example shirt:", len(faces), "faces")

# ---------------------------------------------------------------- text blocks
for name in ("render_uo_sprites.py",):
    if name in bpy.data.texts:
        bpy.data.texts.remove(bpy.data.texts[name])
for name in ("uo_vd_writer.py", "render_uo_layer.py"):
    t = bpy.data.texts.get(name) or bpy.data.texts.new(name)
    t.from_string(open(name).read())
    t.use_module = False   # loaded on demand via as_module(); no auto-run warning
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(os.path.join(OUT, "UO_Body_0x190.blend")))
print("saved")
