# Put the materials of an item (typically a free model brought in by uo_import_item.py) into the UO look: every material slot is wired to the node group
# "UO_Look" (UO light: albedo x (ambient + diffuse * max(N.L, 0)), flat, no gloss, no reflections), with the colour the model's own material had.
# A foreign model brings PBR materials (metal, roughness, normal maps, emission, environment reflections); rendered as they are they come out with the wrong
# brightness and with reflections of an environment that UO does not have. UO metal (plate, helms, shields) is NOT matte, though: measured on the original
# sprites (plate 527, helm 563 against the same shape lit by UO_Look) it has a bright highlight where the surface faces the light/camera (the light sits at
# the camera), absent from cloth (trousers 431: brightest pixel 90/255, plate 252/255). So metal gets a Phong-like lobe on top of the UO light.
# What this script keeps from the material:
#   - the colour: whatever feeds "Base Color" of the Principled BSDF (a texture, a colour attribute, a plain colour), or "Color" of a Diffuse / Emission node,
#     or the viewport colour of a material without nodes;
#   - the cut-out: whatever feeds "Alpha" (hair cards, lace, chains on a transparent texture) becomes transparency (a pixel is in the sprite when alpha >= 0.5);
#   - metal: a material with Metallic >= METAL_AT (or METAL = True) gets the highlight  SPEC_STRENGTH * albedo * max(N.L, 0) ^ SPEC_POWER  added to the UO light;
# and drops the rest (roughness, normal / bump maps, emission, subsurface, coat, environment reflections): UO draws no such things. Normal maps are not baked into the
# geometry; a model that relies on them for its shape will look flatter than on its own.
# Run from Blender's Text Editor (Alt+P) after uo_import_item.py (the imported object is selected), or on the selected mesh objects of the scene. With nothing
# selected it takes every mesh object of the collection "Clothing". Idempotent: a material already wired to UO_Look is left alone.
#   SATURATION = 0 : grey item. In UO items that take a hue (a dye) are drawn in greys, so a dyeable shirt should be SATURATION = 0, BRIGHTNESS = 1.
import bpy
import numpy as np

SATURATION = 1.0      # 1 = the model's colours, 0 = greys only (an item the game tints with a hue), in between = washed out
BRIGHTNESS = 1.0      # multiplier of the albedo (UO items are rarely darker than 0.15 or lighter than 0.9; the light is 0.08 + 0.92 cos)
CLAMP_MAX = 0.98      # upper limit of the albedo when CLAMP (linear; a lit face renders at sRGB(albedo): 0.98 = 250/255, 0.5 = 188, 0.22 = 130). A grey that must never look white (a blade): 0.22-0.3
CLAMP = True          # albedo kept between 0.02 and CLAMP_MAX (0.98) (sprites have neither pure black nor pure white, the 1-px outline is added by the renderer)
ALPHA = True          # keep transparency from the model's Alpha input (False = opaque)
METAL = None          # None = metal where the model's Metallic >= METAL_AT, True = every material is metal (plate), False = none (cloth, leather)
METAL_AT = 0.5
SPEC_STRENGTH = 1.0   # highlight = SPEC_STRENGTH * albedo * max(N.L, 0) ^ SPEC_POWER, added to the UO light (linear light; the metal tints its own highlight).
SPEC_POWER = 16       # Measured on the metal-named wearable animations of the client (light_items.py, 41 animations, body normals as the proxy): mail / ring / chain
                      # SPEC_STRENGTH 0.7, power 11; the brightest quartile (plate, helms) 2.0, power 19; cloth and leather: Lambert only (0.3, no better than none).
                      # 1.0 / 16 is in between; use 2.0 / 19 for shiny plate, 0.7 / 11 for mail. Docs: docs/qa/light_shadow.md
TEXTURE_PX = 0        # > 0: a texture larger than this (px, the longer side) is scaled down to it: a fine weave or noise texture rendered at 36 px/m aliases into white speckles, which UO cloth does not have
                      # (the colour of the cloth is its average); 0 = leave the textures. A recipe of uo_make_item.py: "materials": {"TEXTURE_PX": 64}. Do not use for cut-out textures (hair cards, lace).
TEXTURE_FILTER = True # box-average every colour / normal texture that is finer than the sprite (more than FILTER_TEXELS_PER_M texels per metre of the item): at one sample per pixel
                      # a 1 m coat on a 1024 px texture is sampled every ~25th texel and comes out as noise, and the thin dark details (laces, buttons, stitches) appear and disappear
                      # from frame to frame. Averaged, they stay as one soft dark pixel line. Skipped for cut-out textures (Alpha used) and for small textures.
FILTER_TEXELS_PER_M = 54.0   # = 1.5 texels per UO pixel (36 px/m)
NORMAL_MAP = True     # a normal map of the model lights the item (UO_Look_N: the UO light on the mapped normal): weave, folds and raised straps give the shading the flat shell lacks.
                      # False = the old behaviour (the map is dropped). The map is filtered like the colour (renormalised)
NORMAL_STRENGTH = 1.0
SHADOW = 0.4          # own shadow (docs/qa/light_shadow.md: the UO sprites are lit  S = ambient + (1 - ambient) * c * s  in the shade of the body / of the item itself, s = 0.4 measured):
                      # the item gets s of the light as emission (no shadow) and 1 - s as a diffuse BSDF lit by a Sun with the UO light direction that casts shadows (render_uo_layer.py makes
                      # the Sun). Folds, a sleeve over the chest, an arm over the coat get their shade. 0 = off (UO_Look: Lambert, no shadows)
FLAT_GREY = None      # 0..1: one plain grey instead of the model's colours and textures (an item the game tints with a hue: a sword, a blade; 0.55 = mid grey, the hue then shows). None = the model's colour
FLAT_COLOR = None     # (r, g, b) linear 0..1: one plain colour instead of the model's colours and textures (e.g. a leather grip (0.5, 0.28, 0.12)); wins over FLAT_GREY
REPORT = True

_metallic = 0.0
OUTPUT_TYPES = ("OUTPUT_MATERIAL",)


def linked_mean(sock):
    """mean value of what feeds a scalar input: a channel of an image (Separate Color) or an image's colour; 1.0 when it cannot be told"""
    if not sock.links:
        return float(sock.default_value)
    node, out = sock.links[0].from_node, sock.links[0].from_socket
    img, ch = None, None
    if node.type == "SEPARATE_COLOR" and node.inputs["Color"].links and node.inputs["Color"].links[0].from_node.type == "TEX_IMAGE":
        img, ch = node.inputs["Color"].links[0].from_node.image, {"Red": 0, "Green": 1, "Blue": 2}.get(out.name)
    elif node.type == "TEX_IMAGE":
        img, ch = node.image, 0
    if img is None or ch is None or img.type != "IMAGE":
        return 1.0
    w, h = img.size
    px = np.empty(w * h * 4, np.float32); img.pixels.foreach_get(px)
    return float(px.reshape(-1, 4)[:, ch].mean())


def find_colour_source(nt):
    """(socket or None, default colour or None, alpha socket or None, default alpha) of the material's shader tree"""
    out = next((n for n in nt.nodes if n.type in OUTPUT_TYPES and n.is_active_output), None) or next((n for n in nt.nodes if n.type in OUTPUT_TYPES), None)
    if out is None or not out.inputs["Surface"].links:
        return None, None, None, 1.0
    node = out.inputs["Surface"].links[0].from_node
    seen = set()
    while node.type in ("MIX_SHADER", "ADD_SHADER", "GROUP") and node not in seen:      # first shader that carries a colour
        seen.add(node)
        ins = [i for i in node.inputs if i.type == "SHADER" and i.links]
        if not ins:
            break
        node = ins[0].links[0].from_node
    names = {"BSDF_PRINCIPLED": ("Base Color", "Alpha"), "BSDF_DIFFUSE": ("Color", None), "EMISSION": ("Color", None), "BSDF_TOON": ("Color", None),
             "BSDF_GLOSSY": ("Color", None), "BSDF_TRANSLUCENT": ("Color", None), "SUBSURFACE_SCATTERING": ("Color", None), "BSDF_SHEEN": ("Color", None)}
    if node.type not in names:
        return None, None, None, 1.0
    cn, an = names[node.type]
    global _metallic
    _metallic = node.inputs["Metallic"].default_value if node.type == "BSDF_PRINCIPLED" and not node.inputs["Metallic"].links else \
        (linked_mean(node.inputs["Metallic"]) if node.type == "BSDF_PRINCIPLED" else 0.0)       # a Metallic fed by a texture: its mean (cloth with a metallicRoughness map is not metal)
    ci = node.inputs[cn]
    col = ci.links[0].from_socket if ci.links else None
    default = tuple(ci.default_value) if not ci.links else None
    asock, aval = None, 1.0
    if an and ALPHA:
        ai = node.inputs[an]
        asock = ai.links[0].from_socket if ai.links else None
        aval = ai.default_value if not ai.links else 1.0
    return col, default, asock, aval


def add_highlight(nt, ng, shader, where, albedo, default):
    """shader + Emission(albedo * SPEC_STRENGTH * max(N.L, 0) ^ SPEC_POWER), L = the UO light of the node group (world space)"""
    ldir = next(n for n in ng.nodes if n.type == "COMBXYZ")                   # "UO light direction (world)"
    geo = nt.nodes.new("ShaderNodeNewGeometry"); geo.location = (where[0] - 600, where[1] - 420)
    lv = nt.nodes.new("ShaderNodeCombineXYZ"); lv.location = (where[0] - 600, where[1] - 600)
    for i in range(3):
        lv.inputs[i].default_value = ldir.inputs[i].default_value
    dot = nt.nodes.new("ShaderNodeVectorMath"); dot.operation = "DOT_PRODUCT"; dot.location = (where[0] - 400, where[1] - 480)
    mxn = nt.nodes.new("ShaderNodeMath"); mxn.operation = "MAXIMUM"; mxn.inputs[1].default_value = 0.0; mxn.location = (where[0] - 250, where[1] - 480)
    pw = nt.nodes.new("ShaderNodeMath"); pw.operation = "POWER"; pw.inputs[1].default_value = SPEC_POWER; pw.location = (where[0] - 120, where[1] - 480)
    em = nt.nodes.new("ShaderNodeEmission")
    if albedo is not None:
        nt.links.new(albedo, em.inputs["Color"])
    else:
        em.inputs["Color"].default_value = default
    em.location = (where[0] + 40, where[1] - 400)
    ml = nt.nodes.new("ShaderNodeMath"); ml.operation = "MULTIPLY"; ml.inputs[1].default_value = SPEC_STRENGTH; ml.location = (where[0] + 40, where[1] - 520)
    nt.links.new(geo.outputs["Normal"], dot.inputs[0]); nt.links.new(lv.outputs["Vector"], dot.inputs[1])
    nt.links.new(dot.outputs["Value"], mxn.inputs[0]); nt.links.new(mxn.outputs["Value"], pw.inputs[0])
    nt.links.new(pw.outputs["Value"], ml.inputs[0]); nt.links.new(ml.outputs["Value"], em.inputs["Strength"])
    add = nt.nodes.new("ShaderNodeAddShader"); add.location = (where[0] + 200, where[1] - 100)
    nt.links.new(shader, add.inputs[0]); nt.links.new(em.outputs["Emission"], add.inputs[1])
    return add.outputs["Shader"]


def normal_group(ng, shadow=0.0):
    """UO_Look with an extra input "Normal" (world space) in place of the interpolated normal of the Geometry node (the UO light on a mapped normal); with `shadow` > 0 also the own
    shadow: s = shadow of the light stays emission, the rest is a diffuse BSDF of the Sun that casts shadows (custom property uo_shadow of the group, read by render_uo_layer.py)"""
    name = "UO_Look_N" if shadow <= 0 else "UO_Look_NS"
    g = bpy.data.node_groups.get(name)
    if g is not None:
        return g
    g = ng.copy(); g.name = name
    g.interface.new_socket("Normal", in_out="INPUT", socket_type="NodeSocketVector")
    gi = next(n for n in g.nodes if n.type == "GROUP_INPUT")
    dot = next(n for n in g.nodes if n.type == "VECT_MATH" and n.operation == "DOT_PRODUCT")
    for l in list(g.links):
        if l.from_node.type == "NEW_GEOMETRY" and l.to_node == dot:
            g.links.remove(l)
    g.links.new(gi.outputs["Normal"], dot.inputs[0])
    if shadow > 0:
        ma = next(n for n in g.nodes if n.type == "MATH" and n.operation == "MULTIPLY_ADD")          # light = (1 - ambient) * c + ambient
        amb = ma.inputs[2].default_value
        ma.inputs[1].default_value = (1.0 - amb) * shadow                                            # emission: ambient + (1 - ambient) * s * c
        em = next(n for n in g.nodes if n.type == "EMISSION")
        df = g.nodes.new("ShaderNodeBsdfDiffuse"); df.location = (em.location.x, em.location.y - 200)
        g.links.new(gi.outputs["Albedo"], df.inputs["Color"]); g.links.new(gi.outputs["Normal"], df.inputs["Normal"])
        ad = g.nodes.new("ShaderNodeAddShader"); ad.location = (em.location.x + 200, em.location.y)
        g.links.new(em.outputs["Emission"], ad.inputs[0]); g.links.new(df.outputs["BSDF"], ad.inputs[1])
        go = next(n for n in g.nodes if n.type == "GROUP_OUTPUT")
        g.links.new(ad.outputs["Shader"], go.inputs["Shader"])
        g["uo_shadow"] = float(shadow); g["uo_ambient"] = float(amb)
    return g


def texel_density(ob, im):
    """texels per metre of the image on the object: sqrt(pixels * UV area / surface area)"""
    me = ob.data
    if not me.uv_layers:
        return None
    me.calc_loop_triangles()
    nt_ = len(me.loop_triangles)
    if nt_ == 0:
        return None
    tri = np.empty(nt_ * 3, np.int32); me.loop_triangles.foreach_get("loops", tri); tri = tri.reshape(-1, 3)
    tv = np.empty(nt_ * 3, np.int32); me.loop_triangles.foreach_get("vertices", tv); tv = tv.reshape(-1, 3)
    uv = np.empty(len(me.loops) * 2, np.float32); me.uv_layers.active.data.foreach_get("uv", uv); uv = uv.reshape(-1, 2)
    co = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3).astype(np.float64)
    co = co @ np.array(ob.matrix_world)[:3, :3].T
    a2 = lambda p, q, r: 0.5 * np.abs((q[:, 0] - p[:, 0]) * (r[:, 1] - p[:, 1]) - (q[:, 1] - p[:, 1]) * (r[:, 0] - p[:, 0]))
    uva = a2(uv[tri[:, 0]], uv[tri[:, 1]], uv[tri[:, 2]]).sum()
    sa = (0.5 * np.linalg.norm(np.cross(co[tv[:, 1]] - co[tv[:, 0]], co[tv[:, 2]] - co[tv[:, 0]]), axis=1)).sum()
    if uva <= 0 or sa <= 0:
        return None
    return float(np.sqrt(im.size[0] * im.size[1] * uva / sa))


def filter_textures(obs, lines):
    """box-average the item's textures down to FILTER_TEXELS_PER_M (see TEXTURE_FILTER)"""
    roles = {}
    for o in obs:
        for sl in o.material_slots:
            m = sl.material
            if m is None or not m.use_nodes:
                continue
            for n in m.node_tree.nodes:
                if n.type != "TEX_IMAGE" or n.image is None or n.image.type != "IMAGE":
                    continue
                if n.outputs["Alpha"].links:
                    roles[n.image] = "skip"; continue
                role = "normal" if any(l.to_node.type == "NORMAL_MAP" for l in n.outputs["Color"].links) else "colour"
                if roles.get(n.image) in (None, role):
                    roles[n.image] = role
                else:
                    roles[n.image] = "skip"                    # one image used both ways: left alone
                d = texel_density(o, n.image)
                if d is not None:
                    roles[(n.image, "d")] = min(d, roles.get((n.image, "d"), 1e9))
    for im, role in [(k, v) for k, v in roles.items() if not isinstance(k, tuple)]:
        d = roles.get((im, "d"))
        w, h = im.size
        if role == "skip" or d is None or max(w, h) <= 128:
            continue
        k = int(d // FILTER_TEXELS_PER_M)
        k = min(k, max(1, min(w, h) // 16))                      # never below 16 px
        if k < 2:
            continue
        w2, h2 = w // k, h // k
        px = np.empty(w * h * 4, np.float32); im.pixels.foreach_get(px)
        px = px.reshape(h, w, 4)[:h2 * k, :w2 * k].reshape(h2, k, w2, k, 4)
        if role == "normal":
            v = px[..., :3] * 2 - 1
            v = v.mean((1, 3)); v /= np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-6)
            px = np.concatenate([v * 0.5 + 0.5, px[..., 3:].mean((1, 3))], -1)
        else:
            px = px.mean((1, 3))
        im.scale(w2, h2); im.pixels.foreach_set(px.astype(np.float32).ravel()); im.update(); im.pack()
        lines.append("texture %s (%s, %.0f texels/m) %dx%d -> %dx%d (box average)" % (im.name, role, d, w, h, w2, h2))


def convert(mat, ng):
    """rewire `mat` to UO_Look; returns a short description"""
    global _metallic
    if mat is None:
        return None
    _metallic = 0.0
    if bpy.app.version < (5, 0, 0) and not mat.use_nodes:      # Blender 5: every material has a node tree (use_nodes is deprecated)
        d = tuple(mat.diffuse_color)
        mat.use_nodes = True
        nt = mat.node_tree
        col, default, asock, aval = None, d, None, 1.0
    else:
        nt = mat.node_tree
        if any(n.type == "GROUP" and n.node_tree.name in (ng.name, "UO_Look_N", "UO_Look_NS") for n in nt.nodes):
            return "%s: already UO_Look" % mat.name
        col, default, asock, aval = find_colour_source(nt)
    metallic = _metallic
    out = next((n for n in nt.nodes if n.type in OUTPUT_TYPES and n.is_active_output), None) or next((n for n in nt.nodes if n.type in OUTPUT_TYPES), None)
    if out is None:
        out = nt.nodes.new("ShaderNodeOutputMaterial")
    where = out.location.x - 300, out.location.y
    grp = nt.nodes.new("ShaderNodeGroup"); grp.node_tree = ng; grp.label = "UO_Look"; grp.location = (where[0], where[1])
    how = "colour"
    if FLAT_COLOR is not None:
        col, default = None, (*FLAT_COLOR, 1.0)
    elif FLAT_GREY is not None:
        col, default = None, (FLAT_GREY, FLAT_GREY, FLAT_GREY, 1.0)
    nmap = next((n for n in (nt.nodes if mat.use_nodes else []) if n.type == "NORMAL_MAP" and n.inputs["Color"].links), None) if NORMAL_MAP else None
    if nmap is not None or SHADOW > 0:                    # the model's normal map lights the item; the own shadow needs the Normal input too
        grp.node_tree = normal_group(ng, SHADOW)
        if nmap is not None:
            nmap.inputs["Strength"].default_value = NORMAL_STRENGTH
            nt.links.new(nmap.outputs["Normal"], grp.inputs["Normal"])
            how += " + normal map"
        else:
            geo = nt.nodes.new("ShaderNodeNewGeometry"); geo.location = (where[0] - 600, where[1] + 300)
            nt.links.new(geo.outputs["Normal"], grp.inputs["Normal"])
        if SHADOW > 0:
            how += " + own shadow %.2f" % SHADOW
    if col is None:
        grp.inputs["Albedo"].default_value = default if default is not None else (0.5, 0.5, 0.5, 1.0)
    # saturation / brightness / clamp between the colour and the light
    cur = col
    if SATURATION != 1.0 or BRIGHTNESS != 1.0:
        hs = nt.nodes.new("ShaderNodeHueSaturation"); hs.location = (where[0] - 220, where[1])
        hs.inputs["Saturation"].default_value = SATURATION; hs.inputs["Value"].default_value = BRIGHTNESS
        if cur is not None:
            nt.links.new(cur, hs.inputs["Color"])
        else:
            hs.inputs["Color"].default_value = grp.inputs["Albedo"].default_value
        cur = hs.outputs["Color"]
    if CLAMP:
        mapr = nt.nodes.new("ShaderNodeVectorMath"); mapr.operation = "MAXIMUM"; mapr.location = (where[0] - 440, where[1])
        mapr.inputs[1].default_value = (0.02, 0.02, 0.02)
        mapx = nt.nodes.new("ShaderNodeVectorMath"); mapx.operation = "MINIMUM"; mapx.location = (where[0] - 330, where[1])
        mapx.inputs[1].default_value = (CLAMP_MAX, CLAMP_MAX, CLAMP_MAX)
        if cur is not None:
            nt.links.new(cur, mapr.inputs[0])
        else:
            mapr.inputs[0].default_value = grp.inputs["Albedo"].default_value[:3]
        nt.links.new(mapr.outputs["Vector"], mapx.inputs[0])
        cur = mapx.outputs["Vector"]
    if cur is not None:
        nt.links.new(cur, grp.inputs["Albedo"])
    shader = grp.outputs["Shader"]
    if METAL or (METAL is None and metallic >= METAL_AT):             # before the cut-out, so that nothing glows where the item is transparent
        shader = add_highlight(nt, ng, shader, where, cur, grp.inputs["Albedo"].default_value)
        how += " + metal highlight"
    if ALPHA and (asock is not None or aval < 1.0):
        tr = nt.nodes.new("ShaderNodeBsdfTransparent"); tr.location = (where[0], where[1] - 160)
        mx = nt.nodes.new("ShaderNodeMixShader"); mx.location = (where[0] + 150, where[1])
        if asock is not None:
            nt.links.new(asock, mx.inputs["Fac"])
        else:
            mx.inputs["Fac"].default_value = aval
        nt.links.new(tr.outputs["BSDF"], mx.inputs[1]); nt.links.new(shader, mx.inputs[2])
        shader = mx.outputs["Shader"]
        how += " + alpha"
    nt.links.new(shader, out.inputs["Surface"])
    # blend mode of the viewport / Cycles material: cut-out
    try:
        mat.blend_method = "CLIP" if "alpha" in how else "OPAQUE"
    except Exception:
        pass
    return "%s: %s%s" % (mat.name, how, "" if col is not None else " (plain colour %s)" % ", ".join("%.2f" % c for c in grp.inputs["Albedo"].default_value[:3]))


def run():
    ng = bpy.data.node_groups.get("UO_Look")
    if ng is None:
        raise RuntimeError("node group UO_Look not found: open UO_Body_0x190.blend")
    obs = [o for o in bpy.context.selected_objects if o.type == "MESH" and o.name not in ("UO_Body",)]
    if not obs and "Clothing" in bpy.data.collections:
        obs = [o for o in bpy.data.collections["Clothing"].all_objects if o.type == "MESH"]
    done = set(); lines = []
    if TEXTURE_FILTER:
        filter_textures(obs, lines)
    if TEXTURE_PX > 0:
        used = {n.image for o in obs for sl in o.material_slots if sl.material and sl.material.use_nodes for n in sl.material.node_tree.nodes if n.type == "TEX_IMAGE" and n.image}   # only the item's own textures
        for im in used:
            w, h = im.size
            if im.type == "IMAGE" and max(w, h) > TEXTURE_PX:
                k = max(1, int(max(w, h) // TEXTURE_PX)); w2, h2 = w // k, h // k          # box average (image.scale does not filter: it would keep the speckles)
                px = np.empty(w * h * 4, np.float32); im.pixels.foreach_get(px)
                px = px.reshape(h, w, 4)[:h2 * k, :w2 * k].reshape(h2, k, w2, k, 4).mean((1, 3))
                im.scale(w2, h2); im.pixels.foreach_set(px.ravel()); im.update(); im.pack()                # packed: the saved .blend keeps the reduced pixels (an unpacked image is read again from its file)
                lines.append("texture %s %dx%d -> %dx%d (box average)" % (im.name, w, h, w2, h2))
    for o in obs:
        if not o.material_slots:
            o.data.materials.append(bpy.data.materials.new(o.name + "_Mat"))
            lines.append("%s: had no material, plain grey UO_Look added" % o.name)
        for sl in o.material_slots:
            if sl.material is None:
                sl.material = bpy.data.materials.new(o.name + "_Mat")
            m = sl.material
            if m.name in done:
                continue
            done.add(m.name)
            r = convert(m, ng)
            if r:
                lines.append(r)
    if REPORT:
        print("uo_materials: %d object(s), %d material(s)" % (len(obs), len(done)))
        for l in lines:
            print("   " + l)
    return lines


_result = run()
