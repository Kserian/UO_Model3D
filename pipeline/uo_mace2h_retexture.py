"""Mace2H item blend -> a blend ready to render: the scene properties of a recipe (mace2h.json = version 1, mace2h_staff.json = version 2) and the textures of the original model
with steel ONLY where the original has steel.

    blender -b --python uo_mace2h_retexture.py -- IN.blend RECIPE.json OUT.blend [TEX_DIR]     (or: python uo_mace2h_retexture.py IN.blend RECIPE.json OUT.blend [TEX_DIR] with bpy installed)

TEX_DIR holds tex_Image_0.png (base colour) and tex_Image_1.png (glTF metallic-roughness: blue = metallic) of the .glb (512 px, not in the repo). Without TEX_DIR only the recipe's scene
properties are set. What it does to the material of the weapon:
  - the metal map of the original (blue channel, 0 / 1) says what is steel; the colour texture is rebuilt at 256 px with every class averaged on its own (a wooden texel never gets the grey
    of the steel next to it in the atlas), the wood made browner (saturation x 1.7: the original's wood is a grey-brown that read as grey), both textures sampled with "Closest";
  - the metal highlight of uo_materials.py (a Phong lobe) is multiplied by that metal map: the haft is matte wood, only the ball, spikes, collar, rings and pommel shine.
"""
import json, sys
import bpy
import numpy as np

a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
src, rec, out = a[0], a[1], a[2]
tex = a[3] if len(a) > 3 else None
bpy.ops.wm.open_mainfile(filepath=src)
sc = bpy.context.scene
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
    hsv = np.array(Image.fromarray((np.clip(wood, 0, 1) * 255).astype(np.uint8)).convert("HSV")).astype(np.float32)
    hsv[..., 1] = np.clip(hsv[..., 1] * 1.7, 0, 255)
    wood = np.array(Image.fromarray(hsv.astype(np.uint8), "HSV").convert("RGB")).astype(np.float32) / 255.0
    m_small = down(metal[..., None].astype(np.float32))[..., 0] > 0.5
    col = np.where(m_small[..., None], steel, wood)
    img0, img1 = bpy.data.images["Image_0"], bpy.data.images["Image_1"]
    for im, data in ((img0, np.dstack([col, np.ones((N, N, 1), np.float32)])),
                     (img1, np.dstack([np.ones((N, N), np.float32), np.full((N, N), 0.8, np.float32), m_small.astype(np.float32), np.ones((N, N), np.float32)]))):
        im.scale(N, N)
        im.pixels.foreach_set(data[::-1].reshape(-1).astype(np.float32))                  # Blender images are bottom-up
        im.update()
    for m in bpy.data.materials:
        if m.node_tree is None:
            continue
        for n in m.node_tree.nodes:
            if n.type == "TEX_IMAGE" and n.image in (img0, img1):
                n.interpolation = "Closest"
        sep = next((n for n in m.node_tree.nodes if n.type == "SEPARATE_COLOR"), None)
        ml = next((n for n in m.node_tree.nodes if n.type == "MATH" and n.operation == "MULTIPLY" and n.name == "Math.002"), None)
        if sep is not None and ml is not None:
            m.node_tree.links.new(sep.outputs["Blue"], ml.inputs[1])                      # the highlight only where the original has metal
bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
print("saved", out)
