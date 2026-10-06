"""Split a model that is ONE mesh of several loose parts (a cuirass and two pauldrons in one object) into one object per part, so that a recipe of uo_make_item.py can treat them
separately ("parts"; `keep` takes whole objects). The vertices are welded first (a model exported with split vertices has one island per face).

    python split_model.py IN.glb OUT.glb [--scale N=sx,sy,sz ...]
    python split_model.py IN.glb --list

The parts are named Part0, Part1, ... (most vertices first, then by x). --scale N=sx,sy,sz stretches part N about its centre (file units): a stylised model whose torso is far too wide for the UO body
(0.57,0.63,0.9 for the Quaternius armour) gets the proportions of the body before the autofit makes one uniform scale of it. Run with bpy 4.2 (python -I).
"""
import os, sys
import bpy
import bmesh
import numpy as np


def main(argv):
    src = os.path.abspath(argv[0])
    listing = "--list" in argv
    out = None if listing else os.path.abspath(argv[1])
    scales = {int(a.split("=")[0]): [float(x) for x in a.split("=")[1].split(",")] for a in argv if "=" in a and not a.startswith("--")}
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=src)
    obs = [o for o in bpy.data.objects if o.type == "MESH"]
    if not obs:
        raise SystemExit("no mesh in " + src)
    if len(obs) > 1:                                         # several objects: join them first (their loose parts are split again below)
        bpy.ops.object.select_all(action="DESELECT")
        for o in obs:
            o.select_set(True)
        bpy.context.view_layer.objects.active = obs[0]; bpy.ops.object.join()
    o = [o for o in bpy.data.objects if o.type == "MESH"][0]
    me = o.data; me.transform(o.matrix_world); o.matrix_world.identity()
    bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4); bm.to_mesh(me); bm.free()
    bpy.ops.object.select_all(action="DESELECT"); o.select_set(True); bpy.context.view_layer.objects.active = o
    bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.select_all(action="SELECT"); bpy.ops.mesh.separate(type="LOOSE"); bpy.ops.object.mode_set(mode="OBJECT")
    parts = [x for x in bpy.data.objects if x.type == "MESH"]
    info = []
    for x in parts:
        v = np.array([p.co[:] for p in x.data.vertices]); info.append((x, len(v), v.mean(0)))
    info.sort(key=lambda t: (-t[1], t[2][0]))
    for k, (x, n, c) in enumerate(info):
        print("Part%d: %d vertices, centre %s, size %s" % (k, n, np.round(c, 3), np.round(np.ptp(np.array([p.co[:] for p in x.data.vertices]), axis=0), 3)))
        x.name = "Part%d" % k
    if listing:
        return
    for k, (x, n, c) in enumerate(info):
        for p in x.data.polygons:
            p.use_smooth = False
        if k in scales:
            s = scales[k]
            for p in x.data.vertices:
                p.co = c + (np.array(p.co[:]) - c) * s
    bpy.ops.export_scene.gltf(filepath=out, export_format="GLB")
    print("wrote", out)


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
