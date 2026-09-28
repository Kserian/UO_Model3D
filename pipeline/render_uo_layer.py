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


sc = bpy.context.scene
rig = bpy.data.objects["UO_Rig"]
body = bpy.data.objects["UO_Body"]
clothes = [o for o in bpy.data.collections[CLOTHING].all_objects if o.type == "MESH"] if CLOTHING in bpy.data.collections else []
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
             action=rig.animation_data.action, direction=rig.get("uo_direction", 0))
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


def body_coverage():
    """pixels covered by the (deformed) body mesh through UO_Camera, pixel-centre rule (like the EXACT render)"""
    rig.update_tag(); body.update_tag(); bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = body.evaluated_get(dg); me = ev.to_mesh()
    co = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
    me.calc_loop_triangles()
    tri = np.empty(len(me.loop_triangles) * 3, np.int32); me.loop_triangles.foreach_get("vertices", tri); tri = tri.reshape(-1, 3)
    Mw = np.array(ev.matrix_world)
    ev.to_mesh_clear()
    cam = sc.camera.evaluated_get(dg)
    M = np.array(cam.calc_matrix_camera(dg, x=136, y=120)) @ np.array(cam.matrix_world.inverted()) @ Mw
    h = np.c_[co, np.ones(len(co))] @ M.T
    ndc = h[:, :2] / h[:, 3:4]
    P = np.stack([(ndc[:, 0] + 1) * 0.5 * 136, (1 - ndc[:, 1]) * 0.5 * 120], 1)[tri]
    img = np.zeros((120, 136), bool)
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
    return img


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
            orig = original(a, i, d) if EXACT_ANY else None
            orig_m = orig[..., 3] > 0 if orig is not None else None
            if LAYER == "body" and EXACT_BODY and orig is not None:
                rgba = orig                                    # the original UO body frame, pixel for pixel
            elif LAYER == "clothing":
                px = render_frame(a, i, d, "holdout")
                if EXACT_BODY and orig is not None:
                    px = exact_clothing(px, render_frame(a, i, d, "hidden"), orig_m, body_coverage())
                rgba = uo_post(px)
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
body.is_holdout, body.hide_render = state["holdout"], state["body_hide"]
for o in clothes:
    o.hide_render = state["cloth"][o.name]
rig.animation_data.action, rig["uo_direction"] = state["action"], state["direction"]
print("done ->", root)
