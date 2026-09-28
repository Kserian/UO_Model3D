"""Apply the all-frames refinement to the finished .blend: vertex offsets, refined poses, all-frames texture,
'UO look' material (unlit, grey like the sprites), half-pixel camera correction. Saves a new .blend."""
import bpy, sys, os, math, pickle
import numpy as np
from mathutils import Vector
import jax.numpy as jnp
from body import JI, NJ, CANVAS_W, CANVAS_H, ANCHOR_X, ANCHOR_Y
from fit import params_to_shape, pose_from_params
from rig import bone_defs, apply_pose
from vd import ACTIONS_PEOPLE

SRC = sys.argv[sys.argv.index("--src") + 1]
OUT = sys.argv[sys.argv.index("--out") + 1]
TEXPNG = sys.argv[sys.argv.index("--tex") + 1]
LIGHT = pickle.load(open(sys.argv[sys.argv.index("--light") + 1], "rb")) if "--light" in sys.argv else None
PERDIR = sys.argv[sys.argv.index("--perdir") + 1] if "--perdir" in sys.argv else None   # e.g. UO_Body_Albedo_dir
FINAL = pickle.load(open(sys.argv[sys.argv.index("--poses") + 1], "rb")) if "--poses" in sys.argv else None
os.makedirs(OUT, exist_ok=True)
STEP = 3
PX_OFF = 0.5
# the UO anchor lies ~7 cm above the soles of standing frames: lift the animation (and the camera) so that the floor is z = 0
LIFT = float(sys.argv[sys.argv.index("--lift") + 1]) if "--lift" in sys.argv else 0.070

bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.open_mainfile(filepath=os.path.abspath(SRC))
sc = bpy.context.scene
body = bpy.data.objects["UO_Body"]; arm = bpy.data.objects["UO_Rig"]
sf = pickle.load(open("shape_fit.pkl", "rb"))
S = params_to_shape({k: jnp.asarray(v) for k, v in sf["params"]["shape"].items()}, {k: jnp.asarray(v) for k, v in sf["fixed"].items()})
Snp = {k: np.asarray(v, np.float64) for k, v in S.items()}
md = pickle.load(open("mesh_data.pkl", "rb"))
ref = pickle.load(open("refine_mesh.pkl", "rb"))
DELTA = pickle.load(open(sys.argv[sys.argv.index("--delta") + 1], "rb"))["delta"] if "--delta" in sys.argv else ref["delta"]
anim = pickle.load(open("anim_fit.pkl", "rb"))

# 1) rest-pose vertex positions
arm.animation_data.action = None
apply_pose(arm, {d[0]: d[1] for d in bone_defs(Snp, np.zeros((NJ, 3)))}, np.zeros((NJ, 3)), np.zeros(3))
newv = (md["v"] + DELTA).astype(np.float32)
body.data.vertices.foreach_set("co", newv.ravel())
body.data.update()

# 2) texture
img = bpy.data.images.get("UO_Body_Texture")
src = bpy.data.images.load(os.path.abspath(TEXPNG))
px = np.zeros(src.size[0] * src.size[1] * 4, np.float32); src.pixels.foreach_get(px)
if img is None or tuple(img.size) != tuple(src.size):
    img = bpy.data.images.new("UO_Body_Texture", src.size[0], src.size[1], alpha=False)
img.pixels.foreach_set(px)
img.update()
img.pack()
img.filepath = "//UO_Body_Texture.png"
bpy.data.images.remove(src)
old_grey = bpy.data.images.get("UO_Body_Texture_grey")
if old_grey:
    bpy.data.images.remove(old_grey)

# 3) material. The sprites were lit by a light fixed to the UO camera; the texture is the albedo (light removed).
#    "UO look" (default) = albedo * (ambient + diffuse * max(0, N.L)) as emission -> renders like the sprites.
#    "Lit" = ordinary Principled BSDF for editing / game engines.
theta_ = float(Snp["theta"])
right_w = Vector((1, 0, 0)); up_w = Vector((0, math.sin(theta_), math.cos(theta_))); tow_w = right_w.cross(up_w)
Lc = LIGHT["L_camera"] if LIGHT else [0.0, 0.2, 0.98]
Lw = (right_w * Lc[0] + up_w * Lc[1] + tow_w * Lc[2]).normalized()
amb = LIGHT["ambient"] if LIGHT else 0.1
dif = LIGHT["diffuse"] if LIGHT else 0.9
mat = bpy.data.materials["UO_Skin"]
nt = mat.node_tree
nt.nodes.clear()
N = nt.nodes.new; Lk = nt.links.new
outn = N("ShaderNodeOutputMaterial"); outn.location = (700, 0)
tex = N("ShaderNodeTexImage"); tex.image = img; tex.location = (-900, 100); tex.label = "UO albedo (grey, from all frames)"
bsdf = N("ShaderNodeBsdfPrincipled"); bsdf.location = (-150, 350); bsdf.inputs["Roughness"].default_value = 0.8
geo = N("ShaderNodeNewGeometry"); geo.location = (-900, -300)
ldir = N("ShaderNodeCombineXYZ"); ldir.location = (-900, -500); ldir.label = "UO light direction (world)"
for i, v in enumerate(Lw):
    ldir.inputs[i].default_value = v
dot = N("ShaderNodeVectorMath"); dot.operation = "DOT_PRODUCT"; dot.location = (-650, -350)
mx = N("ShaderNodeMath"); mx.operation = "MAXIMUM"; mx.inputs[1].default_value = 0.0; mx.location = (-450, -350)
mad = N("ShaderNodeMath"); mad.operation = "MULTIPLY_ADD"; mad.location = (-250, -350); mad.label = "ambient + diffuse*cos"
mad.inputs[1].default_value = dif; mad.inputs[2].default_value = amb
mul = N("ShaderNodeMix"); mul.data_type = "RGBA"; mul.blend_type = "MULTIPLY"; mul.location = (-50, -150)
mul.inputs["Factor"].default_value = 1.0
emis = N("ShaderNodeEmission"); emis.location = (200, -150)
mix = N("ShaderNodeMixShader"); mix.location = (450, 0); mix.label = "UO look"
look = N("ShaderNodeValue"); look.location = (200, 250); look.label = "UO look: 1 = like the sprites, 0 = normal lighting"
look.outputs[0].default_value = 1.0
Lk(tex.outputs["Color"], bsdf.inputs["Base Color"])
Lk(geo.outputs["Normal"], dot.inputs[0]); Lk(ldir.outputs["Vector"], dot.inputs[1])
Lk(dot.outputs["Value"], mx.inputs[0]); Lk(mx.outputs["Value"], mad.inputs[0])
uo_col = tex.outputs["Color"]
if PERDIR:
    # per-direction albedo for the UO render: the rig's "uo_direction" (0..4) picks the texture; other values -> shared
    dval = N("ShaderNodeValue"); dval.location = (-1500, -800); dval.label = "UO direction (driver)"
    fc = dval.outputs[0].driver_add("default_value")
    fc.driver.type = "AVERAGE"
    var = fc.driver.variables.new(); var.type = "SINGLE_PROP"
    var.targets[0].id_type = "OBJECT"; var.targets[0].id = arm; var.targets[0].data_path = '["uo_direction"]'
    for k in range(5):
        path = os.path.abspath(f"{PERDIR}{k}.png")
        im = bpy.data.images.load(path); im.name = f"UO_Body_Albedo_dir{k}"; im.pack(); im.filepath = f"//UO_Body_Albedo_dir{k}.png"
        tk = N("ShaderNodeTexImage"); tk.image = im; tk.location = (-1300, -700 - 260 * k); tk.label = f"albedo seen from UO direction {k}"
        cmp = N("ShaderNodeMath"); cmp.operation = "COMPARE"; cmp.location = (-1050, -700 - 260 * k)
        cmp.inputs[1].default_value = float(k); cmp.inputs[2].default_value = 0.5
        Lk(dval.outputs[0], cmp.inputs[0])
        mk = N("ShaderNodeMix"); mk.data_type = "RGBA"; mk.location = (-850, -700 - 260 * k)
        Lk(cmp.outputs[0], mk.inputs["Factor"]); Lk(uo_col, mk.inputs[6]); Lk(tk.outputs["Color"], mk.inputs[7])
        uo_col = mk.outputs[2]
Lk(uo_col, mul.inputs[6])
Lk(mad.outputs["Value"], mul.inputs[7])
Lk(mul.outputs[2], emis.inputs["Color"])
Lk(look.outputs[0], mix.inputs["Fac"])
Lk(bsdf.outputs["BSDF"], mix.inputs[1]); Lk(emis.outputs["Emission"], mix.inputs[2])
Lk(mix.outputs["Shader"], outn.inputs["Surface"])
ramp = N("ShaderNodeValToRGB"); ramp.location = (-600, 450); ramp.label = "Skin hue (optional, UO-style)"
bw = N("ShaderNodeRGBToBW"); bw.location = (-750, 450)
Lk(tex.outputs["Color"], bw.inputs["Color"]); Lk(bw.outputs["Val"], ramp.inputs["Fac"])
cr = ramp.color_ramp
cr.elements[0].color = (0.10, 0.06, 0.04, 1); cr.elements[1].color = (1.0, 0.86, 0.74, 1)
sc.view_settings.view_transform = "Standard"   # exact sprite colours
sc["uo_light_camera_space"] = list(Lc); sc["uo_light_ambient"] = amb; sc["uo_light_diffuse"] = dif
sun = bpy.data.objects.get("UO_Sun")
if sun:   # for the "Lit" branch put the scene sun where the UO light is
    sun.rotation_euler = (-Lw).to_track_quat("-Z", "Y").to_euler()

# 3b) clavicle bones: chest -> clavicle -> upper arm. They do not deform the mesh themselves; their LOCATION moves
#     the whole arm chain (shoulder up/out when the arm is raised), fitted per frame like the other joints.
def ensure_clavicles(arm_ob):
    if "clavicle.L" in arm_ob.data.bones:
        return
    bpy.context.view_layer.objects.active = arm_ob
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm_ob.data.edit_bones
    for s_, sx in (("L", 1.0), ("R", -1.0)):
        ua = eb["upper_arm." + s_]
        c = eb.new("clavicle." + s_)
        c.head = Vector((sx * 0.03, ua.head.y - 0.035, ua.head.z - 0.045))
        c.tail = ua.head.copy()
        c.align_roll(Vector((0.0, -1.0, 0.0)))
        c.parent = eb["chest"]; c.use_connect = False; c.use_deform = False
        ua.parent = c; ua.use_connect = True
    bpy.ops.object.mode_set(mode="OBJECT")


ensure_clavicles(arm)
CLAV_B = {s_: np.array(arm.data.bones["clavicle." + s_].matrix_local.to_3x3()) for s_ in "LR"}

# 4) actions: refined poses (non-mounted), fitted poses (mounted)
bone_joint = {d[0]: d[1] for d in bone_defs(Snp, np.zeros((NJ, 3)))}
ref_pose = {}
for k, (a, i) in enumerate(ref["samples"]):
    ref_pose[(a, i)] = {n: ref["poses"][n][k] for n in ("ball", "hinge", "trans")}
for a in range(35):
    name = f"{a:02d}_{ACTIONS_PEOPLE[a]}"
    act = bpy.data.actions[name]
    for fc in list(act.fcurves):
        act.fcurves.remove(fc)
    arm.animation_data.action = act
    F = anim[a]["poses"]["trans"].shape[0]
    cyc = a in (0, 1, 2, 3, 23, 24)
    keys = list(range(F)) + ([0] if cyc and F > 1 else [])
    for ki, i in enumerate(keys):
        if FINAL is not None:
            pp = {k: v[i] for k, v in FINAL[a]["poses"].items()}
        else:
            pp = ref_pose.get((a, i)) or {k: v[i] for k, v in anim[a]["poses"].items()}
        pose = pose_from_params({k: jnp.asarray(v) for k, v in pp.items()})
        apply_pose(arm, bone_joint, np.asarray(pose["rot"]), np.asarray(pose["trans"]) + np.array([0.0, 0.0, LIFT]))
        if "clav" in pp:                      # offset in the chest frame -> clavicle location in its own rest frame
            for k_, s_ in enumerate("LR"):
                arm.pose.bones["clavicle." + s_].location = Vector((CLAV_B[s_].T @ np.asarray(pp["clav"][k_], float)).tolist())
        for pb in arm.pose.bones:
            pb.keyframe_insert("rotation_quaternion", frame=1 + ki * STEP, group=pb.name)
            if pb.parent is None or pb.name.startswith("clavicle."):
                pb.keyframe_insert("location", frame=1 + ki * STEP, group=pb.name)
arm.animation_data.action = bpy.data.actions["04_stand"]

# 5) camera: UO anchor sits on the pixel centre (+0.5 px in x)
theta, scale = float(Snp["theta"]), float(Snp["scale"])
co = bpy.data.objects["UO_Camera"]
up = Vector((0, math.sin(theta), math.cos(theta)))
view = Vector((0, math.cos(theta), -math.sin(theta)))
target = up * ((ANCHOR_Y - CANVAS_H / 2) / scale) + Vector(((CANVAS_W / 2 - ANCHOR_X - PX_OFF) / scale, 0, LIFT))
co.location = target - view * 10
sc["uo_anchor_px"] = [ANCHOR_X + PX_OFF, ANCHOR_Y]
sc["uo_anchor_height"] = LIFT      # world height of the UO anchor point (floor = 0)

txt = bpy.data.texts.get("render_uo_sprites.py") or bpy.data.texts.new("render_uo_sprites.py")
txt.from_string(open("render_uo_sprites.py").read())
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(os.path.join(OUT, "UO_Body_0x190.blend")))
print("saved", os.path.join(OUT, "UO_Body_0x190.blend"))
