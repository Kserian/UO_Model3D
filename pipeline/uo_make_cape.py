"""A clean cape for the UO body, built as a regular silk sheet (no foreign mesh): the way the original cloak 468 is a straight, even rectangle pinned at the shoulders.

Runs inside Blender in place of uo_import_item.py (uo_make_item.py: recipe "cape": {...}, kind cloak). Why: a cape from a generator (Meshy) is a flared, finely pleated shell decimated to
30k triangles: its hem and sides are wavy at the scale of a UO pixel and no motion can make it look like the original (smooth, straight, soft vertical shading). Here the shape is built:
  - a grid of CELL m (2.5 cm: one UO pixel is 2.8 cm) across WIDTH_TOP (at the shoulders) .. WIDTH_HEM and from Z_TOP down to Z_HEM;
  - its rest shape hangs from the shoulders over the back: y(x, z) = the upper envelope of the skin of the back above it (the highest back contour above that height: it rests on the shoulder
    blades and the buttocks, it never goes into the body), GAP off it, leaning LEAN back with the depth, smoothed;
  - the colours come from the model the recipe names ("colors_from", a .glb): the cloth is the median of its saturated pixels, the trim the gold of its brightest saturated ones; the texture
    (u across, v along the sheet: no UV problems) is the cloth with a gentle weave, a gold band along the whole hem and two brooches at the shoulders.
Weights, motion and the cloth simulation are those of every cloak (uo_prepare_item.py KIND cloak, uo_cloak_motion.py / uo_cloth_sim.py).
"""
import json, math, os
import numpy as np
import bpy
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from scipy.ndimage import gaussian_filter

NAME = "cape"
COLORS_FROM = ""      # .glb / .png whose base colour texture gives the cloth and the trim colours ("" = CLOTH / TRIM below)
CLOTH = (0.50, 0.07, 0.09)     # linear RGB of the cloth when no model is given
TRIM = (0.62, 0.45, 0.16)
Z_TOP = 1.60          # m: the shoulder line of the cape (a bit above the shoulders: it covers them, the collar near the neck)
Z_HEM = 0.30          # m: the hem (the original cloak 468 ends 0.06-0.1 m above the ground)
WIDTH_TOP = 0.48      # m
WIDTH_HEM = 0.66      # m: nearly straight, slightly flared (the original is a rectangle)
SHOULDER_COVER = 0.05   # m: the top edge lies this far above the top of the shoulders (the corners rest on them, the middle stays at Z_TOP)
PIN_DROP = 0.05       # m: the shoulder line the motion pivots about is this far below the highest point of the cape (what is above it follows the body)
CELL = 0.025          # m
GAP = 0.035            # m: off the skin of the back where it rests on it
LEAN = 0.12           # the hem stands this much of the depth off the back (7 %: hangs freely, a hand off the body)
SMOOTH = 0.05         # m: gaussian smoothing of the rest shape
FOLDS = 0.012         # m: amplitude of the very gentle vertical folds the rest shape starts with (the simulation makes the real ones)
FOLD_COUNT = 5
HEM_BAND = 0.07       # m: gold band along the hem
TEX_W, TEX_H = 256, 1024


def read_colours(path):
    """(cloth RGB, trim RGB) from the base colour image of a glb / image file"""
    if path.lower().endswith(".glb") or path.lower().endswith(".gltf"):
        before = set(bpy.data.objects); bpy.ops.import_scene.gltf(filepath=path)
        new = [o for o in bpy.data.objects if o not in before]
        img = next((n.image for o in new if o.type == "MESH" for m in o.data.materials if m and m.node_tree for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.image), None)
        a = None
        if img is not None:
            w, h = img.size; a = np.array(img.pixels[:], np.float32).reshape(h, w, 4)[..., :3]
        for o in new:
            bpy.data.objects.remove(o, do_unlink=True)
    else:
        img = bpy.data.images.load(path); w, h = img.size; a = np.array(img.pixels[:], np.float32).reshape(h, w, 4)[..., :3]; bpy.data.images.remove(img)
    if a is None:
        return CLOTH, TRIM
    px = a.reshape(-1, 3); mx = px.max(1); mn = px.min(1); sat = (mx - mn) / np.maximum(mx, 1e-6)
    ok = (mx > 0.12) & (sat > 0.35)
    red = ok & (px[:, 0] >= px[:, 1] * 1.6)
    gold = ok & (px[:, 1] > px[:, 2] * 1.3) & (px[:, 0] > 0.3) & (px[:, 1] > 0.18)
    cloth = tuple(np.median(px[red], 0)) if red.sum() > 100 else CLOTH
    trim = tuple(np.percentile(px[gold], 70, axis=0)) if gold.sum() > 100 else TRIM
    print("uo_make_cape: colours from %s: cloth %s (%d px), trim %s (%d px)" % (os.path.basename(path), np.round(cloth, 3), red.sum(), np.round(trim, 3), gold.sum()))
    return cloth, trim


def texture(cloth, trim, length):
    """RGBA float image TEX_W x TEX_H: u across, v along the sheet (0 at the hem, 1 at the shoulders)"""
    rng = np.random.default_rng(7)
    v = (np.arange(TEX_H) + 0.5) / TEX_H; u = (np.arange(TEX_W) + 0.5) / TEX_W
    img = np.zeros((TEX_H, TEX_W, 3), np.float32); img[:] = np.array(cloth, np.float32)
    n = gaussian_filter(rng.standard_normal((TEX_H, TEX_W)), (6, 1.5)); n /= max(np.abs(n).max(), 1e-6)       # a faint vertical sheen of the weave
    img *= (1.0 + 0.05 * n)[..., None]
    hh = HEM_BAND / length
    band = np.clip((hh - v) / 0.004, 0.0, 1.0)[:, None] * np.ones((1, TEX_W))                                     # the gold band along the hem
    line = np.clip(1.0 - np.abs(v - (hh + 0.012 / length)) / (0.004 / length), 0.0, 1.0)[:, None] * np.ones((1, TEX_W))   # a thin line above it
    pat = 0.85 + 0.15 * np.sin(2 * math.pi * u * 26)[None, :] * np.sin(2 * math.pi * v * length / 0.05)[:, None]     # a small repeated motif inside the band
    for m, col in ((band, np.array(trim) * pat[..., None]), (line, np.array(trim)[None, None, :] * np.ones((1, 1, 1)))):
        img = img * (1 - m[..., None]) + np.broadcast_to(col, img.shape) * m[..., None]
    out = np.ones((TEX_H, TEX_W, 4), np.float32); out[..., :3] = np.clip(img, 0, 1)
    return out


def main():
    rig = bpy.data.objects["UO_Rig"]; rig.data.pose_position = "REST"; bpy.context.view_layer.update()
    body = bpy.data.objects["UO_Body"]
    cloth, trim = read_colours(COLORS_FROM) if COLORS_FROM else (CLOTH, TRIM)
    dg = bpy.context.evaluated_depsgraph_get(); mb = body.evaluated_get(dg).to_mesh(); M = np.array(body.matrix_world)
    VB = np.array([v.co for v in mb.vertices]) @ M[:3, :3].T + M[:3, 3]
    bvh = BVHTree.FromPolygons([tuple(v) for v in VB], [tuple(p.vertices) for p in mb.polygons])
    nu = int(round(WIDTH_HEM / CELL)); nv = int(round((Z_TOP - Z_HEM) / CELL)); nu += nu % 2                      # even: a column on the middle
    s = np.linspace(0.0, 1.0, nv + 1)                                                                            # 0 at the top edge
    half = 0.5 * (WIDTH_TOP + (WIDTH_HEM - WIDTH_TOP) * s)
    xs = np.linspace(-1.0, 1.0, nu + 1)
    X = xs[None, :] * half[:, None]                                                                              # (nv+1, nu+1)
    top = np.full(nu + 1, Z_TOP)                                                                                 # the top edge follows the shoulders: the corners lie on them
    for i in range(nu + 1):
        loc, nor, _, d = bvh.ray_cast(Vector((X[0, i], 0.05, 2.2)), Vector((0.0, 0.0, -1.0)), 2.0)
        if loc is not None:
            top[i] = min(Z_TOP, loc.z + SHOULDER_COVER)
    top = gaussian_filter(top, 1.5, mode="nearest")
    z = top[None, :] - s[:, None] * (top[None, :] - Z_HEM)                                                       # (nv+1, nu+1): the columns have their own top
    # the skin of the back above every point: the highest contour of the back (max y) from the top down to its height
    back = np.full(X.shape, -np.inf); fwd = Vector((0.0, -1.0, 0.0))
    for j in range(nv + 1):
        for i in range(nu + 1):
            loc, nor, _, d = bvh.ray_cast(Vector((X[j, i], 1.0, z[j, i])), fwd, 2.0)
            if loc is not None:
                back[j, i] = loc.y
    env = np.maximum.accumulate(back, axis=0)                                                                    # rests on what is above it
    for j in range(nv + 1):                                                                                      # past the sides of the body: the nearest column that has a back
        ok = np.isfinite(env[j])
        if ok.any() and not ok.all():
            idx = np.nonzero(ok)[0]; env[j] = np.interp(np.arange(nu + 1), idx, env[j, idx])
    first = np.nonzero(np.isfinite(env).any(1))[0]
    if len(first):
        env[:first[0]] = env[first[0]]
    d = Z_TOP - z
    Y = env + GAP + LEAN * d
    Y = gaussian_filter(Y, SMOOTH / CELL, mode="nearest")
    ph = 0.7
    Y = Y + FOLDS * np.minimum(s * 3, 1.0)[:, None] * np.sin(2 * math.pi * FOLD_COUNT * xs[None, :] * 0.5 + ph)
    V = np.stack([X, Y, z], -1).reshape(-1, 3)
    me = bpy.data.meshes.new(NAME); bm = bmesh.new()
    vs = [bm.verts.new(tuple(p)) for p in V]; W = nu + 1
    for j in range(nv):
        for i in range(nu):
            bm.faces.new([vs[j * W + i], vs[j * W + i + 1], vs[(j + 1) * W + i + 1], vs[(j + 1) * W + i]])
    bm.verts.index_update(); uv = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        for l in f.loops:
            k = l.vert.index; l[uv].uv = ((k % W) / (W - 1), 1.0 - (k // W) / (nv))
    bm.normal_update(); bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = True
    # the normals face the back (+y): the sheet is seen from outside there
    if np.mean([p.normal.y for p in me.polygons]) < 0:
        me.flip_normals()
    ob = bpy.data.objects.new(NAME, me); bpy.data.collections["Clothing"].objects.link(ob); ob["uo_pin_drop"] = PIN_DROP
    for o in bpy.context.view_layer.objects:                                                                    # the next steps (uo_prepare_item.py) work on the selection
        o.select_set(False)
    ob.select_set(True); bpy.context.view_layer.objects.active = ob
    img = bpy.data.images.new("uo_cape_tex", TEX_W, TEX_H, alpha=False)
    img.pixels[:] = texture(cloth, trim, Z_TOP - Z_HEM)[::-1].ravel() if False else texture(cloth, trim, Z_TOP - Z_HEM).ravel()
    img.pack()
    mat = bpy.data.materials.new("uo_cape"); mat.use_nodes = True; nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]; tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = img; tex.interpolation = "Linear"
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    me.materials.append(mat)
    print("uo_make_cape: %s: %d x %d cells of %.1f cm, %d vertices, from z %.2f to %.2f, width %.2f..%.2f m, shoulder line y %.3f, hem y %.3f" % (NAME, nu, nv, 100 * CELL, len(V), top.max(), Z_HEM, WIDTH_TOP, WIDTH_HEM, Y[0].mean(), Y[-1].mean()))


main()
