"""Paperdoll gumps (male / female, two ways of holding) and the item art of the harp, rendered from the same 3D model as its animation.

    python uo_render_harp_gump.py GUMP.blend ART.blend OUT_DIR [--set NAME=VALUE ...]

GUMP.blend / ART.blend: items of uo_make_item.py (recipes harp_gump*.json / harp.json, harp_strings.json): the gump wants a thin frame (THICKEN 0.004: the frame is 3-4 px at 90.5 px/m),
the art the animation's thick one (THICKEN 0.019: 2-3 px at 34 px/m). Light, materials, supersampling, the tone of wood: uo_render_weapon_gump.py (its functions are used).

Gumps (260 x 237, front view, 90.5 px/m, like the body gumps 12 / 13 of docs/paperdoll): the harp is held by the pillar (the thin arm) in the character's right fist (the left of the picture, the
grip of the client's maces: (48, 114.5) male, (48, 113) female). Two holds, each in the right hand and (_left) in the other one, mirrored (VARIANTS):
  weapon: like a weapon at the side: the pillar nearly upright, its top leaning TILT out from the body, the sound box side out too (turned YAW towards the viewer so that it stays in the picture);
  play  : close to the body, as if about to play it: the pillar leaning a little towards the body, the sound box over the torso, the hand lower on the pillar (GRIP_AT) so the harp rises to the chest.
The pillar is cut out under the body gump's fist (HOLD_CUT, HOLD_SHOW rows left at the bottom of the fist), so the fist holds it.
Art: the harp lying flat on the ground seen from above (UO draws items top-down with the map turned 45 deg), the pillar along the picture's diagonal, a dark rim round it; the second art is its mirror.
Writes gump_<variant>_<male|female>.png / .bin (Gumpart.mul entries), art.png / art_mirror.png (+ .bin), sheet.png (the gumps over the body gumps) in OUT_DIR.
"""
import json, os, sys
import numpy as np
import bpy
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(globals().get("__file__") or sys.argv[0])); sys.path.insert(0, HERE)
import uo_render_weapon_gump as W
import uo_gump_art as ga
from PIL import Image

PXM, GW, GH, SS = W.PXM, W.GW, W.GH, W.SS
_levels_map = W.levels_map
W.levels_map = lambda y, levels: _levels_map(y, levels) if len(y) else (lambda v: v)      # a harp without strings has no metal pixels: the weapon script's tone() needs at least one
GRIP = W.GRIP
BODY_PNG = {"male": os.path.join(HERE, "..", "docs", "paperdoll", "paperdoll_male_0xc.png"), "female": os.path.join(HERE, "..", "docs", "paperdoll", "paperdoll_female_0xd.png")}
VARIANTS = {"weapon": dict(hand="right", side=-1, yaw=45.0, tilt=-15.0, grip_at=0.5),   # side -1: the sound box to the left of the picture (out); tilt: about the view axis, - = the top to the left
            "play": dict(hand="right", side=+1, yaw=22.0, tilt=+8.0, grip_at=0.38),     # side +1: over the body
            # the same two holds in the other hand (the character's left = the right of the picture), mirrored: side and tilt reversed
            "weapon_left": dict(hand="left", side=+1, yaw=45.0, tilt=+15.0, grip_at=0.5),
            "play_left": dict(hand="left", side=-1, yaw=22.0, tilt=-8.0, grip_at=0.38)}
GRIP_LEFT = {"male": (132.5, 123.5), "female": (131.0, 121.5)}   # the fist of the body gump on the right of the picture (male bbox x 124..138 y 111..130, the fist itself x 131..138 y 119..130)
WOOD = (38.0, 80.0, 124.0)       # gump: output luma at the wood's 10th / 50th / 90th percentile (the client's wooden hafts 17-25 / 42-58 / 65-91: a harp is a large piece, lighter, like the animation's)
ART_WOOD = (52.0, 92.0, 140.0)
STRING_LEVELS = (50.0, 62.0, 76.0)  # the dark grey strings (version with strings)
STRING_MAX = 84                  # no string pixel brighter than this (a few highlights came out at 136); the strings get no darkened edge in the gump (a 1-px line is all edge: it came out at 24, nearly black)
ART_STRING_LEVELS = (56.0, 66.0, 80.0)
ART_YAW = 45.0                   # deg: the pillar of the art along the picture's diagonal (up to the right), the harp's front face up


def canon_of(ob, rig, V):
    """the harp's own frame (X sound box, Y depth, Z pillar, floor of the pillar at z = 0, pillar axis x = y = 0) of the rest-placed vertices: as uo_harp.py placed it"""
    info = json.loads(ob["uo_harp"]); WM = json.loads(bpy.data.texts["weapon_motion.json"].as_string())["weapon1h.R"]
    H = np.array(rig.matrix_world @ rig.data.bones[WM["parent"]].matrix_local)
    piv = (H @ np.append(WM["pivot"], 1.0))[:3]
    z = np.array([0.0, 0.0, 1.0]); fwd = np.array([0.0, -1.0, 0.0])
    R2 = np.array([fwd, np.cross(z, fwd), z]).T                                  # the harp's axes in the rest pose (yaw 0)
    c1 = piv - R2 @ np.array([0.0, 0.0, info["grip"] * info["height"]])
    return (V - c1) @ R2, info


def open_harp(path):
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    rig = bpy.data.objects["UO_Rig"]; rig.data.pose_position = "REST"; rig["uo_direction"] = 0
    bpy.context.view_layer.update()
    ob = next(o for o in bpy.data.collections["Clothing"].all_objects if o.type == "MESH" and not o.hide_render)
    for o in bpy.data.objects:
        if o.type == "MESH" and o is not ob:
            o.hide_render = True
    nv = len(ob.data.vertices); co = np.empty(nv * 3); ob.data.vertices.foreach_get("co", co)
    Mw = np.array(ob.matrix_world); V = co.reshape(-1, 3) @ Mw[:3, :3].T + Mw[:3, 3]
    canon, info = canon_of(ob, rig, V)
    for m in list(ob.modifiers):
        ob.modifiers.remove(m)
    if ob.data.shape_keys:
        ob.shape_key_clear()
    ob.parent = None; ob.matrix_world = Matrix.Identity(4)
    # which pixels are wood (material 0) and which string (material 1): a face attribute read by W.part_pass
    mi = np.array([p.material_index for p in ob.data.polygons], np.float32)
    ob.data.attributes.new("uo_flail_part", "FLOAT", "FACE").data.foreach_set("value", mi)
    return sc, ob, canon, info, bool((mi > 0).any())


def gump_R(side, yaw, tilt):
    """the harp's axes -> world for the front-view gump: pillar up, sound box towards `side` (X of the picture) and turned `yaw` deg towards the viewer (-Y), then tilted about the view axis"""
    g = np.radians(yaw)
    x = np.array([side * np.cos(g), -np.sin(g), 0.0]); z = np.array([0.0, 0.0, 1.0]); y = np.cross(z, x)
    R = np.array([x, y, z]).T
    th = np.radians(tilt)
    Ry = np.array([[np.cos(th), 0, np.sin(th)], [0, 1, 0], [-np.sin(th), 0, np.cos(th)]])
    return Ry @ R


def main(gump_blend, art_blend, out):
    os.makedirs(out, exist_ok=True); tmp = os.path.join(out, "_tmp.png")
    strings_levels = STRING_LEVELS
    # ---------------------------------------------------------------- gumps
    sc, ob, canon, info, has_strings = open_harp(gump_blend)
    cam = W.setup_render(sc)
    H = info["height"]

    def place(P):
        ob.data.vertices.foreach_set("co", P.astype(np.float64).ravel()); ob.data.update()

    res = {}
    for var, v in VARIANTS.items():
        R = gump_R(v["side"], v["yaw"], v["tilt"])
        P = (canon - np.array([0.0, 0.0, v["grip_at"] * H])) @ R.T                # the grip point at the origin
        place(P)
        for gender in GRIP:
            gx, gy = (GRIP_LEFT if v["hand"] == "left" else GRIP)[gender]
            cx = (GW / 2 - gx) / PXM; cz = (gy - GH / 2) / PXM
            a = W.box_down(W.render(sc, cam, tmp, GW * SS, GH * SS, PXM * SS, cx, cz, False), SS)
            pp = W.part_pass(sc, cam, ob, tmp, GW * SS, GH * SS, PXM * SS, cx, cz, False)
            W.PART_GAIN = (1.0, 1.0, 1.0)
            img = W.tone(a, strings_levels, pp, WOOD, W.OUTLINE)
            st = (pp == 1) & (img[..., 3] > 0)
            if st.any():
                flat = W.tone(a, strings_levels, pp, WOOD, 1.0)
                flat[..., :3] = (np.minimum(flat[..., :3], STRING_MAX).astype(np.int32) >> 3) << 3
                img[st] = flat[st]
            body = np.array(Image.open(BODY_PNG[gender]).convert("RGBA"))[..., 3] > 0
            bm = np.zeros((GH, GW), bool); bm[:body.shape[0], :body.shape[1]] = body[:GH, :GW]
            yy, xx = np.mgrid[0:GH, 0:GW]
            win = (np.abs(xx + 0.5 - gx) <= W.HOLD_CUT[0]) & (yy + 0.5 >= gy - W.HOLD_CUT[1]) & (yy + 0.5 <= gy + W.HOLD_CUT[2])
            cut = win & bm & (pp == 0) & (img[..., 3] > 0)
            fist = win & bm
            bottom = np.where(fist.any(0), GH - 1 - np.argmax(fist[::-1], 0), -1)
            cut &= yy <= bottom[None, :] - W.HOLD_SHOW[gender]
            img[cut] = 0
            ys, xs = np.nonzero(img[..., 3])
            print("HG gump %s %s: bbox x %d..%d y %d..%d, %d px, %d px cut under the fist%s" % (var, gender, xs.min(), xs.max(), ys.min(), ys.max(), len(xs), cut.sum(),
                                                                                     "  (!) the left edge of the gump is touched" if xs.min() <= 0 else ""))
            name = "gump_%s_%s" % (var, gender)
            Image.fromarray(img).save(os.path.join(out, name + ".png"))
            data, extra = ga.encode_gump(img); open(os.path.join(out, name + ".bin"), "wb").write(data)
            res[(var, gender)] = img
    # ---------------------------------------------------------------- art
    sc, ob, canon, info, has_strings = open_harp(art_blend)
    cam = W.setup_render(sc)
    d = np.radians(ART_YAW)
    z = np.array([np.cos(d), np.sin(d), 0.0]); yv = np.array([0.0, 0.0, 1.0]); x = np.cross(yv, z)           # X x Y = Z: the sound box to the upper left of the pillar
    R = np.array([x, yv, z]).T
    P = canon @ R.T; P[:, 2] -= P[:, 2].min()
    place_obj = lambda Q: (ob.data.vertices.foreach_set("co", Q.astype(np.float64).ravel()), ob.data.update())
    place_obj(P)
    lo, hi = P[:, :2].min(0), P[:, :2].max(0); c = (lo + hi) / 2
    wpx = int(np.ceil((hi[0] - lo[0]) * W.ART_PXM)) + 3; hpx = int(np.ceil((hi[1] - lo[1]) * W.ART_PXM)) + 3
    w = max(W.ART_W, wpx); h = hpx
    a = W.box_down(W.render(sc, cam, tmp, w * SS, h * SS, W.ART_PXM * SS, c[0], c[1], True), SS)
    pp = W.part_pass(sc, cam, ob, tmp, w * SS, h * SS, W.ART_PXM * SS, c[0], c[1], True)
    art = W.tone(a, ART_STRING_LEVELS, pp, ART_WOOD, W.ART_OUTLINE, W.ART_RIM)
    ys, xs = np.nonzero(art[..., 3]); art = art[ys.min():ys.max() + 1]
    for name, im in (("art", art), ("art_mirror", art[:, ::-1].copy())):
        Image.fromarray(im).save(os.path.join(out, name + ".png")); open(os.path.join(out, name + ".bin"), "wb").write(ga.encode_art(im))
    print("HG art: %d x %d px (the item %d x %d)" % (art.shape[1], art.shape[0], xs.max() - xs.min() + 1, ys.max() - ys.min() + 1))
    # ---------------------------------------------------------------- sheet: the gumps over the body gumps
    tiles = []
    for gender in GRIP:
        for var in VARIANTS:
            bg = Image.open(BODY_PNG[gender]).convert("RGBA"); base = Image.new("RGBA", (GW, GH), (70, 82, 70, 255))
            base.alpha_composite(bg.crop((0, 0, GW, GH))); base.alpha_composite(Image.fromarray(res[(var, gender)]))
            tiles.append(base.resize((GW * 3, GH * 3), Image.NEAREST).convert("RGB"))
    nv = len(VARIANTS); sheet = Image.new("RGB", (GW * 3 * nv, GH * 3 * len(GRIP))); [sheet.paste(t, ((i % nv) * GW * 3, (i // nv) * GH * 3)) for i, t in enumerate(tiles)]
    sheet.save(os.path.join(out, "sheet.png"))
    if os.path.exists(tmp):
        os.remove(tmp)


if __name__ == "__main__":
    a = sys.argv[1:]; pos = []; i = 0
    while i < len(a):
        if a[i] == "--set":
            k, v = a[i + 1].split("=", 1); g = globals()
            g[k] = eval(v) if isinstance(g[k], (tuple, dict)) else type(g[k])(v); i += 2
        else:
            pos.append(a[i]); i += 1
    main(pos[0], pos[1], pos[2])
    sys.stdout.flush(); os._exit(0)
