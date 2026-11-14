"""Paperdoll gumps (male on body gump 12, female on body gump 13) and the item icon (art) of a prop worn ON THE BACK (crossed axes, quiver, sword on the back), rendered from the same 3D model as its animation.

    PD_OUT=DIR [PD_BODY_MALE=12.png PD_BODY_FEMALE=13.png] python run_script_in_blend.py ITEM.blend uo_render_back_gump.py     (ITEM.blend from uo_make_item.py with a "rigid" recipe)

Gump (gumpart.mul, 260 x 237): front view, orthographic, 90.5 px/m, the same alignment as uo_render_paperdoll.py (body gump 12: head top y 54 .. feet y 221, body axis x 94.5). What the viewer sees of a back prop is
what sticks out beyond the drawn body: the blades above the shoulders, the haft ends beside the hips. The drawn body gump (reference png, default docs/paperdoll) is cut out of the picture, so the
gump is right whether the client draws it under or over the body (the paperdoll arms of the drawn body differ from the 3D rest pose, so the 3D body is no use as a holdout).
Female: the same prop on body gump 13 (head top y 58, feet y 219, narrower shoulders): scaled about the body axis and the feet by FEM_KX (width) and the height ratio, the hub kept on the same body height.
Art (art.mul): seen head-on and turned PD_ART_ROLL (45) degrees clockwise in the picture plane (PD_ART_TILT=55, PD_ART_ROLL=0, PD_ART_TURN=-35 = the old view of a lying item), fitted into ART_W x ART_H px; the mirrored second icon is written too.
Writes gump_male.png, gump_female.png, art.png, art_mirror.png and the mul entries *.bin (uo_gump_art.py) in PD_OUT. Light / materials as render_uo_layer.py (UO_Look, 1 sample per pixel, 3 x 3 supersampling box-averaged).
"""
import os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(globals().get("__file__") or sys.argv[2]))
sys.path.insert(0, HERE)
import uo_gump_art as ga
_src = open(os.path.join(HERE, "uo_render_paperdoll.py"), encoding="utf-8").read()
exec(compile(_src[:_src.index("\nbelt = [o")], "uo_render_paperdoll.py", "exec"), globals())    # scene, light, camera, render(), cap(), box_down(), to_rgba8() only
from PIL import Image
from scipy import ndimage

REF = {"male": os.environ.get("PD_BODY_MALE", os.path.join(HERE, "..", "docs", "paperdoll", "paperdoll_male_0xc.png")),
       "female": os.environ.get("PD_BODY_FEMALE", os.path.join(HERE, "..", "docs", "paperdoll", "paperdoll_female_0xd.png"))}
FEET = {"male": 221.0, "female": 219.0}            # gump row of the floor (measured on the body gumps 12 / 13: rows 54..221 / 58..219)
HEAD = {"male": 54.0, "female": 58.0}              # gump row of the head top
AXIS = {"male": 94.5, "female": 93.5}              # gump column of the body axis (the middle of the torso at the hips)
FEM_KX = float(os.environ.get("PD_FEM_KX", "0.90"))   # female: width of the prop relative to the male one (the shoulders of gump 13 are 45 px wide, gump 12's 55 px: 0.82; the prop keeps a bit more)
OUTLINE_G = float(os.environ.get("PD_OUTLINE", "0.62"))   # the edge pixels of the item (next to transparency) multiplied by this (a soft dark edge like the client's gumps)
ART_W, ART_H = int(os.environ.get("PD_ART_W", "44")), int(os.environ.get("PD_ART_H", "44"))
COLOR_K = float(os.environ.get("PD_COLOR_K", "0.6"))   # gump: the coloured (not grey) parts, the wood, are scaled by this: the front view is lit brighter than the animation (wood median (146, 89, 44) against the animation's (82, 47, 30))
RAISE = {"male": float(os.environ.get("PD_RAISE_MALE", "3")), "female": float(os.environ.get("PD_RAISE_FEMALE", "6"))}   # px: the prop is moved up on the gump by this (the male torso is longer: the blades stood too high above the shoulders at 6)
BODY_GROW = int(os.environ.get("PD_BODY_GROW", "0"))   # px: the drawn body's silhouette is grown by this before it is cut out of the prop

tmp = os.path.join(OUT, "_tmp.png")
cxw = (GW / 2 - GX0) / PXM
czw = (GY_FEET - GH / 2) / PXM
W, H = GW * SS, GH * SS
STRAIGHT = int(os.environ.get("PD_STRAIGHT", "1"))                 # 1 = the two hafts are made straight lines through the hub (the Meshy model's halves are skewed and offset: 9 deg and 5 px)
STRAIGHT_DEG = float(os.environ.get("PD_STRAIGHT_DEG", "30"))      # deg from the vertical of both hafts (symmetric X)
HUB_XZ = (0.0, float(os.environ.get("PD_HUB_Z", "1.36")))          # world x, z of the hub plate (rest pose of the recipe: the plate at the shoulder blades)
CUT_R, BLEND_R = 0.10, 0.08                                        # m: the hub plate (within CUT_R of the hub) stays; the halves are blended in over BLEND_R


def front_halves(a):
    """wood pixel fits of the four half-hafts in a front render a (supersampled): {name: (centroid, unit direction, angle from vertical deg, signed distance of the hub from the line, px)}"""
    al = a[..., 3] > 0.5; r, g, b = a[..., 0], a[..., 1], a[..., 2]
    wood = al & (r > g) & (g > b) & ((r - b) >= 40.0 / 255.0)
    iron = al & ~wood
    lab, n = ndimage.label(iron); sizes = ndimage.sum(iron, lab, range(1, n + 1))
    yy, xx = np.nonzero(lab == (np.argmax(sizes) + 1)); hx, hy = xx.mean(), yy.mean()
    wy, wx = np.nonzero(wood); dx, dy = wx - hx, wy - hy; far = np.hypot(dx, dy) > 14 * SS
    out = {}
    for name, m in (("UL", (dx < 0) & (dy < 0)), ("UR", (dx > 0) & (dy < 0)), ("LL", (dx < 0) & (dy > 0)), ("LR", (dx > 0) & (dy > 0))):
        sel = far & m
        P = np.c_[wx[sel], wy[sel]].astype(float); c = P.mean(0)
        d = np.linalg.svd(P - c, full_matrices=False)[2][0]
        if d[1] < 0:
            d = -d                                                 # pointing down the picture
        nrm = np.array([-d[1], d[0]])
        out[name] = (c, d, float(np.degrees(np.arctan2(d[0], d[1]))), float(np.dot(np.array([hx, hy]) - c, nrm)), (hx, hy))
    return out


def straighten(a):
    """rest-pose mesh edit: each half-haft (with the head on it) is rotated about the hub to the common angle and shifted so that its axis passes through the hub centre"""
    f = front_halves(a); k = PXM * SS
    for ob in items:
        M = ob.matrix_world.copy(); Mi = M.inverted()
        co = np.array([(M @ v.co)[:] for v in ob.data.vertices])
        x, z = co[:, 0] - HUB_XZ[0], co[:, 2] - HUB_XZ[1]; r = np.hypot(x, z)
        w = np.clip((r - CUT_R) / BLEND_R, 0.0, 1.0); w = w * w * (3 - 2 * w)
        new = co.copy()
        for name, (xs, zs, deg_tgt) in {"UL": (-1, 1, -STRAIGHT_DEG), "UR": (1, 1, STRAIGHT_DEG), "LL": (-1, -1, STRAIGHT_DEG), "LR": (1, -1, -STRAIGHT_DEG)}.items():
            m = (np.sign(x) == xs) & (np.sign(z) == zs)
            ang = np.radians(f[name][2])                           # angle of the half's line from the picture's vertical, measured (x right, y down): down-right = +
            # picture direction (right, down); the world (x right, z up): the same line in the world is (dx, -dy)
            tgt = np.radians({"UL": 180 - STRAIGHT_DEG, "UR": 180 + STRAIGHT_DEG, "LL": STRAIGHT_DEG * -1, "LR": STRAIGHT_DEG}[name])
            cur = np.arctan2(np.sin(ang), np.cos(ang))
            # direction of the half in the picture pointing down: (sin ang, cos ang); target pointing down: up-left half continues the down-right half: LR / UL share the angle +T, LL / UR share -T
            T = np.radians(STRAIGHT_DEG)
            want = {"UL": T, "LR": T, "UR": -T, "LL": -T}[name]
            dth = want - ang                                       # rotation of the line in the picture, + = the down-pointing end turns to the right (clockwise seen by the viewer)
            off = f[name][3] / k                                   # m, signed distance of the hub from the half's line, along the picture normal (-dy, dx) of the line
            # picture normal n_p = (-d_y, d_x) with d = (sin ang, cos ang); in the world (x right, z up) that is (-cos ang, -sin ang) (y down -> z up)
            c, s_ = np.cos(dth), np.sin(dth)
            # the half's line turns by dth in the picture (measured from the vertical, down-right positive): the upper-left half, 8 deg too tilted, is turned clockwise = a negative angle in the world (x right, z up)
            xr = x * np.cos(dth) - z * np.sin(dth); zr = x * np.sin(dth) + z * np.cos(dth)
            nx, nz = -np.cos(want), -np.sin(want)                  # the normal after the rotation (picture normal of the new direction, in the world)
            # shift so that the line passes through the hub: the hub is `off` from the line along n_p, so move the half by +off along n_p
            xs_, zs_ = xr + off * nx, zr + off * nz
            tx, tz = x + w * (xs_ - x), z + w * (zs_ - z)
            new[m, 0] = HUB_XZ[0] + tx[m]; new[m, 2] = HUB_XZ[1] + tz[m]
        for v, p in zip(ob.data.vertices, new):
            v.co = Mi @ Vector(p.tolist())
        ob.data.update()
    bpy.context.view_layer.update()


a0 = render(tmp, W, H, PXM * SS, cxw, czw, items, False)           # the prop alone, float RGBA at SS x SS
if STRAIGHT:
    f0 = front_halves(a0)
    print("PD haft halves before: " + "  ".join("%s %.1f deg off %.1f px" % (n, f0[n][2], f0[n][3] / SS) for n in f0))
    straighten(a0)
    a0 = render(tmp, W, H, PXM * SS, cxw, czw, items, False)
    f1 = front_halves(a0)
    print("PD haft halves after:  " + "  ".join("%s %.1f deg off %.1f px" % (n, f1[n][2], f1[n][3] / SS) for n in f1))


def affine(a, kx, ky, ax, ay, dy):
    """scale about (ax, ay) (supersampled px) by kx / ky, then move by dy rows; premultiplied linear resampling"""
    pm = a.copy(); pm[..., :3] *= pm[..., 3:]
    out = np.zeros_like(pm)
    for c in range(4):
        out[..., c] = ndimage.affine_transform(pm[..., c], [1.0 / ky, 1.0 / kx], offset=[ay - ay / ky - dy / ky, ax - ax / kx], order=1, mode="constant", cval=0.0)
    out[..., :3] /= np.maximum(out[..., 3:], 1e-6)
    return out


WOOD_SAT = float(os.environ.get("PD_WOOD_SAT", "40")) / 255.0   # a brownish pixel is wood when red - blue is at least this (the gump wood: 50-60); the dull brown specks of the metal texture (rust) are less saturated and are turned grey
SPECK = float(os.environ.get("PD_SPECK", "20")) / 255.0      # a metal pixel darker than the median of its 5 x 5 neighbourhood by more than this (levels) is a speck of the texture
SMOOTH_IRON = int(os.environ.get("PD_SMOOTH_IRON", "1"))   # passes of a 3 x 3 median on the metal pixels (not the wood, not the silhouette): the blades' texture noise reads as blemishes at 260 x 237


def clean_iron(img):
    """float RGBA (h, w, 4): small brown patches among the grey metal desaturated, then the metal evened by a 3 x 3 median (alpha unchanged)"""
    img = img.copy(); rgb = img[..., :3]; m = img[..., 3] > 0.5
    brown = m & (rgb[..., 0] > rgb[..., 1]) & (rgb[..., 1] > rgb[..., 2]) & ((rgb[..., 0] - rgb[..., 2]) > 10.0 / 255.0)
    wood = brown & ((rgb[..., 0] - rgb[..., 2]) >= WOOD_SAT)
    wood = ndimage.binary_opening(wood, structure=np.ones((2, 2), bool)) | (wood & ndimage.binary_dilation(ndimage.binary_opening(wood, structure=np.ones((2, 2), bool)), iterations=1))    # a lone saturated pixel in the metal is not wood
    rust = brown & ~wood
    grey_l = rgb.mean(-1, keepdims=True)
    rgb[rust] = np.repeat(grey_l, 3, -1)[rust] * 0.95
    iron = m & ~wood
    for _ in range(SMOOTH_IRON):
        out = rgb.copy()
        for c in range(3):
            ch = np.where(iron, rgb[..., c], np.nan)
            pad = np.pad(ch, 1, constant_values=np.nan)
            st = np.stack([pad[dy:dy + ch.shape[0], dx:dx + ch.shape[1]] for dy in range(3) for dx in range(3)])
            med = np.nanmedian(st, 0)
            out[..., c] = np.where(iron & np.isfinite(med), med, rgb[..., c])
        rgb = out
    # dark specks: a metal pixel (not on the silhouette edge) much darker than the median of its 5 x 5 neighbourhood takes that median
    inner = ndimage.binary_erosion(iron, structure=np.ones((3, 3), bool), border_value=0)
    lum = np.where(iron, rgb.mean(-1), np.nan)
    pad = np.pad(lum, 2, constant_values=np.nan)
    med5 = np.nanmedian(np.stack([pad[dy:dy + lum.shape[0], dx:dx + lum.shape[1]] for dy in range(5) for dx in range(5)]), 0)
    speck = inner & np.isfinite(med5) & ((med5 - rgb.mean(-1)) > SPECK)
    if speck.any():
        sc_ = np.where(speck, med5 / np.maximum(rgb.mean(-1), 1e-3), 1.0)[..., None]
        rgb = np.where(speck[..., None], np.clip(rgb * sc_, 0, 1), rgb)
    img[..., :3] = rgb
    return img


MIN_COMP = int(os.environ.get("PD_MIN_COMP", "14"))          # px: a detached piece of the gump smaller than this is removed (loose pixels)
THIN = int(os.environ.get("PD_THIN", "1"))                    # px: the lower part of the hafts is this much narrower (1 or 2): 1 = one pixel off the outer side, 2 = one off each side
THIN_FROM = {"male": float(os.environ.get("PD_THIN_FROM_MALE", "112")), "female": float(os.environ.get("PD_THIN_FROM_FEMALE", "108"))}   # gump row from which the hafts are thinned (below the hub and the body's waist: only the haft ends beside the hips)


def thin_wood(img, n, y_from, axis):
    """the wood runs of the rows from y_from down are trimmed by n px in total (n = 1: the outer pixel, n = 2: one on each side); a haft keeps at least 2 px"""
    img = img.copy(); rgb = img[..., :3]; m = img[..., 3] > 0.5
    wood = m & (rgb[..., 0] > rgb[..., 1]) & (rgb[..., 1] > rgb[..., 2]) & ((rgb[..., 0] - rgb[..., 2]) >= WOOD_SAT)
    for y in range(int(y_from), img.shape[0]):
        x = 0
        while x < img.shape[1]:
            if not wood[y, x]:
                x += 1; continue
            x1 = x
            while x1 < img.shape[1] and wood[y, x1]:
                x1 += 1
            if x1 - x > n + 1:                                  # run [x, x1)
                outer_left = (x + x1) / 2.0 < axis
                if n == 1:
                    cut = [x] if outer_left else [x1 - 1]
                else:
                    cut = [x, x1 - 1][:n]
                for c in cut:
                    img[y, c, 3] = 0
            x = x1
    return img


def darken_edges(img, k):
    m = img[..., 3] > 0.5
    inner = ndimage.binary_erosion(m, structure=np.ones((3, 3), bool), border_value=1)
    edge = m & ~inner
    img = img.copy(); img[edge, :3] *= k
    return img


for gender in ("male", "female"):
    kx = 1.0 if gender == "male" else FEM_KX
    ky = 1.0 if gender == "male" else (FEET[gender] - HEAD[gender]) / (FEET["male"] - HEAD["male"])
    # the 3D model's feet are at GY_FEET (male); the female feet at FEET[female]: scale about the male feet row, then move the feet row
    g = affine(a0, kx, ky, GX0 * SS, GY_FEET * SS, (FEET[gender] - GY_FEET) * SS) if gender == "female" else a0
    if gender == "female":                       # also the body axis: 94.5 -> 93.5 (a shift in x)
        g = ndimage.shift(g, (0, (AXIS[gender] - GX0) * SS, 0), order=1, mode="constant", cval=0.0)
    g = ndimage.shift(g, (-RAISE[gender] * SS, 0, 0), order=1, mode="constant", cval=0.0)
    r = cap(box_down(g, SS))
    top = r[..., :3].max(-1, keepdims=True); grey = (top - r[..., :3].min(-1, keepdims=True)) <= 10.0 / 255.0
    r[..., :3] = np.where(grey, r[..., :3], r[..., :3] * COLOR_K)
    r = clean_iron(r)
    if THIN:
        r = thin_wood(r, THIN, THIN_FROM[gender], AXIS[gender])
    r = darken_edges(r, OUTLINE_G)
    bmask = np.asarray(Image.open(REF[gender]).convert("RGBA"))[..., 3] > 0
    if BODY_GROW:
        bmask = ndimage.binary_dilation(bmask, iterations=BODY_GROW)
    r[bmask, 3] = 0
    r[r[..., 3] == 0, :3] = 0
    # loose pixels: a pixel with no 4-neighbour is dropped, then every detached piece smaller than MIN_COMP px (what is left of a haft end after the body is cut out)
    m = r[..., 3] > 0
    nb = ndimage.convolve(m.astype(int), np.array([[0, 1, 0], [1, 0, 1], [0, 1, 0]]), mode="constant")
    r[m & (nb == 0), 3] = 0
    lab, n = ndimage.label(r[..., 3] > 0, structure=np.ones((3, 3), int))
    if n:
        area = ndimage.sum(np.ones_like(lab), lab, index=np.arange(1, n + 1))
        r[np.isin(lab, 1 + np.nonzero(area < MIN_COMP)[0]), 3] = 0
    out = to_rgba8(r)
    Image.fromarray(out).save(os.path.join(OUT, "gump_%s.png" % gender))
    data, extra = ga.encode_gump(out)
    open(os.path.join(OUT, "gump_%s.bin" % gender), "wb").write(data)
    mm = out[..., 3] > 0
    ys, xs = np.nonzero(mm)
    print("PD %s: %d px, x %d..%d, y %d..%d (body gump rows %d..%d), extra=%d (w<<16|h)" % (gender, mm.sum(), xs.min(), xs.max(), ys.min(), ys.max(), HEAD[gender], FEET[gender], extra))

# art: the item as one object, tilted towards the camera, fitted into ART_W x ART_H
tilt = float(os.environ.get("PD_ART_TILT", "0"))             # 0 = seen head-on (the default now); 55 = lying on the ground seen from above (UO draws items at 45 degrees)
turn = float(os.environ.get("PD_ART_TURN", "0"))
roll = float(os.environ.get("PD_ART_ROLL", "45"))            # deg, in the picture plane, + = clockwise (to the right) as the viewer sees it
ART_COLOR_K = float(os.environ.get("PD_ART_COLOR_K", str(COLOR_K if tilt < 20 else 1.0)))   # head-on is lit like the gump: the same wood level
rig.rotation_mode = "ZYX"; rig.rotation_euler = (np.radians(tilt), np.radians(roll), np.radians(turn))
rig.location = (0, 0, 0)
bpy.context.view_layer.update()
S2 = 4
probe = render(tmp, 1024, 1024, 200.0, 0.0, 0.6, items, False)
ys, xs = np.nonzero(probe[..., 3] > 0.5)
bw, bh = (xs.max() - xs.min() + 1) / 200.0, (ys.max() - ys.min() + 1) / 200.0
k = min((ART_W - 2) / bw, (ART_H - 2) / bh)
ccx = ((xs.max() + xs.min()) / 2 - 512) / 200.0; ccz = 0.6 - ((ys.max() + ys.min()) / 2 - 512) / 200.0
art = render(tmp, ART_W * S2, ART_H * S2, k * S2, ccx, ccz, items, False)
res_art = cap(box_down(art, S2))
top = res_art[..., :3].max(-1, keepdims=True); grey = (top - res_art[..., :3].min(-1, keepdims=True)) <= 10.0 / 255.0
res_art[..., :3] = np.where(grey, res_art[..., :3], res_art[..., :3] * ART_COLOR_K)
res_art = darken_edges(clean_iron(res_art), OUTLINE_G)
res_art[res_art[..., 3] == 0, :3] = 0
np.save(os.path.join(OUT, "art_raw.npy"), res_art)
a8 = to_rgba8(res_art)
for name, im in (("art", a8), ("art_mirror", a8[:, ::-1].copy())):
    Image.fromarray(im).save(os.path.join(OUT, name + ".png"))
    open(os.path.join(OUT, name + ".bin"), "wb").write(ga.encode_art(im))
print("PD done: art %dx%d, px/m %.1f, object %.2f x %.2f m" % (ART_W, ART_H, k, bw, bh))
