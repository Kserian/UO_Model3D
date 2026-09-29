# UO layer renderer: renders the body or the clothing layer through "UO_Camera" for every UO action,
# 5 directions and every frame, post-processes like UO art and writes PNGs (vdtool layout) and a .vd file.
# Run from Blender's Text Editor (Alt+P). Edit the settings below first.
#
#   LAYER = "clothing" : objects in the "Clothing" collection; the body is a HOLDOUT (it hides what is behind it,
#                        but is not drawn itself) - exactly what an equipment layer in UO must contain.
#   LAYER = "body"     : only the body (clothing hidden).
#   LAYER = "all"      : body + clothing together (preview; not a UO layer).
#   EXACT_BODY / EXACT_COLORS: use the original UO frames packed in this file (see README) for a pixel-exact body.
#   To cancel a running render: create an empty file named STOP in the output folder (e.g. uo_render/clothing/STOP),
#   or press Ctrl+C in Blender's system console (Window > Toggle System Console). Delete STOP before the next run.
#   Several runs into the same OUT_DIR add up: e.g. render ONLY = [attacks] with one grip, then ONLY = [others] with
#   another; each run writes a .vd with ALL actions rendered so far (delete OUT_DIR to start from scratch).
import bpy, os, json
import numpy as np

LAYER = "clothing"
ONLY = []                          # e.g. ["04_stand", "00_walk_unarmed"]; empty = all 35 UO actions
OUTLINE = 0.38                     # dark 1-px outline like UO art (measured on the original body); 1.0 = off
OUT_DIR = "//uo_render/"           # PNG output root (vdtool 'canvas' layout + meta.json)
WRITE_VD = True
VD_FILE = "//uo_render/%s.vd"      # %s -> LAYER
STEP = 3                           # scene frames between two UO frames
ANCHOR = (68, 86)                  # UO anchor pixel of the 136x120 render (world point 0, 0, scene["uo_anchor_height"])
CLOTHING = "Clothing"              # collection with the clothing / equipment meshes
HORSE_HOLDOUT = True               # mounted actions: the horse hides what is behind it, clipped to the exact horse sprite
EXACT_COLORS = True                # body in the UO look: colours projected from the original UO frames packed in the file
EXACT_BODY = True                  # body = original UO frames: the "body" layer reproduces the original exactly, and in
                                   # the "clothing" layer the body hides items exactly along the ORIGINAL outline
                                   # (the 3D model only decides what is in front / behind). Turn off for a modified body.
HOLDOUT_MARGIN = 0.01              # m: in the clothing layer the body hides an item only where it is at least this much in
                                   # front of it, so skin poking a few mm through tight armour does not cut holes
                                   # (1 px = 2.8 cm). 0 = plain Cycles holdout (renders every frame twice).
OCCLUDERS = ["head", "upper_arm", "forearm", "hand", "thigh", "shin", "foot"]   # body parts that may hide items
                                   # (with HOLDOUT_MARGIN > 0); the torso (pelvis, spine, chest, neck) never does, because
                                   # items are worn over it and a torso poking through is a model error, not an occluder
DESPECKLE = 28                     # clothing: single dark pixels inside the item darker than their neighbours by more
                                   # than this (0-255) take the colour around them - deep sculpt details / rivets that
                                   # turn into black dots at UO size. 0 = off
FILL_HOLES = 4                     # px: holes INSIDE an item (fully surrounded by it) up to this size are filled - skin
                                   # poking through or a gap in the item mesh, not a real occluder. 0 = off
MIN_PIECE = 8                      # px: detached bits of the item smaller than this are removed (collar or cuff rims cut
                                   # off by the head or a hand read as dirt at UO size); the biggest piece always stays. 0 = off


sc = bpy.context.scene
rig = bpy.data.objects["UO_Rig"]
body = bpy.data.objects["UO_Body"]
clothes = [o for o in bpy.data.collections[CLOTHING].all_objects if o.type == "MESH"] if CLOTHING in bpy.data.collections else []

# items baked by uo_cloth_bake.py: their cloth simulation replaces the bound pose in the actions it covers
CLOTH = {}
for o in clothes:
    if o.get("uo_cloth"):
        p = bpy.path.abspath(o["uo_cloth"])
        base = o.data.shape_keys.key_blocks[0].data if o.data.shape_keys else o.data.vertices
        co = np.empty(len(o.data.vertices) * 3, np.float32); base.foreach_get("co", co)
        sig = np.array([len(o.data.vertices), float(np.abs(co.astype(np.float64)).sum())])
        d = np.load(p) if os.path.exists(p) else None
        if d is not None and "item_sig" in d.files and np.allclose(d["item_sig"], sig, rtol=1e-5):
            CLOTH[o.name] = {k: d[k] for k in d.files}
            print("render_uo_layer: %s uses its cloth bake %s" % (o.name, p))
        elif d is not None:
            print("render_uo_layer: %s changed after its cloth bake - rendered as bound (bake it again)" % o.name)
        else:
            print("render_uo_layer: cloth bake of %s not found (%s) - rendered as bound" % (o.name, p))


def cloth_show(o, a, i):
    """baked cloth shape of UO action a, frame i on item o (shape key 'uo_cloth', Armature off); else the bound item"""
    c = CLOTH.get(o.name)
    arm = [m for m in o.modifiers if m.type == "ARMATURE"]
    key = o.data.shape_keys.key_blocks.get("uo_cloth") if o.data.shape_keys else None
    if c is None or ("a%d_f%d" % (a, i)) not in c:
        for m in arm:
            m.show_viewport = m.show_render = True
        if key:
            key.value = 0.0
        return
    co = c["a%d_f%d" % (a, i)].astype(np.float64); tris, fi = c["tris"], c["fi"]
    A, B, C = co[tris[:, 0]], co[tris[:, 1]], co[tris[:, 2]]
    e1 = B - A; e1 /= np.maximum(np.linalg.norm(e1, axis=1, keepdims=True), 1e-12)
    n = np.cross(B - A, C - A); n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    fr = np.stack([e1, np.cross(n, e1), n], 1)[fi]
    pos = (co[tris[fi]] * c["bc"][..., None]).sum(1) + np.einsum("nk,nkj->nj", c["off"], fr)
    if "fix_node" in c and ("d%d_f%d_i" % (a, i)) in c:              # pushed out of the real body after the simulation
        Dn = np.zeros((int(c["fix_node"].max()) + 1, 3)); Dn[c["d%d_f%d_i" % (a, i)]] = c["d%d_f%d_v" % (a, i)]
        pos += Dn[c["fix_node"]]
    if key is None:
        if o.data.shape_keys is None:
            o.shape_key_add(name="Basis", from_mix=False)
        key = o.shape_key_add(name="uo_cloth", from_mix=False)
    key.data.foreach_set("co", pos.astype(np.float32).ravel()); key.value = 1.0
    for m in arm:
        m.show_viewport = m.show_render = False
    o.data.update()
writer = bpy.data.texts["uo_vd_writer.py"].as_module()

if sc.render.engine != "CYCLES":                     # holdout, exact modes and UO shading are set up for Cycles
    print("render_uo_layer: render engine %s -> CYCLES" % sc.render.engine)
    sc.render.engine = "CYCLES"
if not bpy.context.preferences.filepaths.use_scripts_auto_execute:
    print("render_uo_layer: NOTE - 'Auto Run Python Scripts' is off; if the body looks wrong, enable it "
          "(Preferences > Save & Load) and reopen the file")
sc.camera = bpy.data.objects["UO_Camera"]
sc.render.resolution_x, sc.render.resolution_y = 136, 120
sc.render.resolution_percentage = 100
sc.render.film_transparent = True
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGBA"
sc.view_settings.view_transform = "Standard"
sc["uo_look"] = 1.0                 # UO lighting (see node group "UO_Look")
sc["uo_exact"] = 1.0 if (EXACT_COLORS and "UO_Original_Atlas" in bpy.data.images) else 0.0   # no atlas -> model colours
EXACT_ANY = EXACT_COLORS or EXACT_BODY
if EXACT_ANY and sc.render.engine == "CYCLES":
    sc.cycles.pixel_filter_type = "BOX"          # one sample point per pixel centre, like the UO art (no blur)
    sc.cycles.filter_width = 0.01
    sc.cycles.use_denoising = False
    sc.cycles.samples = 1                        # 1 sample = exactly the pixel centre (the UO shading is noise-free)
ORIG = {}
if EXACT_ANY and "uo_original_frames.json" in bpy.data.texts:
    import base64, zlib
    ORIG = json.loads(bpy.data.texts["uo_original_frames.json"].as_string())


def original(a, i, d):
    """original UO body frame (uint8 RGBA 120x136, anchor 68,86) or None"""
    v = ORIG.get("frames", {}).get("%d,%d,%d" % (a, i, d)) if ORIG else None
    if v is None:
        return None
    return np.frombuffer(zlib.decompress(base64.b64decode(v)), np.uint8).reshape(120, 136, 4).copy()


def set_tile(a, i, d):
    t = ORIG.get("tiles", {}).get("%d,%d,%d" % (a, i, d)) if ORIG else None
    sc["uo_tile_col"], sc["uo_tile_row"] = (t if t else (0, 0))

horses = {o.name: o for o in bpy.data.objects if o.name.startswith("Horse_")}
for o in horses.values():
    o.hide_render = True
    o.is_holdout = True


HORSE_MASKS = {}                   # exact horse sprite silhouettes: only there can the horse hide anything
if "uo_horse_masks.json" in bpy.data.texts:
    import base64, zlib
    for k, v in json.loads(bpy.data.texts["uo_horse_masks.json"].as_string())["masks"].items():
        bits = np.unpackbits(np.frombuffer(zlib.decompress(base64.b64decode(v)), np.uint8))[:120 * 136]
        HORSE_MASKS[tuple(int(x) for x in k.split(","))] = bits.reshape(120, 136).astype(bool)


def set_horse(a, i):
    for o in horses.values():
        o.hide_render = True
    o = horses.get("Horse_a%d_f%d" % (a, i)) if HORSE_HOLDOUT else None
    if o is not None:          # the horse proxy made for exactly this mounted frame
        o.hide_render = False


state = dict(holdout=body.is_holdout, body_hide=body.hide_render, cloth={o.name: o.hide_render for o in clothes},
             action=rig.animation_data.action, direction=rig.get("uo_direction", 0), pose=rig.data.pose_position)
rig.data.pose_position = "POSE"                      # the actions only play in Pose Position
body.hide_render = False
body.is_holdout = LAYER == "clothing"
for o in clothes:
    o.hide_render = LAYER == "body"
if LAYER == "clothing" and not any(not o.hide_render for o in clothes):
    raise RuntimeError("No visible meshes in the 'Clothing' collection")


def uo_post(px, keep=None):
    """float RGBA (h,w,4), straight alpha -> UO look: over black, 1-bit alpha, dark outline. Returns uint8 RGBA.
    keep: pixels that already carry original UO colours (no extra outline)."""
    a = px[..., 3:4]
    rgb = px[..., :3] * a
    m = px[..., 3] >= 0.5
    inner = m.copy()
    inner[1:] &= m[:-1]; inner[:-1] &= m[1:]; inner[:, 1:] &= m[:, :-1]; inner[:, :-1] &= m[:, 1:]
    edge = m & ~inner
    if keep is not None:
        edge &= ~keep
        rgb[keep & m] = px[..., :3][keep & m]
    rgb[edge] *= OUTLINE
    out = np.zeros(px.shape, np.uint8)
    out[..., :3] = np.clip(rgb * 255 + 0.5, 0, 255).astype(np.uint8)
    out[..., 3] = m * 255
    out[~m, :3] = 0
    return out


def render_px():
    sc.render.filepath = tmp
    bpy.ops.render.render(write_still=True)
    im = bpy.data.images.load(tmp)
    w, h = im.size
    px = np.empty(w * h * 4, np.float32); im.pixels.foreach_get(px)
    bpy.data.images.remove(im)
    return px.reshape(h, w, 4)[::-1]                        # Blender pixels start at the bottom row


def body_part_mask(parts):
    """body triangles (loop_triangles order) whose dominant bone is one of `parts` (names without .L / .R)"""
    me = body.data
    sub = {"upper_arm_twist": "upper_arm", "forearm_twist": "forearm", "toe": "foot"}   # v13 extra bones
    names = [g.name.split(".")[0] for g in body.vertex_groups]
    names = ["hand" if n.startswith("finger") else sub.get(n, n) for n in names]
    W = np.zeros((len(me.vertices), len(names)))
    for v in me.vertices:
        for g in v.groups:
            W[v.index, g.group] = g.weight
    me.calc_loop_triangles()
    tri = np.array([t.vertices[:] for t in me.loop_triangles])
    dom = W[tri].sum(1).argmax(1)
    return np.array([names[k] in parts for k in dom])


OCCLUDER_TRIS = body_part_mask(set(OCCLUDERS))


def raster(objs, tri_mask=None):
    """pixel coverage and camera depth (m) of the deformed meshes through UO_Camera, pixel-centre rule (like the
    EXACT render). Returns (bool 120x136, float 120x136 with inf where nothing is). tri_mask: triangles to use."""
    rig.update_tag(); body.update_tag(); bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    cam = sc.camera.evaluated_get(dg)
    Pm = np.array(cam.calc_matrix_camera(dg, x=136, y=120)); Vm = np.array(cam.matrix_world.inverted())
    img = np.zeros((120, 136), bool); depth = np.full((120, 136), np.inf)
    for ob in objs:
        ev = ob.evaluated_get(dg); me = ev.to_mesh()
        co = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
        me.calc_loop_triangles()
        tri = np.empty(len(me.loop_triangles) * 3, np.int32); me.loop_triangles.foreach_get("vertices", tri); tri = tri.reshape(-1, 3)
        if tri_mask is not None and len(tri_mask) == len(tri):
            tri = tri[tri_mask]
        Mw = np.array(ev.matrix_world)
        ev.to_mesh_clear()
        hv = np.c_[co, np.ones(len(co))] @ (Vm @ Mw).T                  # camera space
        h = hv @ Pm.T
        ndc = h[:, :2] / h[:, 3:4]
        P = np.stack([(ndc[:, 0] + 1) * 0.5 * 136, (1 - ndc[:, 1]) * 0.5 * 120], 1)[tri]
        Z = -hv[:, 2][tri]
        mn = np.floor(P.min(1)).astype(int); mx = np.ceil(P.max(1)).astype(int)
        A, B, C = P[:, 0], P[:, 1], P[:, 2]
        den = (B[:, 1] - C[:, 1]) * (A[:, 0] - C[:, 0]) + (C[:, 0] - B[:, 0]) * (A[:, 1] - C[:, 1])
        ok = np.abs(den) > 1e-12; size = np.clip(mx - mn, 0, 16)
        for dy in range(int(size[:, 1].max(initial=0)) + 1):
            for dx in range(int(size[:, 0].max(initial=0)) + 1):
                t = np.nonzero(ok & (dx <= size[:, 0]) & (dy <= size[:, 1]))[0]
                px_ = mn[t, 0] + dx; py_ = mn[t, 1] + dy; cx, cy = px_ + 0.5, py_ + 0.5
                l0 = ((B[t, 1] - C[t, 1]) * (cx - C[t, 0]) + (C[t, 0] - B[t, 0]) * (cy - C[t, 1])) / den[t]
                l1 = ((C[t, 1] - A[t, 1]) * (cx - C[t, 0]) + (A[t, 0] - C[t, 0]) * (cy - C[t, 1])) / den[t]
                k = (l0 >= -1e-4) & (l1 >= -1e-4) & (1 - l0 - l1 >= -1e-4) & (px_ >= 0) & (py_ >= 0) & (px_ < 136) & (py_ < 120)
                img[py_[k], px_[k]] = True
                z = l0[k] * Z[t[k], 0] + l1[k] * Z[t[k], 1] + (1 - l0[k] - l1[k]) * Z[t[k], 2]
                np.minimum.at(depth, (py_[k], px_[k]), z)
    return img, depth


def body_coverage():
    """pixels covered by the (deformed) body mesh through UO_Camera, pixel-centre rule (like the EXACT render)"""
    return raster([body])[0]


def body_occlusion(free, margin):
    """the clothing render without the body, with the body in front of the item removed. The body hides a pixel only
    where it is more than `margin` in front of the visible item surface. Returns (hold, body coverage)."""
    cov, _ = raster([body])
    occ, zb = raster([body], OCCLUDER_TRIS)            # only the parts that may hide items (not the torso)
    _, zi = raster([o for o in clothes if not o.hide_render])
    seen = free[..., 3] >= 0.5
    for _ in range(2):                                  # item pixels Cycles drew but the raster missed: neighbour depth
        miss = seen & np.isinf(zi)
        if not miss.any():
            break
        pad = np.pad(zi, 1, constant_values=np.inf)
        nb = np.min([pad[y:y + 120, x:x + 136] for y in range(3) for x in range(3)], axis=0)
        zi = np.where(miss, nb, zi)
    hold = free.copy()
    hold[occ & (zb < zi - margin)] = 0.0
    return hold, cov


def render_frame(a, i, d, body_mode):
    """body_mode: 'visible' | 'holdout' | 'hidden'. Includes the horse holdout of mounted actions."""
    body.hide_render = body_mode == "hidden"
    body.is_holdout = body_mode == "holdout"
    set_horse(a, i)
    px = render_px()
    hm = HORSE_MASKS.get((a, i, d)) if HORSE_HOLDOUT else None
    if hm is not None and horses.get("Horse_a%d_f%d" % (a, i)) is not None:
        set_horse(-1, 0)                                # outside the horse sprite nothing is hidden
        px = np.where(hm[..., None], px, render_px())
    return px


def binary_dilation(m, iterations=1):
    """4-neighbour dilation (same result as scipy.ndimage.binary_dilation), numpy only."""
    for _ in range(iterations):
        d = m.copy()
        d[1:] |= m[:-1]
        d[:-1] |= m[1:]
        d[:, 1:] |= m[:, :-1]
        d[:, :-1] |= m[:, 1:]
        m = d
    return m


def fill_small_holes(px, free, max_px):
    """transparent patches up to max_px fully surrounded by the item are filled: with the item from the render without
    the body (skin poking through) or, where the item mesh itself leaves a gap, with the colour of the item around it"""
    a = px[..., 3] >= 0.5
    H, W = a.shape
    outside = np.zeros_like(a)
    outside[0, :] = outside[-1, :] = outside[:, 0] = outside[:, -1] = True
    outside &= ~a
    while True:                                         # transparent pixels connected to the image border
        g = outside.copy()
        g[1:] |= outside[:-1]; g[:-1] |= outside[1:]; g[:, 1:] |= outside[:, :-1]; g[:, :-1] |= outside[:, 1:]
        g &= ~a
        if (g == outside).all():
            break
        outside = g
    hole = ~a & ~outside
    seen = np.zeros_like(hole)
    for y, x in zip(*np.nonzero(hole)):
        if seen[y, x]:
            continue
        comp, stack = [], [(y, x)]
        seen[y, x] = True
        while stack:
            cy, cx = stack.pop()
            comp.append((cy, cx))
            for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                if 0 <= ny < H and 0 <= nx < W and hole[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        if len(comp) > max_px:
            continue                                    # a real opening (e.g. an arm in front of the chest)
        todo = []
        for cy, cx in comp:
            if free[cy, cx, 3] >= 0.5:
                px[cy, cx] = free[cy, cx]
            else:
                todo.append((cy, cx))
        for _ in range(max_px):                         # mesh gap: colour of the neighbouring item pixels
            left = []
            for cy, cx in todo:
                nb = [px[ny, nx] for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1))
                      if 0 <= ny < H and 0 <= nx < W and px[ny, nx, 3] >= 0.5]
                if nb:
                    px[cy, cx] = np.mean(nb, axis=0); px[cy, cx, 3] = 1.0
                else:
                    left.append((cy, cx))
            todo = left
            if not todo:
                break
    return px


def despeckle(img, thr, passes=2):
    """uint8 RGBA: dark single pixels inside the item (not its outline) -> colour of their non-dark neighbours"""
    out = img.copy(); m = out[..., 3] > 0; H, W = m.shape
    offs = [(y, x) for y in range(3) for x in range(3) if (y, x) != (1, 1)]
    for _ in range(passes):
        rgb = out[..., :3].astype(float)
        lum = rgb.mean(-1)
        pad = np.pad(rgb, ((1, 1), (1, 1), (0, 0)), mode="edge"); pm = np.pad(m, 1)
        stack = np.stack([pad[y:y + H, x:x + W] for y, x in offs], 0)
        valid = np.stack([pm[y:y + H, x:x + W] for y, x in offs], 0)
        sl = stack.mean(-1)
        srt = np.sort(np.where(valid, sl, np.inf), axis=0)
        n = valid.sum(0)
        lo = np.take_along_axis(srt, np.clip((n - 1) // 2, 0, 7)[None], 0)[0]
        hi = np.take_along_axis(srt, np.clip(n // 2, 0, 7)[None], 0)[0]
        med = np.where(np.isfinite(hi), (lo + hi) / 2, lo)
        dark = m & (n >= 7) & (lum < med - thr)
        if not dark.any():
            break
        ok = valid & (sl >= (med - thr / 2)[None])
        w = ok.sum(0)
        fill = (stack * ok[..., None]).sum(0) / np.maximum(w, 1)[..., None]
        sel = dark & (w > 0)
        out[sel, :3] = np.clip(fill[sel] + 0.5, 0, 255).astype(np.uint8)
    return out


def drop_small_pieces(img, min_px):
    """uint8 RGBA: detached pieces of the item (8-connected) smaller than min_px -> transparent, except the biggest"""
    m = img[..., 3] > 0; H, W = m.shape
    seen = np.zeros_like(m); pieces = []
    for y0, x0 in zip(*np.nonzero(m)):
        if seen[y0, x0]:
            continue
        comp = [(y0, x0)]; seen[y0, x0] = True; k = 0
        while k < len(comp):
            cy, cx = comp[k]; k += 1
            for ny in (cy - 1, cy, cy + 1):
                for nx in (cx - 1, cx, cx + 1):
                    if 0 <= ny < H and 0 <= nx < W and m[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        comp.append((ny, nx))
        pieces.append(comp)
    out = img.copy()
    big = max(pieces, key=len) if pieces else None
    for comp in pieces:
        if len(comp) < min_px and comp is not big:
            ys, xs = zip(*comp)
            out[list(ys), list(xs)] = 0
    return out


def exact_clothing(hold, free, orig_body, cov):
    """Hide the item exactly where the ORIGINAL body is in front of it; the 3D model decides front/behind."""
    a_h, a_f = hold[..., 3] >= 0.5, free[..., 3] >= 0.5
    hidden = a_f & ~a_h                                 # the model body hides the item here
    out = free.copy()                                   # outside the original body nothing hides the item
    use_hold = orig_body & cov
    out[use_hold] = hold[use_hold]
    rim = orig_body & ~cov & binary_dilation(hidden, iterations=2)   # thin rim the model body does not reach
    out[rim] = 0.0
    return out


root = bpy.path.abspath(OUT_DIR + LAYER + "/")
tmp = os.path.join(root, "_tmp.png")
os.makedirs(root, exist_ok=True)
if os.path.exists(os.path.join(root, "STOP")):
    os.remove(os.path.join(root, "STOP"))                  # a leftover STOP from a cancelled run
blocks, meta_blocks = {}, []
acts = sorted([a for a in bpy.data.actions if "uo_action" in a], key=lambda a: int(a["uo_action"]))
for act in acts:
    if ONLY and act.name not in ONLY:
        continue
    a = int(act["uo_action"])
    rig.animation_data.action = act
    for d in range(5):
        rig["uo_direction"] = d
        rig.update_tag()
        fdir = os.path.join(root, "frames", act.name, "dir%d" % d)
        os.makedirs(fdir, exist_ok=True)
        frames, meta_frames = [], []
        for i in range(int(act["uo_frames"])):
            if os.path.exists(os.path.join(root, "STOP")):      # create an empty file named STOP to cancel
                raise KeyboardInterrupt("STOP file found in " + root)
            set_tile(a, i, d)
            sc.frame_set(1 + i * STEP)
            for o in clothes:
                if o.name in CLOTH:
                    cloth_show(o, a, i)
            orig = original(a, i, d) if EXACT_ANY else None
            orig_m = orig[..., 3] > 0 if orig is not None else None
            if LAYER == "body" and EXACT_BODY and orig is not None:
                rgba = orig                                    # the original UO body frame, pixel for pixel
            elif LAYER == "clothing" and HOLDOUT_MARGIN > 0:
                free = render_frame(a, i, d, "hidden")
                hold, cov = body_occlusion(free, HOLDOUT_MARGIN)
                px = exact_clothing(hold, free, orig_m, cov) if (EXACT_BODY and orig is not None) else hold
                if FILL_HOLES > 0:
                    px = fill_small_holes(px, free, FILL_HOLES)
                rgba = uo_post(px)
                if DESPECKLE > 0:
                    rgba = despeckle(rgba, DESPECKLE)
                if MIN_PIECE > 0:
                    rgba = drop_small_pieces(rgba, MIN_PIECE)
            elif LAYER == "clothing":
                px = render_frame(a, i, d, "holdout")
                if EXACT_BODY and orig is not None:
                    px = exact_clothing(px, render_frame(a, i, d, "hidden"), orig_m, body_coverage())
                rgba = uo_post(px)
                if MIN_PIECE > 0:
                    rgba = drop_small_pieces(rgba, MIN_PIECE)
            else:
                px = render_frame(a, i, d, "visible")
                rgba = uo_post(px, keep=orig_m if (EXACT_COLORS and orig_m is not None) else None)
            h, w = rgba.shape[:2]
            frames.append(rgba)
            png = bpy.data.images.new("uo_tmp_out", w, h, alpha=True)
            png.pixels.foreach_set((rgba[::-1].astype(np.float32) / 255.0).ravel())
            png.filepath_raw = os.path.join(fdir, "%02d.png" % i); png.file_format = "PNG"; png.save()
            bpy.data.images.remove(png)
            meta_frames.append(dict(file="%02d.png" % i))
        blocks[(a, d)] = frames
        meta_blocks.append(dict(action=a, dir=d, name=act.name, frames=meta_frames))
if os.path.exists(tmp):
    os.remove(tmp)
# actions rendered in EARLIER runs into the same folder are kept: each run can use a different item setup (e.g. another
# grip for some actions) and the final .vd contains every action whose frames are on disk
names = {int(a["uo_action"]): a.name for a in acts}
for act in acts:
    a = int(act["uo_action"])
    for d in range(5):
        if (a, d) in blocks:
            continue
        fdir = os.path.join(root, "frames", act.name, "dir%d" % d)
        files = ["%02d.png" % i for i in range(int(act["uo_frames"]))]
        if not all(os.path.exists(os.path.join(fdir, f)) for f in files):
            continue
        frames = []
        for f in files:
            im = bpy.data.images.load(os.path.join(fdir, f)); w, h = im.size
            px = np.empty(w * h * 4, np.float32); im.pixels.foreach_get(px); bpy.data.images.remove(im)
            frames.append(np.clip(px.reshape(h, w, 4)[::-1] * 255 + 0.5, 0, 255).astype(np.uint8))
        blocks[(a, d)] = frames
        meta_blocks.append(dict(action=a, dir=d, name=act.name, frames=[dict(file=f) for f in files]))
print("actions in this .vd:", sorted({a for a, _ in blocks}))
# vdtool-compatible meta.json (canvas mode) so the PNGs can also be packed with: python vdtool.py pack <folder> out.vd
done_blocks = {(b["action"], b["dir"]): b for b in meta_blocks}
meta_blocks = [done_blocks.get((a, d), dict(action=a, dir=d, name=names.get(a, "action"), frames=[]))
               for a in range(35) for d in range(5)]
with open(os.path.join(root, "meta.json"), "w") as fh:
    json.dump(dict(tool="render_uo_layer", anim_type=2, actions=35, mode="canvas", canvas=[136, 120],
                   anchor=list(ANCHOR), blocks=meta_blocks), fh, indent=1)
if WRITE_VD:
    vd_path = bpy.path.abspath(VD_FILE % LAYER)
    writer.write_vd(vd_path, blocks, anim_type=2, anchor=ANCHOR)
    print("wrote", vd_path)

set_horse(-1, 0)
for o in clothes:
    if o.name in CLOTH:
        cloth_show(o, -1, 0)                                # back to the bound item
body.is_holdout, body.hide_render = state["holdout"], state["body_hide"]
for o in clothes:
    o.hide_render = state["cloth"][o.name]
rig.animation_data.action, rig["uo_direction"] = state["action"], state["direction"]
rig.data.pose_position = state["pose"]
print("done ->", root)
