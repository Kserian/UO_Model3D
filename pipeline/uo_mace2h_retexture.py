"""Mace2H item blend -> a blend ready to render: the scene properties of a recipe (mace2h.json = version 1, mace2h_staff.json = version 2) and the textures of the original model
with steel ONLY where the original has steel.

    blender -b --python uo_mace2h_retexture.py -- IN.blend RECIPE.json|- OUT.blend [TEX_DIR ]     (or: python uo_mace2h_retexture.py IN.blend RECIPE.json OUT.blend [TEX_DIR] with bpy installed)

TEX_DIR holds tex_Image_0.png (base colour) and tex_Image_1.png (glTF metallic-roughness: blue = metallic) of the .glb (512 px, not in the repo). Without TEX_DIR only the recipe's scene
properties are set. What it does to the material of the weapon:
  - the metal map of the original (blue channel, 0 / 1) says what is steel; the colour texture is rebuilt at 256 px with every class averaged on its own (a wooden texel never gets the grey
    of the steel next to it in the atlas), the wood of ONE brown (WOOD_COLOR) with the grain of the original's texture, both textures sampled with "Closest";
  - the metal highlight of uo_materials.py (a Phong lobe) is multiplied by that metal map: the haft is matte wood, only the ball, spikes, collar, rings and pommel shine.
"""
import json, sys
import bpy
import numpy as np

a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
src, rec, out = a[0], a[1], a[2]
tex = a[3] if len(a) > 3 else None
WOOD_COLOR = (0.36, 0.23, 0.13)    # sRGB of the wood (the original's wood is a dark grey-brown that rendered nearly black / grey); the item's BRIGHTNESS 2.1 and the UO light come on top
WOOD_GRAIN = 0.25                  # exponent of the texel's light / dark relative to the median of the wood texels (the grain)
STEEL_VALUE = 0.65                 # the steel of the original is lighter than the UO look wants (the ball came out almost white)
bpy.ops.wm.open_mainfile(filepath=src)
sc = bpy.context.scene
if rec != "-":                                                                    # "-": keep the scene properties the blend has (version 1 = item.blend of the work, whose properties are those of mace2h.json)
    for k, v in json.load(open(rec))["scene"].items():
        sc[k] = v
for k in ("uo_fist_report", "uo_staff_report"):
    if k in sc:
        del sc[k]
if tex:
    import os
    from PIL import Image
    from scipy import ndimage as ndi
    base = np.array(Image.open(os.path.join(tex, "tex_Image_0.png")).convert("RGB")).astype(np.float32) / 255.0
    mr = np.array(Image.open(os.path.join(tex, "tex_Image_1.png")).convert("RGB")).astype(np.float32) / 255.0
    metal = mr[..., 2] > 0.5
    N = 256; f = base.shape[0] // N

    def class_fill(col, mask):
        idx = ndi.distance_transform_edt(~mask, return_distances=False, return_indices=True)
        return col[idx[0], idx[1]]

    def down(x):
        return x.reshape(N, f, N, f, -1).mean((1, 3))
    wood = down(class_fill(base, ~metal)); steel = down(class_fill(base, metal))
    luma = wood.mean(2); med = np.median(luma[~(down(metal[..., None].astype(np.float32))[..., 0] > 0.5)])
    wood = np.clip(np.array(WOOD_COLOR, np.float32)[None, None, :] * (np.clip(luma, 0.05, None) / med)[..., None] ** WOOD_GRAIN, 0, 1)      # wood: ONE brown, the grain (light / dark) of the original's texture kept
    steel = np.clip(steel * STEEL_VALUE, 0, 1)
    img0 = bpy.data.images["Image_0"]
    for im, data in ((img0, np.dstack([wood, np.ones((N, N, 1), np.float32)])), ):
        im.scale(N, N)
        im.pixels.foreach_set(data[::-1].reshape(-1).astype(np.float32))                  # Blender images are bottom-up
        im.update(); im.pack()                                                              # a packed image is saved from its packed file, not from the changed buffer
    img_s = bpy.data.images.new("Image_steel", N, N)
    img_s.colorspace_settings.name = "sRGB"
    img_s.pixels.foreach_set(np.dstack([steel, np.ones((N, N, 1), np.float32)])[::-1].reshape(-1).astype(np.float32)); img_s.update(); img_s.pack()       # packed: a generated image is blank after the blend is reloaded
    # which vertices are steel: the UVs of the decimated item mix the islands of the atlas (10-30 % of the haft's vertices sat on steel texels), so the steel is placed by the ORIGINAL model's
    # profile along the axis instead (pommel and the ring above it, the ring at 0.40 m, the collar and the ball with its spikes), as the vertex attribute uo_metal (0 / 1)
    ob = next(o for o in bpy.data.objects if o.type == "MESH" and o.name.lower().startswith("mace"))
    me = ob.data
    V = np.empty(len(me.vertices) * 3); me.vertices.foreach_get("co", V); V = V.reshape(-1, 3)
    c = V.mean(0); _, _, vt = np.linalg.svd(V - c, full_matrices=False); t = (V - c) @ vt[0]
    rad = np.linalg.norm((V - c) - np.outer(t, vt[0]), axis=1)
    pommel_first = (rad[t > t.max() - 0.30] > 0.07).sum() > (rad[t < t.min() + 0.30] > 0.07).sum()    # the ball (more thick vertices) is at t.max: then s = 0 is the pommel end
    sm = (t - t.min()) if pommel_first else (t.max() - t)
    UO_METAL = [(0.0, 0.118), (0.368, 0.432), (0.935, 9.0)]                              # s ranges (m from the pommel end) of the item that are steel in the original: pommel + ring, ring, collar + ball
    metal_v = np.zeros(len(V), np.float32)
    for lo, hi in UO_METAL:
        metal_v[(sm >= lo) & (sm < hi)] = 1.0
    at = me.attributes.get("uo_metal") or me.attributes.new("uo_metal", "FLOAT", "POINT")
    at.data.foreach_set("value", metal_v)
    print("steel vertices %d of %d" % (metal_v.sum(), len(V)))
    for m in bpy.data.materials:
        if m.node_tree is None or not any(n.type == "TEX_IMAGE" and n.image == img0 for n in m.node_tree.nodes):
            continue
        nt = m.node_tree
        t0 = next(n for n in nt.nodes if n.type == "TEX_IMAGE" and n.image == img0)
        t0.interpolation = "Closest"
        ts = nt.nodes.new("ShaderNodeTexImage"); ts.image = img_s; ts.interpolation = "Closest"; ts.location = (t0.location.x, t0.location.y - 300)
        if t0.inputs["Vector"].links:
            nt.links.new(t0.inputs["Vector"].links[0].from_socket, ts.inputs["Vector"])
        att = nt.nodes.new("ShaderNodeAttribute"); att.attribute_name = "uo_metal"; att.attribute_type = "GEOMETRY"; att.location = (t0.location.x, t0.location.y - 600)
        mx = nt.nodes.new("ShaderNodeMix"); mx.data_type = "RGBA"; mx.blend_type = "MIX"; mx.location = (t0.location.x + 300, t0.location.y)
        outs = [l.to_socket for l in t0.outputs["Color"].links]
        nt.links.new(att.outputs["Fac"], mx.inputs["Factor"])
        nt.links.new(t0.outputs["Color"], mx.inputs["A"]); nt.links.new(ts.outputs["Color"], mx.inputs["B"])
        for so in outs:
            nt.links.new(mx.outputs["Result"], so)                                         # wood where uo_metal = 0, steel where 1: the wooden parts get the wood map whatever their UV hit
        ml = next((n for n in nt.nodes if n.type == "MATH" and n.operation == "MULTIPLY" and n.name == "Math.002"), None)
        if ml is not None:
            nt.links.new(att.outputs["Fac"], ml.inputs[1])                                 # the metal highlight only on the steel
bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
print("saved", out)
