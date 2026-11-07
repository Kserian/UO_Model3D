"""Celtic harp (the user's glTF, 1 mesh of 300k vertices, 4096 px textures) -> the same harp without strings, upright on its thin arm, small enough for the repo.

    python harp_prepare_model.py IN.glb OUT.glb [--faces 60000] [--tex 1024]

1. The strings: faces whose texture colour is grey / white (saturation < 0.25: strings and metal pins; the carved wood is orange), grouped into connected pieces; every piece
   longer than 0.4 m (in the file's units) is a string and is deleted. The metal pins and hooks (short pieces) stay. Nothing else is touched: the frame, the carving, the pegs.
2. The frame of the model for pipeline/uo_harp.py: the THIN arm of the V (the side the harp is held by, on the -X side of the model) is turned about Y until it is vertical and put
   on x = y = 0; Z up (the scroll at the top), the floor at the lowest point; the sound-box arm is on +X, Y is the depth.
3. Reduced: collapse decimation to `--faces` faces (UVs and the material kept), textures scaled to `--tex` px (the harp is ~20 px tall in the game).
"""
import sys, os, math
import numpy as np
import bpy, bmesh

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
IN, OUT = ARGS[0], ARGS[1]
FACES = int(ARGS[ARGS.index("--faces") + 1]) if "--faces" in ARGS else 60000
TEX = int(ARGS[ARGS.index("--tex") + 1]) if "--tex" in ARGS else 1024
SAT = 0.25                # faces with a lower colour saturation than this are strings / metal
STRING_LEN = 0.4          # m (file units): a grey piece longer than this is a string
STUB_DIST = 0.012         # m: pale faces (saturation < STUB_SAT) closer than this to a string are what its ends left behind (slivers by the pins): deleted too
STUB_SAT = 0.5            # the carved wood is more saturated than this


def base_color_image(mat):
    for n in mat.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED" and n.inputs["Base Color"].links:
            src = n.inputs["Base Color"].links[0].from_node
            if src.type == "TEX_IMAGE":
                return src.image
    raise RuntimeError("no base colour texture")


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=IN)
    ob = [o for o in bpy.data.objects if o.type == "MESH"][0]
    me = ob.data
    img = base_color_image(me.materials[0]); W, H = img.size
    px = np.array(img.pixels[:], np.float32).reshape(H, W, 4)
    uv = me.uv_layers[0].data
    sat = np.zeros(len(me.polygons))
    for p in me.polygons:
        u = np.mean([uv[l].uv[:] for l in p.loop_indices], axis=0)
        c = px[int(np.clip(u[1], 0, 0.9999) * H), int(np.clip(u[0], 0, 0.9999) * W), :3]
        sat[p.index] = (c.max() - c.min()) / max(c.max(), 1e-6)
    bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
    lay = bm.faces.layers.int.new("low"); slay = bm.faces.layers.float.new("sat")
    for f in bm.faces:
        f[lay] = 1 if sat[f.index] < SAT else 0; f[slay] = sat[f.index]
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)           # the import splits vertices along UV seams: weld them, else a string is never connected to anything
    bm.faces.ensure_lookup_table()
    low = [f for f in bm.faces if f[lay]]
    vf = {}
    for f in low:
        for v in f.verts:
            vf.setdefault(v.index, []).append(f.index)
    seen, kill = set(), []
    nstr = 0
    for f in low:
        if f.index in seen:
            continue
        st, comp = [f.index], []
        seen.add(f.index)
        while st:
            a = st.pop(); comp.append(a)
            for v in bm.faces[a].verts:
                for b in vf[v.index]:
                    if b not in seen:
                        seen.add(b); st.append(b)
        p = np.array([v.co[:] for fi in comp for v in bm.faces[fi].verts])
        if (p.max(0) - p.min(0)).max() > STRING_LEN:
            kill += comp; nstr += 1
    from scipy.spatial import cKDTree
    bm.verts.ensure_lookup_table()
    sv = np.array(sorted({v.index for i in kill for v in bm.faces[i].verts}))
    tree = cKDTree(np.array([bm.verts[i].co[:] for i in sv]))
    killed = set(kill)
    stubs = [f.index for f in bm.faces if f.index not in killed and f[slay] < STUB_SAT and tree.query(np.array(f.calc_center_median()[:]))[0] < STUB_DIST]
    kill += stubs
    bmesh.ops.delete(bm, geom=[bm.faces[i] for i in kill], context="FACES")
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    print("harp_prepare_model: %d strings removed (%d faces, of them %d stubs by the pins), %d faces left" % (nstr, len(kill), len(stubs), len(bm.faces)))
    # the thin arm of the V -> vertical at x = y = 0: its centre line from the leftmost wood of each height slice
    co = np.array([v.co[:] for v in bm.verts])
    zs = np.linspace(co[:, 2].min() + 0.25, co[:, 2].max() - 0.25, 14)
    pts = []
    for z in zs:
        s = co[np.abs(co[:, 2] - z) < 0.02]
        if len(s):
            pts.append((np.percentile(s[:, 0], 1) + 0.035, z))                       # leftmost wood + half the width of the arm
    pts = np.array(pts)
    b, a = np.polyfit(pts[:, 1], pts[:, 0], 1)                                        # x = a + b z
    tilt = math.atan(b)
    print("harp_prepare_model: thin arm leans %.1f deg; turned upright" % math.degrees(tilt))
    c, s = math.cos(tilt), math.sin(tilt)                                             # rotation about Y that makes x = a + b z vertical: (x, z) -> (x c - z s, x s + z c)
    for v in bm.verts:
        x, y, z = v.co
        v.co = (x * c - z * s, y, x * s + z * c)
    co = np.array([v.co[:] for v in bm.verts])
    zs = np.linspace(co[:, 2].min() + 0.25, co[:, 2].max() - 0.25, 14)
    ax = np.mean([np.percentile(co[np.abs(co[:, 2] - z) < 0.02][:, 0], 1) + 0.035 for z in zs])
    ymid = (co[:, 1].min() + co[:, 1].max()) / 2
    for v in bm.verts:
        v.co = (v.co.x - ax, v.co.y - ymid, v.co.z - co[:, 2].min())
    bm.normal_update(); bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.update()
    # reduce
    n0 = len(me.polygons)
    md = ob.modifiers.new("dec", "DECIMATE"); md.ratio = min(1.0, FACES / n0)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.modifier_apply(modifier="dec")
    for im in bpy.data.images:
        if im.size[0] > TEX:
            im.scale(TEX, TEX)
    bpy.ops.export_scene.gltf(filepath=OUT, export_format="GLB", export_image_format="JPEG", export_jpeg_quality=88, export_apply=True)
    v = np.array([v.co[:] for v in ob.data.vertices])
    print("harp_prepare_model: %d -> %d faces, size x %.3f y %.3f z %.3f, x %.3f..%.3f, %.1f MB -> %s" % (
        n0, len(ob.data.polygons), *(v.max(0) - v.min(0)), v[:, 0].min(), v[:, 0].max(), os.path.getsize(OUT) / 1e6, OUT))


main()
