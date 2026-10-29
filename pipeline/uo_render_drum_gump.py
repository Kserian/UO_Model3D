"""Paperdoll gumps (male 50000 + 490, female 60000 + 490: on the body gumps 12 / 13) and item art (two IDs, the second mirrored) of a drum on a sash, from the same 3D drum as its animation.

    PD_OUT=DIR PD_GUMPS=DIR_WITH_PNGS  [PD_COLOR=teal:dark PD_SCRIPTS=pipeline]  python run_script_in_blend.py ITEM.blend uo_render_drum_gump.py

PD_GUMPS: gump12.png, gump13.png (the drawn bodies), gump50490.png, gump60490.png (the ORIGINAL body sash of the client, anim 490), made by uo_gump_art.py.
Gump (260 x 237, 90.5 px/m like uo_render_paperdoll.py: head top y 54 .. feet y 221): the original sash is kept pixel for pixel (it already fits the drawn body: it runs from the left shoulder to the right waist),
a strap of the same grey is drawn from its lower end to the rim of the drum, and the drum (the 3D model, orthographic front view, UO light) hangs at the right hip (the left of the picture), its axis tilted so
that the head looks up, out and to the front, lower than on the animation (the drum of the animation rides on the chest; on the paperdoll it hangs near the legs like a side drum on a baldric).
Art (45 x 32): the drum lying on the ground with the strap in a loop beside it, seen like the other lying items (tilted towards the camera, turned), and its mirror.
Writes gump_male.png, gump_female.png, art.png, art_mirror.png and preview.png in PD_OUT.
"""
import json, os, sys
import colorsys
import bpy
import numpy as np
from mathutils import Matrix, Vector
from PIL import Image, ImageDraw
from scipy import ndimage

OUT = os.environ["PD_OUT"]; GUMPS = os.environ["PD_GUMPS"]
sys.path.insert(0, os.environ.get("PD_SCRIPTS", os.path.abspath("pipeline")))
COLOR = os.environ.get("PD_COLOR", "")           # "teal:dark" (drum_colors.py): the red shell of the drum is recoloured; "" = as it is
if COLOR:
    from drum_colors import params as color_params, recolor_rgb
    HUE, SAT_M, LUM_M = color_params(*COLOR.split(":"))
PXM = 90.5
GW, GH = 260, 237
GX0, GY_FEET = 94.5, 221.0
SS = 4
# the drum on the paperdoll (gump pixels of its centre; female: the waist of the body gump 13 is ca. 7 px higher)
CENTRE = {"male": (71.0, 150.0), "female": (71.0, 145.0)}            # the height is then set so that the rim of the drum covers the lower end of the original sash (EXTEND_STRAP off)
EXTEND_STRAP = False                            # True: a strap of the same grey is drawn from the end of the original sash to the rim (the drum hangs lower)
TUCK = 2.0                                      # px: the drum covers the end of the sash by this much
HEAD_N = Vector((-0.34, -0.52, 0.79))           # direction the upper head looks (x: to the left of the picture = the right of the character, -y: to the viewer, z: up)
STRAP_END = {"male": (80.0, 130.0), "female": (80.0, 125.0)}   # the lower end of the original sash on each gump
STRAP_W = 6.5                                   # px; the original sash is 7-9 px wide
OUTLINE = 0.5
GAIN = 0.80                                     # brightness of the drum: the UO light from the front lit the head white
CEIL = 215.0                                    # no channel above this (the client's items peak lower)
RING = (176, 150, 84)                           # the brass ring on the strap where it meets the drum
sc = bpy.context.scene
rig, body = bpy.data.objects["UO_Rig"], bpy.data.objects["UO_Body"]
rig.data.pose_position = "REST"
sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = 1; sc.cycles.use_denoising = False
sc.cycles.pixel_filter_type = "BOX"; sc.cycles.filter_width = 0.01; sc.render.dither_intensity = 0.0
sc.render.film_transparent = True; sc.view_settings.view_transform = "Standard"
sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGBA"
sc["uo_look"] = 1.0; sc["uo_exact"] = 0.0
sc.render.resolution_percentage = 100
g = bpy.data.node_groups.get("UO_Look_NS")
if g is not None:                                # the Sun of the own shadow, as uo_render_paperdoll.py
    Lv = Vector(next(n for n in g.nodes if n.type == "COMBXYZ").inputs[i].default_value for i in range(3))
    ld = bpy.data.lights.new("UO_Sun", "SUN"); sun = bpy.data.objects.new("UO_Sun", ld); sc.collection.objects.link(sun)
    ld.angle = 0.0; ld.energy = 3.14159265 * (1.0 - g["uo_ambient"]) * (1.0 - g["uo_shadow"])
    sun.rotation_euler = Vector((0, 0, 1)).rotation_difference(Lv.normalized()).to_euler()
    sc.cycles.diffuse_bounces = 0
    for m in bpy.data.materials:
        m.cycles.emission_sampling = "NONE"
cd = bpy.data.cameras.new("PD_Camera"); cd.type = "ORTHO"; cam = bpy.data.objects.new("PD_Camera", cd); sc.collection.objects.link(cam)
cam.data.sensor_fit = "HORIZONTAL"; sc.camera = cam

src = next(o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("drum"))
tmp = os.path.join(OUT, "_tmp.png")


SHELL = {}


def make_drum(name):
    """an unbound copy of the drum with its mesh in world coordinates, centred on its middle"""
    ob = src.copy(); ob.data = src.data.copy(); sc.collection.objects.link(ob)
    ob.parent = None
    for m in list(ob.modifiers):
        ob.modifiers.remove(m)
    ob.data.transform(src.matrix_world); ob.matrix_world = Matrix.Identity(4)
    V = np.array([v.co[:] for v in ob.data.vertices]); c = (V.min(0) + V.max(0)) / 2
    ob.data.transform(Matrix.Translation(-Vector(c.tolist())))
    ob.name = name; ob.hide_render = False
    SHELL[name] = shell_faces(ob)
    return ob


def shell_faces(ob):
    """per polygon: is it part of the drum that takes the new colour = everything but the heads (the cream membranes): the shell, the hoops (brass: they read dark red-brown in the render, and stood out red on a blue drum), the rods, the
    clamps and the badge; a head = a face that looks along the axis at an end of it, inside the hoop; the mesh in the frame of the model (axis along x)"""
    me = ob.data
    V = np.array([v.co[:] for v in me.vertices])
    idx = [np.array(p.vertices) for p in me.polygons]
    cen = np.array([V[i].mean(0) for i in idx]); nrm = np.array([p.normal[:] for p in me.polygons])
    depth = V[:, 0].max() - V[:, 0].min()
    r = np.hypot(cen[:, 1], cen[:, 2])
    head = (np.abs(nrm[:, 0]) > 0.9) & (np.abs(cen[:, 0]) > 0.35 * depth) & (r < 0.9 * np.percentile(r, 99))
    return ~head


def emission(name, v):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    em = nt.nodes.new("ShaderNodeEmission"); em.inputs["Color"].default_value = (v, v, v, 1); em.inputs["Strength"].default_value = 1.0
    out = nt.nodes.new("ShaderNodeOutputMaterial"); nt.links.new(em.outputs[0], out.inputs[0])
    return m


MAT_W, MAT_B = None, None


def shell_cov(ob, shell, w, h, px_per_m, cx, cz, k):
    """share of every output pixel (k x k samples) that is the recoloured part of the drum (everything but the heads): the same view with it white and the heads black (emission)"""
    global MAT_W, MAT_B
    if MAT_W is None:
        MAT_W, MAT_B = emission("m_shell", 1.0), emission("m_rest", 0.0)
    mk = ob.copy(); mk.data = ob.data.copy(); sc.collection.objects.link(mk)
    mk.data.materials.clear(); mk.data.materials.append(MAT_B); mk.data.materials.append(MAT_W)
    for p, s in zip(mk.data.polygons, shell):
        p.material_index = 1 if s else 0
    a = render(tmp, w, h, px_per_m, cx, cz, [mk])
    bpy.data.objects.remove(mk, do_unlink=True)
    bit = ((a[..., 0] > 0.5) & (a[..., 3] > 0.5)).astype(np.float32)
    return bit[:h // k * k, :w // k * k].reshape(h // k, k, w // k, k).mean((1, 3))


def colorize(da, cov, lo=0.25):
    """float RGBA: the pixels of the recoloured part (coverage > lo) whose colour is red / orange (hue within -60..+50 degrees, saturation >= 0.08) get the new hue, saturation and luminance"""
    out = da.copy()
    sel = (da[..., 3] > 0.5) & (cov > lo)
    ys, xs = np.nonzero(sel)
    cache = {}
    for y, x in zip(ys, xs):
        c = tuple(int(round(v * 255)) for v in da[y, x, :3])
        if c not in cache:
            h, s, v = colorsys.rgb_to_hsv(*[q / 255.0 for q in c]); hd = ((h * 360 + 180) % 360) - 180
            cache[c] = recolor_rgb(c, HUE, SAT_M, LUM_M) if (-60 <= hd <= 50 and s >= 0.08) else c
        out[y, x, :3] = [q / 255.0 for q in cache[c]]
    return out


def aim(ob, head_n, badge_to):
    """rotate the drum (axis along x, the badge of the shell looking to -y) so that its +x head looks along head_n and the badge as much as possible towards badge_to"""
    q = Vector((1, 0, 0)).rotation_difference(head_n.normalized())
    best, ang = -9, 0.0
    for a in np.radians(np.arange(0, 360, 5)):
        R = Matrix.Rotation(a, 3, head_n.normalized()) @ q.to_matrix()
        d = (R @ Vector((0, -1, 0))).dot(badge_to)
        if d > best:
            best, ang = d, a
    R = Matrix.Rotation(ang, 3, head_n.normalized()) @ q.to_matrix()
    ob.data.transform(R.to_4x4())


def render(path, w, h, px_per_m, cx, cz, show):
    """orthographic front view (camera in front, looking along +Y), pixel (w/2, h/2) = world (cx, cz); float RGBA, straight alpha"""
    for o in bpy.data.objects:
        if o.type == "MESH":
            o.hide_render = o not in show
    cam.data.ortho_scale = w / px_per_m
    cam.location = (cx, -6.0, cz); cam.rotation_euler = (np.pi / 2, 0, 0)
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return np.asarray(Image.open(path).convert("RGBA"), np.float32) / 255.0


def box_down(a, k):
    h, w = a.shape[0] // k, a.shape[1] // k
    a = a[:h * k, :w * k].reshape(h, k, w, k, 4)
    al = a[..., 3].mean((1, 3))
    rgb = (a[..., :3] * a[..., 3:]).sum((1, 3)) / np.maximum(a[..., 3].sum((1, 3)), 1e-6)[..., None]
    out = np.zeros((h, w, 4), np.float32); out[..., :3] = rgb; out[..., 3] = (al >= 0.5)
    return out


def rim(img, f):
    """the edge pixels (next to transparency) of an RGBA uint8 image multiplied by f"""
    m = img[..., 3] > 0
    inner = m.copy(); inner[1:] &= m[:-1]; inner[:-1] &= m[1:]; inner[:, 1:] &= m[:, :-1]; inner[:, :-1] &= m[:, 1:]
    e = m & ~inner
    out = img.copy(); out[e, :3] = np.clip(out[e, :3].astype(float) * f + 0.5, 0, 255).astype(np.uint8)
    return out


def bezier(p0, p1, p2, n=60):
    t = np.linspace(0, 1, n)[:, None]
    return (1 - t) ** 2 * np.array(p0) + 2 * (1 - t) * t * np.array(p1) + t ** 2 * np.array(p2)


def paste(dst, src):
    m = src[..., 3] > 0
    dst[m] = src[m]
    return dst


# ---------------------------------------------------------------- gumps
results = {}
for gender, gid in (("male", 50490), ("female", 60490)):
    sash = np.array(Image.open(os.path.join(GUMPS, "gump%d.png" % gid)).convert("RGBA"))
    drum = make_drum("drum_" + gender)
    aim(drum, HEAD_N, Vector((0, -1, 0.2)))
    gx, gy = CENTRE[gender]
    W, H = GW * SS, GH * SS
    cxw = (GW / 2 - GX0) / PXM; czw = (GY_FEET - GH / 2) / PXM
    sx, sy = STRAP_END[gender]
    for it in range(4):                           # the drum is put at (gx, gy); then moved so that its top edge in the columns of the sash end lies TUCK px above the end of the sash
        drum.location = ((gx - GX0) / PXM, -0.5, (GY_FEET - gy) / PXM)
        bpy.context.view_layer.update()
        a = render(tmp, W, H, PXM * SS, cxw, czw, [drum])
        da = box_down(a, SS)
        if COLOR:
            da = colorize(da, shell_cov(drum, SHELL["drum_" + gender], W, H, PXM * SS, cxw, czw, SS))
        da[..., :3] = np.minimum(da[..., :3] * GAIN, CEIL / 255.0)
        d = rim(np.clip(da * 255 + 0.5, 0, 255).astype(np.uint8), OUTLINE)
        dm = d[..., 3] > 0
        ys, xs = np.nonzero(dm)
        if EXTEND_STRAP:
            break
        cols = dm[:, int(sx) - 2:int(sx) + 3]
        if not cols.any():
            gx += 1.0; continue
        top_at_end = np.nonzero(cols.any(1))[0].min()
        err = (sy - TUCK) - top_at_end
        if abs(err) < 0.5:
            break
        gy += err
    print("%s: drum centre (%.1f, %.1f)" % (gender, gx, gy))
    print("%s: drum px %d, bbox x %d..%d y %d..%d" % (gender, dm.sum(), xs.min(), xs.max(), ys.min(), ys.max()))
    # (EXTEND_STRAP) the strap from the lower end of the original sash to the rim of the drum: the point of the silhouette nearest to the end of the sash
    strap = np.zeros((GH, GW, 4), np.uint8)
    if EXTEND_STRAP:
        cand = np.stack([xs, ys], 1).astype(float)
        top = cand[cand[:, 1] < gy - 0.1 * (ys.max() - ys.min())]
        att = top[np.argmin(((top - [sx - 1.0, sy + 3.0]) ** 2).sum(1))]
        tang = np.array([-0.37, 0.93])                                      # the direction in which the original sash arrives at its lower end (measured on the client's gumps)
        dist = float(np.hypot(att[0] - sx, att[1] - sy))
        ctrl = (sx + tang[0] * dist * 0.5, sy + tang[1] * dist * 0.5)
        path = bezier((sx, sy), ctrl, (att[0] + 0.5, att[1] + 1.0))
        # grey levels like the original sash near its end
        mm = sash[..., 3] > 0
        yy, xx = np.nonzero(mm)
        end = sash[yy.max() - 8:yy.max() - 2][sash[yy.max() - 8:yy.max() - 2, :, 3] > 0][:, :3].mean(0) if mm.any() else np.array([60, 60, 60])
        lvl = float(end.mean()) if not np.isnan(end).any() else 60.0
        S2 = 4
        st = Image.new("RGBA", (GW * S2, GH * S2), (0, 0, 0, 0)); dr = ImageDraw.Draw(st)
        dr.line([tuple(p * S2) for p in path], fill=(int(lvl * 0.8), int(lvl * 0.8), int(lvl * 0.8), 255), width=int(STRAP_W * S2), joint="curve")
        dr.line([tuple((p + [-0.2, -0.2]) * S2) for p in path], fill=(int(lvl * 1.3), int(lvl * 1.3), int(lvl * 1.3), 255), width=int((STRAP_W - 2.5) * S2), joint="curve")
        st = np.array(st).reshape(GH, S2, GW, S2, 4)
        sa = st[..., 3].mean((1, 3)) >= 0.5
        srgb = (st[..., :3].astype(float) * st[..., 3:] / 255.0).sum((1, 3)) / np.maximum((st[..., 3] / 255.0).sum((1, 3)), 1e-6)[..., None]
        strap = np.zeros((GH, GW, 4), np.uint8); strap[..., :3] = np.clip(srgb + 0.5, 0, 255).astype(np.uint8); strap[..., 3] = sa * 255
        strap = rim(strap, 0.55)
    out = np.zeros((GH, GW, 4), np.uint8)
    out = paste(out, sash); out = paste(out, strap); out = paste(out, d)
    if EXTEND_STRAP:
        ax, ay = int(round(att[0] + 0.5)), int(round(att[1] + 1.0))            # the ring over the end of the strap and the rim of the drum
        for dx, dy, f in ((0, 0, 1.0), (1, 0, 0.8), (0, 1, 0.8), (-1, 0, 0.6), (0, -1, 0.6)):
            out[ay + dy, ax + dx] = (int(RING[0] * f), int(RING[1] * f), int(RING[2] * f), 255)
    Image.fromarray(out).save(os.path.join(OUT, "gump_%s.png" % gender))
    results[gender] = out
    bpy.data.objects.remove(drum, do_unlink=True)

# ---------------------------------------------------------------- preview: the gumps on the drawn bodies
prev = []
for gender, bid in (("male", 12), ("female", 13)):
    b = Image.open(os.path.join(GUMPS, "gump%d.png" % bid)).convert("RGBA")
    bg = Image.new("RGBA", b.size, (20, 20, 20, 255)); bg.alpha_composite(b); bg.alpha_composite(Image.fromarray(results[gender]))
    prev.append(bg.convert("RGB").resize((b.width * 3, b.height * 3), Image.NEAREST))
pv = Image.new("RGB", (prev[0].width * 2 + 20, prev[0].height), (0, 0, 0)); pv.paste(prev[0], (0, 0)); pv.paste(prev[1], (prev[0].width + 20, 0))
pv.save(os.path.join(OUT, "preview.png"))
print("PD gumps done")

# ---------------------------------------------------------------- art: the drum lying on the ground with the strap in a loop beside it (45 x 32)
AW, AH, S2 = 45, 32, 4
ART_PXM = float(os.environ.get("PD_ART_PXM", "56"))               # art px per m (a drum of 0.376 m: ~15 px; the original sash art is 21 x 18 px)
drum = make_drum("drum_art")
aim(drum, Vector((-0.22, -0.52, 0.82)), Vector((0, -1, 0.3)))     # the head up and towards the camera (a camera ~55 deg above the horizon), a little turned
drum.location = (0, 0, 0)
bpy.context.view_layer.update()
DX, DY = 15.0, 17.0                                              # the pixel of the drum's centre in the art
a = render(tmp, AW * S2, AH * S2, ART_PXM * S2, (AW / 2 - DX) / ART_PXM, (DY - AH / 2) / ART_PXM, [drum])
da = box_down(a, S2)
if COLOR:
    da = colorize(da, shell_cov(drum, SHELL["drum_art"], AW * S2, AH * S2, ART_PXM * S2, (AW / 2 - DX) / ART_PXM, (DY - AH / 2) / ART_PXM, S2))
da[..., :3] = np.minimum(da[..., :3] * GAIN, CEIL / 255.0)
dart = rim(np.clip(da * 255 + 0.5, 0, 255).astype(np.uint8), OUTLINE)
dm = dart[..., 3] > 0; ys, xs = np.nonzero(dm)
print("art: drum px %d, bbox x %d..%d y %d..%d" % (dm.sum(), xs.min(), xs.max(), ys.min(), ys.max()))
# the strap: a loop (an ellipse of 4 px thickness) that starts at the right rim of the drum and comes back to it, grey like the original sash art
lvl = 70.0
loop = Image.new("RGBA", (AW * S2, AH * S2), (0, 0, 0, 0)); dl = ImageDraw.Draw(loop)
cx0, cy0 = xs.max() - 5.0, ys.min() + 0.42 * (ys.max() - ys.min())       # the loop starts behind the right rim of the drum: its ends are hidden by the drum
rx, ry = 10.0, 8.5
bb = [((cx0 - 1.0) * S2, (cy0 - ry) * S2), ((cx0 + 2 * rx - 1.0) * S2, (cy0 + ry) * S2)]
dl.ellipse(bb, outline=(int(lvl * 0.8),) * 3 + (255,), width=int(4.2 * S2))
dl.ellipse([bb[0][0] + 1.3 * S2, bb[0][1] + 1.3 * S2, bb[1][0] - 1.3 * S2, bb[1][1] - 1.3 * S2], outline=(int(lvl * 1.35),) * 3 + (255,), width=int(1.6 * S2))
lp = np.array(loop).reshape(AH, S2, AW, S2, 4)
la = lp[..., 3].mean((1, 3)) >= 0.5
lrgb = (lp[..., :3].astype(float) * lp[..., 3:] / 255.0).sum((1, 3)) / np.maximum((lp[..., 3] / 255.0).sum((1, 3)), 1e-6)[..., None]
lart = np.zeros((AH, AW, 4), np.uint8); lart[..., :3] = np.clip(lrgb + 0.5, 0, 255).astype(np.uint8); lart[..., 3] = la * 255
lart = rim(lart, 0.5)
art_img = paste(paste(np.zeros((AH, AW, 4), np.uint8), lart), dart)                 # the drum over the loop
Image.fromarray(art_img).save(os.path.join(OUT, "art.png"))
Image.fromarray(art_img[:, ::-1].copy()).save(os.path.join(OUT, "art_mirror.png"))
bg = Image.new("RGBA", (AW * 2 + 6, AH), (60, 60, 60, 255))
bg.alpha_composite(Image.fromarray(art_img), (0, 0)); bg.alpha_composite(Image.fromarray(art_img[:, ::-1].copy()), (AW + 6, 0))
bg.convert("RGB").resize((bg.width * 8, bg.height * 8), Image.NEAREST).save(os.path.join(OUT, "preview_art.png"))
print("PD art done")
