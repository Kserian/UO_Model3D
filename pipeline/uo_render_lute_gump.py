"""Paperdoll gumps (male / female) and item art of the lute, rendered from the same 3D model as its animation (ITEM.blend from uo_make_item.py: the object keeps its upright
local axes, z = butt -> headstock, strings towards -Y; placement and skin are ignored). Settings and conventions as uo_render_weapon_gump.py (260 x 237, 90.5 px/m, the body gumps 12 / 13).

    python uo_render_lute_gump.py ITEM.blend OUT_DIR [--set NAME=VALUE ...]

Two gumps per gender:
  1h  the lute upright in the character's right hand (the left of the picture) like the client's weapons: the neck in the fist (GRIP_1H m above the bowl's end), the headstock up, leaning
      TILT_1H deg out, the strings towards the viewer. The neck is cut out under the body gump's fist (the fist shows over it, except the bottom HOLD_SHOW rows).
  2h  the lute held across the belly with both hands as in the stand actions: its axis along the line from fist to fist of the body gump (the arms of the drawn body are out, the fists
      ~88 px = 0.97 m apart), the middle of the lute at the middle of the two fists, HEADSTOCK_LEFT = the headstock to the left of the picture (the character's right hand) or to the right;
      cut out under both fists.
Art: the lute lying on the ground, strings up, seen from above (the client draws items top-down with the map turned 45 deg): the neck along the picture's diagonal, a dark rim
(ART_RIM) around, the second art its mirror.
Colours: those of the animation (the item's own texture in the UO look), edge pixels of the gump darkened by OUTLINE, 15-bit levels as the client stores them.
The body gumps (for the fists) are read from BODY_GUMPS (docs/paperdoll/paperdoll_male_0xc.png / paperdoll_female_0xd.png: the client's gumps 12 / 13).
--set CUT=False leaves the lute whole (nothing cut out under the fists).
Writes gump_{male,female}_{1h,2h}.png, art.png, art_mirror.png and the mul entries *.bin (uo_gump_art.py).
"""
import json, os, sys
import numpy as np
import bpy
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import uo_render_weapon_gump as wg

PXM = wg.PXM
GW, GH = wg.GW, wg.GH
SS = 4
BODY_GUMPS = {"male": os.path.join(HERE, "..", "docs", "paperdoll", "paperdoll_male_0xc.png"),
              "female": os.path.join(HERE, "..", "docs", "paperdoll", "paperdoll_female_0xd.png")}
GRIP_1H = 0.64                 # m above the bowl's end where the right fist holds the neck (the neck is 0.5 - 0.8)
FIST_1H = {"male": (48.0, 114.5), "female": (48.0, 113.0)}   # gump pixel of the middle of the fist (as uo_render_weapon_gump.py GRIP)
TILT_1H = 12.0                 # deg: the headstock leans out of the body (to the left of the picture)
HEADSTOCK_LEFT = True          # 2h: the headstock at the character's right hand (left of the picture)
LUTE_2H = 1.0                  # 2h: the lute's scale (the fists are 0.97 m apart)
HOLD_CUT = (9, 9, 7)           # the window of a fist (x within +-9 px, y 9 above .. 7 below its middle): the lute is cut out where the body gump's fist lies in it
HOLD_SHOW = {"male": 2, "female": 3}
CUT = True                     # False = the lute whole, nothing cut out under the fists (to fit it by hand over the body gump)
ART_PXM = 34.0
ART_W = 44
ART_RIM = 16.0
OUTLINE = 0.45
GAIN = 0.9                     # the gump's light level against the animation's (the client's wooden items are darker than a bright texture)
CLIENT_BODY = None


def tone(a, outline=OUTLINE, rim=None, gain=GAIN):
    """display RGB 0..1 + alpha -> uint8 RGBA: gain, edge pixels x outline, 15-bit levels, no true black (the 15-bit colour 0 is transparent); rim: a grey level drawn in the
    pixels next to the item (the dark rim of the client's arts)"""
    m = a[..., 3] > 0
    rgb = a[..., :3] * 255.0 * gain
    if outline < 1:
        pad = np.pad(m, 1)
        edge = m & ~(pad[:-2, 1:-1] & pad[2:, 1:-1] & pad[1:-1, :-2] & pad[1:-1, 2:])
        rgb[edge] *= outline
    q = (np.clip(np.round(rgb), 8, 255).astype(np.int32) >> 3) << 3
    out = np.zeros(a.shape[:2] + (4,), np.uint8)
    out[..., :3] = np.where(m[..., None], q, 0); out[..., 3] = np.where(m, 255, 0)
    if rim is not None:
        pad = np.pad(m, 1)
        ring = ~m & (pad[:-2, 1:-1] | pad[2:, 1:-1] | pad[1:-1, :-2] | pad[1:-1, 2:])
        out[ring, :3] = (int(rim) >> 3) << 3; out[ring, 3] = 255
    return out


def body_mask(gender):
    from PIL import Image
    a = np.asarray(Image.open(BODY_GUMPS[gender]).convert("RGBA"))
    bm = np.zeros((GH, GW), bool); h, w = min(GH, a.shape[0]), min(GW, a.shape[1]); bm[:h, :w] = a[:h, :w, 3] > 0
    return bm


def fists(bm):
    """middle of the two open hands of the body gump: the character's right (left of the picture) and left (right of the picture)"""
    ys, xs = np.nonzero(bm)
    L = (xs <= 54) & (ys <= 126); R = xs >= 128
    return (xs[L].mean(), ys[L].mean()), (xs[R].mean(), ys[R].mean())


def cut_under(img, bm, centres, show):
    """the lute is cut out where the body gump's hand lies in the window around each centre, except the bottom `show` rows of the hand (in each column)"""
    yy, xx = np.mgrid[0:GH, 0:GW]
    cut = np.zeros((GH, GW), bool)
    for gx, gy in centres:
        win = (np.abs(xx + 0.5 - gx) <= HOLD_CUT[0]) & (yy + 0.5 >= gy - HOLD_CUT[1]) & (yy + 0.5 <= gy + HOLD_CUT[2])
        hand = win & bm
        bottom = np.where(hand.any(0), GH - 1 - np.argmax(hand[::-1], 0), -1)
        c = hand & (img[..., 3] > 0)
        if show:
            c &= yy <= bottom[None, :] - show
        cut |= c
    img[cut] = 0
    return int(cut.sum())


def main(src, out):
    from PIL import Image
    import uo_gump_art as ga
    bpy.ops.wm.open_mainfile(filepath=src)
    sc = bpy.context.scene
    rig = bpy.data.objects["UO_Rig"]; rig.data.pose_position = "REST"; rig["uo_direction"] = 0
    bpy.context.view_layer.update()
    ob = next(o for o in bpy.data.collections["Clothing"].all_objects if o.type == "MESH" and not o.hide_render)
    for o in bpy.data.objects:
        if o.type == "MESH" and o is not ob:
            o.hide_render = True
    for m in list(ob.modifiers):
        ob.modifiers.remove(m)
    if ob.animation_data:
        ob.animation_data_clear()
    ob.parent = None; ob.matrix_world = Matrix.Identity(4); ob.rotation_mode = "XYZ"
    nv = len(ob.data.vertices)
    co = np.empty(nv * 3); ob.data.vertices.foreach_get("co", co); V0 = co.reshape(-1, 3)        # the local axes: z butt -> headstock, -Y the strings
    near = V0[np.abs(V0[:, 2] - GRIP_1H) < 0.03]; cxy = near[:, :2].mean(0)                       # the neck's axis at the grip
    cam = wg.setup_render(sc)
    os.makedirs(out, exist_ok=True); tmp = os.path.join(out, "_tmp.png")

    def place(P):
        ob.data.vertices.foreach_set("co", P.astype(np.float64).ravel()); ob.data.update()

    def front(P, gx, gy):
        """P placed with its origin at the gump pixel (gx, gy); returns the supersampled image reduced to the gump's size"""
        place(P)
        cx = (GW / 2 - gx) / PXM; cz = (gy - GH / 2) / PXM
        return wg.box_down(wg.render(sc, cam, tmp, GW * SS, GH * SS, PXM * SS, cx, cz, False), SS)

    def about_y(P, deg):          # rotation about the view axis, positive = the top goes to -X (the left of the picture)
        return P @ np.array(Matrix.Rotation(-np.radians(deg), 3, Vector((0, 1, 0)))).T

    res = {}
    for gender in ("male", "female"):
        bm = body_mask(gender)
        (lx, ly), (rx, ry) = fists(bm)
        # 1h: the neck upright in the right fist, the headstock up, leaning out
        P = about_y(V0 - np.array([cxy[0], cxy[1], GRIP_1H]), TILT_1H)
        gx, gy = FIST_1H[gender]
        img = tone(front(P, gx, gy))
        n = cut_under(img, bm, [(gx, gy)], HOLD_SHOW[gender]) if CUT else 0
        res[gender + "_1h"] = img
        print("LG %s 1h: fist (%.1f, %.1f), %d px cut under the fist" % (gender, gx, gy, n))
        # 2h: across the belly, the axis along the line from fist to fist, the middle of the lute at the middle of the two fists
        mid = np.array([(lx + rx) / 2, (ly + ry) / 2]); d = np.array([rx - lx, ry - ly]); ang = np.degrees(np.arctan2(-(d[1]), d[0]))   # deg above the horizontal (picture y is down)
        # the lute's axis (local z) turned from vertical onto the line: top towards the left (headstock left) or the right
        Pc = (V0 - np.array([cxy[0], cxy[1], 0.5])) * LUTE_2H
        turn = 90.0 + ang if HEADSTOCK_LEFT else ang - 90.0
        P2 = about_y(Pc, turn)
        img2 = tone(front(P2, mid[0], mid[1]))
        n2 = cut_under(img2, bm, [(lx, ly), (rx, ry)], HOLD_SHOW[gender]) if CUT else 0
        res[gender + "_2h"] = img2
        print("LG %s 2h: fists (%.1f, %.1f) (%.1f, %.1f), line %.1f deg, %d px cut" % (gender, lx, ly, rx, ry, ang, n2))
    for name, img in res.items():
        Image.fromarray(img).save(os.path.join(out, "gump_%s.png" % name))
        data, extra = ga.encode_gump(img)
        open(os.path.join(out, "gump_%s.bin" % name), "wb").write(data)
        ys, xs = np.nonzero(img[..., 3]); print("LG gump %s: bbox x %d..%d y %d..%d, %d px, extra %08x" % (name, xs.min(), xs.max(), ys.min(), ys.max(), len(xs), extra))

    # art: lying on the ground, strings up, the neck along the diagonal of the picture (butt bottom left), seen from above
    a = Vector((1, 1, 0)).normalized(); f = Vector((0, 0, 1))
    x = (-f).cross(a).normalized()
    Rp = np.array(Matrix(((x.x, -f.x, a.x), (x.y, -f.y, a.y), (x.z, -f.z, a.z))))
    P = (V0 - np.array([cxy[0], cxy[1], 0.5])) @ Rp.T
    P[:, 2] -= P[:, 2].min()
    lo, hi = P[:, :2].min(0), P[:, :2].max(0); c = (lo + hi) / 2
    w = max(ART_W, int(np.ceil((hi[0] - lo[0]) * ART_PXM)) + 3); h = int(np.ceil((hi[1] - lo[1]) * ART_PXM)) + 3
    place(P)
    img = wg.box_down(wg.render(sc, cam, tmp, w * SS, h * SS, ART_PXM * SS, c[0], c[1], True), SS)
    art = tone(img, outline=1.0, rim=ART_RIM)
    ys, xs = np.nonzero(art[..., 3]); art = art[ys.min():ys.max() + 1]
    for name, im in (("art", art), ("art_mirror", art[:, ::-1].copy())):
        Image.fromarray(im).save(os.path.join(out, name + ".png"))
        open(os.path.join(out, name + ".bin"), "wb").write(ga.encode_art(im))
    print("LG art: %d x %d" % (art.shape[1], art.shape[0]))
    if os.path.exists(tmp):
        os.remove(tmp)


if __name__ == "__main__":
    a = sys.argv[1:]; pos = []; i = 0
    while i < len(a):
        if a[i] == "--set":
            k, v = a[i + 1].split("=", 1); g = globals()
            g[k] = eval(v) if isinstance(g[k], (tuple, dict, bool)) else type(g[k])(v); i += 2
        else:
            pos.append(a[i]); i += 1
    main(pos[0], pos[1])
