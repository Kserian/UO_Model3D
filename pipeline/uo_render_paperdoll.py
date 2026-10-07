"""Paperdoll gump and item icon (art) of a worn item, rendered from the same 3D model as its animation.

    python run_script_in_blend.py ITEM.blend uo_render_paperdoll.py      with the environment  PD_OUT=DIR  [PD_SWORD=blade,ring,grip,hilt]  [PD_ART_TILT=...]

Gump (gumpart.mul, 260 x 237 like the body gump 12 of the Nelderim client): front view, orthographic, 90.5 px/m, the body (rest pose) is a holdout that hides the back of a belt,
the objects named in PD_SWORD (hang at the side, drawn over the leg like the original gump of Belt_Sword) are rendered without the holdout. Alignment measured on the client's body gump 12:
head top y 54 .. feet y 221 (1.855 m), the pelvis centre at x 94.5; the original belt gump 50000 + 1519 has its band at y 126-135.
Art (art.mul): the item turned towards the camera like a lying item (UO draws items from above at 45 degrees), fitted into 44 x 32 px.
Writes gump.png, gump_raw.npy, art.png in PD_OUT. Light, materials, own shadow: as render_uo_layer.py (UO_Look, Sun with the UO direction, 1 sample per pixel); 3 x 3 supersampling is box-averaged.
"""
import os
import bpy
import numpy as np
from mathutils import Vector

OUT = os.environ["PD_OUT"]
SWORD = os.environ.get("PD_SWORD", "blade,ring,grip,hilt").split(",")
PXM = float(os.environ.get("PD_PX_PER_M", "90.5"))
GW, GH = 260, 237
GX0, GY_FEET = 94.5, 221.0                    # gump pixel of the body axis (x) and of the floor (y)
SS = 3
sc = bpy.context.scene
rig, body = bpy.data.objects["UO_Rig"], bpy.data.objects["UO_Body"]
items = [o for o in bpy.data.collections["Clothing"].all_objects if o.type == "MESH"]
rig.data.pose_position = "REST"
sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = 1; sc.cycles.use_denoising = False
sc.cycles.pixel_filter_type = "BOX"; sc.cycles.filter_width = 0.01; sc.render.dither_intensity = 0.0
sc.render.film_transparent = True; sc.view_settings.view_transform = "Standard"
sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGBA"
sc["uo_look"] = 1.0; sc["uo_exact"] = 0.0
sc.render.resolution_percentage = 100
if "PD_WORLD" in os.environ and sc.world is not None and sc.world.use_nodes:        # debugging: strength of the world light
    sc.world.node_tree.nodes["Background"].inputs[1].default_value = float(os.environ["PD_WORLD"])

# the Sun of the own shadow (render_uo_layer.shadow_sun): same direction as the UO light, no bounces, emission is not sampled
g = bpy.data.node_groups.get("UO_Look_NS")
if g is not None:
    Lv = Vector(next(n for n in g.nodes if n.type == "COMBXYZ").inputs[i].default_value for i in range(3))
    ld = bpy.data.lights.new("UO_Sun", "SUN"); sun = bpy.data.objects.new("UO_Sun", ld); sc.collection.objects.link(sun)
    ld.angle = 0.0; ld.energy = float(os.environ.get("PD_SUN_SCALE", "1")) * 3.14159265 * (1.0 - g["uo_ambient"]) * (1.0 - g["uo_shadow"])
    sun.rotation_euler = Vector((0, 0, 1)).rotation_difference(Lv.normalized()).to_euler()
    sc.cycles.diffuse_bounces = 0
    for m in bpy.data.materials:
        m.cycles.emission_sampling = "NONE"
cam = bpy.data.objects.get("PD_Camera")
if cam is None:
    cd = bpy.data.cameras.new("PD_Camera"); cd.type = "ORTHO"; cam = bpy.data.objects.new("PD_Camera", cd); sc.collection.objects.link(cam)
cam.data.sensor_fit = "HORIZONTAL"
sc.camera = cam


def render(path, w, h, px_per_m, cx, cz, show, holdout_body):
    """orthographic front view (camera in front of the character, looking along +Y), pixel (w/2, h/2) = world (cx, cz); returns float RGBA (h, w, 4)"""
    for o in bpy.data.objects:
        if o.type == "MESH":
            o.hide_render = o not in show and not (o is body and holdout_body)
    body.is_holdout = bool(holdout_body)
    cam.data.ortho_scale = w / px_per_m
    cam.location = (cx, -6.0, cz); cam.rotation_euler = (np.pi / 2, 0, 0)
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    from PIL import Image
    return np.asarray(Image.open(path).convert("RGBA"), np.float32) / 255.0      # straight alpha, display values


def to_rgba8(a):
    """straight-alpha float (the PNG the render wrote is already display-referred) -> uint8"""
    return np.clip(a * 255 + 0.5, 0, 255).astype(np.uint8)


GRAY_MAX = float(os.environ.get("PD_MAX_LEVEL", "160")) / 255.0     # brightness ceiling of the item (the animation frames of this item peak at 159): no white on the blade


def cap(a):
    """pixels brighter than GRAY_MAX are scaled down to it (hue and the dark shading stay): the lighting of the front view is brighter than the animation's"""
    top = a[..., :3].max(-1, keepdims=True)
    k = np.minimum(1.0, GRAY_MAX / np.maximum(top, 1e-6))
    out = a.copy(); out[..., :3] = a[..., :3] * k
    return out


def box_down(a, k):
    h, w = a.shape[0] // k, a.shape[1] // k
    a = a[:h * k, :w * k].reshape(h, k, w, k, 4)
    al = a[..., 3].mean((1, 3))
    rgb = (a[..., :3] * a[..., 3:]).sum((1, 3)) / np.maximum(a[..., 3].sum((1, 3)), 1e-6)[..., None]
    out = np.zeros((h, w, 4), np.float32); out[..., :3] = rgb; out[..., 3] = (al >= 0.5)
    return out


belt = [o for o in items if o.name not in SWORD]
sword = [o for o in items if o.name in SWORD]
cxw = (GW / 2 - GX0) / PXM                       # world x of the gump centre column
czw = (GY_FEET - GH / 2) / PXM
W, H = GW * SS, GH * SS
tmp = os.path.join(OUT, "_tmp.png")
a1 = render(tmp, W, H, PXM * SS, cxw, czw, belt, True)
a2 = render(tmp, W, H, PXM * SS, cxw, czw, sword, False)

# Where the belt band sits on each body gump (the client's own belts, measured on their gumps): the 3D model's body has other proportions than the drawn paperdoll bodies, so the belt is fitted
# to the waist of each: horizontally to x0..x1, the top edge of the band to `top` (male: Belt_Sword / Belt_Mace / Belt_Dagger 50000 + 1519 / 1517 / 1521: x 79..112, top 126-127, thickness 6-10;
# female: the waist belts 60000 + 1053 (Gargoyle Belt) and 943 (Elven Plate Belt): x 79..110, top 118-121; the female body gump 13 has the waist ca. 7 px higher than the male one)
TARGETS = {"male": (79.0, 112.0, 127.0), "female": (79.0, 110.0, 120.0)}


def band_of(a):
    """x range (percentiles 2 / 98 of the band rows) and top edge (median of the column tops over the middle half) of the belt in a supersampled render, in supersampled pixels"""
    m = a[..., 3] > 0.5
    ys, xs = np.nonzero(m)
    x0, x1 = xs.min(), xs.max()
    cols = range(int(x0 + 0.25 * (x1 - x0)), int(x0 + 0.75 * (x1 - x0)))
    top = float(np.median([np.nonzero(m[:, c])[0].min() for c in cols if m[:, c].any()]))
    rows = m[int(top):int(top + 10 * SS)]
    rx = np.nonzero(rows)[1]
    return float(np.percentile(rx, 2)), float(np.percentile(rx, 98)), top


def fit(a, kx, dx, dy, x_ref, y_ref):
    """scale about x_ref horizontally by kx, move by (dx, dy) (supersampled pixels); premultiplied linear resampling"""
    from scipy import ndimage
    pm = a.copy(); pm[..., :3] *= pm[..., 3:]
    out = np.zeros_like(pm)
    for c in range(4):
        out[..., c] = ndimage.affine_transform(pm[..., c], [1.0, 1.0 / kx], offset=[-dy, x_ref - (x_ref + dx) / kx], order=1, mode="constant", cval=0.0)
    out[..., :3] /= np.maximum(out[..., 3:], 1e-6)
    return out


sx0, sx1, stop = band_of(a1)
print("PD our band: x %.1f..%.1f top %.1f (gump px)" % (sx0 / SS, sx1 / SS, stop / SS))
from PIL import Image
for gender, (tx0, tx1, ttop) in TARGETS.items():
    kx = (tx1 - tx0) * SS / (sx1 - sx0)
    # fit(): x' = x_ref + (x - x_ref) * kx + dx with x_ref = sx0: the left end of the band (sx0) goes to tx0, the right end to tx1
    belt_g = fit(a1, kx, tx0 * SS - sx0, ttop * SS - stop, sx0, 0)
    # the sword hangs from the right end of the band: it moves as that end does, keeps its own size and tilt
    rx_old, rx_new = sx1, tx1 * SS
    sword_g = fit(a2, 1.0, rx_new - rx_old, ttop * SS - stop, 0, 0)
    r1, r2 = box_down(belt_g, SS), cap(box_down(sword_g, SS))
    res = np.where(r2[..., 3:4] > 0, r2, r1)
    np.save(os.path.join(OUT, "gump_%s_raw.npy" % gender), res)
    Image.fromarray(to_rgba8(res)).save(os.path.join(OUT, "gump_%s.png" % gender))
    b0, b1, bt = band_of(belt_g)
    print("PD %s: band now x %.1f..%.1f top %.1f (target %.0f..%.0f top %.0f), kx %.3f" % (gender, b0 / SS, b1 / SS, bt / SS, tx0, tx1, ttop, kx))

# art: the item as one object, tilted towards the camera, fitted into 44 x 32
AW, AH = 44, 32
tilt = float(os.environ.get("PD_ART_TILT", "55"))
turn = float(os.environ.get("PD_ART_TURN", "-35"))
rig.rotation_mode = "ZYX"; rig.rotation_euler = (np.radians(tilt), 0, np.radians(turn))      # first the turn about the vertical axis, then the tilt of the top towards the camera (= a camera `tilt` degrees above the horizon)
rig.location = (0, 0, 0)
bpy.context.view_layer.update()
S2 = 4
probe = render(tmp, 1024, 1024, 200.0, 0.0, 0.6, items, False)
ys, xs = np.nonzero(probe[..., 3] > 0.5)
bw, bh = (xs.max() - xs.min() + 1) / 200.0, (ys.max() - ys.min() + 1) / 200.0       # the object in m on the screen
k = min((AW - 2) / bw, (AH - 2) / bh)             # px per m so that the object fills the 44 x 32 tile
ccx = ((xs.max() + xs.min()) / 2 - 512) / 200.0; ccz = 0.6 - ((ys.max() + ys.min()) / 2 - 512) / 200.0
art = render(tmp, AW * S2, AH * S2, k * S2, ccx, ccz, items, False)
res_art = cap(box_down(art, S2))
np.save(os.path.join(OUT, "art_raw.npy"), res_art)
Image.fromarray(to_rgba8(res_art)).save(os.path.join(OUT, "art.png"))
print("PD done: gump", res.shape, "art", res_art.shape, "art px/m %.1f" % k, "object %.2f x %.2f m" % (bw, bh))
