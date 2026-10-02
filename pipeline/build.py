"""Assemble the final Blender scene: mesh, rig, weights, UVs, projected texture, actions, UO camera; save + export."""
import os, sys, math, pickle
import numpy as np
import bpy
from mathutils import Vector, Matrix
import jax.numpy as jnp

from body import fk, zero_pose, JI, NJ, CANVAS_W, CANVAS_H, ANCHOR_X, ANCHOR_Y
from fit import params_to_shape, pose_from_params
from basemesh import build_base_mesh, symmetrize
from rig import build_armature, apply_pose
from texbake import bake, pull_push_fill
from targets import targets
from vd import ACTIONS_PEOPLE
from bpy_compat import eevee_engine

OUT = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "out"
os.makedirs(OUT, exist_ok=True)
FPS, STEP = 24, 3  # one UO frame every 3 scene frames (8 UO frames / s)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.preferences.filepaths.save_version = 0
sc = bpy.context.scene
sc.render.fps = FPS

SHAPE = sys.argv[sys.argv.index("--shape") + 1] if "--shape" in sys.argv else "shape_fit.pkl"
sf = pickle.load(open(SHAPE, "rb"))
fixed = {k: jnp.asarray(v) for k, v in sf["fixed"].items()}
S = params_to_shape({k: jnp.asarray(v) for k, v in sf["params"]["shape"].items()}, fixed)
Snp = {k: np.asarray(v, np.float64) for k, v in S.items()}
anim = pickle.load(open("anim_fit.pkl", "rb")) if os.path.exists("anim_fit.pkl") and "--no-anim" not in sys.argv else {}
stand_pp = {k: v[0] for k, v in anim[4]["poses"].items()} if 4 in anim else \
    {k: v[0] for k, v in sf["params"]["poses"].items()}

# ------------------------------------------------------------------ mesh
v, faces, parts, P = build_base_mesh(S, subdiv=2)
v, mirror, ok = symmetrize(v)
mirror = np.where(ok, mirror, np.arange(len(v)))
me = bpy.data.meshes.new("UO_Body")
me.from_pydata(v.tolist(), [], faces)
me.update()
me.use_mirror_x = True
for p in me.polygons:
    p.use_smooth = True
body = bpy.data.objects.new("UO_Body", me)
sc.collection.objects.link(body)

# ------------------------------------------------------------------ rig + weights
arm, bone_joint = build_armature(S, np.asarray(P))
bpy.ops.object.select_all(action="DESELECT")
body.select_set(True); arm.select_set(True)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.parent_set(type="ARMATURE_AUTO")
arm["uo_body_id"] = 0x190

# ------------------------------------------------------------------ UVs
bpy.ops.object.select_all(action="DESELECT")
bpy.context.view_layer.objects.active = body
body.select_set(True)
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.006, scale_to_bounds=False)
bpy.ops.object.mode_set(mode="OBJECT")

# ------------------------------------------------------------------ texture projection (stand pose)
def posed_vertices(rot, trans):
    apply_pose(arm, bone_joint, rot, trans)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = body.evaluated_get(dg)
    m = ev.to_mesh()
    out = np.array([x.co[:] for x in m.vertices])
    ev.to_mesh_clear()
    return out

pose = pose_from_params({k: jnp.asarray(v_) for k, v_ in stand_pp.items()})
posed = posed_vertices(np.asarray(pose["rot"]), np.asarray(pose["trans"]))
loops_v = np.zeros(len(me.loops), np.int64); me.loops.foreach_get("vertex_index", loops_v)
uv = np.zeros(len(me.loops) * 2); me.uv_layers.active.data.foreach_get("uv", uv); uv = uv.reshape(-1, 2)
tris, tri_uv = [], []
for poly in me.polygons:
    ls = list(poly.loop_indices)
    for k in range(1, len(ls) - 1):
        tri = [ls[0], ls[k], ls[k + 1]]
        tris.append(loops_v[tri]); tri_uv.append(uv[tri])
tris = np.array(tris); tri_uv = np.array(tri_uv)
spr = [s for s in targets(4)[0]]
TEX = 1024
tex, wt, cover = bake(tris, tri_uv, posed, mirror, spr, float(Snp["theta"]), float(Snp["scale"]), size=TEX)
print("texture coverage: %.1f%% of UV area" % (100 * wt[cover].mean()))
filled = pull_push_fill(tex, wt)
SKIN_RAMP = [(0.0, (0.10, 0.06, 0.04)), (0.45, (0.55, 0.37, 0.27)), (0.8, (0.93, 0.74, 0.60)), (1.0, (1.0, 0.90, 0.80))]


def apply_partial_hue(rgb):
    """UO 'partial hue': grey pixels are recoloured by the hue ramp, coloured pixels (loincloth) kept."""
    g = rgb.mean(-1)
    sat = (rgb.max(-1) - rgb.min(-1)) / np.maximum(rgb.max(-1), 1e-6)
    xs = [p for p, _ in SKIN_RAMP]
    ramp = np.stack([np.interp(g, xs, [c[i] for _, c in SKIN_RAMP]) for i in range(3)], -1)
    f = np.clip((sat - 0.10) / 0.10, 0, 1)[..., None]
    return ramp * (1 - f) + rgb * f


def save_image(name, rgb01):
    im = bpy.data.images.new(name, TEX, TEX, alpha=False)
    px = np.ones((TEX, TEX, 4), np.float32)
    px[..., :3] = np.clip(rgb01[::-1], 0, 1)
    im.pixels.foreach_set(px.ravel())
    im.filepath_raw = os.path.abspath(os.path.join(OUT, name + ".png"))
    im.file_format = "PNG"
    im.save()
    return im


grey = filled / 255.0
body_px = grey[wt > 0].mean(-1)
grey = np.clip(grey * (0.88 / np.percentile(body_px, 92)), 0, 1)   # normalise brightness
img_grey = save_image("UO_Body_Texture_grey", grey)
img_col = save_image("UO_Body_Texture", apply_partial_hue(grey))

# rest pose back
apply_pose(arm, bone_joint, np.zeros((NJ, 3)), np.zeros(3))

# ------------------------------------------------------------------ material
# Default: coloured texture. Alternative node chain kept in the material: grey UO texture -> skin ramp
# (mimics how the UO client hues the grey body); switch by connecting "Hue mix" to Base Color.
mat = bpy.data.materials.new("UO_Skin")
mat.use_nodes = True
nt = mat.node_tree
bsdf = nt.nodes["Principled BSDF"]
bsdf.inputs["Roughness"].default_value = 0.7
tc = nt.nodes.new("ShaderNodeTexImage"); tc.image = img_col; tc.location = (-500, 350); tc.label = "Skin (coloured)"
nt.links.new(tc.outputs["Color"], bsdf.inputs["Base Color"])
tg = nt.nodes.new("ShaderNodeTexImage"); tg.image = img_grey; tg.location = (-1300, -50); tg.label = "UO grey (hue-able)"
tg.image.colorspace_settings.name = "sRGB"
ramp = nt.nodes.new("ShaderNodeValToRGB"); ramp.location = (-950, -50); ramp.label = "Skin hue"
cr = ramp.color_ramp
while len(cr.elements) > 1:
    cr.elements.remove(cr.elements[-1])
cr.elements[0].position = SKIN_RAMP[0][0]; cr.elements[0].color = (*SKIN_RAMP[0][1], 1)
for pos, c in SKIN_RAMP[1:]:
    e = cr.elements.new(pos); e.color = (*c, 1)
bw = nt.nodes.new("ShaderNodeRGBToBW"); bw.location = (-1100, -250)
nt.links.new(tg.outputs["Color"], bw.inputs["Color"])
nt.links.new(bw.outputs["Val"], ramp.inputs["Fac"])
sep = nt.nodes.new("ShaderNodeSeparateColor"); sep.mode = "HSV"; sep.location = (-1100, -400)
nt.links.new(tg.outputs["Color"], sep.inputs["Color"])
mr = nt.nodes.new("ShaderNodeMapRange"); mr.location = (-900, -400)
mr.inputs["From Min"].default_value = 0.10; mr.inputs["From Max"].default_value = 0.20
nt.links.new(sep.outputs[1], mr.inputs["Value"])
hm = nt.nodes.new("ShaderNodeMix"); hm.data_type = "RGBA"; hm.location = (-650, -150); hm.label = "Hue mix"
nt.links.new(mr.outputs["Result"], hm.inputs["Factor"])
nt.links.new(ramp.outputs["Color"], hm.inputs[6])
nt.links.new(tg.outputs["Color"], hm.inputs[7])
me.materials.append(mat)

# ------------------------------------------------------------------ actions
arm.animation_data_create()
first_action = None
for a in sorted(anim):
    poses = anim[a]["poses"]
    F = poses["trans"].shape[0]
    act = bpy.data.actions.new(f"{a:02d}_{ACTIONS_PEOPLE[a]}")
    act.use_fake_user = True
    arm.animation_data.action = act
    cyc = a in (0, 1, 2, 3, 23, 24)
    keys = list(range(F)) + ([0] if cyc and F > 1 else [])
    for ki, i in enumerate(keys):
        pp = pose_from_params({k: jnp.asarray(v_[i]) for k, v_ in poses.items()})
        apply_pose(arm, bone_joint, np.asarray(pp["rot"]), np.asarray(pp["trans"]))
        fr = 1 + ki * STEP
        for pb in arm.pose.bones:
            pb.keyframe_insert("rotation_quaternion", frame=fr, group=pb.name)
            if pb.parent is None:
                pb.keyframe_insert("location", frame=fr, group=pb.name)
    act["uo_action"] = a
    act["uo_frames"] = F
    act.frame_range = (1, 1 + (len(keys) - 1) * STEP)
    if first_action is None or a == 4:
        first_action = act
arm.animation_data.action = anim and bpy.data.actions.get("00_walk_unarmed") or first_action
apply_pose(arm, bone_joint, np.zeros((NJ, 3)), np.zeros(3))

# ------------------------------------------------------------------ UO camera (orthographic, matches sprite projection)
theta, scale = float(Snp["theta"]), float(Snp["scale"])
cam = bpy.data.cameras.new("UO_Camera"); cam.type = "ORTHO"
cam.ortho_scale = CANVAS_W / scale
cam.sensor_fit = "HORIZONTAL"
co = bpy.data.objects.new("UO_Camera", cam)
sc.collection.objects.link(co)
up = Vector((0, math.sin(theta), math.cos(theta)))
view = Vector((0, math.cos(theta), -math.sin(theta)))  # looking direction
center_px_up = (ANCHOR_Y - CANVAS_H / 2) / scale
center_px_x = (CANVAS_W / 2 - ANCHOR_X) / scale
target = up * center_px_up + Vector((center_px_x, 0, 0))
co.location = target - view * 10
co.rotation_euler = view.to_track_quat("-Z", "Y").to_euler()
sc.camera = co
sc.render.resolution_x, sc.render.resolution_y = CANVAS_W, CANVAS_H
sc.render.film_transparent = True
sc.render.filter_size = 0.5
# direction control: custom property on the rig drives its Z rotation (UO file direction 0..4, 5..7 = mirrored)
arm["uo_direction"] = 0
arm.id_properties_ui("uo_direction").update(min=0, max=4)
fc = arm.driver_add("rotation_euler", 2)
fc.driver.type = "SCRIPTED"
var = fc.driver.variables.new(); var.name = "d"; var.type = "SINGLE_PROP"
var.targets[0].id = arm; var.targets[0].data_path = '["uo_direction"]'
fc.driver.expression = "-d*pi/4"
sun = bpy.data.lights.new("UO_Sun", "SUN"); sun.energy = 3.0
so = bpy.data.objects.new("UO_Sun", sun); so.rotation_euler = (math.radians(40), 0, math.radians(-30))
sc.collection.objects.link(so)
w = bpy.data.worlds.new("World"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[1].default_value = 0.8
sc.render.engine = eevee_engine()

# metadata
sc["uo_theta_deg"] = math.degrees(theta)
sc["uo_px_per_m"] = scale
sc.frame_start, sc.frame_end = 1, 1 + 9 * STEP

txt = bpy.data.texts.new("render_uo_sprites.py")
txt.from_string(open("render_uo_sprites.py").read())

pickle.dump(dict(v=v, faces=faces, mirror=mirror, tris=tris, tri_uv=tri_uv), open(os.path.join(OUT, "mesh_cache.pkl"), "wb"))
for im in (img_col, img_grey):
    im.pack()
    im.filepath = "//" + im.name + ".png"
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(os.path.join(OUT, "UO_Body_0x190.blend")))
print("saved blend")
