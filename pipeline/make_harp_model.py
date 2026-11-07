"""A small wooden harp without strings, built from primitives (no outside model): `python make_harp_model.py OUT.glb [--height 1.1]`.

Frame of the model (metres): Z up along the pillar, the pillar axis is x = 0, y = 0, the floor under it is z = 0; the strings' plane is XZ and the sound box leans to +X;
Y is the depth. The pillar (the thin side, where it is held) stands in front, the curved neck joins its top to the sound box, the sound box is the thick tapered
body on the far side. One material, a plain walnut-brown texture with a very faint grain (no strong light/dark patches: the colour of the item stays one colour).
Default: a hand harp, 0.52 m tall (not taller than the torso of the body), about 0.42 m wide (`--height`, `--wide`, `--thick`).
"""
import sys, os, math
import numpy as np
import bpy, bmesh

H = 0.52
XS = 1.45         # the harp is wider than a tall one of the same height (a hand harp), so that it spans the two hands of a standing body
TK = 2.1         # thicker parts than a uniform scaling gives: at 36 px/m a 3 cm pillar is one pixel
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
OUT = ARGS[0] if ARGS else "harp.glb"
if "--height" in ARGS:
    H = float(ARGS[ARGS.index("--height") + 1])
if "--wide" in ARGS:
    XS = float(ARGS[ARGS.index("--wide") + 1])
if "--thick" in ARGS:
    TK = float(ARGS[ARGS.index("--thick") + 1])
S = H / 1.1                                                       # every dimension below is for 1.1 m (then X widened by XS, the cross-sections by TK)


def loft(bm, path, sizes, sides=16, cap=True, flat=0.0):
    """a tube along `path` (list of 3D points): a ring of `sides` points per station with half-sizes (a, b) = (in the plane XZ, along Y). flat > 0 flattens the side of the ring that faces -X-ish
    (the strings' side of the sound box): the ring's points are pressed to at least -flat*a from the centre in the direction `side`"""
    path = [np.array(p, float) * np.array([XS, 1.0, 1.0]) for p in path]
    sizes = [(a * TK, b * TK) for a, b in sizes]
    rings = []
    for i, p in enumerate(path):
        t = path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]
        t /= np.linalg.norm(t)
        side = np.cross([0, 1, 0], t); side /= np.linalg.norm(side)     # in the plane XZ, perpendicular to the path
        a, b = sizes[i]
        ring = []
        for k in range(sides):
            ang = 2 * math.pi * k / sides
            u, v = math.cos(ang), math.sin(ang)
            if flat > 0 and u < 0:
                u = max(u, -(1 - flat))                                  # a flatter face on the strings' side
            ring.append(bm.verts.new(p + side * (a * u) + np.array([0, 1, 0]) * (b * v)))
        rings.append(ring)
    for i in range(len(rings) - 1):
        for k in range(sides):
            bm.faces.new([rings[i][k], rings[i][(k + 1) % sides], rings[i + 1][(k + 1) % sides], rings[i + 1][k]])
    if cap:
        for ring in (rings[0], rings[-1][::-1]):
            bm.faces.new(ring)
    return rings


def bezier(p0, p1, p2, n):
    return [tuple((1 - t) ** 2 * np.array(p0) + 2 * (1 - t) * t * np.array(p1) + t * t * np.array(p2)) for t in np.linspace(0, 1, n)]


def build():
    bm = bmesh.new()
    # pillar: a column that tapers a little towards the top, with a foot ring and a capital
    z = np.linspace(0.02, 1.06, 14)
    loft(bm, [(0, 0, v * S) for v in z], [(0.030 * S * (1 - 0.16 * (v - 0.02) / 1.04),) * 2 for v in z], sides=14)
    for z0, z1, r in ((0.0, 0.08, 0.046), (1.01, 1.10, 0.042)):             # foot block, capital
        loft(bm, [(0, 0, z0 * S), (0, 0, (z0 + z1) / 2 * S), (0, 0, z1 * S)], [(r * S, r * S), (r * S * 1.12, r * S * 1.12), (r * S * 0.9, r * S * 0.9)], sides=14)
    # foot: joins the bottom of the pillar to the sound box (a low block)
    loft(bm, [(0.0 * S, 0, 0.032 * S), (0.09 * S, 0, 0.04 * S), (0.17 * S, 0, 0.05 * S)], [(0.046 * S, 0.075 * S), (0.050 * S, 0.090 * S), (0.056 * S, 0.090 * S)], sides=14)
    # sound box: a tapered body from the foot up to the end of the neck, flat on the strings' side, round on the back
    p0, p1 = np.array([0.14, 0, 0.055]) * S, np.array([0.52, 0, 0.90]) * S
    n = 14
    path = [tuple(p0 + (p1 - p0) * t) for t in np.linspace(0, 1, n)]
    sizes = []
    for t in np.linspace(0, 1, n):
        a = (0.090 - 0.040 * t) * S                                      # half width in the plane: 15.6 cm at the bottom, 8.8 cm at the top
        b = (0.100 - 0.045 * t) * S                                      # half depth
        sizes.append((a, b))
    loft(bm, path, sizes, sides=18, flat=0.45)
    # neck: an arch from the top of the pillar to the top of the sound box
    npath = bezier((0.0, 0, 1.07), (0.30, 0, 1.17), (0.53, 0, 0.93), 16)
    npath = [tuple(np.array(p) * S) for p in npath]
    nsizes = [((0.028 + 0.008 * math.sin(math.pi * t)) * S, (0.046 + 0.008 * math.sin(math.pi * t)) * S) for t in np.linspace(0, 1, 16)]
    loft(bm, npath, nsizes, sides=14)
    # a small rounded cap where the neck meets the sound box
    loft(bm, [(0.50 * S, 0, 0.86 * S), (0.525 * S, 0, 0.90 * S), (0.545 * S, 0, 0.94 * S)], [(0.050 * S, 0.056 * S), (0.054 * S, 0.060 * S), (0.038 * S, 0.042 * S)], sides=14)
    return bm


def uvs(bm):
    """planar map from the front (XZ, the grain runs along the pillar / sound box) with a little of Y so the sides are not streaks; the wood texture is faint, a stretch does not show"""
    uv = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        for l in f.loops:
            p = l.vert.co
            l[uv].uv = (0.5 + 1.6 * (p.x + 0.8 * p.y), 0.5 + 0.9 * p.z)


def wood_texture(path, size=256):
    rng = np.random.default_rng(7)
    u = np.linspace(0, 1, size)
    stripes = np.zeros(size)
    for f, a in ((9, 1.0), (23, 0.6), (51, 0.35)):                       # grain: stripes of a few frequencies along U
        stripes += a * np.sin(2 * np.pi * (f * u + rng.random()))
    stripes /= np.abs(stripes).max()
    img = np.ones((size, size))                                          # V (along the grain) is nearly constant: a faint wobble only
    wob = 0.5 * np.sin(2 * np.pi * (np.linspace(0, 3, size) + rng.random()))[:, None]
    g = 1 + 0.045 * (stripes[None, :] + 0.25 * wob) + 0.01 * rng.standard_normal((size, size))
    base = np.array([112, 72, 38]) / 255.0                             # walnut brown, sRGB
    rgb = np.clip(base[None, None, :] * g[:, :, None], 0, 1)
    from PIL import Image
    Image.fromarray((rgb * 255 + 0.5).astype(np.uint8)).save(path)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bm = build()
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    uvs(bm)
    me = bpy.data.meshes.new("harp"); bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new("harp", me); bpy.context.scene.collection.objects.link(ob)
    tex = os.path.splitext(OUT)[0] + "_wood.png"
    wood_texture(tex)
    mat = bpy.data.materials.new("wood"); mat.use_nodes = True
    nt = mat.node_tree; bsdf = nt.nodes["Principled BSDF"]
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = bpy.data.images.load(tex); t.image.pack()
    nt.links.new(t.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 1.0
    bsdf.inputs["Metallic"].default_value = 0.0
    me.materials.append(mat)
    bpy.ops.export_scene.gltf(filepath=OUT, export_format="GLB", export_apply=True)
    os.remove(tex)
    v = np.array([v.co[:] for v in me.vertices])
    print("harp: %d vertices, %d faces, size x %.3f y %.3f z %.3f m, z %.3f..%.3f -> %s" % (len(v), len(me.polygons), *(v.max(0) - v.min(0)), v[:, 2].min(), v[:, 2].max(), OUT))


main()
