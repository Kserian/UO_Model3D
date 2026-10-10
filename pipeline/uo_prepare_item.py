# One step from an imported item to a skinned one, with the settings of its SLOT: uo_autofit_item.py -> uo_densify_item.py -> uo_fit_item.py -> uo_bind_item.py.
# Select the item (after uo_import_item.py), set KIND (the slot) and run (Alt+P). What each slot gets, and why:
#   mesh density   uo_densify_item.py EDGE_BY_KIND: a low-poly item is subdivided (shape unchanged) to the mean edge length the slot needs, so that it
#                  bends smoothly at elbows / knees / hips and no face is bigger than the gap to the skin. Rigid slots (hair, beard, hat) are not densified:
#                  they do not bend.
#   distance       uo_fit_item.py GAP_BY_KIND: how far from the skin (tight cloth 1.5 cm, armour / helmets / sleeves 3 cm).
#   skinning       uo_bind_item.py PART: which bones the item follows (and RIGID presets: hair on the head).
# The settings are measured where noted in the scripts (docs/qa/slot_geometry.md); weights stay "as the skin under the item" (SMOOTH 4, STIFF 1): the originals
# do not tell another policy from it (docs/qa/bind_sweep.json: SMOOTH 0..12 and STIFF 0.5..4 change the IoU with the sprites by +-0.002 at most).
import json
import os
import re
import bpy

KIND = "shirt"        # slot: shirt, plate, arms, pants, legs, boots, gloves, helm, neck, hair, beard, hat, robe, skirt, harness, waist, vest, quiver
AUTOFIT = True        # first uo_autofit_item.py: units, size and place from the skin the slot covers (False: the item already stands where it should)
DENSIFY = True        # False: keep the mesh as it is
FIT = True            # False: skip uo_fit_item.py (the item already sits right)
HEM = None            # m: a robe / skirt that is longer than the body (made on a taller mannequin) has its part below HEM_FROM shortened (uniformly, folds and embroidery squeezed) so that the hem lands this high above the ground
                      # (the original robes end at 0.0-0.2 m; a hem below the ground would hang under the feet of the sprite). None = leave. Recipe: "prepare": {"HEM": 0.02}
HEM_FROM = 0.70       # m: the shortening starts here (the sleeves of the model end above it)
HEM_BAND = None       # {"height": 0.09, "fade": 0.02, "skip_front": 20, "edge": 5}: a gold band along the whole hem (an embroidered band that the model has only on some panels breaks off
                      # between the legs in the sprites): up to `height` m above the LOCAL hem (lowest point per angle around the skirt), fading over `fade` m, none within `skip_front`
                      # degrees of the front (-Y; the opening of a robe, soft over `edge` degrees). Point attribute uo_hem_band + the item's material mixes in the gold of its own texture
                      # (mottled like embroidery; texels already gold are kept). docs/qa/robe_black.md. Recipe: "prepare": {"HEM_BAND": {...}}
PART = None           # skin weights of uo_bind_item.py: None = those of the slot (SLOTS below); e.g. "torso" for a cuirass whose pauldrons are a separate part (stays on pelvis / spine / chest / neck, does not stretch with the arms)

# KIND -> (PART of uo_bind_item.py, densify?, class). class: "tight" (cloth / leather close to the skin), "hard" (armour, thick: keeps its distance, 3 cm),
# "rigid" (one bone). Same parts as EXTENTS of uo_import_item.py.
SLOTS = {
    "shirt":  ("chest", True, "tight"), "pants": ("legs", True, "tight"), "boots": ("boots", True, "tight"), "gloves": ("gloves", True, "tight"),
    "plate":  ("chest", True, "hard"),  "arms":  ("arms", True, "hard"),  "legs":  ("legs", True, "hard"),   "helm":   ("helm", True, "hard"),
    "neck":   ("neck", True, "hard"),
    "robe":   ("robe", True, "loose"), "skirt": ("skirt", True, "loose"), "cloak": ("cloak", True, "loose"),
    "waist":  ("belt", True, "tight"), "vest": ("chest", True, "tight"),   # belt / sash (Waist), waistcoat / doublet (MiddleTorso): measured ranges, settings by analogy (docs/qa/autofit.md)
    "harness": ("torso", True, "tight"),   # straps over the trunk (follow pelvis / spine / chest / neck only)
    "quiver": ("quiver", False, "rigid"),  # a quiver, a sword on the back: rigid on the chest (custom properties uo_no_body_gap, uo_behind_torso: render_uo_layer.py)
    "hair":   ("hair", False, "rigid"), "beard": ("beard", False, "rigid"), "hat":   ("hat", False, "rigid"),
}


def source(name):
    """the script's text: from the folder UO_SCRIPTS when that is set (development, tests, uo_make_item.py), else the copy inside the .blend, else ../pipeline"""
    env = os.environ.get("UO_SCRIPTS")
    if env and os.path.exists(os.path.join(env, name)):
        return open(os.path.join(env, name), encoding="utf-8").read()
    t = bpy.data.texts.get(name)
    if t is not None:
        return t.as_string()
    here = env or os.path.dirname(os.path.abspath(bpy.data.filepath)) + "/../pipeline"
    return open(os.path.join(here, name), encoding="utf-8").read()


EXTRA = json.loads(os.environ.get("UO_PREPARE_EXTRA", "{}"))     # {"uo_fit_item.py": {"MIN_GAP": 0.02}, ...}: settings for the steps (uo_make_item.py "tune")


def run(name, **over):
    over = dict(EXTRA.get(name, {}), **over)
    text = source(name)
    for k, v in over.items():
        text, n = re.subn(r"^%s\s*=.*$" % k, "%s = %r" % (k, v), text, count=1, flags=re.M)
        assert n == 1, (name, k)
    exec(compile(text, name, "exec"), {"__name__": "__main__"})


if KIND not in SLOTS:
    raise ValueError("KIND must be one of %s" % list(SLOTS))
_part, _dens, _cls = SLOTS[KIND]
_part = PART or _part
print("uo_prepare_item: KIND %s -> PART %s, class %s" % (KIND, _part, _cls))
try:
    import scipy                                      # noqa: F401
    _scipy = True
except ImportError:
    _scipy = False
if AUTOFIT and not _scipy:
    print("uo_prepare_item: scipy is not installed in this Python: no fit to the skin (uo_autofit_item.py); the item stays where uo_import_item.py put it")
elif AUTOFIT:
    run("uo_autofit_item.py", KIND=KIND)
if HEM is not None:                                   # after the autofit the mesh holds world coordinates (the object's own transform is the identity)
    import numpy as np
    _obs = [o for o in bpy.context.selected_objects if o.type == "MESH" and o.name != "UO_Body"]
    _co = {o: np.empty(len(o.data.vertices) * 3, np.float32) for o in _obs}
    for o in _obs:
        o.data.vertices.foreach_get("co", _co[o])
    _zmin = float(min(c[2::3].min() for c in _co.values()))
    if _zmin < HEM - 1e-3:
        _k = (HEM_FROM - HEM) / (HEM_FROM - _zmin)
        for o, c in _co.items():
            z = c[2::3]; low = z < HEM_FROM
            z[low] = HEM_FROM - (HEM_FROM - z[low]) * _k
            o.data.vertices.foreach_set("co", c); o.data.update()
        print("uo_prepare_item: HEM: the part below %.2f m shortened x%.2f, the hem was at %.3f m, now %.3f m" % (HEM_FROM, _k, _zmin, HEM))
if DENSIFY and _dens:
    run("uo_densify_item.py", KIND=KIND)
if FIT:
    run("uo_fit_item.py", KIND=KIND)
run("uo_bind_item.py", PART=_part)


def hem_band(obs, cfg):
    """HEM_BAND: the weight uo_hem_band per vertex and the gold mixed in by it in the materials of `obs`"""
    import numpy as np
    cfg = dict(dict(height=0.09, fade=0.02, skip_front=0.0, edge=5.0, bins=36, noise=30.0, color=None), **cfg)
    co = {}
    for o in obs:
        c = np.empty(len(o.data.vertices) * 3, np.float32); o.data.vertices.foreach_get("co", c)
        M = np.array(o.matrix_world); co[o] = c.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
    allc = np.concatenate(list(co.values()))
    z0 = allc[:, 2].min(); sk = allc[allc[:, 2] < z0 + 0.3]
    cx, cy = sk[:, 0].mean(), sk[:, 1].mean()
    B = int(cfg["bins"]); step = 360.0 / B
    ang = lambda p: np.degrees(np.arctan2(p[:, 0] - cx, -(p[:, 1] - cy)))          # 0 = the front (-Y)
    a = ang(allc); b = ((a + 180) / step).astype(int) % B
    zb = np.full(B, np.nan)
    for i in range(B):
        m = (b == i) & (allc[:, 2] < HEM_FROM)
        if m.any():
            zb[i] = allc[m, 2].min()
    ok = ~np.isnan(zb)                                                               # empty bins: from their neighbours (circular)
    zb = np.interp(np.arange(B), np.nonzero(ok)[0], zb[ok], period=B)
    zb = (np.roll(zb, 1) + 2 * zb + np.roll(zb, -1)) / 4
    cen = -180 + step * (np.arange(B) + 0.5)
    lines = []
    for o, p in co.items():
        ap = ang(p)
        h = p[:, 2] - np.interp(ap, cen, zb, period=360)
        w = np.clip(1 - (h - cfg["height"]) / max(cfg["fade"], 1e-4), 0, 1)
        if cfg["skip_front"] > 0:
            w *= np.clip((np.abs(ap) - cfg["skip_front"]) / max(cfg["edge"], 1e-3), 0, 1)
        w[p[:, 2] > HEM_FROM] = 0
        at = o.data.attributes.get("uo_hem_band") or o.data.attributes.new(name="uo_hem_band", type="FLOAT", domain="POINT")
        at.data.foreach_set("value", w.astype(np.float32)); o.data.update()
        lines.append("%s: %.0f%% of the vertices in the band" % (o.name, 100 * (w > 0.5).mean()))
        for m in {sl.material for sl in o.material_slots if sl.material is not None}:
            lines.append(band_material(m, cfg))
    print("uo_prepare_item: HEM_BAND %.3f m above the hem (%.3f-%.3f m), front opening %.0f deg kept: %s" % (cfg["height"], zb.min(), zb.max(), cfg["skip_front"], "; ".join(lines)))


def band_material(m, cfg):
    """mix the gold of the material's own texture into its albedo by the attribute uo_hem_band (texels already gold kept)"""
    import numpy as np
    nt = m.node_tree
    if nt is None or any(n.name == "uo_hem_band" for n in nt.nodes):
        return "%s: no change" % m.name
    grp = next((n for n in nt.nodes if n.type == "GROUP" and n.node_tree and n.node_tree.name.startswith("UO_Look")), None)
    if grp is None or not grp.inputs["Albedo"].links:
        return "%s: no UO_Look with a texture" % m.name
    src = grp.inputs["Albedo"].links[0].from_socket
    col = cfg["color"]
    if col is None:                                                      # the texture's gold: saturated yellow / orange texels (as GREY_CLOTH of uo_materials.py)
        im = next((n.image for n in nt.nodes if n.type == "TEX_IMAGE" and n.image is not None), None)
        if im is None:
            return "%s: no texture, no gold" % m.name
        px = np.empty(im.size[0] * im.size[1] * 4, np.float32); im.pixels.foreach_get(px); rgb = px.reshape(-1, 4)[:, :3].astype(np.float64)
        mx = rgb.max(1); mn = rgb.min(1); d = np.maximum(mx - mn, 1e-9); r, g, bb = rgb.T
        sat = np.where(mx > 1e-6, d / np.maximum(mx, 1e-6), 0)
        hue = np.where(mx == r, ((g - bb) / d) % 6, np.where(mx == g, (bb - r) / d + 2, (r - g) / d + 4)) / 6.0
        gold = (sat > 0.3) & (hue > 0.04) & (hue < 0.2) & (mx > 0.15)
        if gold.sum() < 50:
            return "%s: no gold in the texture" % m.name
        lum = rgb[gold] @ np.array([0.299, 0.587, 0.114]); mean = rgb[gold].mean(0); ml = lum.mean()
        dark, light = mean * np.percentile(lum, 20) / ml, mean * np.percentile(lum, 80) / ml
        if im.colorspace_settings.name == "sRGB":                        # Image.pixels of an sRGB image are sRGB-encoded, the node colours are linear
            lin = lambda c: np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
            dark, light = lin(dark), lin(light)
    else:
        dark = light = np.array(col[:3], float)
    N = nt.nodes; L = nt.links; x, y = grp.location.x - 260, grp.location.y - 360
    at = N.new("ShaderNodeAttribute"); at.name = "uo_hem_band"; at.attribute_type = "GEOMETRY"; at.attribute_name = "uo_hem_band"; at.location = (x - 600, y)
    sep = N.new("ShaderNodeSeparateColor"); sep.mode = "HSV"; sep.location = (x - 600, y - 180); L.new(src, sep.inputs[0])
    keep = N.new("ShaderNodeMapRange"); keep.location = (x - 420, y - 180); keep.clamp = True
    keep.inputs["From Min"].default_value, keep.inputs["From Max"].default_value = 0.17, 0.33       # saturation of the texel: gold already -> the band leaves it
    keep.inputs["To Min"].default_value, keep.inputs["To Max"].default_value = 1.0, 0.0
    L.new(sep.outputs[1], keep.inputs["Value"])
    fac = N.new("ShaderNodeMath"); fac.operation = "MULTIPLY"; fac.location = (x - 240, y); L.new(at.outputs["Fac"], fac.inputs[0]); L.new(keep.outputs["Result"], fac.inputs[1])
    tc = N.new("ShaderNodeTexCoord"); tc.location = (x - 780, y - 380)
    noi = N.new("ShaderNodeTexNoise"); noi.location = (x - 600, y - 380); noi.inputs["Scale"].default_value = cfg["noise"]; noi.inputs["Detail"].default_value = 2.0
    L.new(tc.outputs["Object"], noi.inputs["Vector"])                    # mottled like the embroidery (light and dark gold of the texture)
    nr = N.new("ShaderNodeMapRange"); nr.location = (x - 420, y - 380); nr.clamp = True
    nr.inputs["From Min"].default_value, nr.inputs["From Max"].default_value = 0.35, 0.65
    L.new(noi.outputs["Fac"], nr.inputs["Value"])
    gc = N.new("ShaderNodeMix"); gc.data_type = "RGBA"; gc.location = (x - 240, y - 380)
    gc.inputs[6].default_value = (*dark, 1.0); gc.inputs[7].default_value = (*light, 1.0); L.new(nr.outputs["Result"], gc.inputs[0])
    mix = N.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.location = (x, y)
    L.new(fac.outputs["Value"], mix.inputs[0]); L.new(src, mix.inputs[6]); L.new(gc.outputs[2], mix.inputs[7])
    L.new(mix.outputs[2], grp.inputs["Albedo"])
    return "%s: gold %s-%s" % (m.name, "(%.2f %.2f %.2f)" % tuple(dark), "(%.2f %.2f %.2f)" % tuple(light))


if HEM_BAND:
    hem_band([o for o in bpy.context.selected_objects if o.type == "MESH" and o.name != "UO_Body"], HEM_BAND)
if KIND == "waist":                                    # a belt is a ring: the half behind the torso is hidden by it in the clothing layer (render_uo_layer.py TORSO_HIDE_MARGIN), otherwise the client draws it over the chest
    for _o in bpy.context.selected_objects:
        if _o.type == "MESH" and _o.name != "UO_Body":
            _o["uo_behind_torso"] = 1
# Cloth and leather keep the dark details of their texture (laces, buttons, stitches): the renderer's DESPECKLE (single dark pixels inside the item) is meant for sculpted
# armour (rivets, deep folds) and removed the front closure of a gambeson. Hard items keep it; "tune": {"scene": {"uo_despeckle": 0}} in a recipe overrides.
_dsp = EXTRA.get("scene", {}).get("uo_despeckle", 0 if _cls in ("tight", "loose") else None)
if _dsp is not None:
    _sc = bpy.context.scene
    _sc["uo_despeckle"] = min(int(_dsp), int(_sc["uo_despeckle"])) if "uo_despeckle" in _sc else int(_dsp)
    print("uo_prepare_item: renderer DESPECKLE %d (scene property uo_despeckle)" % _sc["uo_despeckle"])
