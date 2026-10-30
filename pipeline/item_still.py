# High quality stills of an item.blend (made by uo_make_item.py, with "materials": {"TEXTURE_FILTER": false} for the full textures): the UO pose through UO_Camera zoomed in (field ORTHO_M metres),
# the UO light and the item's materials, a plain grey body (the scene's own skin projects the 136x120 original sprites and is pixelated when zoomed), transparent background.
#   python item_still.py -- ITEM.blend OUT_PREFIX ACTION FRAME_INDEX DIRS(comma) [ORTHO_M 1.9] [PX 1400] [SAMPLES 256]      e.g. ... 07_combat_idle_1h 0 0,2,3,1 2.3 1500 160
# item.blend is saved in REST position: this switches to POSE (the renderer does the same). Output: OUT_PREFIX_d<dir>.png
import bpy, sys, math
from mathutils import Vector
a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[-8:]
blend, out, act, fi, dirs = a[0], a[1], a[2], int(a[3]), [int(x) for x in a[4].split(",")]
field = float(a[5]) if len(a) > 5 else 1.9; px = int(a[6]) if len(a) > 6 else 1400; samples = int(a[7]) if len(a) > 7 else 256
bpy.ops.wm.open_mainfile(filepath=blend)
sc = bpy.context.scene; rig = bpy.data.objects["UO_Rig"]; body = bpy.data.objects["UO_Body"]; cam = bpy.data.objects["UO_Camera"]
sc.camera = cam; rig.data.pose_position = "POSE"
# a plain UO-lit grey body (the scene's skin projects the 136x120 original sprites: pixelated when zoomed)
g = bpy.data.node_groups["UO_Look"]; m = bpy.data.materials.new("hq_body"); m.use_nodes = True; nt = m.node_tree
for n in list(nt.nodes): nt.nodes.remove(n)
gn = nt.nodes.new("ShaderNodeGroup"); gn.node_tree = g; gn.inputs[0].default_value = (0.42, 0.42, 0.42, 1); mo = nt.nodes.new("ShaderNodeOutputMaterial")
nt.links.new(gn.outputs[0], mo.inputs["Surface"]); body.data.materials.clear(); body.data.materials.append(m)
rig.animation_data.action = bpy.data.actions[act]
try: rig.animation_data.action_slot = rig.animation_data.action_suitable_slots[0]
except Exception: pass
sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = samples; sc.cycles.use_adaptive_sampling = True; sc.cycles.adaptive_threshold = 0.002
try:
    sc.cycles.use_denoising = True; sc.cycles.denoiser = "OPENIMAGEDENOISE"
except Exception: pass
sc.render.film_transparent = True; sc.render.resolution_x = px; sc.render.resolution_y = px; sc.render.resolution_percentage = 100
sc.view_settings.view_transform = "Standard"
cd = cam.data; cd.sensor_fit = "AUTO"; cd.ortho_scale = field
for d in dirs:
    rig["uo_direction"] = d; rig.update_tag(); body.update_tag()
    sc.frame_set(1 + fi * 3); rig.update_tag(); bpy.context.view_layer.update()
    pb = rig.pose.bones["weapon1h.R"]; hand = rig.matrix_world @ rig.pose.bones["hand.R"].head
    target = Vector((0, 0, 1.15)) * 0.5 + hand * 0.5                                    # between the body centre and the hand
    cd.shift_x = cd.shift_y = 0; bpy.context.view_layer.update()
    p = cam.matrix_world.inverted() @ Vector((target.x, target.y, target.z))
    cd.shift_x = p.x / field; cd.shift_y = p.y / field
    sc.render.filepath = "%s_d%d.png" % (out, d); bpy.ops.render.render(write_still=True); print("rendered", sc.render.filepath, flush=True)
