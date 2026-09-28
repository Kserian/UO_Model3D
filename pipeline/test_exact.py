"""Render one action with the exact modes and compare with the original frames."""
import bpy, sys, os, numpy as np
from PIL import Image
arg = lambda k, d=None: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
blend, out, action = arg("--blend"), os.path.abspath(arg("--out")), arg("--action")
layer, exb, exc = arg("--layer", "body"), arg("--exact-body", "0") == "1", arg("--exact-colors", "1") == "1"
bpy.ops.wm.open_mainfile(filepath=os.path.abspath(blend))
sc = bpy.context.scene; sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = 4
src = bpy.data.texts["render_uo_layer.py"].as_string()
src = src.replace('LAYER = "clothing"', 'LAYER = %r' % layer).replace("ONLY = []", "ONLY = [%r]" % action)
src = src.replace("WRITE_VD = True", "WRITE_VD = False").replace('OUT_DIR = "//uo_render/"', "OUT_DIR = %r" % (out + "/"))
src = src.replace("EXACT_BODY = True", "EXACT_BODY = %r" % exb).replace("EXACT_COLORS = True", "EXACT_COLORS = %r" % exc)
exec(compile(src, "render_uo_layer.py", "exec"))
a = int(action[:2])
for d in range(5):
    fdir = os.path.join(out, layer, "frames", action, "dir%d" % d)
    for fn in sorted(os.listdir(fdir)):
        i = int(fn[:2]); r = np.array(Image.open(os.path.join(fdir, fn)).convert("RGBA")); o = original(a, i, d)
        mr, mo = r[..., 3] > 0, o[..., 3] > 0
        both = mr & mo
        same = (np.abs(r[..., :3].astype(int) - o[..., :3].astype(int)).max(-1) <= 8) & both
        print(f"dir{d} f{i}: IoU {(both).sum()/max((mr|mo).sum(),1):.3f}  missing {(mo&~mr).sum()}  outside {(mr&~mo).sum()}  "
              f"colour equal on overlap {same.sum()/max(both.sum(),1):.3f}")
