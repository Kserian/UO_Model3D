"""Perspective Blender render of the skinned mesh in fitted poses (plausibility check, like the user's viewport)."""
import bpy, sys, pickle, math, os
import numpy as np
from mathutils import Vector
sys.argv = [a for a in sys.argv]
res_file = sys.argv[sys.argv.index("--res") + 1]; a = int(sys.argv[sys.argv.index("--action") + 1]); out = sys.argv[sys.argv.index("--out") + 1]
import jax.numpy as jnp
from posefit_mesh import posed, md
res = pickle.load(open(res_file, "rb"))[a]["poses"]
F = res["trans"].shape[0]
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "CYCLES"; sc.cycles.samples = 8; sc.render.resolution_x, sc.render.resolution_y = 260, 320
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True; w.node_tree.nodes["Background"].inputs[0].default_value = (0.2, 0.21, 0.24, 1)
l = bpy.data.lights.new("S", "SUN"); l.energy = 3; lo = bpy.data.objects.new("S", l); lo.rotation_euler = (0.8, 0, -0.6); sc.collection.objects.link(lo)
cam = bpy.data.cameras.new("C"); cam.lens = 50; co = bpy.data.objects.new("C", cam); sc.collection.objects.link(co); sc.camera = co
mat = bpy.data.materials.new("M"); mat.use_nodes = True; mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.7, 0.7, 0.7, 1)
tiles = []
from PIL import Image
for i in range(F):
    X = np.asarray(posed({k: jnp.asarray(v[i]) for k, v in res.items()}))
    me = bpy.data.meshes.new("B%d" % i); me.from_pydata(X.tolist(), [], md["faces"]); me.update()
    for p in me.polygons: p.use_smooth = True
    me.materials.append(mat)
    ob = bpy.data.objects.new("B%d" % i, me); sc.collection.objects.link(ob)
    c = X.mean(0)
    for yaw in (30, 120):
        r = math.radians(yaw); pos = Vector((c[0] + 4.5 * math.sin(r), c[1] - 4.5 * math.cos(r), c[2] + 1.2))
        co.location = pos; co.rotation_euler = (Vector(c.tolist()) - pos).to_track_quat("-Z", "Y").to_euler()
        p = os.path.abspath(f"{out}_{i}_{yaw}.png"); sc.render.filepath = p; bpy.ops.render.render(write_still=True)
        tiles.append(p)
    bpy.data.objects.remove(ob)
ims = [Image.open(p).convert("RGB") for p in tiles]
cols = 2
grid = Image.new("RGB", (ims[0].width * F, ims[0].height * cols))
for i in range(F):
    for j in range(cols):
        grid.paste(ims[i * cols + j], (i * ims[0].width, j * ims[0].height))
grid.save(out + "_grid.png")
