"""3D perspective preview GIFs of UO actions from a built .blend (textured body, floor, horse proxy for mounted).
usage: python render3d_gif.py --blend out_v9/UO_Body_0x190.blend --out gifs3d --actions 0,9,23 [--only-frame N]"""
import bpy, sys, os, math
import numpy as np
from mathutils import Vector
from PIL import Image, ImageDraw
arg = lambda k, d=None: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
blend, out = arg("--blend"), os.path.abspath(arg("--out"))
ACTS = [int(x) for x in arg("--actions").split(",")]
ONLY = int(arg("--only-frame", "-1"))
os.makedirs(out, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=os.path.abspath(blend))
sc = bpy.context.scene
sc.render.engine = "CYCLES"; sc.cycles.samples = 16; sc.cycles.device = "CPU"; sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = 360, 420; sc.render.resolution_percentage = 100
sc.render.film_transparent = False; sc.render.image_settings.file_format = "PNG"
sc.view_settings.view_transform = "Standard"
sc["uo_look"] = 0.0                                   # normal lighting (Principled BSDF + albedo texture)
rig = bpy.data.objects["UO_Rig"]; rig["uo_direction"] = 0
if "Clothing" in bpy.data.collections:
    for o in bpy.data.collections["Clothing"].all_objects:
        o.hide_render = True
w = sc.world or bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.32, 0.34, 0.38, 1); w.node_tree.nodes["Background"].inputs[1].default_value = 0.6
sun = bpy.data.lights.new("PreviewSun", "SUN"); sun.energy = 3.0; so = bpy.data.objects.new("PreviewSun", sun)
so.rotation_euler = (math.radians(50), 0, math.radians(35)); sc.collection.objects.link(so)
me = bpy.data.meshes.new("Floor"); me.from_pydata([(-4, -4, 0), (4, -4, 0), (4, 4, 0), (-4, 4, 0)], [], [(0, 1, 2, 3)])
fl = bpy.data.objects.new("Floor", me); sc.collection.objects.link(fl)
fm = bpy.data.materials.new("FloorMat"); fm.use_nodes = True
fb = fm.node_tree.nodes["Principled BSDF"]; fb.inputs["Base Color"].default_value = (0.22, 0.2, 0.18, 1)
fb.inputs["Roughness"].default_value = 1.0
if "Specular IOR Level" in fb.inputs:
    fb.inputs["Specular IOR Level"].default_value = 0.0
me.materials.append(fm)
hm = bpy.data.materials.get("Horse_Proxy_Mat")
if hm:
    hm.use_nodes = True
    hm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.36, 0.24, 0.14, 1)
    hm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.8
horses = {o.name: o for o in bpy.data.objects if o.name.startswith("Horse_a")}
for o in horses.values():
    o.is_holdout = False; o.hide_render = True
cd = bpy.data.cameras.new("PreviewCam"); cd.lens = 50
cam = bpy.data.objects.new("PreviewCam", cd); sc.collection.objects.link(cam); sc.camera = cam
lift = float(sc.get("uo_anchor_height", 0.0))
acts = {int(a["uo_action"]): a for a in bpy.data.actions if "uo_action" in a}
for a in ACTS:
    act = acts[a]; rig.animation_data.action = act; F = int(act["uo_frames"])
    mounted = 23 <= a <= 29
    tgt = Vector((0, 0.1 if mounted else 0, 1.25 if mounted else 0.95)); dist = 6.2 if mounted else 4.4
    yaw, el = math.radians(55 if mounted else 35), math.radians(14)
    cam.location = tgt + Vector((math.sin(yaw) * math.cos(el), -math.cos(yaw) * math.cos(el), math.sin(el))) * dist
    cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()
    cyc = a in (0, 1, 2, 3, 23, 24)
    last = 3 * F if (cyc and F > 1) else 3 * (F - 1) + 1
    frames = [ONLY] if ONLY > 0 else list(range(1, last + 1)) if F > 1 else [1] * 24
    ims = []
    for k, f in enumerate(frames):
        if F == 1 and ONLY <= 0:                 # single-frame action: turntable
            yk = yaw + 2 * math.pi * k / len(frames)
            cam.location = tgt + Vector((math.sin(yk) * math.cos(el), -math.cos(yk) * math.cos(el), math.sin(el))) * dist
            cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()
        i = int(round((f - 1) / 3.0)) % F
        for o in horses.values():
            o.hide_render = True
        h = horses.get("Horse_a%d_f%d" % (a, i))
        if h: h.hide_render = False
        sc.frame_set(f)
        p = os.path.join(out, "_tmp.png"); sc.render.filepath = p; bpy.ops.render.render(write_still=True)
        im = Image.open(p).convert("RGB"); d = ImageDraw.Draw(im)
        d.text((8, 8), "%s   UO %d/%d" % (act.name, i + 1, F), fill=(240, 240, 240)); ims.append(im)
    name = os.path.join(out, "3d_%s.%s" % (act.name, "png" if ONLY > 0 else "gif"))
    if F == 1 and ONLY <= 0:
        ims[0].save(name, save_all=True, append_images=ims[1:], duration=120, loop=0)
    elif ONLY > 0 or len(ims) == 1:
        ims[0].save(name.replace(".gif", ".png"))
    else:
        ims[0].save(name, save_all=True, append_images=ims[1:], duration=42, loop=0)
    print("saved", name, flush=True)
