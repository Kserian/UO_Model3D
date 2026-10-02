# Put the materials of an item (typically a free model brought in by uo_import_item.py) into the UO look: every material slot is wired to the node group
# "UO_Look" (UO light: albedo x (ambient + diffuse * max(N.L, 0)), flat, no gloss, no reflections), with the colour the model's own material had.
# A foreign model brings PBR materials (metal, roughness, normal maps, emission, environment reflections) that UO sprites do not have; rendered as they
# are they come out with the wrong brightness and with highlights that no UO item shows. What this script keeps from the material:
#   - the colour: whatever feeds "Base Color" of the Principled BSDF (a texture, a colour attribute, a plain colour), or "Color" of a Diffuse / Emission node,
#     or the viewport colour of a material without nodes;
#   - the cut-out: whatever feeds "Alpha" (hair cards, lace, chains on a transparent texture) becomes transparency (a pixel is in the sprite when alpha >= 0.5);
# and drops the rest (metallic, roughness, normal / bump maps, emission, subsurface, coat): UO draws no such things. Normal maps are not baked into the
# geometry; a model that relies on them for its shape will look flatter than on its own.
# Run from Blender's Text Editor (Alt+P) after uo_import_item.py (the imported object is selected), or on the selected mesh objects of the scene. With nothing
# selected it takes every mesh object of the collection "Clothing". Idempotent: a material already wired to UO_Look is left alone.
#   SATURATION = 0 : grey item. In UO items that take a hue (a dye) are drawn in greys, so a dyeable shirt should be SATURATION = 0, BRIGHTNESS = 1.
import bpy

SATURATION = 1.0      # 1 = the model's colours, 0 = greys only (an item the game tints with a hue), in between = washed out
BRIGHTNESS = 1.0      # multiplier of the albedo (UO items are rarely darker than 0.15 or lighter than 0.9; the light is 0.08 + 0.92 cos)
CLAMP = True          # albedo kept between 0.02 and 0.98 (sprites have neither pure black nor pure white, the 1-px outline is added by the renderer)
ALPHA = True          # keep transparency from the model's Alpha input (False = opaque)
REPORT = True

OUTPUT_TYPES = ("OUTPUT_MATERIAL",)


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
    ci = node.inputs[cn]
    col = ci.links[0].from_socket if ci.links else None
    default = tuple(ci.default_value) if not ci.links else None
    asock, aval = None, 1.0
    if an and ALPHA:
        ai = node.inputs[an]
        asock = ai.links[0].from_socket if ai.links else None
        aval = ai.default_value if not ai.links else 1.0
    return col, default, asock, aval


def convert(mat, ng):
    """rewire `mat` to UO_Look; returns a short description"""
    if mat is None:
        return None
    if not mat.use_nodes:
        d = tuple(mat.diffuse_color)
        mat.use_nodes = True
        nt = mat.node_tree
        col, default, asock, aval = None, d, None, 1.0
    else:
        nt = mat.node_tree
        if any(n.type == "GROUP" and n.node_tree == ng for n in nt.nodes):
            return "%s: already UO_Look" % mat.name
        col, default, asock, aval = find_colour_source(nt)
    out = next((n for n in nt.nodes if n.type in OUTPUT_TYPES and n.is_active_output), None) or next((n for n in nt.nodes if n.type in OUTPUT_TYPES), None)
    if out is None:
        out = nt.nodes.new("ShaderNodeOutputMaterial")
    where = out.location.x - 300, out.location.y
    grp = nt.nodes.new("ShaderNodeGroup"); grp.node_tree = ng; grp.label = "UO_Look"; grp.location = (where[0], where[1])
    how = "colour"
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
        mapx.inputs[1].default_value = (0.98, 0.98, 0.98)
        if cur is not None:
            nt.links.new(cur, mapr.inputs[0])
        else:
            mapr.inputs[0].default_value = grp.inputs["Albedo"].default_value[:3]
        nt.links.new(mapr.outputs["Vector"], mapx.inputs[0])
        cur = mapx.outputs["Vector"]
    if cur is not None:
        nt.links.new(cur, grp.inputs["Albedo"])
    shader = grp.outputs["Shader"]
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
