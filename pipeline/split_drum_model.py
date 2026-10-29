"""Split a drum model with a strap in ONE mesh (e.g. a Meshy glb) into the drum and the strap, both scaled and placed for uo_make_item.py "rigid" recipes.

    python split_drum_model.py DRUM.glb OUT_DIR [--dia 0.28] [--depth 0.23] [--cut 1.2] [--pct 92]

The drum axis must be the model's Y axis in Blender coordinates (after the glTF import) - for a model with its axis elsewhere turn it first. The axis is found by a circle fit of the points of the
front head (y < the lowest y + 5 %), the radius of the drum is the largest distance of a drum vertex from it. Connected pieces of the mesh whose farthest vertex lies more than `cut` x (the radius of the
head's circle) from the axis are the strap and its fittings (a glTF from an AI generator has hundreds of loose pieces; the strap is split into stitched segments, the hardware hangs on the rim);
everything else is the drum. Both come out centred on the middle of the drum, scaled so that the drum (hoops included) is DIA across (x, z) and DEPTH deep (y: a squat drum on the chest takes
less room across the body), textures kept: OUT_DIR/drum.glb and OUT_DIR/strap.glb (the same transform, so that they fit together). Prints the numbers.
"""
import argparse, os, sys
import numpy as np
import bpy
import bmesh


def components(bm):
    comp = np.full(len(bm.verts), -1, np.int32); k = 0
    for v in bm.verts:
        if comp[v.index] >= 0:
            continue
        st = [v]; comp[v.index] = k
        while st:
            a = st.pop()
            for e in a.link_edges:
                b = e.other_vert(a)
                if comp[b.index] < 0:
                    comp[b.index] = k; st.append(b)
        k += 1
    return comp


def export(ob, path):
    for o in bpy.data.objects:
        o.select_set(o is ob)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_apply=False)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("out")
    ap.add_argument("--dia", type=float, default=0.28); ap.add_argument("--depth", type=float, default=0.23); ap.add_argument("--cut", type=float, default=1.2); ap.add_argument("--pct", type=float, default=92.0)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=a.src)
    src = [o for o in bpy.data.objects if o.type == "MESH"][0]
    bm = bmesh.new(); bm.from_mesh(src.data); bm.verts.ensure_lookup_table()
    V = np.array([v.co[:] for v in bm.verts], np.float64)
    h = V[V[:, 1] < V[:, 1].min() + 0.05 * np.ptp(V[:, 1])]
    sol = np.linalg.lstsq(np.c_[2 * h[:, 0], 2 * h[:, 2], np.ones(len(h))], h[:, 0] ** 2 + h[:, 2] ** 2, rcond=None)[0]
    x0, z0 = sol[:2]; Rh = float(np.sqrt(sol[2] + x0 * x0 + z0 * z0))
    r = np.hypot(V[:, 0] - x0, V[:, 2] - z0)
    comp = components(bm); n = comp.max() + 1
    rmax = np.zeros(n); np.maximum.at(rmax, comp, r)
    strap_c = rmax > a.cut * Rh
    is_strap = strap_c[comp]
    D = V[~is_strap]; rd = r[~is_strap]
    R = float(np.percentile(rd, a.pct)); y0, y1 = float(D[:, 1].min()), float(D[:, 1].max())
    yc = (y0 + y1) / 2
    fxz = a.dia / 2 / R; fy = a.depth / (y1 - y0)
    print("split: circle of the head R %.4f at (%.4f, %.4f); drum radius %.4f, y %.4f .. %.4f; strap pieces %d of %d (%d of %d vertices)" % (Rh, x0, z0, R, y0, y1, strap_c.sum(), n, is_strap.sum(), len(V)))
    print("split: scale across x %.4f, along the axis y %.4f (squash %.2f); drum %.3f x %.3f m" % (fxz, fy, fy / fxz, a.dia, a.depth))
    for name, keep_strap in (("drum", False), ("strap", True)):
        b2 = bm.copy(); b2.verts.ensure_lookup_table()
        kill = [v for v in b2.verts if bool(is_strap[v.index]) != keep_strap]
        bmesh.ops.delete(b2, geom=kill, context="VERTS")
        for v in b2.verts:
            c = v.co
            v.co = ((c.x - x0) * fxz, (c.y - yc) * fy, (c.z - z0) * fxz)
        me = bpy.data.meshes.new(name); b2.to_mesh(me); b2.free()
        for m in src.data.materials:
            me.materials.append(m)
        ob = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(ob)
        export(ob, os.path.join(a.out, name + ".glb"))
        print("split: %s: %d vertices -> %s" % (name, len(me.vertices), os.path.join(a.out, name + ".glb")))
