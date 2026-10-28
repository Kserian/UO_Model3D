"""A geometric war drum (side drum / tabor) for uo_make_item.py: shell, two heads, two hoops, a painted band.

    python make_drum_model.py OUT.glb [--radius 0.14] [--depth 0.22]

The model is made at the origin with its axis along Y and the front head looking to -Y (the front of the UO body); the recipe ("rigid" + "place") puts it on the body.
Blender coordinates, exported with the standard glTF Y-up conversion, which uo_import_item.py undoes.
"""
import argparse, math
import bpy
import bmesh


def material(name, rgb, metal=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1.0); b.inputs["Metallic"].default_value = metal; b.inputs["Roughness"].default_value = 0.6
    return m


def cylinder(name, radius, depth, y, mat, seg=48, dome=0.0):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=radius, radius2=radius, depth=depth)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=__import__("mathutils").Matrix.Rotation(math.pi / 2, 3, "X"))      # axis Z -> Y
    if dome:
        for v in bm.verts:
            v.co.y += math.copysign(dome * max(0.0, 1.0 - (v.co.x ** 2 + v.co.z ** 2) / radius ** 2), v.co.y)
    for v in bm.verts:
        v.co.y += y
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(ob); ob.data.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = True
    return ob


def ring(name, major, minor, y, mat):
    bm = bmesh.new()
    n, m = 48, 10
    for i in range(n):
        a = 2 * math.pi * i / n
        for j in range(m):
            b = 2 * math.pi * j / m
            r = major + minor * math.cos(b)
            bm.verts.new((r * math.cos(a), y + minor * math.sin(b), r * math.sin(a)))
    bm.verts.ensure_lookup_table()
    for i in range(n):
        for j in range(m):
            bm.faces.new([bm.verts[i * m + j], bm.verts[((i + 1) % n) * m + j], bm.verts[((i + 1) % n) * m + (j + 1) % m], bm.verts[i * m + (j + 1) % m]])
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(ob); ob.data.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = True
    return ob


def build(radius, depth):
    wood, skin = material("wood", (0.36, 0.20, 0.09)), material("head", (0.78, 0.66, 0.46))
    iron, red = material("iron", (0.30, 0.30, 0.33), 0.8), material("band", (0.55, 0.08, 0.05))
    h = depth / 2
    rs = radius * 0.93                                  # shell radius: the hoops stand out of it to the full radius
    hoop = radius * 0.085
    cylinder("shell", rs, depth - 2 * hoop, 0.0, wood)
    cylinder("band", rs * 1.01, depth * 0.22, 0.0, red)
    for s in (-1, 1):
        cylinder("head%+d" % s, radius - hoop, 0.012, s * (h - hoop), skin, dome=0.008)
        ring("hoop%+d" % s, radius - hoop, hoop, s * (h - hoop), iron)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("out"); ap.add_argument("--radius", type=float, default=0.14); ap.add_argument("--depth", type=float, default=0.22)
    a = ap.parse_args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    build(a.radius, a.depth)
    bpy.ops.export_scene.gltf(filepath=a.out, export_format="GLB", export_apply=True)
    print("drum: radius %.3f m, depth %.3f m -> %s" % (a.radius, a.depth, a.out))
