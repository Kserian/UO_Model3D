"""Paperdoll gumps and item art of a RIGID two-handed spiked mace (ITEM.blend from uo_make_item.py with "weapon": part polearm), the same 3D model as its animation.

    python uo_render_mace2h_gump.py ITEM.blend OUT_DIR [--set NAME=VALUE ...]

Like uo_render_weapon_gump.py (flails): gump 260 x 237 px, front view, orthographic, 90.5 px/m (body gump 12 / 13: head top y 54 .. feet y 221 = 1.855 m), the weapon in the
character's right hand (the left of the picture, x 48) at the fist of the body gump (male y 114.5, female y 113), the wood cut out under the body gump's fist so that the fist holds
it. Two variants, each for the male and the female body gump:
  down  the ball DOWN, resting on the floor at the height of the feet (y 221), the haft upright (leaning TILT_DOWN deg, the ball out) with its butt sticking BUTT_ABOVE m out over the fist
        (a mace of 1.35 m would end under the fist of a standing body: the shaft between the knob and the ball is stretched, the knob and the ball keep their size);
  up    the ball UP, the fist at the middle of the whole weapon (butt to the tips of the spikes), the haft leaning TILT_UP deg (the ball out).
Art (item icon, art.mul): the weapon lying on the ground seen from above (UO draws items top-down with the map turned 45 deg), the haft along the picture's diagonal (butt bottom left),
a dark rim around, ART_PXM px/m; the second art is its mirror (the client's weapons come in pairs). Colours as the flail script: metal grey only, the wooden haft brown (WOOD_TINT).
Writes gump_{male,female}_{down,up}.png (+ .bin = the Gumpart entry), art.png, art_mirror.png (+ .bin), and *_preview.png (the gump over the client's body gump).
Needs the client's Gumpart.mul / Gumpidx.mul in ../uo_client/NelderimServUO (never committed).
"""
import json, os, sys
import numpy as np
import bpy
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import uo_render_weapon_gump as W
import uo_gump_art as ga

TILT_DOWN = 4.0              # deg: the haft of the 'down' gump leans, the ball (at the floor) out from the body
TILT_UP = 8.0                # deg: the haft of the 'up' gump leans, the ball out
BUTT_ABOVE = 0.12            # m: the butt of the 'down' gump sticks out over the fist
KNOB = 0.09                  # m: the knob at the butt keeps its length when the shaft is stretched
BALL_FLOOR = 0.0             # m: the lowest tip of the ball above the floor line of the 'down' gump
THIN_HAFT = 0.75             # the haft's cross-section scaled about the axis (the animation needs a thick haft: 7.5 cm = 2.7 px at 36 px/m, the gump is 2.5 x larger: 6.8 px; the client's maces 3-5 px)
SS_GUMP = 6                  # supersampling of the gump (the flail script: 3): rendered 6 x larger and averaged down, so that the shading of the spikes survives the reduction
SPIKE_SCALE = 0.7            # gump / art: the spikes' length beyond the ball's surface x this (the animation's spikes are long to read at 36 px/m; at 90 px/m they are too big)
METAL_CONTRAST = 1.9         # the metal (ball, spikes): the grey's deviation from its local 5 x 5 px mean x this, so that every spike shows a lit and a dark side
METAL_LEVELS = (22.0, 100.0, 205.0)   # metal: output grey at the 10th / 50th / 90th percentile (the flail script: 48 / 105 / 165)
HD_SCALE = 4                 # the large weapon-only gump (gump_*_hd.png): rendered at HD_SCALE x the gump's resolution, not quantized to the client's palette (0 = none)
ART_STRETCH = 1.2            # art: the shaft x this (as HAFT_LEN of the flail art)
HOLD_CUT = (8, 9, 6)         # as uo_render_weapon_gump.py: the window of the fist around the grip, the wood is cut where the body gump's fist lies in it
HOLD_SHOW = {"male": 2, "female": 3}
GY_FEET = 221.0
GRIP = W.GRIP


def axis_of(V, head):
    """the shaft's unit direction butt -> ball (PCA of the vertices, the ball end = the end with more vertices), distances s from the butt, and the ball's bottom / top in s"""
    c = V.mean(0); u, sv, vt = np.linalg.svd(V - c, full_matrices=False); v = vt[0]
    t = (V - c) @ v
    if (t > t.max() - 0.25).sum() < (t < t.min() + 0.25).sum():
        v = -v; t = -t
    s = t - t.min()
    butt = c + v * t.min()
    if head is not None and abs(float(s.max()) - float(head[3])) < 0.05:
        bb = float(head[2])
    else:
        rad = np.linalg.norm((V - c) - np.outer(t, v), axis=1)
        bb = float(s[rad > 0.05].min())
    return v, butt, s, bb


def stretch_shaft(V, hd, s, bb, k):
    """the shaft between the knob and the ball's bottom x k along the axis (the knob and the ball move, not grow); returns the vertices and the new s of the ball's bottom"""
    s0 = KNOB
    s2 = np.where(s <= s0, s, np.where(s <= bb, s0 + (s - s0) * k, s + (k - 1) * (bb - s0)))
    return V + np.outer(s2 - s, hd), s0 + (bb - s0) * k


def pose(V, butt, hd, s_grip, d_w):
    """vertices with the grip (on the axis, s_grip from the butt) at the origin and the axis turned to d_w"""
    R = np.array(Vector(hd.tolist()).rotation_difference(Vector(list(d_w))).to_matrix())
    G = butt + hd * s_grip
    return (V - G) @ R.T


def shade_metal(img, pp):
    """the metal's grey: the deviation from its 5 x 5 local mean x METAL_CONTRAST (a lit and a dark side on every spike); the haft's wood and the dark rim are left as they are"""
    m = (pp == 2) & (img[..., 3] > 0)
    if METAL_CONTRAST == 1.0 or m.sum() < 10:
        return img
    y = img[..., 0].astype(np.float32); w = m.astype(np.float32)
    k = 2; pad_y = np.pad(y * w, k); pad_w = np.pad(w, k)
    sy = sum(pad_y[i:i + y.shape[0], j:j + y.shape[1]] for i in range(2 * k + 1) for j in range(2 * k + 1))
    sw = sum(pad_w[i:i + y.shape[0], j:j + y.shape[1]] for i in range(2 * k + 1) for j in range(2 * k + 1))
    mean = sy / np.maximum(sw, 1e-6)
    out = np.clip(mean + METAL_CONTRAST * (y - mean), 10, 230)
    q = ((np.round(out).astype(np.int32)) >> 3) << 3
    res = img.copy()
    for c in range(3):
        res[..., c] = np.where(m, np.clip(q, 8, 255), res[..., c])
    return res


def main(src, out):
    bpy.ops.wm.open_mainfile(filepath=src)
    sc = bpy.context.scene
    rig = bpy.data.objects["UO_Rig"]; rig.data.pose_position = "REST"; rig["uo_direction"] = 0
    bpy.context.view_layer.update()
    ob = next(o for o in bpy.data.collections["Clothing"].all_objects if o.type == "MESH" and not o.hide_render)
    for o in bpy.data.objects:
        if o.type == "MESH" and o is not ob:
            o.hide_render = True
    nv = len(ob.data.vertices)
    co = np.empty(nv * 3); ob.data.vertices.foreach_get("co", co)
    Mw = np.array(ob.matrix_world); V = co.reshape(-1, 3) @ Mw[:3, :3].T + Mw[:3, 3]
    head = ob.get("uo_head")
    hd, butt, s, bb = axis_of(V, head)
    for m in list(ob.modifiers):
        ob.modifiers.remove(m)
    if ob.data.shape_keys:
        ob.shape_key_clear()
    ob.parent = None; ob.matrix_world = Matrix.Identity(4)
    rad_v = (V - butt) - np.outer(s, hd)
    V = np.where((s < bb - 0.005)[:, None], butt + np.outer(s, hd) + rad_v * THIN_HAFT, V)
    if head is not None and SPIKE_SCALE != 1.0:                                  # the spikes shorter: the ball's vertices beyond its radius pulled towards its centre
        cb = butt + hd * float(head[0]); rb = float(head[1])
        dv = V - cb; dist = np.linalg.norm(dv, axis=1)
        msk = (s >= bb - 0.005) & (dist > rb)
        V[msk] = cb + dv[msk] / dist[msk, None] * (rb + (dist[msk] - rb) * SPIKE_SCALE)[:, None]
    part = np.where(s < bb - 0.005, 0, 2).astype(np.int32)                      # 0 = the haft (wood), 2 = the ball and the spikes (metal)
    at = ob.data.attributes.get("uo_flail_part") or ob.data.attributes.new("uo_flail_part", "FLOAT", "POINT")
    at.data.foreach_set("value", part.astype(np.float32))
    print("MG: weapon %.3f m, ball from %.3f m (butt = 0), axis %s" % (s.max(), bb, np.round(hd, 3).tolist()))
    W.SS = SS_GUMP; W.LEVELS = METAL_LEVELS
    cam = W.setup_render(sc)
    from PIL import Image
    os.makedirs(out, exist_ok=True); tmp = os.path.join(out, "_tmp.png")

    def place(P):
        ob.data.vertices.foreach_set("co", P.astype(np.float64).ravel()); ob.data.update()

    def put(img_dir, gender, name, Vp, gx, gy):
        cx = (W.GW / 2 - gx) / W.PXM; cz = (gy - W.GH / 2) / W.PXM
        place(Vp)
        a = W.box_down(W.render(sc, cam, tmp, W.GW * W.SS, W.GH * W.SS, W.PXM * W.SS, cx, cz, False), W.SS)
        pp = W.part_pass(sc, cam, ob, tmp, W.GW * W.SS, W.GH * W.SS, W.PXM * W.SS, cx, cz, False)
        img = W.tone(a, W.LEVELS, pp, W.WOOD_LEVELS)
        img = shade_metal(img, pp)
        try:
            bodyg = ga.read_gump(W.CLIENT, W.BODY[gender])
        except OSError:
            bodyg = None
        if bodyg is not None:
            bm = np.zeros((W.GH, W.GW), bool); h_, w_ = min(W.GH, bodyg.shape[0]), min(W.GW, bodyg.shape[1]); bm[:h_, :w_] = bodyg[:h_, :w_, 3] > 0
            yy, xx = np.mgrid[0:W.GH, 0:W.GW]
            win = (np.abs(xx + 0.5 - gx) <= HOLD_CUT[0]) & (yy + 0.5 >= gy - HOLD_CUT[1]) & (yy + 0.5 <= gy + HOLD_CUT[2])
            cut = win & bm & (pp == 0) & (img[..., 3] > 0)
            hs = HOLD_SHOW[gender]
            fist = win & bm
            bottom = np.where(fist.any(0), W.GH - 1 - np.argmax(fist[::-1], 0), -1)
            cut &= yy <= bottom[None, :] - hs
            img[cut] = 0
            prev = Image.fromarray(bodyg).convert("RGBA"); prev.alpha_composite(Image.fromarray(img))
            bg = Image.new("RGBA", prev.size, (70, 70, 70, 255)); bg.alpha_composite(prev)
            bg.resize((bg.width * 2, bg.height * 2), Image.NEAREST).save(os.path.join(out, "%s_preview.png" % name))
        Image.fromarray(img).save(os.path.join(out, name + ".png"))
        if HD_SCALE:                                                          # the large weapon-only picture (no body gump: the fist is not cut)
            ss0, k = W.SS, HD_SCALE; W.SS = 2
            a2 = W.box_down(W.render(sc, cam, tmp, W.GW * k * 2, W.GH * k * 2, W.PXM * k * 2, cx, cz, False), 2)
            pp2 = W.part_pass(sc, cam, ob, tmp, W.GW * k * 2, W.GH * k * 2, W.PXM * k * 2, cx, cz, False)
            Image.fromarray(shade_metal(W.tone(a2, W.LEVELS, pp2, W.WOOD_LEVELS, 0.6), pp2)).save(os.path.join(out, name + "_hd.png"))
            W.SS = ss0
        data, extra = ga.encode_gump(img)
        open(os.path.join(out, name + ".bin"), "wb").write(data)
        ys, xs = np.nonzero(img[..., 3]); print("MG %s: bbox x %d..%d y %d..%d, %d px, extra %08x" % (name, xs.min(), xs.max(), ys.min(), ys.max(), len(xs), extra))

    for gender, (gx, gy) in GRIP.items():
        Hf = (GY_FEET - gy) / W.PXM                                          # the fist's height above the floor line
        # down: the lowest tip of the ball (a spike) at the floor, the grip on the axis at the fist's height, the butt BUTT_ABOVE over the fist
        th = np.radians(TILT_DOWN); d_down = (-np.sin(th), 0.0, -np.cos(th))
        R = np.array(Vector(hd.tolist()).rotation_difference(Vector(list(d_down))).to_matrix())

        def depth(k):                                                         # how far below the butt the lowest vertex lies when the shaft is stretched x k
            Vs_, _ = stretch_shaft(V, hd, s, bb, k)
            return -float(((Vs_ - butt) @ R.T)[:, 2].min())
        lo_k, hi_k = 1.0, 3.0
        for _ in range(40):
            mid = (lo_k + hi_k) / 2
            if depth(mid) < Hf + BUTT_ABOVE + BALL_FLOOR:
                lo_k = mid
            else:
                hi_k = mid
        k = max(1.0, hi_k)
        Vs, bb2 = stretch_shaft(V, hd, s, bb, k)
        low = -float(((Vs - butt) @ R.T)[:, 2].min())                         # the lowest tip below the butt
        s_g = (low - Hf - BALL_FLOOR) / np.cos(th)                            # the grip's distance from the butt along the axis (grip z = -s_g cos(th) from the butt)
        put(out, gender, "gump_%s_down" % gender, pose(Vs, butt, hd, s_g, d_down), gx, gy)
        print("MG %s down: shaft x %.2f, fist %.2f m above the floor, grip %.2f m above the butt" % (gender, k, Hf, s_g))
        # up: the fist at the middle of the whole weapon
        th = np.radians(TILT_UP); d_up = (-np.sin(th), 0.0, np.cos(th))
        put(out, gender, "gump_%s_up" % gender, pose(V, butt, hd, float(s.max()) / 2, d_up), gx, gy)

    # art: lying on the ground (z up), seen from above; the shaft stretched, the butt at the bottom left of the picture's diagonal
    d45 = (np.sqrt(0.5), np.sqrt(0.5), 0.0)
    Va, bba = stretch_shaft(V, hd, s, bb, ART_STRETCH)
    R = np.array(Vector(hd.tolist()).rotation_difference(Vector(d45)).to_matrix())
    P = (Va - butt) @ R.T
    P[:, 2] -= P[:, 2].min()
    place(P)
    lo, hi = P[:, :2].min(0), P[:, :2].max(0); c = (lo + hi) / 2
    w = max(W.ART_W, int(np.ceil((hi[0] - lo[0]) * W.ART_PXM)) + 3); h = int(np.ceil((hi[1] - lo[1]) * W.ART_PXM)) + 3
    a = W.box_down(W.render(sc, cam, tmp, w * W.SS, h * W.SS, W.ART_PXM * W.SS, c[0], c[1], True), W.SS)
    pp = W.part_pass(sc, cam, ob, tmp, w * W.SS, h * W.SS, W.ART_PXM * W.SS, c[0], c[1], True)
    art = W.tone(a, W.ART_LEVELS, pp, W.ART_WOOD_LEVELS, W.ART_OUTLINE, W.ART_RIM)
    ys, xs = np.nonzero(art[..., 3]); art = art[ys.min():ys.max() + 1]
    for name, im in (("art", art), ("art_mirror", art[:, ::-1].copy())):
        Image.fromarray(im).save(os.path.join(out, name + ".png"))
        open(os.path.join(out, name + ".bin"), "wb").write(ga.encode_art(im))
    print("MG art: %d x %d" % (art.shape[1], art.shape[0]))
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
    main(pos[0], pos[1])
