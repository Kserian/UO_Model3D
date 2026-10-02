"""Test of uo_materials.py: a sphere in front of the chest with a foreign PBR material (metallic, rough, image texture) is converted to the UO look and
rendered (Cycles, 04_stand); it must come out exactly as the same sphere with the plain UO_Look material of the same albedo (flat colour case), keep the
texture (checker case), and cut out transparent texels (alpha case).

    python test_materials.py [--tmp DIR]
"""
import argparse, os, subprocess, sys, tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PRE = r'''
import bpy, os, numpy as np
V = os.environ["MAT_VARIANT"]
col = (0.55, 0.30, 0.12, 1.0)
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.18, location=(0, -0.05, 1.35), segments=32, ring_count=16)
ob = bpy.context.active_object; ob.name = "T_" + V
for p in ob.data.polygons: p.use_smooth = True
clo = bpy.data.collections["Clothing"]
for o in list(clo.all_objects): bpy.data.objects.remove(o, do_unlink=True)
for c in list(ob.users_collection): c.objects.unlink(ob)
clo.objects.link(ob)
ng = bpy.data.node_groups["UO_Look"]
mat = bpy.data.materials.new("M_" + V); mat.use_nodes = True
nt = mat.node_tree
if V == "ref":
    nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial"); g = nt.nodes.new("ShaderNodeGroup"); g.node_tree = ng
    g.inputs["Albedo"].default_value = col; nt.links.new(g.outputs["Shader"], o.inputs["Surface"])
else:
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Metallic"].default_value = 1.0; b.inputs["Roughness"].default_value = 0.15
    if V in ("flat", "raw"):
        img = bpy.data.images.new("t", 8, 8, alpha=True); img.colorspace_settings.name = "Non-Color"; px = np.tile(np.array(col, np.float32), 64); img.pixels.foreach_set(px)
    elif V == "checker":
        img = bpy.data.images.new("t", 64, 64, alpha=True); img.colorspace_settings.name = "Non-Color"; a = np.zeros((64, 64, 4), np.float32); a[..., 3] = 1
        a[...] = (0.8, 0.2, 0.2, 1); a[(np.arange(64)[:, None] // 8 + np.arange(64)[None] // 8) % 2 == 0] = (0.2, 0.3, 0.8, 1); img.pixels.foreach_set(a.ravel())
    elif V == "alpha":
        img = bpy.data.images.new("t", 64, 64, alpha=True); img.colorspace_settings.name = "Non-Color"; a = np.zeros((64, 64, 4), np.float32); a[...] = col; a[:, :, 3] = (np.arange(64)[None] // 16 % 2)
        img.pixels.foreach_set(a.ravel())
    tx = nt.nodes.new("ShaderNodeTexImage"); tx.image = img; tx.interpolation = "Closest"
    nt.links.new(tx.outputs["Color"], b.inputs["Base Color"])
    if V == "alpha": nt.links.new(tx.outputs["Alpha"], b.inputs["Alpha"])
ob.data.materials.append(mat)
bpy.ops.object.select_all(action="DESELECT"); ob.select_set(True); bpy.context.view_layer.objects.active = ob
if V not in ("ref", "raw"):                                 # raw = the foreign material as it came (the "before" measurement)
    text = open(os.path.join(os.environ["MAT_SCRIPTS"], "uo_materials.py")).read()
    exec(compile(text, "uo_materials.py", "exec"), {"__name__": "__main__"})
'''


def render(variant, tmp):
    pre = os.path.join(tmp, "pre.py"); open(pre, "w").write(PRE)
    out = os.path.join(tmp, variant)
    env = dict(os.environ, MAT_VARIANT=variant, MAT_SCRIPTS=HERE)
    r = subprocess.run([sys.executable, os.path.join(HERE, "run_render_headless.py"), os.path.join(HERE, "..", "model", "UO_Body_0x190.blend"), out, "--pre", pre,
                        'LAYER="clothing"', 'ONLY=["04_stand"]'], capture_output=True, text=True, env=env)
    for l in r.stdout.splitlines():
        if l.startswith(("uo_materials", "   ")):
            print(l)
    if r.returncode:
        sys.exit("render failed:\n%s\n%s" % (r.stdout[-1500:], r.stderr[-1500:]))
    from PIL import Image
    d = os.path.join(out, "clothing", "frames")
    fs = sorted(os.path.join(dp, f) for dp, _, fn in os.walk(d) for f in fn if f.endswith(".png"))
    return [np.array(Image.open(f).convert("RGBA")) for f in fs]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--tmp"); a = ap.parse_args()
    tmp = os.path.abspath(a.tmp) if a.tmp else tempfile.mkdtemp(prefix="test_mat_")
    os.makedirs(tmp, exist_ok=True)
    res = {v: render(v, tmp) for v in ("ref", "raw", "flat", "checker", "alpha")}
    ok = True
    for v, fr in res.items():
        print("%-8s frames %d, opaque px %d, colours %d" % (v, len(fr), sum(int((f[..., 3] > 0).sum()) for f in fr), len({tuple(p) for f in fr for p in f[f[..., 3] > 0][:, :3]})))
    ref = res["ref"]
    d = max(int(np.abs(f.astype(int) - g.astype(int)).max()) for f, g in zip(ref, res["flat"])) if len(ref) == len(res["flat"]) else 999
    dr = np.mean([np.abs(f.astype(int) - g.astype(int))[f[..., 3] > 0].mean() for f, g in zip(ref, res["raw"])])
    print("before (raw foreign PBR material vs UO look): mean channel difference %.1f of 255" % dr)
    print("flat vs ref: max channel difference %d (0 = identical)" % d); ok &= d <= 1
    nref = len({tuple(p) for f in ref for p in f[f[..., 3] > 0][:, :3]}); nchk = len({tuple(p) for f in res["checker"] for p in f[f[..., 3] > 0][:, :3]})
    print("checker: %d colours vs %d for the flat sphere" % (nchk, nref)); ok &= nchk > nref
    areas = {v: sum(int((f[..., 3] > 0).sum()) for f in res[v]) for v in res}
    print("alpha sphere area %.2f of the flat one" % (areas["alpha"] / areas["flat"])); ok &= 0.2 < areas["alpha"] / areas["flat"] < 0.95   # the inside of the far half shows through the cut-out
    print("RESULT", "OK" if ok else "FAIL")
    print("output in", tmp)
