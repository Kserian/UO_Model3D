# Heal the dark smudges on the heads (membranes) of a drum: the texture baked from a high-poly original (uo_import_item.py BAKE_TEXTURE) has black blotches where the rays of the bake hit the inside of the
# hoop / missed; they have no counterpart in the model's own render. Run on the SELECTED drum, in the model's own frame (axis along Y), after uo_materials.py (which averages the baked image to the resolution of the sprite).
#   1. The head faces: faces whose normal looks along the axis, at the two ends of it, inside the radius of the head (HEAD_R x the radius of the item).
#   2. Their UV islands are drawn on a mask of the image (4x supersampled); the median luminance of the head pixels is the colour of the membrane.
#   3. A pixel of a head island darker than SPOT x the median luminance is a smudge (grown by GROW px).
#   4. A smudge is filled from the healthy pixels of its island: a Gaussian-weighted mean of them (SIGMA px, widening until every pixel has some), plus the grain of the membrane: the difference of a healthy pixel to ITS neighbourhood,
#      taken from a random healthy pixel (so the patch is not one flat colour, but as noisy as its surroundings).
import bpy
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

SPOT = 0.62          # a pixel darker than this share of the median luminance of the head is a smudge
GROW = 1             # px: the smudge is grown by this much
SIGMA = 2.5          # px: the first width of the fill
HEAD_R = 0.92        # share of the radius of the item inside which a face is a membrane (the hoop rings are outside)
HEAD_END = 0.38      # share of the depth from the middle: faces beyond are at the ends (the membranes)
SEED = 7

obs = [o for o in bpy.context.selected_objects if o.type == "MESH"]
for ob in obs:
    me = ob.data
    img = next((n.image for m in me.materials if m and m.use_nodes for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.image and n.image.name.startswith("uo_baked")), None)
    if img is None:
        print("uo_fix_texture: %s has no baked image" % ob.name); continue
    W, H = img.size
    V = np.array([v.co[:] for v in me.vertices]); c = (V.min(0) + V.max(0)) / 2; ext = V.max(0) - V.min(0)
    depth = ext[1]; R = max(ext[0], ext[2]) / 2
    uv = me.uv_layers[0].data
    S = 4
    mask = Image.new("L", (W * S, H * S), 0); dr = ImageDraw.Draw(mask)
    nf = 0
    for p in me.polygons:
        if abs(p.normal[1]) < 0.9:
            continue
        P = V[list(p.vertices)]
        if np.abs(P[:, 1].mean() - c[1]) < HEAD_END * depth or np.hypot(P[:, 0] - c[0], P[:, 2] - c[2]).max() > HEAD_R * R:
            continue
        dr.polygon([(uv[l].uv[0] * W * S, (1 - uv[l].uv[1]) * H * S) for l in p.loop_indices], fill=255); nf += 1
    head = np.array(mask.resize((W, H), Image.BOX)) > 127
    head = ndimage.binary_erosion(head, iterations=1)                              # a pixel on the rim of an island mixes in the margin: left alone
    px = np.array(img.pixels[:], np.float32).reshape(H, W, 4)[::-1]               # top row first
    lum = 0.2126 * px[..., 0] + 0.7152 * px[..., 1] + 0.0722 * px[..., 2]
    if not head.any():
        print("uo_fix_texture: %s: no head pixels (%d faces)" % (ob.name, nf)); continue
    med = float(np.median(lum[head]))
    spot = head & (lum < SPOT * med)
    spot = ndimage.binary_dilation(spot, iterations=GROW) & head
    good = head & ~spot
    if not spot.any() or good.sum() < 20:
        print("uo_fix_texture: %s: nothing to heal (head median %.2f, %d head pixels)" % (ob.name, med, head.sum())); continue
    rgb = px[..., :3].copy()
    num = np.zeros((H, W, 3)); den = np.zeros((H, W)); sig = SIGMA
    for _ in range(6):
        g = good.astype(np.float64)
        num = np.stack([ndimage.gaussian_filter(rgb[..., k] * g, sig) for k in range(3)], -1); den = ndimage.gaussian_filter(g, sig)
        if (den[spot] > 1e-3).all():
            break
        sig *= 1.8
    base = num / np.maximum(den[..., None], 1e-6)
    # the grain: residual of the healthy pixels to their own neighbourhood, laid over the fill from random healthy pixels
    blur = np.stack([ndimage.gaussian_filter(rgb[..., k] * good, 2.0) / np.maximum(ndimage.gaussian_filter(good.astype(np.float64), 2.0), 1e-6) for k in range(3)], -1)
    resid = (rgb - blur)[good]
    rng = np.random.default_rng(SEED)
    fill = base[spot] + resid[rng.integers(0, len(resid), spot.sum())]
    out = rgb.copy(); out[spot] = np.clip(fill, 0.0, 1.0)
    px[..., :3] = out
    img.pixels.foreach_set(px[::-1].ravel()); img.update()
    if img.packed_file:
        img.pack()
    print("uo_fix_texture: %s: %d smudge pixels healed on the heads (%d head pixels, median luminance %.2f, darkest %.2f)" % (ob.name, spot.sum(), head.sum(), med, float(lum[spot].min())))
