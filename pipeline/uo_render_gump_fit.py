"""Paperdoll gumps (male / female) and the item icon (art) of a garment that covers the body (robe, dress), fitted to an ORIGINAL item of the same kind.

    PD_OUT=DIR PD_REF_MALE=50469.png PD_REF_FEMALE=60469.png PD_ART_REF=7939.png  python run_script_in_blend.py ITEM.blend uo_render_gump_fit.py

uo_render_paperdoll.py fits a belt to the waist; a robe covers the whole body and the arms of the drawn paperdoll bodies (gumps 12 / 13: arms out, elbows bent) stand otherwise than the
rest pose of the 3D body (arms straight, 40 deg from the vertical). So per gender the arms are posed (the same angle out at both shoulders and bend at both elbows, in the front plane) and the
render is scaled / moved (x and y apart) so that the silhouette of the item matches the original gump of the same kind of item (plain robe 50469 / 60469 for a robe; docs/qa/robe_black.md).
The search uses the item's triangles projected flat (fast), the final image is rendered like uo_render_paperdoll.py (UO_Look, the Sun of the own shadow, the body a holdout for the back of
the item, 3 x 3 supersampling). The grey of the item is mapped to the levels of the original gump (p50 / p95 of its luminance), coloured parts (gold) keep their colour.
Art: the item laid flat (arms out at a right angle, front view) turned PD_ART_TURN degrees and stretched into the box of the original icon (PD_ART_REF; the mirrored second icon
is written too). Writes gump_male.png, gump_female.png, art.png, art_mirror.png, fit.json in PD_OUT.
"""
import json, os
import bpy
import numpy as np
from mathutils import Matrix, Vector
from PIL import Image, ImageDraw
from scipy import ndimage, optimize

OUT = os.environ["PD_OUT"]
REFS = {g: os.environ.get("PD_REF_" + g.upper()) for g in ("male", "female")}
ART_REF = os.environ.get("PD_ART_REF")
ART_TURN = float(os.environ.get("PD_ART_TURN", "-45"))      # deg, counter-clockwise on the screen
ART_ARMS = float(os.environ.get("PD_ART_ARMS", "15"))       # deg the arms are raised from the rest pose (40 deg from the vertical) for the laid item
GOLD_K = float(os.environ.get("PD_GOLD_K", "1.5"))
DESPECKLE = float(os.environ.get("PD_DESPECKLE", "0.6"))    # a pixel darker than this share of its neighbours' mean is a speck (0 = off)
DARK_FILL = float(os.environ.get("PD_DARK_FILL", "0.45"))  # share of the item's median luminance below which a pixel is a slit / deep shadow to fill (0 = off)
DESPECKLE_PASSES = int(os.environ.get("PD_DESPECKLE_PASSES", "3"))   # repeated: small clusters of dark pixels shrink from their edges          # coloured parts: the grey's mean factor times this (embroidery stays brighter than the cloth)
PXM = 90.5                                   # gump px per m and the body axis / floor of the gump of body 12 (uo_render_paperdoll.py, docs/qa/belt_swords.md)
GW, GH = 260, 237
GX0, GY_FEET = 94.5, 221.0
SS = 3
os.makedirs(OUT, exist_ok=True)
sc = bpy.context.scene
rig, body = bpy.data.objects["UO_Rig"], bpy.data.objects["UO_Body"]
items = [o for o in bpy.data.collections["Clothing"].all_objects if o.type == "MESH"]
rig.data.pose_position = "POSE"
rig.animation_data_clear() if rig.animation_data else None
for pb in rig.pose.bones:
    pb.matrix_basis = Matrix()
sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = 1; sc.cycles.use_denoising = False
sc.cycles.pixel_filter_type = "BOX"; sc.cycles.filter_width = 0.01; sc.render.dither_intensity = 0.0
sc.render.film_transparent = True; sc.view_settings.view_transform = "Standard"
sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGBA"
sc["uo_look"] = 1.0; sc["uo_exact"] = 0.0
sc.render.resolution_percentage = 100
g = bpy.data.node_groups.get("UO_Look_NS")
if g is not None:                            # the Sun of the own shadow, as render_uo_layer.shadow_sun / uo_render_paperdoll.py
    Lv = Vector(next(n for n in g.nodes if n.type == "COMBXYZ").inputs[i].default_value for i in range(3))
    ld = bpy.data.lights.new("UO_Sun", "SUN"); sun = bpy.data.objects.new("UO_Sun", ld); sc.collection.objects.link(sun)
    ld.angle = 0.0; ld.energy = 3.14159265 * (1.0 - g["uo_ambient"]) * (1.0 - g["uo_shadow"])
    sun.rotation_euler = Vector((0, 0, 1)).rotation_difference(Lv.normalized()).to_euler()
    sc.cycles.diffuse_bounces = 0
    for m in bpy.data.materials:
        m.cycles.emission_sampling = "NONE"
cd = bpy.data.cameras.new("PD_Camera"); cd.type = "ORTHO"; cam = bpy.data.objects.new("PD_Camera", cd); sc.collection.objects.link(cam)
cam.data.sensor_fit = "HORIZONTAL"; sc.camera = cam
for o in items:                              # no per-frame cloth push here: the item as the skeleton skins it
    for k in ("uo_cloth",):
        if k in o:
            del o[k]


def pose_arms(out_deg, bend_deg):
    """both arms `out_deg` further out at the shoulder and `bend_deg` more out at the elbow, in the front plane (about the forward axis)"""
    for pb in rig.pose.bones:
        pb.matrix_basis = Matrix()
    for side, sg in (("L", -1.0), ("R", 1.0)):
        for bn, ang in (("upper_arm." + side, out_deg), ("forearm." + side, bend_deg)):
            ml = rig.data.bones[bn].matrix_local.to_3x3()
            R = Matrix.Rotation(np.radians(sg * ang), 3, "Y")
            q = (ml.inverted() @ R @ ml).to_quaternion()
            pb = rig.pose.bones[bn]; pb.rotation_mode = "QUATERNION"; pb.rotation_quaternion = q
    bpy.context.view_layer.update()


def flat_tris(objs):
    """posed triangles of `objs` in world (x, z): (n, 3, 2)"""
    dg = bpy.context.evaluated_depsgraph_get(); out = []
    for o in objs:
        ev = o.evaluated_get(dg); me = ev.to_mesh(); me.calc_loop_triangles()
        co = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
        M = np.array(ev.matrix_world); co = co @ M[:3, :3].T + M[:3, 3]
        t = np.empty(len(me.loop_triangles) * 3, np.int32); me.loop_triangles.foreach_get("vertices", t)
        out.append(co[t.reshape(-1, 3)][:, :, [0, 2]]); ev.to_mesh_clear()
    return np.concatenate(out)


def to_gump(xz, p):
    """world (x, z) -> gump pixel with the fit p = (kx, ky, dx, dy) about the body axis / the floor"""
    kx, ky, dx, dy = p
    return np.stack([GX0 + xz[..., 0] * PXM * kx + dx, GY_FEET - xz[..., 1] * PXM * ky + dy], -1)


def raster(tris_px, w, h, k=2):
    im = Image.new("L", (w * k, h * k), 0); dr = ImageDraw.Draw(im)
    for t in tris_px * k:
        dr.polygon([tuple(v) for v in t], fill=255)
    return np.asarray(im.resize((w, h), Image.BOX)) >= 128


def iou(a, b):
    return (a & b).sum() / max((a | b).sum(), 1)


def fit_gender(ref):
    """arms (out, bend) and kx, ky, dx, dy that make the item's silhouette best match the original gump `ref` (alpha)"""
    cache = {}

    def cost(x):
        out, bend, kx, ky, dx, dy = x
        key = (round(out, 1), round(bend, 1))
        if key not in cache:
            pose_arms(*key); cache[key] = flat_tris(items)
        return 1.0 - iou(raster(to_gump(cache[key], (kx, ky, dx, dy)), GW, GH, 1), ref)
    best = None
    for out0, bend0 in ((0, 0), (10, 25), (20, 40)):                   # a few starts (the cost is flat in some directions)
        r = optimize.minimize(cost, [out0, bend0, 1.0, 1.0, 0.0, 0.0], method="Nelder-Mead",
                              options=dict(initial_simplex=np.array([[out0, bend0, 1, 1, 0, 0]] + [[out0 + (i == 0) * 8, bend0 + (i == 1) * 12, 1 + (i == 2) * 0.06, 1 + (i == 3) * 0.06,
                                                                                                    (i == 4) * 4, (i == 5) * 4] for i in range(6)], float), maxiter=260, xatol=0.05, fatol=1e-4))
        if best is None or r.fun < best.fun:
            best = r
    return best


def render(path, w, h, px_per_m, cx, cz, show, holdout_body):
    for o in bpy.data.objects:
        if o.type == "MESH":
            o.hide_render = o not in show and not (o is body and holdout_body)
    body.is_holdout = bool(holdout_body)
    cam.data.ortho_scale = w / px_per_m
    cam.location = (cx, -6.0, cz); cam.rotation_euler = (np.pi / 2, 0, 0)
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return np.asarray(Image.open(path).convert("RGBA"), np.float32) / 255.0


def warp(a, A, t, shape):
    """premultiplied linear resampling: output pixel (y, x) samples input A @ (y, x) + t"""
    pm = a.copy(); pm[..., :3] *= pm[..., 3:]
    out = np.zeros(shape + (4,), np.float32)
    for c in range(4):
        out[..., c] = ndimage.affine_transform(pm[..., c], A, offset=t, output_shape=shape, order=1, mode="constant", cval=0.0)
    out[..., :3] /= np.maximum(out[..., 3:], 1e-6)
    return out


def box_down(a, k):
    h, w = a.shape[0] // k, a.shape[1] // k
    a = a[:h * k, :w * k].reshape(h, k, w, k, 4)
    al = a[..., 3].mean((1, 3))
    rgb = (a[..., :3] * a[..., 3:]).sum((1, 3)) / np.maximum(a[..., 3].sum((1, 3)), 1e-6)[..., None]
    out = np.zeros((h, w, 4), np.float32); out[..., :3] = rgb; out[..., 3] = (al >= 0.5)
    return out


def match_levels(a, ref_rgba):
    """grey pixels of `a` mapped (linear in luminance) so that their p50 / p95 equal those of the original's opaque pixels; coloured pixels (gold) keep their colour"""
    m = a[..., 3] > 0; lum = a[..., :3] @ np.array([0.299, 0.587, 0.114])
    rm = ref_rgba[..., 3] > 0; rl = (ref_rgba[..., :3].astype(np.float32) / 255.0) @ np.array([0.299, 0.587, 0.114])
    sat = a[..., :3].max(-1) - a[..., :3].min(-1)
    grey = m & (sat <= 0.06)
    s50, s95 = np.percentile(lum[grey], 50), np.percentile(lum[grey], 95); r50, r95 = np.percentile(rl[rm], 50), np.percentile(rl[rm], 95)
    k = (r95 - r50) / max(s95 - s50, 1e-4)
    new = np.clip(r50 + (lum - s50) * k, 0, 1)
    f = np.where(lum > 1e-4, new / np.maximum(lum, 1e-4), 1.0)
    f = np.where(sat <= 0.06, f, GOLD_K * r50 / s50)   # gold: one factor (its shading stays; the stretch of the grey turned it brown-black, a cap at p95 made it flat)
    out = a.copy(); out[..., :3] = np.clip(a[..., :3] * f[..., None], 0, 1)
    return out, (s50, s95, r50, r95)


def despeckle(a, k=DESPECKLE, passes=None):
    """dark pixels: below DARK_FILL of the median of the item -> the colour of the cloth around (normalised Gaussian, sigma 2 px); the slits between the panels of the model and the shadows
    in its folds are black lines at the gump scale (the originals are smooth); then single specks against their neighbours, DESPECKLE_PASSES times"""
    m = a[..., 3] > 0; lum = a[..., :3] @ np.array([0.299, 0.587, 0.114]); tot = 0
    if DARK_FILL > 0 and m.any():
        dark = m & (lum < DARK_FILL * np.median(lum[m])); ok = (m & ~dark).astype(np.float32)
        den = ndimage.gaussian_filter(ok, 2.0)
        col = np.stack([ndimage.gaussian_filter(a[..., c] * ok, 2.0) for c in range(3)], -1) / np.maximum(den, 1e-6)[..., None]
        fill = dark & (den > 0.05)
        a = a.copy(); a[fill, :3] = col[fill]; tot += int(fill.sum())
    for _ in range(DESPECKLE_PASSES if passes is None else passes):
        a, n = despeckle1(a, k); tot += n
        if not n:
            break
    return a, tot


def despeckle1(a, k):
    """single dark pixels (shadows of folds in the texture, much darker than the cloth around) replaced by the mean of their opaque neighbours: the original gumps are smooth"""
    m = a[..., 3] > 0; lum = a[..., :3] @ np.array([0.299, 0.587, 0.114])
    pad = lambda x: np.pad(x, ((1, 1), (1, 1)) + ((0, 0),) * (x.ndim - 2))
    lm, mm, rgb = pad(np.where(m, lum, 0)), pad(m.astype(np.float32)), pad(a[..., :3] * m[..., None])
    H, W = m.shape; sh = [(y, x) for y in range(3) for x in range(3) if (y, x) != (1, 1)]
    n = sum(mm[y:y + H, x:x + W] for y, x in sh)
    mean_l = sum(lm[y:y + H, x:x + W] for y, x in sh) / np.maximum(n, 1)
    mean_c = sum(rgb[y:y + H, x:x + W] for y, x in sh) / np.maximum(n, 1)[..., None]
    bad = m & (n >= 5) & (lum < k * mean_l)
    out = a.copy(); out[bad, :3] = mean_c[bad]
    return out, int(bad.sum())


def to8(a):
    return np.clip(a * 255 + 0.5, 0, 255).astype(np.uint8)


report = {}
tmp = os.path.join(OUT, "_tmp.png")
for gender, refp in REFS.items():
    if not refp:
        continue
    ref = np.asarray(Image.open(refp).convert("RGBA")); refm = ref[..., 3] > 0
    pose_arms(0, 0); before = iou(raster(to_gump(flat_tris(items), (1, 1, 0, 0)), GW, GH, 1), refm)
    r = fit_gender(refm); out_deg, bend, kx, ky, dx, dy = r.x
    pose_arms(round(out_deg, 1), round(bend, 1))
    # render at the gump scale times SS with the uniform scale min(kx, ky), then the rest of the fit as a resampling
    k0 = min(kx, ky); W, H = GW * SS, GH * SS
    cxw = (GW / 2 - GX0) / PXM; czw = (GY_FEET - GH / 2) / PXM
    a = render(tmp, W, H, PXM * SS * k0, cxw / k0, czw / k0, items, True)
    # the render maps world (x, z) to SS * (GX0 + x PXM k0, GY_FEET - z PXM k0) (camera centred so that the body axis / floor land there); the wanted map uses kx, ky and the shift
    sx, sy = kx / k0, ky / k0
    A = np.array([1.0 / sy, 1.0 / sx])                                    # output (y, x) -> input (y, x): about (GY_FEET, GX0) in supersampled px
    t = np.array([SS * GY_FEET - (SS * GY_FEET + SS * dy) / sy, SS * GX0 - (SS * GX0 + SS * dx) / sx])
    res = box_down(warp(a, A, t, (H, W)), SS)
    res, lv = match_levels(res, ref)
    res, nsp = despeckle(res) if DESPECKLE > 0 else (res, 0)          # after the levels: their stretch made the darker folds black again
    Image.fromarray(to8(res)).save(os.path.join(OUT, "gump_%s.png" % gender))
    after = iou(res[..., 3] > 0, refm)
    report[gender] = dict(arms_out=round(out_deg, 1), elbow_bend=round(bend, 1), kx=round(kx, 3), ky=round(ky, 3), dx=round(dx, 1), dy=round(dy, 1),
                          iou_rest=round(before, 3), iou_fit_flat=round(1 - r.fun, 3), iou_render=round(after, 3), levels=[round(float(v), 3) for v in lv], specks=nsp)
    print("GUMP %s: %s" % (gender, report[gender]), flush=True)

if ART_REF:                                  # the item laid flat: arms out at a right angle, front view, turned 45 deg (the collar up right, the hem down left, as the original icon), fitted to its box
    ref = np.asarray(Image.open(ART_REF).convert("RGBA")); ys, xs = np.nonzero(ref[..., 3] > 0)
    rb = (xs.min(), ys.min(), xs.max(), ys.max()); AW, AH = ref.shape[1], ref.shape[0]
    pose_arms(ART_ARMS, 0)
    tr = flat_tris(items); lo = tr.reshape(-1, 2).min(0); hi = tr.reshape(-1, 2).max(0)
    ppm = 400.0
    w, h = int((hi[0] - lo[0]) * ppm) + 8, int((hi[1] - lo[1]) * ppm) + 8
    a = render(tmp, w, h, ppm, (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, items, False)          # no holdout: the head would cut a hole in the collar
    pm = a.copy(); pm[..., :3] *= pm[..., 3:]
    im = Image.fromarray(np.clip(pm * 255 + 0.5, 0, 255).astype(np.uint8), "RGBA").rotate(ART_TURN, resample=Image.BICUBIC, expand=True)
    rot = np.asarray(im, np.float32) / 255.0
    yy, xx = np.nonzero(rot[..., 3] > 0.5); rot = rot[yy.min():yy.max() + 1, xx.min():xx.max() + 1]
    S4 = 4; bw, bh = (rb[2] - rb[0] + 1) * S4, (rb[3] - rb[1] + 1) * S4          # stretched to the original's box (its proportions are those of a laid robe)
    rs = np.stack([np.asarray(Image.fromarray(rot[..., c]).resize((bw, bh), Image.BILINEAR)) for c in range(4)], -1)
    rs[..., :3] /= np.maximum(rs[..., 3:], 1e-6)
    big = np.zeros((AH * S4, AW * S4, 4), np.float32); big[rb[1] * S4:rb[1] * S4 + bh, rb[0] * S4:rb[0] * S4 + bw] = rs
    art = box_down(big, S4)
    art, lv = match_levels(art, ref)
    art, nsp = despeckle(art) if DESPECKLE > 0 else (art, 0)
    Image.fromarray(to8(art)).save(os.path.join(OUT, "art.png"))
    Image.fromarray(to8(art[:, ::-1])).save(os.path.join(OUT, "art_mirror.png"))
    ys2, xs2 = np.nonzero(art[..., 3] > 0)
    report["art"] = dict(turn=ART_TURN, box_ref=[int(v) for v in rb], box=[int(xs2.min()), int(ys2.min()), int(xs2.max()), int(ys2.max())], iou=round(iou(art[..., 3] > 0, ref[..., 3] > 0), 3))
    print("ART: %s" % report["art"], flush=True)
json.dump(report, open(os.path.join(OUT, "fit.json"), "w"), indent=1)
if os.path.exists(tmp):
    os.remove(tmp)
