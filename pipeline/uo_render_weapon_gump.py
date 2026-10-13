"""Paperdoll gumps (male 50000 + AnimID on body gump 12, female 60000 + AnimID on body gump 13) and item art (art.mul, two IDs: the second one mirrored)
of a one-handed weapon, rendered from the same 3D model as its animation (ITEM.blend from uo_make_item.py; a flail from uo_flail.py has its chain posed here).

    python uo_render_weapon_gump.py ITEM.blend OUT_DIR [--set NAME=VALUE ...]

Gump: front view, orthographic, 90.5 px/m (body gump 12: head top y 54 .. feet y 221 = 1.855 m), the haft upright in the right hand (on the left of the picture) like the
client's own weapon gumps: the grip on the haft line of mace / war mace / maul (gumps 50631 / 50642 / 50633: x 47.5) at the middle of the fist (male y 114; the fist of
the female body 13 is ~1.5 px higher). The weapon leans TILT out from the body; a flail's chain hangs free (straight down) from the top of the haft, the ball beside the haft above the fist.
The haft is cut out under the body gump's fist except its bottom rows (HOLD_CUT, HOLD_SHOW), so the fist holds it. The weapon gumps of the client have no female version (60000 + AnimID does not exist, the client uses the male one).
Art: the weapon lying on the ground seen from above (UO draws items top-down with the map turned 45 deg), the haft along the picture's diagonal (butt bottom left), the
chain turning ART_CURL from its line, a dark rim around (ART_RIM); the second art is its mirror (the client's weapons come in pairs: mace 0xF5C / 0xF5D).
Colours: the metal (chain, ball, grey fittings) grey only (R = G = B), the wooden haft brown like the client's wooden hafts (WOOD_TINT, WOOD_LEVELS). The client dyes
an item by indexing the hue's 32 colours with each pixel's red channel (all pixels; with the tiledata flag PartialHue 0x00040000 only the grey ones): grey metal takes
the hue by its level, the wood stays wood with PartialHue (uo_hue_preview.py shows both; the animation's metal: uo_grey_metal.py). Gump edge pixels darkened by OUTLINE.
Writes gump_male.png, gump_female.png, art.png, art_mirror.png (RGBA) and the mul entries *.bin (uo_gump_art.py).
Light, materials: UO_Look as render_uo_layer.py, 1 sample per pixel; SS x SS supersampling box-averaged.
"""
import json, os, sys
import numpy as np
import bpy
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
PXM = 90.5                     # gump px per m (body gump 12)
GW, GH = 260, 237
GRIP = {"male": (48.0, 114.5), "female": (48.0, 113.0)}   # gump pixel (continuous, pixel i spans i..i+1) of the grip: the haft line of the client's maces, the middle of the fist
SS = 3
ROLL = 0.0                     # deg: the weapon turned about its haft (which side faces the viewer)
THIN = (0.9, 0.8, 0.9)         # gump: the haft's and the chain's cross-section scaled by the first two, the ball by the third (about where the chain holds it): the animation
                               # needs a thick haft (7.5 cm: 2.7 px at 36 px/m), the gump is 2.5 x larger (6.8 px; the client's maces 3-5 px); 0.5 gave a 2 px line,
                               # 0.7 a 3.8 px haft ("a weapon for children", user: 1 px thicker)
HAFT_LEN = 1.56                # gump: the haft x this long (the knob, KNOB m at the butt, kept; the shaft above it stretched; the chain and the ball move with its end): user, +30 %,
                               # then +20 % more (1.3 x 1.2)
KNOB = 0.09
GRIP_AT = 0.22                 # gump: the hand holds the haft this far (m) above the butt (the animation: 0.06); "it need not hold the very end", "somewhere above the end" (user):
                               # 0.15 showed only the knob under the fist; 0.22 / 0.25 / 0.28 compared: wood between the fist and the knob, from 0.25 the ball reaches the fist
ART_HAFT_LEN = 1.56            # art: as HAFT_LEN (the grip does not matter on the ground); 1.0 / 1.56 shown to the user, the gump's length taken
ART_THIN = (1.0, 0.8, 1.4)     # art: as THIN (with the rim the haft is 3-4 px like the client's mace / war hammer; 1.5 / 1.6 / 1.3 was a tube); the chain with LINK_PX: 1.6 thick
                               # links, "thinner, so the gaps between them show" (user): 0.8 / 1.0 / 1.2 compared with dark gaps
ART_OUTLINE = 1.0              # art: no darkened edge inside, a dark rim outside instead (ART_RIM grey level; the client's arts: 2-8; 16 = no true black)
ART_RIM = 16.0
TILT = 20.0                    # deg: the gump weapon leans out from the body (its top to the left of the picture), so a flail's chain hangs free beside the haft (user);
                               # 10 / 15 / 20 compared: the ball (0.4 m of chain and ball under a 0.5 m haft) ends at the height of the fist and lay on it at 10 and 15
DRAPE = ()                     # a flail's chain on the gump: (x, z) direction of the first pieces (x < 0 = outwards), then straight down (() = hanging free; with an upright
                               # haft it was ((-1, -0.2), (-1, -0.7), (-0.5, -1)): an arch over the outer side)
HOLD_CUT = (8, 9, 6)           # the window of the fist around the grip (x within +-8 px, y from 9 above to 6 below): the haft is cut out where the body gump's fist lies in it,
HOLD_SHOW = {"male": 2, "female": 3}   # but the haft shows through the bottom HOLD_SHOW rows of the fist (counted up from the fist's lower edge in each column; 0 = hidden
                               # under the whole fist): "let the stick show through the hand a little" (user). The client's weapon gumps leave out the haft over the top 5 rows
                               # of the fist (male 109-113) and draw it over the rest; that suited the female fist (8 rows high at the haft, user: ok) but on the male one
                               # (9 rows) the haft started in the middle of the fist, pasted on ("cut out ugly", user); male 3 / 2 / 1 compared. Body gumps from CLIENT
CLIENT = os.path.join(HERE, "..", "uo_client", "NelderimServUO")
BODY = {"male": 12, "female": 13}
ART_PXM = 34.0                 # art px per m (the client's maces: 0.7-1 m long weapons are 28-38 px along the diagonal)
ART_CURL = 125.0               # deg: the chain on the ground turns this much from the haft line (35 / 60 / 90 compared: at 90 the chain and the ball stand apart from the haft;
                               # "bent like an A, not an L" (user): 110 / 125 / 140 compared with a sharp bend)
ART_APEX = 2                   # the turn made over the first ART_APEX pieces of the chain, then straight (0 = spread over the whole chain: a round hook)
ART_CHAIN_LEN = 1.25           # art: the chain x this long (its links longer; "a little longer", user)
LINK_PX = 3.0                  # art: draw the chain's links: every LINK_PX px along the chain the last LINK_GAP of it darkened x LINK_DARK (0 = as rendered)
LINK_GAP = 0.34
LINK_DARK = 0.0                # (<= 0: the gap takes the rim's grey, ART_RIM: the gaps read as breaks between the links; x0.45 / x0.3 left a grain)
PART_GAIN = (1.0, 0.85, 1.1)    # a flail: the grey of the haft / chain / ball relative to each other (each part's median first brought to one level: the wooden haft's luma
                               # was 2 x the metal's, a white board on the gump)
ART_W = 44
LEVELS = (48.0, 105.0, 165.0)  # metal: output grey at the 10th / 50th / 90th percentile (gump); the client's grey maces: 16-24 / 41-65 / 82-169
ART_LEVELS = (60.0, 115.0, 170.0)
WOOD_LEVELS = (24.0, 56.0, 86.0)   # the wooden haft: output luma at its 10th / 50th / 90th percentile; the client's wooden hafts (war hammer, hammer pick, club gumps): 17-25 / 42-58 / 65-91
ART_WOOD_LEVELS = (40.0, 66.0, 100.0)  # (their arts: 7-59 / 45-76 / 83-129)
WOOD_TINT = (1.45, 0.86, 0.50)     # wood colour as R : G : B over luma (the same weapons: 1.38-1.52 / 0.84-0.89 / 0.42-0.57; our animation's haft 1.28 / 0.92 / 0.65)
WOOD_CHROMA = 0.25             # a haft pixel is wood when (max - min of its RGB) > this x its luma in the render; greyer pixels are metal fittings
OUTLINE = 0.45                 # the edge pixels (next to transparency) multiplied by this (the client's arts have a dark rim)
LEVEL_MAX = 210.0              # no white


def setup_render(sc):
    sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = 1; sc.cycles.use_denoising = False
    sc.cycles.pixel_filter_type = "BOX"; sc.cycles.filter_width = 0.01; sc.render.dither_intensity = 0.0
    sc.render.film_transparent = True; sc.view_settings.view_transform = "Standard"
    sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGBA"
    sc["uo_look"] = 1.0; sc["uo_exact"] = 0.0; sc.render.resolution_percentage = 100
    g = bpy.data.node_groups.get("UO_Look_NS")
    if g is not None:                                   # the Sun of the own shadow (as uo_render_paperdoll.py): the UO light direction, no bounces
        Lv = Vector(next(n for n in g.nodes if n.type == "COMBXYZ").inputs[i].default_value for i in range(3))
        ld = bpy.data.lights.new("UO_Sun", "SUN"); sun = bpy.data.objects.new("UO_Sun", ld); sc.collection.objects.link(sun)
        ld.angle = 0.0; ld.energy = 3.14159265 * (1.0 - g["uo_ambient"]) * (1.0 - g["uo_shadow"])
        sun.rotation_euler = Vector((0, 0, 1)).rotation_difference(Lv.normalized()).to_euler()
        sc.cycles.diffuse_bounces = 0
        for m in bpy.data.materials:
            m.cycles.emission_sampling = "NONE"
    cd = bpy.data.cameras.new("WG_Camera"); cd.type = "ORTHO"; cd.sensor_fit = "HORIZONTAL"
    cam = bpy.data.objects.new("WG_Camera", cd); sc.collection.objects.link(cam); sc.camera = cam
    return cam


def render(sc, cam, path, w, h, pxm, cx, cy, top):
    """orthographic: front view (camera at -Y looking along +Y, picture x = +X, up = +Z) or top view (looking down, picture up = +Y); pixel (w/2, h/2) = world (cx, cy)"""
    cam.data.ortho_scale = w / pxm
    if top:
        cam.location = (cx, cy, 6.0); cam.rotation_euler = (0, 0, 0)
    else:
        cam.location = (cx, -6.0, cy); cam.rotation_euler = (np.pi / 2, 0, 0)
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    from PIL import Image
    return np.asarray(Image.open(path).convert("RGBA"), np.float32) / 255.0


def box_down(a, k):
    h, w = a.shape[0] // k, a.shape[1] // k
    a = a[:h * k, :w * k].reshape(h, k, w, k, 4)
    al = a[..., 3].mean((1, 3))
    rgb = (a[..., :3] * a[..., 3:]).sum((1, 3)) / np.maximum(a[..., 3].sum((1, 3)), 1e-6)[..., None]
    out = np.zeros((h, w, 4), np.float32); out[..., :3] = rgb; out[..., 3] = (al >= 0.5)
    return out


def levels_map(y, levels):
    """piecewise-linear: the 10th / 50th / 90th percentile of y to `levels` (the top keeps the slope of the upper half)"""
    p = np.percentile(y, [10, 50, 90]); top = max(p[2] + 1e-3, y.max())
    xs = [0.0, p[0], p[1], p[2], top]
    ys = [min(8.0, levels[0]), levels[0], levels[1], levels[2], levels[2] + (top - p[2]) * (levels[2] - levels[1]) / max(p[2] - p[1], 1e-3)]
    return lambda v: np.interp(v, xs, ys)


def tone(a, levels, part=None, wood_levels=None, outline=None, rim=None):
    """display RGB -> the item's colours: metal (chain, ball, the haft's grey fittings) one grey level per pixel (R = G = B: luma, per part brought to one median
    x PART_GAIN, then `levels` = output 10th / 50th / 90th percentile); the wooden haft (part 0, chroma > WOOD_CHROMA of its luma in the render) the same luma
    mapped to wood_levels and coloured WOOD_TINT (the client's wood); edge pixels darkened by `outline` (default OUTLINE); rim: a grey level drawn in the pixels
    next to the item (4-neighbours), the dark rim of the client's arts"""
    outline = OUTLINE if outline is None else outline
    m = a[..., 3] > 0
    y = (0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]) * 255.0
    chroma = (a[..., :3].max(-1) - a[..., :3].min(-1)) * 255.0
    wood = m & (part == 0) & (chroma > WOOD_CHROMA * np.maximum(y, 1e-3)) if (part is not None and wood_levels) else np.zeros_like(m)
    metal = m & ~wood
    if part is not None:
        ref = np.median(y[metal])
        for k, gk in enumerate(PART_GAIN):
            q = metal & (part == k)
            if q.sum() > 3:
                y[q] *= gk * ref / max(np.median(y[q]), 1e-3)
    g = np.zeros_like(y)
    g[metal] = levels_map(y[metal], levels)(y[metal])
    if wood.sum() > 3:
        g[wood] = levels_map(y[wood], wood_levels)(y[wood])
    if outline < 1:
        pad = np.pad(m, 1)
        edge = m & ~(pad[:-2, 1:-1] & pad[2:, 1:-1] & pad[1:-1, :-2] & pad[1:-1, 2:])
        g[edge] *= outline
    g = np.clip(g, 8.0, LEVEL_MAX)                      # 8: the darkest grey (the 15-bit colour 0 is transparent; no true black)
    tint = np.array(WOOD_TINT) / (0.299 * WOOD_TINT[0] + 0.587 * WOOD_TINT[1] + 0.114 * WOOD_TINT[2])
    rgb = np.repeat(g[..., None], 3, -1)
    rgb[wood] = g[wood][:, None] * tint
    q = (np.clip(np.round(rgb), 8, 255).astype(np.int32) >> 3) << 3   # 15-bit levels, as the client stores them
    out = np.zeros(a.shape[:2] + (4,), np.uint8)
    out[..., :3] = np.where(m[..., None], q, 0); out[..., 3] = np.where(m, 255, 0)
    if rim is not None:
        pad = np.pad(m, 1)
        ring = ~m & (pad[:-2, 1:-1] | pad[2:, 1:-1] | pad[1:-1, :-2] | pad[1:-1, 2:])
        out[ring, :3] = (int(rim) >> 3) << 3; out[ring, 3] = 255
    return out


def stretch(V, part, prm, length, grip_at, chain_len=1.0):
    """the haft lengthened x length (KNOB m at the butt kept, the shaft above stretched), the chain and the ball moved with its end; the chain x chain_len along the axis
    (its links longer, the ball moved on); the grip put grip_at m above the butt (0 = where the animation holds it); rest pose; returns (vertices, prm with the moved
    nodes and grip)"""
    R = np.array(prm["nodes"]); G = np.array(prm["grip"]); hd = (R[0] - G) / np.linalg.norm(R[0] - G)
    t = (V - G) @ hd
    tb = t[part == 0].min(); te = (R[0] - G) @ hd; t0 = tb + KNOB
    k = (length * (te - tb) - KNOB) / (te - t0)
    out = V.copy()
    msk = (part == 0) & (t > t0); out[msk] += np.outer((t[msk] - t0) * (k - 1), hd)
    if chain_len != 1.0:                                # the chain from the end of the haft (te) stretched, the ball moved by the chain's growth
        tc = (R[-2] - G) @ hd
        msk = part == 1; out[msk] += np.outer((np.clip(t[msk], te, tc) - te) * (chain_len - 1), hd)
        out[part == 2] += (tc - te) * (chain_len - 1) * hd
        tn = (R - G) @ hd; R = R + np.outer((np.clip(tn, te, tc) - te) * (chain_len - 1) + np.where(tn > tc, (tc - te) * (chain_len - 1), 0), hd)
    dlt = (te - t0) * (k - 1); out[part > 0] += dlt * hd
    p2 = dict(prm); p2["nodes"] = (R + dlt * hd).tolist()
    if grip_at > 0:
        p2["grip"] = (G + (tb + grip_at) * hd).tolist()
    return out, p2


def thin(V, part, prm, k3):
    """the cross-sections of the haft and the chain scaled about the weapon axis (k3[0], k3[1]), the ball about where the chain holds it (k3[2]), rest pose"""
    R = np.array(prm["nodes"]); G = np.array(prm["grip"]); hd = (R[0] - G) / np.linalg.norm(R[0] - G)
    d = V - G; t = d @ hd; rad = d - np.outer(t, hd)
    out = V.copy()
    for k, f in ((0, k3[0]), (1, k3[1])):
        msk = part == k; out[msk] = G + np.outer(t[msk], hd) + rad[msk] * f
    msk = part == 2; out[msk] = R[-2] + (V[msk] - R[-2]) * k3[2]
    return out


def part_pass(sc, cam, ob, path, w, h, pxm, cx, cy, top):
    """which part (0 haft, 1 chain, 2 ball) each pixel shows: the object drawn with an emission of its uo_flail_part, rendered like the picture"""
    keep = list(ob.data.materials)
    m = bpy.data.materials.new("WG_part"); m.use_nodes = True; nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    at = nt.nodes.new("ShaderNodeAttribute"); at.attribute_name = "uo_flail_part"
    mul = nt.nodes.new("ShaderNodeMath"); mul.operation = "MULTIPLY"; mul.inputs[1].default_value = 0.5
    em = nt.nodes.new("ShaderNodeEmission"); outn = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(at.outputs["Fac"], mul.inputs[0]); nt.links.new(mul.outputs[0], em.inputs["Color"]); nt.links.new(em.outputs[0], outn.inputs["Surface"])
    for i in range(len(ob.data.materials)):
        ob.data.materials[i] = m
    look = sc.get("uo_look"); sc["uo_look"] = 0.0
    a = render(sc, cam, path, w, h, pxm, cx, cy, top)
    sc["uo_look"] = look
    for i, mm in enumerate(keep):
        ob.data.materials[i] = mm
    v = a[SS // 2::SS, SS // 2::SS, 0]                  # the middle sample of each pixel; display values of 0 / 0.5 / 1 linear = 0 / 0.74 / 1
    pid = np.where(v < 0.37, 0, np.where(v < 0.87, 1, 2)); vis = a[SS // 2::SS, SS // 2::SS, 3] > 0.5
    print("WG parts (haft / chain / ball px):", [int(((pid == k) & vis).sum()) for k in range(3)])
    return pid


POSED = {}                     # the nodes of the last pose_flail (grip at the origin)


def links(img, part, nodes, to_px, period, gap, dark):
    """visible links on a small art: chain pixels (part 1) whose distance along the chain (the polyline of the posed nodes, in pixels) falls in the last `gap` of each
    `period` px are darkened x dark (at 34 px/m a 5 cm link is ~2 px: the rendered chain was an even grain)"""
    P = np.array([to_px(x) for x in nodes[:-1]])                       # the chain's nodes (the last piece is the ball)
    seg = np.diff(P, axis=0); L = np.linalg.norm(seg, axis=1); cum = np.concatenate([[0], np.cumsum(L)])
    ys, xs = np.nonzero((part == 1) & (img[..., 3] > 0))
    q = np.stack([xs + 0.5, ys + 0.5], 1)
    best = np.full(len(q), np.inf); sval = np.zeros(len(q))
    for k in range(len(seg)):
        u = np.clip(((q - P[k]) @ seg[k]) / max(L[k] ** 2, 1e-9), 0, 1); d = np.linalg.norm(q - (P[k] + np.outer(u, seg[k])), axis=1)
        b = d < best; best[b] = d[b]; sval[b] = cum[k] + u[b] * L[k]
    g = (sval % period) >= period * (1 - gap)
    out = img.copy(); v = out[ys[g], xs[g], :3].astype(float) * dark if dark > 0 else np.full((int(g.sum()), 3), float(ART_RIM))
    out[ys[g], xs[g], :3] = (np.clip(np.round(v), 8, 255).astype(np.int32) >> 3) << 3
    return out


def pose_flail(V, part, s, prm, Q, chain_dirs):
    """vertex positions (grip at the origin): the haft turned by Q, the chain pieces along chain_dirs (one direction per piece), the ball on the last piece"""
    R = np.array(prm["nodes"]); n = len(R); G = np.array(prm["grip"])
    rest = np.linalg.norm(np.diff(R, axis=0), axis=1)
    X = np.zeros_like(R); X[0] = Q @ (R[0] - G)
    for k in range(n - 1):
        d = np.asarray(chain_dirs[min(k, len(chain_dirs) - 1)], float); X[k + 1] = X[k] + d / np.linalg.norm(d) * rest[k]
    P = (V - G) @ Q.T
    seg = (prm["ball_start"] - prm["haft_end"]) / (n - 2)
    piece = np.where(part == 2, n - 2, np.clip(((s - prm["haft_end"]) / seg).astype(int), 0, n - 3))
    F = Q.copy()
    for k in range(n - 1):                              # each piece turned like its segment, the turn carried down from the haft (as render_uo_layer.flail_fix)
        c = F @ (R[k + 1] - R[k]); x = X[k + 1] - X[k]
        F = np.array(Vector(c.tolist()).rotation_difference(Vector(x.tolist())).to_matrix()) @ F
        msk = (piece == k) & (part > 0)
        P[msk] = X[k] + (V[msk] - R[k]) @ F.T
    POSED["nodes"] = X
    return P


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
    Mw = np.array(ob.matrix_world); V = co.reshape(-1, 3) @ Mw[:3, :3].T + Mw[:3, 3]          # rest pose = armature space (the rig sits at the origin)
    flail = "uo_flail" in ob
    if flail:
        prm = json.loads(ob["uo_flail"]); G = np.array(prm["grip"]); R0 = np.array(prm["nodes"])[0]
        part = np.empty(nv, np.int32); ob.data.attributes["uo_flail_part"].data.foreach_get("value", part)
        s = np.empty(nv, np.float32); ob.data.attributes["uo_flail_s"].data.foreach_get("value", s)
        hd = (R0 - G) / np.linalg.norm(R0 - G)
    else:                                               # a rigid weapon: the haft = the long axis of the mesh through its butt end
        raise SystemExit("uo_render_weapon_gump: only flails (uo_flail.py) for now")
    for m in list(ob.modifiers):
        ob.modifiers.remove(m)
    if ob.data.shape_keys:
        ob.shape_key_clear()
    ob.parent = None; ob.matrix_world = Matrix.Identity(4)
    cam = setup_render(sc)
    from PIL import Image
    import uo_gump_art as ga
    os.makedirs(out, exist_ok=True); tmp = os.path.join(out, "_tmp.png")

    def place(P):
        ob.data.vertices.foreach_set("co", P.astype(np.float64).ravel()); ob.data.update()

    # gump: the haft upright (grip at the origin), the chain over the outer side (-X = the character's right, the left of the picture), then straight down
    up = Vector((0, 0, 1)); Q = np.array(Vector(hd.tolist()).rotation_difference(up).to_matrix())
    Q = np.array(Matrix.Rotation(np.radians(ROLL), 3, up)) @ Q
    Q = np.array(Matrix.Rotation(-np.radians(TILT), 3, Vector((0, 1, 0)))) @ Q   # about the view axis: the top goes to -X (out)
    V0 = V; Vg, pg = stretch(V0, part, prm, HAFT_LEN, GRIP_AT); V = thin(Vg, part, pg, THIN)
    dirs = [(x, 0.0, z) for x, z in DRAPE] + [(0.0, 0.0, -1.0)]          # free: every piece straight down (gravity), the ball below the last
    place(pose_flail(V, part, s, pg, Q, dirs))
    res = {}
    for gender, (gx, gy) in GRIP.items():
        cx = (GW / 2 - gx) / PXM; cz = (gy - GH / 2) / PXM
        a = box_down(render(sc, cam, tmp, GW * SS, GH * SS, PXM * SS, cx, cz, False), SS)
        pp = part_pass(sc, cam, ob, tmp, GW * SS, GH * SS, PXM * SS, cx, cz, False)
        img = tone(a, LEVELS, pp, WOOD_LEVELS); res[gender] = img
        try:
            bodyg = ga.read_gump(CLIENT, BODY[gender])
        except OSError:
            bodyg = None
        if HOLD_CUT and bodyg is not None:              # the haft behind the fist: the body gump's fist shows through
            bm = np.zeros((GH, GW), bool); h_, w_ = min(GH, bodyg.shape[0]), min(GW, bodyg.shape[1]); bm[:h_, :w_] = bodyg[:h_, :w_, 3] > 0
            yy, xx = np.mgrid[0:GH, 0:GW]; win = (np.abs(xx + 0.5 - gx) <= HOLD_CUT[0]) & (yy + 0.5 >= gy - HOLD_CUT[1]) & (yy + 0.5 <= gy + HOLD_CUT[2])
            cut = win & bm & (pp == 0) & (img[..., 3] > 0)
            hs = HOLD_SHOW[gender] if isinstance(HOLD_SHOW, dict) else HOLD_SHOW
            if hs:
                fist = win & bm
                bottom = np.where(fist.any(0), GH - 1 - np.argmax(fist[::-1], 0), -1)          # the fist's lowest row in each column
                cut &= yy <= bottom[None, :] - hs
            img[cut] = 0
            print("WG gump %s: %d haft px cut out under the fist (rows %d..%d)" % (gender, cut.sum(), *(lambda r: (r.min(), r.max()))(np.nonzero(cut)[0])) if cut.any() else "WG gump %s: nothing under the fist" % gender)
        elif HOLD_CUT:
            print("WG: no body gump in %s, the haft is not cut at the fist" % CLIENT)
        Image.fromarray(img).save(os.path.join(out, "gump_%s.png" % gender))
        data, extra = ga.encode_gump(img)
        open(os.path.join(out, "gump_%s.bin" % gender), "wb").write(data)
        ys, xs = np.nonzero(img[..., 3]); print("WG gump %s: bbox x %d..%d y %d..%d, %d px, extra %08x" % (gender, xs.min(), xs.max(), ys.min(), ys.max(), len(xs), extra))

    # art: lying on the ground (z up), seen from above; the haft along the picture's diagonal from the bottom left, the chain curling back beside it
    d45 = Vector((1, 1, 0)).normalized()
    Qa = np.array(Vector(hd.tolist()).rotation_difference(d45).to_matrix())
    Qa = np.array(Matrix.Rotation(np.radians(ROLL), 3, d45)) @ Qa
    n = len(prm["nodes"]); ap = ART_APEX if ART_APEX > 0 else n - 2
    turns = [np.radians(ART_CURL) * min(1.0, (k + 1) / ap) for k in range(n - 1)]
    dirs = [tuple(np.array(Matrix.Rotation(-a_, 3, Vector((0, 0, 1)))) @ np.array(d45)) for a_ in turns]
    Va, pa = stretch(V0, part, prm, ART_HAFT_LEN, 0.0, ART_CHAIN_LEN)
    P = pose_flail(thin(Va, part, pa, ART_THIN), part, s, pa, Qa, dirs)
    zshift = P[:, 2].min(); P[:, 2] -= zshift            # on the ground
    place(P)
    lo, hi = P[:, :2].min(0), P[:, :2].max(0); c = (lo + hi) / 2
    wpx = int(np.ceil((hi[0] - lo[0]) * ART_PXM)) + 3; hpx = int(np.ceil((hi[1] - lo[1]) * ART_PXM)) + 3
    w = max(ART_W, wpx); h = hpx
    a = box_down(render(sc, cam, tmp, w * SS, h * SS, ART_PXM * SS, c[0], c[1], True), SS)
    pp = part_pass(sc, cam, ob, tmp, w * SS, h * SS, ART_PXM * SS, c[0], c[1], True)
    art = tone(a, ART_LEVELS, pp, ART_WOOD_LEVELS, ART_OUTLINE, ART_RIM)
    if LINK_PX > 0:
        art = links(art, pp, POSED["nodes"], lambda x: (w / 2 + (x[0] - c[0]) * ART_PXM, h / 2 - (x[1] - c[1]) * ART_PXM), LINK_PX, LINK_GAP, LINK_DARK)
    ys, xs = np.nonzero(art[..., 3]); art = art[ys.min():ys.max() + 1]          # the client's arts start at their top row
    for name, im in (("art", art), ("art_mirror", art[:, ::-1].copy())):
        Image.fromarray(im).save(os.path.join(out, name + ".png"))
        open(os.path.join(out, name + ".bin"), "wb").write(ga.encode_art(im))
    print("WG art: %d x %d, item %d x %d px" % (art.shape[1], art.shape[0], xs.max() - xs.min() + 1, ys.max() - ys.min() + 1))
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
