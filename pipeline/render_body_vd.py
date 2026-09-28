"""Render the BODY layer of a built .blend for all 35 UO actions x 5 directions and write it to a .vd file."""
import bpy, sys, os
blend = sys.argv[sys.argv.index("--blend") + 1]
out = os.path.abspath(sys.argv[sys.argv.index("--out") + 1])
samples = int(sys.argv[sys.argv.index("--samples") + 1]) if "--samples" in sys.argv else 32
bpy.ops.wm.open_mainfile(filepath=os.path.abspath(blend))
sc = bpy.context.scene
sc.render.engine = "CYCLES"; sc.cycles.samples = samples; sc.cycles.device = "CPU"
src = bpy.data.texts["render_uo_layer.py"].as_string()
src = src.replace('LAYER = "clothing"', 'LAYER = "body"').replace('OUT_DIR = "//uo_render/"', 'OUT_DIR = %r' % (out + "/"))
src = src.replace('VD_FILE = "//uo_render/%s.vd"', 'VD_FILE = %r' % (out + "/%s.vd"))
layer = sys.argv[sys.argv.index("--layer") + 1] if "--layer" in sys.argv else "body"
src = src.replace('LAYER = "body"', 'LAYER = %r' % layer)
if "--pure" in sys.argv:
    src = src.replace("EXACT_BODY = True", "EXACT_BODY = False")
assert "WRITE_VD = True" in src
exec(compile(src, "render_uo_layer.py", "exec"))
