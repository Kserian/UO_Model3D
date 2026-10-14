"""Paperdoll gumps (male / female) and the item icon (art) of a garment that covers the body (robe, dress), fitted to an ORIGINAL item of the same kind.

    PD_OUT=DIR PD_REF_MALE=50469.png PD_REF_FEMALE=60469.png PD_ART_REF=7939.png  python run_script_in_blend.py ITEM.blend uo_render_gump_fit.py

uo_render_paperdoll.py fits a belt to the waist; a robe covers the whole body and the arms of the drawn paperdoll bodies (gumps 12 / 13: arms out, elbows bent) stand otherwise than the
rest pose of the 3D body (arms straight, 40 deg from the vertical). So per gender the arms are posed (the same angle out at both shoulders and bend at both elbows, in the front plane) and the
render is scaled / moved (x and y apart) so that the silhouette of the item matches the original gump of the same kind of item (plain robe 50469 / 60469 for a robe; docs/qa/robe_black.md).
The search uses the item's triangles projected flat (fast), the final image is rendered like uo_render_paperdoll.py (UO_Look, the Sun of the own shadow, the body a holdout for the back of
the item, 4 x 4 supersampling) twice: textured and with the light alone (compose(): flat grey cloth times the light, the texture's gold as a cleaned mask). The grey of the item is mapped to
the levels of the original gump (p5 / p50 / p95 of its luminance), coloured parts (gold) keep their colour. PD_SAVE_RAW=1 also writes the raw renders (raw_*.npy, shade_*.npy).
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
BODIES = {g: os.environ.get("PD_BODY_" + g.upper()) for g in ("male", "female")}      # the body gumps (12 / 13): where their fists are, the sleeves must end
HAND_W = float(os.environ.get("PD_HAND_W", "0.5"))          # weight of the hands' distance to the fists (per (10 px)^2) against 1 - IoU
ARM_W = float(os.environ.get("PD_ARM_W", "2.0"))            # weight of 1 - IoU in the sleeves' region alone (the skirt is most of the item: with the whole IoU only, a sleeve could leave
                                                           # the upper arm of the body gump bare)
ARM_ROWS, ARM_DX = (70, 175), 24                           # the sleeves' region: these rows, farther than ARM_DX px from the body axis
BARE_W = float(os.environ.get("PD_BARE_W", "3.0"))         # weight of the share of the body gump's arm skin (under the original's sleeves) left bare
SCALE_W = 200.0                                            # penalty on the scales beyond 15 % (shoulders), 25 % (hem), 8 % (height) from 1: without it the search ran off (height x1.36)
ART_REF = os.environ.get("PD_ART_REF")
ART_TURN = float(os.environ.get("PD_ART_TURN", "-45"))      # deg, counter-clockwise on the screen
ART_ARMS = float(os.environ.get("PD_ART_ARMS", "15"))       # deg the arms are raised from the rest pose (40 deg from the vertical) for the laid item
GOLD_K = float(os.environ.get("PD_GOLD_K", "2.1"))          # coloured parts: the grey's mean factor times this (embroidery stays brighter than the cloth)
DESPECKLE = float(os.environ.get("PD_DESPECKLE", "0.6"))    # a pixel darker than this share of its neighbours' mean is a speck (0 = off)
DARK_FILL = float(os.environ.get("PD_DARK_FILL", "0.45"))  # share of the item's median luminance below which a pixel is a slit / deep shadow to fill (0 = off)
FLATTEN_SIGMA, FLATTEN_K, SOFT_SIGMA, OUTLINE_K, SHARPEN = 10.0, 0.0, 0.0, 0.55, 0.0   # smooth_cloth(): px, share, px, outline, unsharp amount (off since compose(): the cloth is the light alone)
GOLD_SAT = 0.12                                            # compose(): saturation of the texture's gold
GOLD_AREA = 125000                                         # hi-res px of the item the GOLD_* sizes are for (the robe's gump at SS 4); scaled with the item's size (the icon is smaller)
GOLD_BIG, GOLD_SMALL, GOLD_EDGE = 2000, 200, 12            # hi-res px: gold pieces kept (bigger than BIG, or than SMALL touching the item's edge within EDGE: collar, cuffs; stray specks dropped)
GOLD_CLOSE, GOLD_OPEN, GOLD_MAJ = 6, 5, 2                  # hi-res px radii of the closing / opening of the gold mask, passes of a 3 x 3 majority on the gump pixels
GOLD_SIGMA, GOLD_MOTTLE = 2.0, 1.0                         # the gold's colour: its median mixed with the texture's colour smoothed by GOLD_SIGMA hi-res px (the embroidery's pattern)
TEX_FOLDS, TEX_GAMMA, TEX_GRAIN, TEX_MOTTLE, TEX_GOLD, TEX_BORDER = 0.6, 1.2, 0.04, 0.04, 0.5, 0.8   # texture_cloth(): see there
LINE_K = 0.7
COVER_PX = 4                                               # px: the body gump's skin this close to the item (not the fists, head, feet) is covered by it (the original covers all of the body
                                                           # but the hands, head and feet; a bare shoulder / forearm showed through)   # smooth_cloth(): px, share of the evening, px, the outline's share of the colour
DESPECKLE_PASSES = int(os.environ.get("PD_DESPECKLE_PASSES", "3"))   # repeated: small clusters of dark pixels shrink from their edges
PXM = 90.5                                   # gump px per m and the body axis / floor of the gump of body 12 (uo_render_paperdoll.py, docs/qa/belt_swords.md)
GW, GH = 260, 237
GX0, GY_FEET = 94.5, 221.0
SS = 4
LIGHT_SUN_DEG = float(os.environ.get("PD_SUN_DEG", "20"))    # deg: the Sun's angular size in the render of the light (soft own shadows)
LIGHT_SAMPLES = int(os.environ.get("PD_LIGHT_SAMPLES", "32"))
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
g = bpy.data.node_groups.get("UO_Look_NS"); sun = None
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


def pose_arms(out_deg, bend_deg, length=1.0):
    """both arms `out_deg` further out at the shoulder and `bend_deg` more out at the elbow, in the front plane (about the forward axis); upper arm and forearm `length` times as long
    (the drawn paperdoll bodies have shorter arms than the 3D body: with the real length the hand reached the fist only with the upper arm pulled into the torso)"""
    for pb in rig.pose.bones:
        pb.matrix_basis = Matrix()
    for side, sg in (("L", -1.0), ("R", 1.0)):
        for bn, ang in (("upper_arm." + side, out_deg), ("forearm." + side, bend_deg)):
            ml = rig.data.bones[bn].matrix_local.to_3x3()
            R = Matrix.Rotation(np.radians(sg * ang), 3, "Y")
            q = (ml.inverted() @ R @ ml).to_quaternion()
            pb = rig.pose.bones[bn]; pb.rotation_mode = "QUATERNION"; pb.rotation_quaternion = q
            if bn.startswith("upper_arm"):
                pb.scale = (1.0, length, 1.0)                               # along the bone; the forearm inherits it (one factor for both)
    bpy.context.view_layer.update()


# The arms of the drawn paperdoll bodies (gump px, read off gumps 12 / 13 of the Nelderim client): shoulder, elbow, wrist of each arm. They are not symmetric: the character's right arm
# (left on the screen) hangs from the shoulder to the elbow and points the forearm out to the side, the left one goes out at the elbow and down to the fist. A symmetric pose searched
# for the silhouette (the first versions) bunched the sleeves into puffs at the shoulders.
JOINTS = {"male": {"R": ((75, 88), (69, 116), (54, 113)), "L": ((114, 88), (122, 111), (129, 121))},
          "female": {"R": ((75, 88), (70, 115), (52, 111)), "L": ((113, 88), (121, 112), (128, 121))}}
ARM_MODE = os.environ.get("PD_ARM_MODE", "joints")       # "joints": each arm along the drawn body's (JOINTS); "fit": one symmetric pose searched for the silhouette (the first versions)


def from_gump(px, p):
    """gump pixel -> world (x, z) for the fit p (inverse of to_gump)"""
    kxt, kxb, ky, dx, dy = p
    z = (GY_FEET + dy - px[1]) / (PXM * ky)
    return np.array([(px[0] - GX0 - dx) / (PXM * kx_at(z, kxt, kxb)), z])


def pose_arms_to(joints, p, wrist=None):
    """each upper arm along shoulder -> elbow of the body gump, in the front plane, as long as that (the drawn arms are shorter); each forearm aimed at the wrist (aim_forearm);
    the hands shrunk to nothing (the body is a holdout: a 3D hand in front of the sleeve would cut a hole in it, the drawn fist shows instead)"""
    for pb in rig.pose.bones:
        pb.matrix_basis = Matrix()
    out = {}
    for side, (S, E, W) in joints.items():
        if wrist and side in wrist:
            W = wrist[side]
        s, e, w = (from_gump(np.array(v, float), p) for v in (S, E, W))
        b = rig.data.bones["upper_arm." + side]; d0 = np.array([b.tail_local.x - b.head_local.x, b.tail_local.z - b.head_local.z]); tgt = e - s
        ang = -np.arctan2(d0[0] * tgt[1] - d0[1] * tgt[0], d0 @ tgt); k = float(np.linalg.norm(tgt)) / b.length       # Matrix.Rotation(t, "Y") turns (x, z) by -t
        ml = b.matrix_local.to_3x3()
        pb = rig.pose.bones["upper_arm." + side]; pb.rotation_mode = "QUATERNION"; pb.rotation_quaternion = (ml.inverted() @ Matrix.Rotation(ang, 3, "Y") @ ml).to_quaternion(); pb.scale = (1.0, k, 1.0)
        for bn in ("forearm." + side, "hand." + side):
            rig.data.bones[bn].inherit_scale = "NONE"
        bpy.context.view_layer.update()
        fk, lean = aim_forearm(side, w)
        hb = rig.pose.bones["hand." + side]; hb.scale = (0.01, 0.01, 0.01)
        out[side] = [round(float(np.degrees(ang)), 1), round(k, 3), round(fk, 3), round(lean, 1)]
    bpy.context.view_layer.update()
    return out


def aim_forearm(side, w):
    """the forearm from its posed head towards the point w = world (x, z) in the front view: nearer than its length -> it leans towards the viewer (-y) so that its front view is that short
    (the drawn forearm is foreshortened; squashing it along the bone crumpled the sleeve), farther -> stretched. Returns (stretch, lean deg)"""
    pb = rig.pose.bones["forearm." + side]; Mw = rig.matrix_world
    hw = Mw @ pb.head; t = np.array([w[0] - hw.x, w[1] - hw.z]); d2 = float(np.linalg.norm(t)); L = pb.bone.length * Mw.to_scale()[0]
    lean = min(np.arccos(min(1.0, d2 / L)), np.radians(LEAN_MAX))
    dy, k = -L * np.sin(lean), d2 / (L * np.cos(lean))
    dw = Vector((t[0], dy, t[1])).normalized(); da = (Mw.to_3x3().inverted() @ dw).normalized()
    rest = pb.bone.matrix_local.to_3x3()
    M = (rest.col[1].rotation_difference(da).to_matrix() @ rest).to_4x4(); M.translation = pb.head
    pb.rotation_mode = "QUATERNION"; pb.matrix = M; bpy.context.view_layer.update(); pb.scale = (SLEEVE_W, k, SLEEVE_W)
    return k, float(np.degrees(lean))


def fist_blobs(body_png, ref):
    """the fists of a body gump as masks with their centres: its pixels the original item does not cover, at the height of the hands, the two biggest pieces"""
    b = np.asarray(Image.open(body_png).convert("RGBA"))[..., 3] > 0
    free = b & ~ndimage.binary_dilation(ref, iterations=1); free[:85] = False; free[170:] = False
    lab, n = ndimage.label(free)
    sizes = ndimage.sum(free, lab, range(1, n + 1)); big = np.argsort(sizes)[::-1][:2] + 1
    return [(lab == k, ndimage.center_of_mass(free, lab, k)) for k in big]


CUFF_RIM = 0.015                             # m: the sleeve's mouth = per 15 deg around the forearm the vertices this close to the farthest one along it (the whole slanted rim of the bell)
CUFF_INTO = float(os.environ.get("PD_CUFF_INTO", "0.5"))   # px: the mouth's far edge this far past the drawn wrist into the hand (the centre of the mouth on the forearm's line)
LEAN_MAX = float(os.environ.get("PD_LEAN_MAX", "30"))      # deg: the forearm leans towards the viewer at most this much, the rest of the foreshortening is a squash along the bone
SLEEVE_W = float(os.environ.get("PD_SLEEVE_W", "0.75"))    # the forearm (the sleeve's bell) this wide across the bone: leaning, the bell's mouth seen nearly face-on covered the hand


def cuff_rims(objs):
    """per arm side: [(object index, vertex indices)] of the sleeve's mouth, in the rest pose: vertices weighted >= 0.9 to the forearm, per 15 deg sector around its axis the farthest
    CUFF_RIM along it (the farthest 3 cm overall were only the bell's lower lip, 5 cm below the axis)"""
    for pb in rig.pose.bones:
        pb.matrix_basis = Matrix()
    bpy.context.view_layer.update()
    rest = posed_verts(objs); out = {}
    for side in ("R", "L"):
        b = rig.data.bones["forearm." + side]; M = np.array(rig.matrix_world)
        h = M[:3, :3] @ np.array(b.head_local) + M[:3, 3]; t = M[:3, :3] @ np.array(b.tail_local) + M[:3, 3]; d = (t - h) / np.linalg.norm(t - h)
        u = np.cross(d, [0.0, 1.0, 0.0]); u /= np.linalg.norm(u); v = np.cross(d, u)
        rim = []
        for k, o in enumerate(objs):
            gi = o.vertex_groups.get("forearm." + side)
            if gi is None:
                continue
            w = np.zeros(len(o.data.vertices), np.float32)
            for vx in o.data.vertices:
                for g in vx.groups:
                    if g.group == gi.index:
                        w[vx.index] = g.weight
            r = rest[k] - h; along = r @ d; sec = ((np.degrees(np.arctan2(r @ v, r @ u)) + 180) // 15).astype(int)
            sel = (w >= 0.9) & (along > 0.5 * np.linalg.norm(t - h)); ix = []
            for sc_ in np.unique(sec[sel]):
                s2 = sel & (sec == sc_)
                ix.append(np.nonzero(s2 & (along >= along[s2].max() - CUFF_RIM))[0])
            if ix:
                rim.append((k, np.concatenate(ix)))
        out[side] = rim
    return out


def posed_verts(objs):
    dg = bpy.context.evaluated_depsgraph_get(); out = []
    for o in objs:
        ev = o.evaluated_get(dg); me = ev.to_mesh()
        co = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
        M = np.array(ev.matrix_world); out.append(co @ M[:3, :3].T + M[:3, 3]); ev.to_mesh_clear()
    return out


def hand_mask(body_png, ref, E, W):
    """the drawn hand: the body gump's pixels the original item leaves free (fist_blobs) beyond the drawn wrist W (across the line through W square to elbow -> wrist)"""
    d = np.array(W, float) - np.array(E, float); d /= np.linalg.norm(d)
    fm, _ = min(fist_blobs(body_png, ref), key=lambda bc: np.hypot(bc[1][1] - W[0], bc[1][0] - W[1]))
    Y, X = np.mgrid[0:GH, 0:GW]
    return fm & ((X - W[0]) * d[0] + (Y - W[1]) * d[1] > 0)


def fit_cuffs(joints, p, body_png, ref):
    """per arm: the forearm aimed (aim_forearm) until the centre of the sleeve's mouth (cuff_rims) lands CUFF_INTO px past the drawn wrist (JOINTS) in the gump: fixed-point, the forearm's
    target moved by the remaining error. Measured: the drawn forearm left bare (elbow -> wrist, outside the hand) and the hand covered by the sleeve, px"""
    bb = np.asarray(Image.open(body_png).convert("RGBA"))[..., 3] > 0
    rims = cuff_rims(items); tgt, err, bare, over = {}, {}, {}, {}
    Y, X = np.mgrid[0:GH, 0:GW]
    for side, (S, E, W) in joints.items():
        d = np.array(W, float) - np.array(E, float); L = np.linalg.norm(d); d /= L
        wv = np.array(W, float)
        for it in range(15):
            pose_arms_to({side: (S, E, tuple(wv))}, p)
            pv = posed_verts(items)
            rp = to_gump(np.concatenate([pv[k][ix][:, [0, 2]] for k, ix in rims[side]]), p) - np.array(W, float)
            nv = np.array([-d[1], d[0]])
            e = -(np.max(rp @ d) - CUFF_INTO) * d - np.mean(rp @ nv) * nv                     # the far edge to the wrist along the forearm, the centre onto its line
            if np.hypot(*e) < 0.2:
                break
            wv = wv + e
        tgt[side] = (round(float(wv[0]), 2), round(float(wv[1]), 2)); err[side] = round(float(np.hypot(*e)), 2)
        hm = hand_mask(body_png, ref, E, W)
        t = (X - E[0]) * d[0] + (Y - E[1]) * d[1]; nrm = np.abs(-(X - E[0]) * d[1] + (Y - E[1]) * d[0])
        lane = bb & ~hm & (t > 0) & (t <= L) & (nrm <= 6)
        sil = raster(to_gump(flat_tris(items), p), GW, GH, 2)
        bare[side] = int((lane & ~sil).sum()); over[side] = int((hm & sil).sum())
    return tgt, err, bare, over


def cover_body(a, body_png, ref, joints=None):
    """the body gump's skin within COVER_PX of the item (not the hands beyond the drawn wrists, the head and neck, the feet) taken into the item, coloured like the nearest cloth"""
    bb = np.asarray(Image.open(body_png).convert("RGBA"))[..., 3] > 0
    m = a[..., 3] > 0
    keep = np.zeros_like(bb)
    for fm in ([hand_mask(body_png, ref, E, W) for S, E, W in joints.values()] if joints else [f for f, _ in fist_blobs(body_png, ref)]):
        keep |= ndimage.binary_dilation(fm, iterations=1)
    keep[:84] = True; keep[205:] = True                                        # head with the neck, feet
    d, (iy, ix) = ndimage.distance_transform_edt(~m, return_indices=True)
    add = bb & ~m & ~keep & (d <= COVER_PX)
    out = a.copy()
    out[add, :3] = a[iy[add], ix[add], :3]; out[add, 3] = 1.0
    return out, int(add.sum()), int((bb & ~(out[..., 3] > 0) & ~keep).sum())


def fit_body(ref):
    """kx_top, kx_hem, ky, dx, dy that match the item without its sleeves (arms at rest) to the original gump without the sleeves' region"""
    zone = np.zeros((GH, GW), bool); zone[ARM_ROWS[0]:ARM_ROWS[1]] = True; zone[:, int(GX0 - ARM_DX):int(GX0 + ARM_DX)] = False
    pose_arms(0, 0); tr = flat_tris(items)

    def cost(x):
        kxt, kxb, ky, dx, dy = x
        sil = raster(to_gump(tr, x), GW, GH, 1)
        return 1.0 - iou(sil & ~zone, ref & ~zone) + SCALE_W * sum(max(0.0, abs(v - 1.0) - lim) ** 2 for v, lim in ((kxt, 0.15), (kxb, 0.25), (ky, 0.08)))
    x0 = np.array([1.0, 1.0, 1.0, 0.0, 0.0]); step = np.array([0.06, 0.06, 0.06, 4, 4])
    return optimize.minimize(cost, x0, method="Nelder-Mead", options=dict(initial_simplex=np.vstack([x0, x0 + np.diag(step)]), maxiter=400, xatol=0.01, fatol=1e-5))


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


Z_TOP, Z_HEM = 1.45, 0.15                    # m: the horizontal scale goes from kx_top at the shoulders to kx_hem at the hem (a skirt wider than the original's is narrowed without pulling the
                                             # shoulders in: with one kx the upper arm of the body gump came out bare beside the shoulder)


def kx_at(z, kxt, kxb):
    return kxb + (kxt - kxb) * np.clip((z - Z_HEM) / (Z_TOP - Z_HEM), 0, 1)


def to_gump(xz, p):
    """world (x, z) -> gump pixel with the fit p = (kx_top, kx_hem, ky, dx, dy) about the body axis / the floor"""
    kxt, kxb, ky, dx, dy = p
    return np.stack([GX0 + xz[..., 0] * PXM * kx_at(xz[..., 1], kxt, kxb) + dx, GY_FEET - xz[..., 1] * PXM * ky + dy], -1)


def raster(tris_px, w, h, k=2):
    im = Image.new("L", (w * k, h * k), 0); dr = ImageDraw.Draw(im)
    for t in tris_px * k:
        dr.polygon([tuple(v) for v in t], fill=255)
    return np.asarray(im.resize((w, h), Image.BOX)) >= 128


def iou(a, b):
    return (a & b).sum() / max((a | b).sum(), 1)


def fists(body_png, ref):
    """centres of the two fists of a body gump: its pixels that the original item does not cover, at the height of the hands (the two biggest pieces between the shoulders and the knees)"""
    b = np.asarray(Image.open(body_png).convert("RGBA"))[..., 3] > 0
    free = b & ~ndimage.binary_dilation(ref, iterations=1); free[:85] = False; free[170:] = False
    lab, n = ndimage.label(free)
    sizes = ndimage.sum(free, lab, range(1, n + 1)); big = np.argsort(sizes)[::-1][:2] + 1
    c = [ndimage.center_of_mass(free, lab, k) for k in big]
    return sorted([(x, y) for y, x in c])                                  # left on the screen first


def hand_points():
    """the hands (middle of the hand bone) in world (x, z), left on the screen first"""
    pts = []
    for side in ("R", "L"):                                                 # the character's right hand is on the left of the screen (front view)
        pb = rig.pose.bones["hand." + side]; M = rig.matrix_world
        h, t = M @ pb.head, M @ pb.tail
        pts.append(((h.x + t.x) / 2, (h.z + t.z) / 2))
    return np.array(pts)


def fit_gender(ref, fist=None, bare=None):
    """arms (out, bend) and kx, ky, dx, dy that make the item's silhouette best match the original gump `ref` (alpha) and put the hands on the fists of the body gump"""
    cache = {}
    arm_zone = np.zeros((GH, GW), bool); arm_zone[ARM_ROWS[0]:ARM_ROWS[1]] = True; arm_zone[:, int(GX0 - ARM_DX):int(GX0 + ARM_DX)] = False

    def cost(x):
        out, bend, alen, kxt, kxb, ky, dx, dy = x
        key = (round(out, 1), round(bend, 1), round(alen, 3))
        if key not in cache:
            pose_arms(*key); cache[key] = (flat_tris(items), hand_points())
        tr, hp = cache[key]
        sil = raster(to_gump(tr, (kxt, kxb, ky, dx, dy)), GW, GH, 1)
        c = 1.0 - iou(sil, ref) + ARM_W * (1.0 - iou(sil & arm_zone, ref & arm_zone))
        if bare is not None:                                                # skin of the body gump's arms the original covers and ours does not
            c += BARE_W * (bare & ~sil).sum() / max(bare.sum(), 1)
        c += SCALE_W * max(0.0, abs(alen - 0.85) - 0.2) ** 2
        c += SCALE_W * sum(max(0.0, abs(v - 1.0) - lim) ** 2 for v, lim in ((kxt, 0.15), (kxb, 0.25), (ky, 0.08)))   # the scales stay near the body gump's (90.5 px/m)
        if fist is not None:
            d = to_gump(hp, (kxt, kxb, ky, dx, dy)) - np.array(fist)
            c += HAND_W * float((d ** 2).sum(1).mean()) / 100.0
        return c
    best = None
    for out0, bend0 in ((0, 0), (10, 25), (20, 40), (10, 60), (0, 80)):                   # a few starts (the cost is flat in some directions)
        x0 = np.array([out0, bend0, 0.85, 1.0, 1.0, 1.0, 0.0, 0.0]); step = np.array([8, 12, 0.08, 0.06, 0.06, 0.06, 4, 4])
        r = optimize.minimize(cost, x0, method="Nelder-Mead", options=dict(initial_simplex=np.vstack([x0, x0 + np.diag(step)]), maxiter=320, xatol=0.05, fatol=1e-4))
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


def render_light(*args):
    """render() of the light alone (white_albedo) with soft own shadows: the sleeves' hard shadow on the waist was a flat dark patch at the gump scale"""
    ang, spp = (sun.data.angle, sc.cycles.samples) if sun is not None else (None, None)
    if sun is not None:
        sun.data.angle = np.radians(LIGHT_SUN_DEG); sc.cycles.samples = LIGHT_SAMPLES
    try:
        return render(*args)
    finally:
        if sun is not None:
            sun.data.angle, sc.cycles.samples = ang, spp


def disk(r):
    y, x = np.mgrid[-r:r + 1, -r:r + 1]
    return x * x + y * y <= r * r


def compose(tex, sh, k):
    """the item from two renders on the gump grid times k: tex (textured) and sh (white_albedo: the light alone). The texture's small pattern, its dark seams and stray specks of gold were
    noise, black dashes and a dark patch at the gump scale (docs/qa/robe_black.md); so the cloth is a flat grey times the light, and the gold a cleaned mask of the texture's gold (whole gump
    pixels: a mixed edge pixel got the grey's or the gold's levels by chance, a dotted edge) times its colour times the light"""
    m = tex[..., 3] > 0.5
    f = np.sqrt(m.sum() / GOLD_AREA); r = lambda v: max(1, int(round(v * f)))
    sat = tex[..., :3].max(-1) - tex[..., :3].min(-1); g = m & (sat > GOLD_SAT)
    lab, n = ndimage.label(g); sz = np.bincount(lab.ravel()); sz[0] = 0
    touch = np.zeros(n + 1, bool); touch[np.unique(lab[m & ~ndimage.binary_erosion(m, disk(r(GOLD_EDGE)))])] = True
    keep = (sz >= GOLD_BIG * f * f) | ((sz >= GOLD_SMALL * f * f) & touch); keep[0] = False
    gk = ndimage.binary_closing(keep[lab], disk(r(GOLD_CLOSE))) & m
    gk = ndimage.binary_fill_holes(ndimage.binary_opening(gk, disk(r(GOLD_OPEN)))) & m
    if k > 1:
        h, w = gk.shape[0] // k, gk.shape[1] // k
        blk = gk[:h * k, :w * k].reshape(h, k, w, k).mean((1, 3)) >= 0.5
        for _ in range(GOLD_MAJ):
            blk = ndimage.median_filter(blk.astype(np.uint8), size=3).astype(bool)
        gk = np.zeros_like(gk); gk[:h * k, :w * k] = np.repeat(np.repeat(blk, k, 0), k, 1)
    light = sh[..., :3] @ np.array([0.299, 0.587, 0.114])                 # 0.5 = a white-lit grey 0.5 albedo
    alb = tex[..., :3] / np.maximum(light, 0.05)[..., None] * 0.5
    w = g.astype(np.float32); sg = GOLD_SIGMA * f; den = ndimage.gaussian_filter(w, sg)
    gm = np.median(alb[g], axis=0) if g.any() else np.array([0.8, 0.6, 0.3])
    loc = np.stack([ndimage.gaussian_filter(alb[..., c] * w, sg) for c in range(3)], -1) / np.maximum(den, 1e-3)[..., None]
    loc = np.where(den[..., None] > 0.05, loc, gm)
    out = np.zeros_like(tex)
    out[..., :3] = np.where(gk[..., None], gm * (1 - GOLD_MOTTLE) + loc * GOLD_MOTTLE, 0.5) * light[..., None]
    out[..., 3] = tex[..., 3]
    return np.clip(out, 0, 1)


def white_albedo(objs):
    """the items' UO_Look albedo unlinked and set to a flat grey (returned to restore it): a render of the light alone"""
    saved = []
    for o in objs:
        for slot in o.material_slots:
            m = slot.material
            if m is None or m.node_tree is None:
                continue
            for n in m.node_tree.nodes:
                if n.type == "GROUP" and n.node_tree is not None and n.node_tree.name.startswith("UO_Look"):
                    sock = n.inputs["Albedo"]
                    saved.append((m.node_tree, sock, [l.from_socket for l in sock.links], tuple(sock.default_value)))
                    for l in list(sock.links):
                        m.node_tree.links.remove(l)
                    sock.default_value = (0.5, 0.5, 0.5, 1.0)
    return saved


def restore_albedo(saved):
    for nt, sock, srcs, val in saved:
        sock.default_value = val
        for fs in srcs:
            nt.links.new(fs, sock)


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
    s5, s50, s95 = np.percentile(lum[grey], [5, 50, 95]); r5, r50, r95 = np.percentile(rl[rm], [5, 50, 95])
    new = np.clip(np.interp(lum, [0.0, s5, s50, s95, 1.0], [0.0, r5, r50, r95, min(1.0, r95 + (1 - s95) * (r95 - r50) / max(s95 - s50, 1e-4))]), 0, 1)   # p5 / p50 / p95 as the original's
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


def smooth_cloth(a):
    """the look of the original gumps: smooth grey (the texture's small pattern and the darker inner panel were noise and a dark patch at 90 px/m): the grey luminance evened against its
    surroundings (FLATTEN_SIGMA px: panels of another shade come to the level of the cloth around) and softened (SOFT_SIGMA px), the item's edge rounded (a ragged cuff) and drawn as a
    dark 1 px outline like the originals' (OUTLINE_K of the colour)"""
    m = a[..., 3] > 0
    if not m.any():
        return a
    m2 = ndimage.binary_opening(m, iterations=1) | (ndimage.binary_erosion(m, iterations=1))      # single-pixel spikes of the edge (a ragged cuff) cut off
    m2 = ndimage.binary_closing(m2, iterations=1) & ndimage.binary_dilation(m, iterations=1)
    m2 = ndimage.binary_fill_holes(m2)                                      # slits between the panels inside the item: filled, no outline drawn round them
    lum = a[..., :3] @ np.array([0.299, 0.587, 0.114]); sat = a[..., :3].max(-1) - a[..., :3].min(-1)
    grey = m & (sat <= 0.06); g = grey.astype(np.float32)
    nz = lambda x, sg: ndimage.gaussian_filter(x * g, sg) / np.maximum(ndimage.gaussian_filter(g, sg), 1e-6)
    med = np.median(lum[grey]) if grey.any() else 0.5
    flat = lum * (med / np.maximum(nz(lum, FLATTEN_SIGMA), 1e-4)) ** FLATTEN_K
    soft = nz(flat, SOFT_SIGMA) if SOFT_SIGMA > 0 else flat
    if SHARPEN > 0:                                                         # the folds as crisp as in the original (unsharp mask, 1 px)
        soft = soft + SHARPEN * (soft - nz(soft, 1.0))
    new = np.where(grey, np.clip(soft, 0, 1), lum)
    f = np.where(lum > 1e-4, new / np.maximum(lum, 1e-4), 1.0)
    out = a.copy(); out[..., :3] = np.clip(a[..., :3] * f[..., None], 0, 1)
    grow = m2 & ~m                                                          # pixels the closing / the hole filling added: the colour around
    if grow.any():
        _, (iy, ix) = ndimage.distance_transform_edt(~m, return_indices=True)
        out[grow, :3] = out[iy[grow], ix[grow], :3]
    out[..., 3] = m2
    out, _ = despeckle(out)                                                 # the sharpening brought the seams of the panels back as dark dashes
    lum2 = out[..., :3] @ np.array([0.299, 0.587, 0.114]); inside = ndimage.binary_erosion(m2, iterations=1)
    med5 = ndimage.median_filter(np.where(m2, lum2, np.nan_to_num(np.median(lum2[m2]))), size=5)
    line = inside & (lum2 < LINE_K * med5)                                  # dark lines (a dark seam of the texture along the gold bands, slits): darker than LINE_K of the 5 x 5 median
    if line.any():
        medc = np.stack([ndimage.median_filter(out[..., c], size=5) for c in range(3)], -1)
        out[line, :3] = medc[line]
    edge = m2 & ~ndimage.binary_erosion(m2, iterations=1)
    out[edge, :3] *= OUTLINE_K
    return out


def texture_cloth(a, ref, seed=3):
    """the cloth of the original gumps is painted, not smooth: local contrast of the folds (TEX_FOLDS x (blur 1 px - blur 5 px)), deeper shadows (luminance about the median to the power
    TEX_GAMMA), grain and mottle (noise blurred 0.6 / 2 px, TEX_GRAIN / TEX_MOTTLE of the luminance; on the gold TEX_GOLD of it), the grey's p5 / p50 / p95 back to the original's, the gold
    bands' edge TEX_BORDER darker (an embroidered band). Measured on the male gump: fine grain 0.024 -> 0.034 (original 0.020), folds 0.061 -> 0.085 (0.067), p5 0.27 -> 0.17 (0.19)"""
    m = a[..., 3] > 0; inner = ndimage.binary_erosion(m, iterations=1)
    sat = a[..., :3].max(-1) - a[..., :3].min(-1); gold = m & (sat > 0.06); grey = inner & ~gold
    if not grey.any():
        return a
    Lw = np.array([0.299, 0.587, 0.114]); lum = a[..., :3] @ Lw; rng = np.random.default_rng(seed)
    new = lum + TEX_FOLDS * (ndimage.gaussian_filter(lum, 1.0) - ndimage.gaussian_filter(lum, 5.0))
    f = np.where(lum > 1e-3, new / np.maximum(lum, 1e-3), 1.0)
    med = np.median(lum[grey]); f = f * np.where(grey, (np.maximum(lum, 1e-3) / med) ** (TEX_GAMMA - 1.0), 1.0)
    n1 = ndimage.gaussian_filter(rng.standard_normal(lum.shape), 0.6); n2 = ndimage.gaussian_filter(rng.standard_normal(lum.shape), 2.0)
    nz = TEX_GRAIN * n1 / n1.std() + TEX_MOTTLE * n2 / n2.std()
    f = f * np.where(grey, 1 + nz, np.where(gold, 1 + TEX_GOLD * nz, 1.0))
    out = a.copy(); out[..., :3] = np.clip(a[..., :3] * f[..., None], 0, 1)
    l2 = out[..., :3] @ Lw; rm = ref[..., 3] > 0; rl = (ref[..., :3].astype(np.float32) / 255.0) @ Lw
    s5, s50, s95 = np.percentile(l2[grey], [5, 50, 95]); r5, r50, r95 = np.percentile(rl[rm], [5, 50, 95])
    tl = np.interp(l2, [0, s5, s50, s95, 1], [0, r5, r50, r95, min(1.0, r95 + (1 - s95) * (r95 - r50) / max(s95 - s50, 1e-4))])
    out[grey, :3] = np.clip(out[grey, :3] * (tl / np.maximum(l2, 1e-3))[grey][:, None], 0, 1)
    e = gold & ~ndimage.binary_erosion(gold, iterations=1) & inner
    out[e, :3] *= TEX_BORDER
    return out


def to8(a):
    return np.clip(a * 255 + 0.5, 0, 255).astype(np.uint8)


report = {}
tmp = os.path.join(OUT, "_tmp.png")
for gender, refp in REFS.items():
    if not refp:
        continue
    ref = np.asarray(Image.open(refp).convert("RGBA")); refm = ref[..., 3] > 0
    pose_arms(0, 0); before = iou(raster(to_gump(flat_tris(items), (1, 1, 1, 0, 0)), GW, GH, 1), refm)
    fist = fists(BODIES[gender], refm) if BODIES.get(gender) else None
    bare = None
    if BODIES.get(gender):
        bb = np.asarray(Image.open(BODIES[gender]).convert("RGBA"))[..., 3] > 0
        bare = bb & refm; bare[:ARM_ROWS[0]] = False; bare[ARM_ROWS[1]:] = False; bare[:, int(GX0 - ARM_DX):int(GX0 + ARM_DX)] = False
    if ARM_MODE == "joints" and gender in JOINTS:
        r = fit_body(refm); kxt, kxb, ky, dx, dy = r.x; P = tuple(r.x)
        wr, ce, gp, ov = fit_cuffs(JOINTS[gender], P, BODIES[gender], refm) if BODIES.get(gender) else (None, None, None, None)
        arms = pose_arms_to(JOINTS[gender], P, wr); out_deg = bend = alen = float("nan")
        arms = dict(arms, forearm_target=wr, cuff_error_px=ce, forearm_bare_px=gp, hand_covered_px=ov)
    else:
        r = fit_gender(refm, fist, bare); out_deg, bend, alen, kxt, kxb, ky, dx, dy = r.x; P = (kxt, kxb, ky, dx, dy)
        pose_arms(round(out_deg, 1), round(bend, 1), round(alen, 3)); arms = None
    # render at the gump scale times SS with one uniform scale k0, then the rest of the fit as a resampling (map_coordinates: the horizontal scale depends on the height)
    k0 = min(kxt, kxb, ky); W, H = GW * SS, GH * SS
    cxw = (GW / 2 - GX0) / PXM; czw = (GY_FEET - GH / 2) / PXM
    a = render(tmp, W, H, PXM * SS * k0, cxw / k0, czw / k0, items, True)
    saved = white_albedo(items); sh = render_light(tmp, W, H, PXM * SS * k0, cxw / k0, czw / k0, items, True); restore_albedo(saved)
    # the render maps world (x, z) to SS * (GX0 + x PXM k0, GY_FEET - z PXM k0) (camera centred so that the body axis / floor land there); the wanted map uses kx, ky and the shift
    Yo, Xo = np.mgrid[0:H, 0:W].astype(np.float64) + 0.5
    z = (SS * (GY_FEET + dy) - Yo) / (SS * PXM * ky); xw = (Xo - SS * (GX0 + dx)) / (SS * PXM * kx_at(z, kxt, kxb))
    Yi, Xi = SS * GY_FEET - z * SS * PXM * k0 - 0.5, SS * GX0 + xw * SS * PXM * k0 - 0.5
    pm = a.copy(); pm[..., :3] *= pm[..., 3:]
    wa = np.stack([ndimage.map_coordinates(pm[..., c], [Yi, Xi], order=1, mode="constant", cval=0.0) for c in range(4)], -1).astype(np.float32)
    wa[..., :3] /= np.maximum(wa[..., 3:], 1e-6)
    psh = sh.copy(); psh[..., :3] *= psh[..., 3:]
    wsh = np.stack([ndimage.map_coordinates(psh[..., c], [Yi, Xi], order=1, mode="constant", cval=0.0) for c in range(4)], -1).astype(np.float32)
    wsh[..., :3] /= np.maximum(wsh[..., 3:], 1e-6)
    if os.environ.get("PD_SAVE_RAW"):
        np.save(os.path.join(OUT, "raw_%s.npy" % gender), wa); np.save(os.path.join(OUT, "shade_%s.npy" % gender), wsh)
    res = box_down(compose(wa, wsh, SS), SS)
    res, lv = match_levels(res, ref)
    res, nsp = despeckle(res) if DESPECKLE > 0 else (res, 0)          # after the levels: their stretch made the darker folds black again
    covered, skin_left = 0, None
    if BODIES.get(gender):                                            # before smooth_cloth: the outline goes round the grown edge
        res, covered, skin_left = cover_body(res, BODIES[gender], refm, JOINTS.get(gender) if ARM_MODE == "joints" else None)
    res = texture_cloth(smooth_cloth(res), ref)
    Image.fromarray(to8(res)).save(os.path.join(OUT, "gump_%s.png" % gender))
    after = iou(res[..., 3] > 0, refm)
    hand_px = to_gump(hand_points(), P)
    hand_err = [round(float(np.hypot(*(hp - np.array(f)))), 1) for hp, f in zip(hand_px, fist)] if fist else None
    bare_left = int((bare & ~(res[..., 3] > 0)).sum()) if bare is not None else None
    report[gender] = dict(arm_mode=ARM_MODE, arms_deg=arms, arms_out=round(out_deg, 1), elbow_bend=round(bend, 1), arm_length=round(alen, 3), bare_arm_px=bare_left, covered_px=covered, skin_left_px=skin_left, kx_top=round(kxt, 3), kx_hem=round(kxb, 3), ky=round(ky, 3), dx=round(dx, 1), dy=round(dy, 1),
                          iou_rest=round(before, 3), iou_fit_flat=round(1 - r.fun, 3), iou_render=round(after, 3), levels=[round(float(v), 3) for v in lv], specks=nsp, fists=[[round(float(v), 1) for v in f] for f in fist] if fist else None, hand_error_px=hand_err)
    print("GUMP %s: %s" % (gender, report[gender]), flush=True)

if ART_REF:                                  # the item laid flat: arms out at a right angle, front view, turned 45 deg (the collar up right, the hem down left, as the original icon), fitted to its box
    ref = np.asarray(Image.open(ART_REF).convert("RGBA")); ys, xs = np.nonzero(ref[..., 3] > 0)
    rb = (xs.min(), ys.min(), xs.max(), ys.max()); AW, AH = ref.shape[1], ref.shape[0]
    pose_arms(ART_ARMS, 0, 1.0)
    tr = flat_tris(items); lo = tr.reshape(-1, 2).min(0); hi = tr.reshape(-1, 2).max(0)
    ppm = 400.0
    w, h = int((hi[0] - lo[0]) * ppm) + 8, int((hi[1] - lo[1]) * ppm) + 8
    a = render(tmp, w, h, ppm, (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, items, False)          # no holdout: the head would cut a hole in the collar
    saved = white_albedo(items); sh = render_light(tmp, w, h, ppm, (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, items, False); restore_albedo(saved)
    if os.environ.get("PD_SAVE_RAW"):
        np.save(os.path.join(OUT, "rawrot_art.npy"), a); np.save(os.path.join(OUT, "shaderot_art.npy"), sh)
    def laid(x, box=None):                    # turned ART_TURN, cropped (to the textured render's box), stretched to the original's box at S4 times its pixels
        pm = x.copy(); pm[..., :3] *= pm[..., 3:]
        im = Image.fromarray(np.clip(pm * 255 + 0.5, 0, 255).astype(np.uint8), "RGBA").rotate(ART_TURN, resample=Image.BICUBIC, expand=True)
        rot = np.asarray(im, np.float32) / 255.0
        if box is None:
            yy, xx = np.nonzero(rot[..., 3] > 0.5); box = (yy.min(), yy.max() + 1, xx.min(), xx.max() + 1)
        rot = rot[box[0]:box[1], box[2]:box[3]]
        rs = np.stack([np.asarray(Image.fromarray(rot[..., c]).resize((bw, bh), Image.BILINEAR)) for c in range(4)], -1)
        rs[..., :3] /= np.maximum(rs[..., 3:], 1e-6)
        big = np.zeros((AH * S4, AW * S4, 4), np.float32); big[rb[1] * S4:rb[1] * S4 + bh, rb[0] * S4:rb[0] * S4 + bw] = rs
        return big, box
    S4 = 4; bw, bh = (rb[2] - rb[0] + 1) * S4, (rb[3] - rb[1] + 1) * S4          # stretched to the original's box (its proportions are those of a laid robe)
    big, box = laid(a); bigsh, _ = laid(sh, box)
    big = compose(big, bigsh, S4)
    if os.environ.get("PD_SAVE_RAW"):
        np.save(os.path.join(OUT, "raw_art.npy"), big)
    art = box_down(big, S4)
    art, lv = match_levels(art, ref)
    art, nsp = despeckle(art) if DESPECKLE > 0 else (art, 0)
    art = texture_cloth(smooth_cloth(art), ref)
    Image.fromarray(to8(art)).save(os.path.join(OUT, "art.png"))
    Image.fromarray(to8(art[:, ::-1])).save(os.path.join(OUT, "art_mirror.png"))
    ys2, xs2 = np.nonzero(art[..., 3] > 0)
    report["art"] = dict(turn=ART_TURN, box_ref=[int(v) for v in rb], box=[int(xs2.min()), int(ys2.min()), int(xs2.max()), int(ys2.max())], iou=round(iou(art[..., 3] > 0, ref[..., 3] > 0), 3))
    print("ART: %s" % report["art"], flush=True)
json.dump(report, open(os.path.join(OUT, "fit.json"), "w"), indent=1)
if os.path.exists(tmp):
    os.remove(tmp)
