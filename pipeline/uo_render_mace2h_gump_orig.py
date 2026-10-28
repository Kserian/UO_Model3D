"""Paperdoll gumps and item art of the two-handed spiked mace made from the ORIGINAL model (the .glb: its full mesh, its own textures and spikes), not from the UO item of the animation
(decimated, brightened, longer spikes).

    python uo_render_mace2h_gump_orig.py MODEL.glb OUT_DIR [--set NAME=VALUE ...]

Same pictures as uo_render_mace2h_gump.py (gump 260 x 237, 90.5 px/m, the fist of body gump 12 / 13, variants down = the ball on the floor at the feet and up = the fist at the middle of the weapon,
art on the ground seen from above), but the model is imported from the .glb, scaled so that it is LENGTH m long (butt to the tips of the spikes), turned (shaft along the axis, ball up), and
rendered with its own PBR materials (Cycles, a sun from the upper left like the UO light, a soft world light, EXPOSURE) at SS x the resolution, then averaged down (alpha: opaque from 50 %),
a dark outline (from the neighbouring colours, not black) and the 15-bit colours of the client. The spikes may be enlarged for the gump (SPIKE_LEN, SPIKE_WIDTH, 1 = the original). Writes the same files as the other script (gump_*_{down,up}.png/.bin,
*_hd.png, *_preview.png, art.png, art_mirror.png).
"""
import os, sys
import numpy as np
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import uo_render_mace2h_gump as G
import uo_render_weapon_gump as W
import uo_gump_art as ga

LENGTH = 1.35                # m: the whole weapon, butt to the tips of the spikes (as the animation's item)
SS = 4                       # gump: rendered SS x larger and averaged down
SAMPLES = 48                 # Cycles samples per pixel
EXPOSURE = 0.2               # the glb's textures are dark (the item of the animation multiplies them x 2.1)
CONTRAST = 1.3               # the render's contrast about the middle grey, a little more than the render: the pictures of the client are crisp
SUN = 3.2                    # strength of the sun (from the upper left, in front: the UO light), WORLD = the soft light from everywhere
WORLD = 0.9
SPIKE_LEN = 0.9              # the spikes' length x this (1 = the original) and
SPIKE_WIDTH = 1.55           # their width x this: the original's are tiny at 90 px/m
ROLL = 25.0                  # deg: the weapon turned about its axis (the 12 spikes are at 45 deg steps: one at the camera and down hid in front of the ball's collar)
OUTLINE = 0.75               # the edge pixels (next to transparency): the mean colour of their inner neighbours x this
RIM = 0.45                   # art: the ring outside the item: the mean colour of the neighbouring pixels x this
WOOD_COLOR = (0.36, 0.23, 0.13)   # sRGB: the wood of the original's texture recoloured to the one brown of the game's .vd (pipeline/uo_mace2h_retexture.py WOOD_COLOR), so that the haft has the same colour in the gump, the art and the game
WOOD_GRAIN = 0.25            # the grain (light / dark texels) of the original's wood kept: exponent of the texel / the median of the wood
ART_WOOD_GAIN = 1.2          # the art is lit from above by the same sun, its wood came out darker (80 against 97 of the .vd): a little more
WOOD_GAIN = 1.0              # x on WOOD_COLOR: the gump's light is not the game's (the mean wood colour of the gump is matched to the .vd's)
HD_SCALE = 4                 # the large weapon-only pictures (gump_*_hd.png) at this x the gump's resolution (0 = none)


def setup(sc):
    sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = SAMPLES; sc.cycles.use_denoising = False
    sc.cycles.pixel_filter_type = "BOX"; sc.cycles.filter_width = 0.01; sc.render.dither_intensity = 0.0
    sc.render.film_transparent = True; sc.view_settings.view_transform = "Standard"; sc.view_settings.exposure = EXPOSURE
    sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGBA"; sc.render.resolution_percentage = 100
    sc["uo_look"] = 1.0
    sc.cycles.max_bounces = 6; sc.cycles.diffuse_bounces = 2; sc.cycles.glossy_bounces = 4
    wd = bpy.data.worlds.new("WG_World"); wd.use_nodes = True; sc.world = wd
    bg = wd.node_tree.nodes["Background"]; bg.inputs[0].default_value = (0.85, 0.87, 0.9, 1.0); bg.inputs[1].default_value = WORLD
    ld = bpy.data.lights.new("WG_Sun", "SUN"); ld.energy = SUN; ld.angle = 0.05
    sun = bpy.data.objects.new("WG_Sun", ld); sc.collection.objects.link(sun)
    travel = Vector((0.55, 0.45, -0.7)).normalized()                      # the light travels to the right (+X), away from the camera (+Y) and down: it comes from the upper left, in front
    sun.rotation_euler = Vector((0, 0, -1)).rotation_difference(travel).to_euler()
    cd = bpy.data.cameras.new("WG_Camera"); cd.type = "ORTHO"; cd.sensor_fit = "HORIZONTAL"
    cam = bpy.data.objects.new("WG_Camera", cd); sc.collection.objects.link(cam); sc.camera = cam
    return cam


def neigh_mean(rgb, ok):
    """mean colour of the 8 neighbours where ok (and how many there are)"""
    H, Wd = ok.shape; acc = np.zeros(rgb.shape); n = np.zeros((H, Wd))
    po = np.pad(ok, 1); pr = np.pad(rgb, ((1, 1), (1, 1), (0, 0)))
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy or dx:
                o = po[1 + dy:1 + dy + H, 1 + dx:1 + dx + Wd]
                acc += pr[1 + dy:1 + dy + H, 1 + dx:1 + dx + Wd] * o[..., None]; n += o
    return acc / np.maximum(n, 1)[..., None], n


def grade(a, outline=OUTLINE, rim=None):
    """float RGBA (display values) -> uint8 RGBA: contrast about the mid grey, an outline darkened from the colours of the neighbouring pixels (never black), the client's 15-bit colours;
    rim: art only, one more ring of pixels outside the item, from the colours of its edge pixels"""
    m = a[..., 3] > 0
    rgb = (a[..., :3] * 255.0 - 128.0) * CONTRAST + 128.0
    rgb = np.where(m[..., None], rgb, 0.0)
    if outline < 1:
        pad = np.pad(m, 1)
        edge = m & ~(pad[:-2, 1:-1] & pad[2:, 1:-1] & pad[1:-1, :-2] & pad[1:-1, 2:])
        nm, n = neigh_mean(rgb, m & ~edge)
        rgb[edge] = np.where((n > 0)[edge, None], nm[edge], rgb[edge]) * outline
    out = np.zeros(a.shape[:2] + (4,), np.uint8)
    out[..., :3] = np.where(m[..., None], (np.clip(np.round(rgb), 8, 255).astype(np.int32) >> 3) << 3, 0); out[..., 3] = np.where(m, 255, 0)
    if rim is not None:
        pad = np.pad(m, 1)
        ring = ~m & (pad[:-2, 1:-1] | pad[2:, 1:-1] | pad[1:-1, :-2] | pad[1:-1, 2:])
        nm, n = neigh_mean(rgb, m)
        out[ring, :3] = (np.clip(np.round(nm[ring] * rim), 8, 255).astype(np.int32) >> 3) << 3; out[ring, 3] = 255
    return out


_ORIG = {}


def recolour_wood(gain=None):
    """the texels of the base colour map that are not metal (the metal map: blue channel of the metallic-roughness image) get one wood brown with the original's grain; the steel is left"""
    base, mr = bpy.data.images.get("Image_0"), bpy.data.images.get("Image_1")
    if base is None or mr is None:
        print("OG: no Image_0 / Image_1 in the glb, the wood is not recoloured"); return
    w, h = base.size
    if "b" not in _ORIG:
        _ORIG["b"] = np.array(base.pixels[:], np.float32).reshape(h, w, 4); _ORIG["m"] = np.array(mr.pixels[:], np.float32).reshape(h, w, 4)[..., 2] > 0.5
    b = _ORIG["b"].copy(); m = _ORIG["m"]
    gain = WOOD_GAIN if gain is None else gain
    luma = b[..., :3].mean(2); med = float(np.median(luma[~m]))
    wood = np.clip(np.array(WOOD_COLOR, np.float32)[None, None, :] * gain * (np.clip(luma, 0.03, None) / med)[..., None] ** WOOD_GRAIN, 0, 1)
    b[..., :3] = np.where(m[..., None], b[..., :3], wood)
    base.pixels.foreach_set(b.reshape(-1)); base.update()
    print("OG: wood recoloured, %.0f %% of the texels" % (100.0 * (~m).mean()))


def main(src, out):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    bpy.ops.import_scene.gltf(filepath=os.path.abspath(src))
    recolour_wood()
    objs = [o for o in sc.objects if o.type == "MESH"]
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    nv = len(ob.data.vertices)
    co = np.empty(nv * 3); ob.data.vertices.foreach_get("co", co); V = co.reshape(-1, 3)
    c = V.mean(0); _, _, vt = np.linalg.svd(V - c, full_matrices=False); t = (V - c) @ vt[0]
    V = c + (V - c) * (LENGTH / float(t.max() - t.min()))                       # the weapon LENGTH m long
    hd, butt, s, bb = G.axis_of(V, None)
    rad = np.linalg.norm((V - butt) - np.outer(s, hd), axis=1)
    mx = np.zeros(int(s.max() / 0.01) + 2); np.maximum.at(mx, (s / 0.01).astype(int), rad)       # the thickest vertex per cm of the weapon
    bb = float(np.nonzero((mx > 0.045) & (np.arange(len(mx)) * 0.01 > 0.5))[0][0]) * 0.01        # the ball: the first thick cm beyond the half (the pommel at the butt is thick too)
    print("OG: %d vertices, weapon %.3f m, ball from %.3f m, axis %s" % (nv, s.max(), bb, np.round(hd, 3).tolist()))
    ball = s >= bb - 0.005
    if SPIKE_LEN != 1.0 or SPIKE_WIDTH != 1.0:                                    # the spikes of the original are tiny and thin at 90 px/m: each one longer and wider about its own axis
        shell = ball & (rad > 0.07) & (rad < 0.115) & (s < bb + 0.25)
        rb = float(np.median(rad[shell])) if shell.any() else 0.1
        cb = butt + hd * float(s[shell].mean() if shell.any() else bb + rb)
        dv = V - cb; dist = np.linalg.norm(dv, axis=1); u = dv / np.maximum(dist, 1e-9)[:, None]
        axes = []
        for i in np.nonzero(ball & (dist > rb * 1.5))[0][np.argsort(-dist[ball & (dist > rb * 1.5)])]:
            if not any(float(u[i] @ ax) > 0.95 for ax in axes):
                axes.append(u[i].copy())
        A = np.array(axes) if axes else np.zeros((0, 3))
        print("OG: %d spikes found, rb %.3f, tip distance from the ball centre %s" % (len(A), rb, np.round(np.sort(dist[ball & (dist > rb * 1.5)])[-5:], 3).tolist()))
        if len(A):
            cs = u @ A.T; k = cs.argmax(1); near = cs.max(1) > 0.93
            near &= (A[k] @ hd) > -0.9                                         # not the collar where the ball meets the haft (3 stubs along the haft: widened they were a dark blob over the haft)
            msk = ball & near & (dist > rb)
            w = np.clip((dist[msk] - rb) / (0.3 * rb), 0, 1)
            ax = A[k[msk]]; along = (dv[msk] * ax).sum(1); perp = dv[msk] - along[:, None] * ax
            V[msk] = cb + ax * (along * (1 + (SPIKE_LEN - 1) * w))[:, None] + perp * (1 + (SPIKE_WIDTH - 1) * w)[:, None]
    if ROLL:                                                                      # the weapon turned about its own axis: a spike no longer points at the camera and down onto the haft
        r = np.radians(ROLL); R3 = np.array(Vector(hd.tolist()).rotation_difference(Vector((0, 0, 1))).to_matrix())
        K = np.array([[0, -hd[2], hd[1]], [hd[2], 0, -hd[0]], [-hd[1], hd[0], 0]]); Rr = np.eye(3) + np.sin(r) * K + (1 - np.cos(r)) * (K @ K)
        V = butt + (V - butt) @ Rr.T
    part = np.where(ball, 2, 0).astype(np.int32)
    at = ob.data.attributes.get("uo_flail_part") or ob.data.attributes.new("uo_flail_part", "FLOAT", "POINT")
    at.data.foreach_set("value", part.astype(np.float32))
    cam = setup(sc)
    W.SS = SS
    from PIL import Image
    os.makedirs(out, exist_ok=True); tmp = os.path.join(out, "_tmp.png")

    def place(P):
        ob.data.vertices.foreach_set("co", P.astype(np.float64).ravel()); ob.data.update()

    def put(gender, name, Vp, gx, gy):
        cx = (W.GW / 2 - gx) / W.PXM; cz = (gy - W.GH / 2) / W.PXM
        place(Vp)
        a = W.box_down(W.render(sc, cam, tmp, W.GW * SS, W.GH * SS, W.PXM * SS, cx, cz, False), SS)
        pp = W.part_pass(sc, cam, ob, tmp, W.GW * SS, W.GH * SS, W.PXM * SS, cx, cz, False)
        img = grade(a)
        try:
            bodyg = ga.read_gump(W.CLIENT, W.BODY[gender])
        except OSError:
            bodyg = None
        if bodyg is not None:                                                  # the haft behind the fist: the body gump's fist shows through
            bm = np.zeros((W.GH, W.GW), bool); h_, w_ = min(W.GH, bodyg.shape[0]), min(W.GW, bodyg.shape[1]); bm[:h_, :w_] = bodyg[:h_, :w_, 3] > 0
            yy, xx = np.mgrid[0:W.GH, 0:W.GW]
            win = (np.abs(xx + 0.5 - gx) <= G.HOLD_CUT[0]) & (yy + 0.5 >= gy - G.HOLD_CUT[1]) & (yy + 0.5 <= gy + G.HOLD_CUT[2])
            cut = win & bm & (pp == 0) & (img[..., 3] > 0)
            fist = win & bm
            bottom = np.where(fist.any(0), W.GH - 1 - np.argmax(fist[::-1], 0), -1)
            cut &= yy <= bottom[None, :] - G.HOLD_SHOW[gender]
            img[cut] = 0
            prev = Image.fromarray(bodyg).convert("RGBA"); prev.alpha_composite(Image.fromarray(img))
            bg = Image.new("RGBA", prev.size, (70, 70, 70, 255)); bg.alpha_composite(prev)
            bg.resize((bg.width * 2, bg.height * 2), Image.NEAREST).save(os.path.join(out, "%s_preview.png" % name))
        Image.fromarray(img).save(os.path.join(out, name + ".png"))
        if HD_SCALE:
            k = HD_SCALE; W.SS = 2
            a2 = W.box_down(W.render(sc, cam, tmp, W.GW * k * 2, W.GH * k * 2, W.PXM * k * 2, cx, cz, False), 2)
            Image.fromarray(grade(a2, 0.6)).save(os.path.join(out, name + "_hd.png")); W.SS = SS
        data, extra = ga.encode_gump(img)
        open(os.path.join(out, name + ".bin"), "wb").write(data)
        ys, xs = np.nonzero(img[..., 3]); print("OG %s: bbox x %d..%d y %d..%d, %d px" % (name, xs.min(), xs.max(), ys.min(), ys.max(), len(xs)))

    for gender, (gx, gy) in G.GRIP.items():
        Hf = (G.GY_FEET - gy) / W.PXM
        th = np.radians(G.TILT_DOWN); d_down = (-np.sin(th), 0.0, -np.cos(th))
        R = np.array(Vector(hd.tolist()).rotation_difference(Vector(list(d_down))).to_matrix())
        low = -float(((V - butt) @ R.T)[:, 2].min())                              # the lowest tip below the butt
        s_g = (low - Hf - G.BALL_FLOOR) / np.cos(th)
        put(gender, "gump_%s_down" % gender, G.pose(V, butt, hd, s_g, d_down), gx, gy)
        print("OG %s down: grip %.2f m above the butt, butt %.2f m over the fist" % (gender, s_g, s_g * np.cos(th)))
        th = np.radians(G.TILT_UP); d_up = (-np.sin(th), 0.0, np.cos(th))
        put(gender, "gump_%s_up" % gender, G.pose(V, butt, hd, float(s.max()) / 2, d_up), gx, gy)

    recolour_wood(ART_WOOD_GAIN)
    d45 = (np.sqrt(0.5), np.sqrt(0.5), 0.0)
    Va, _ = G.stretch_shaft(V, hd, s, bb, G.ART_STRETCH)
    R = np.array(Vector(hd.tolist()).rotation_difference(Vector(d45)).to_matrix())
    P = (Va - butt) @ R.T; P[:, 2] -= P[:, 2].min()
    place(P)
    lo, hi = P[:, :2].min(0), P[:, :2].max(0); cc = (lo + hi) / 2
    w = max(W.ART_W, int(np.ceil((hi[0] - lo[0]) * W.ART_PXM)) + 3); h = int(np.ceil((hi[1] - lo[1]) * W.ART_PXM)) + 3
    W.SS = SS
    a = W.box_down(W.render(sc, cam, tmp, w * SS, h * SS, W.ART_PXM * SS, cc[0], cc[1], True), SS)
    art = grade(a, OUTLINE, RIM)
    ys, xs = np.nonzero(art[..., 3]); art = art[ys.min():ys.max() + 1]
    for name, im in (("art", art), ("art_mirror", art[:, ::-1].copy())):
        Image.fromarray(im).save(os.path.join(out, name + ".png"))
        open(os.path.join(out, name + ".bin"), "wb").write(ga.encode_art(im))
    print("OG art: %d x %d" % (art.shape[1], art.shape[0]))
    if os.path.exists(tmp):
        os.remove(tmp)


if __name__ == "__main__":
    a = sys.argv[1:]; pos = []; i = 0
    while i < len(a):
        if a[i] == "--set":
            k, v = a[i + 1].split("=", 1); g = globals()
            g[k] = type(g[k])(v); i += 2
        else:
            pos.append(a[i]); i += 1
    main(pos[0], pos[1])
