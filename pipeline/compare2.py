"""Render the BODY layer with render_uo_layer.py (UO look, horse holdout, UO post-process) and build
side-by-side GIFs (original sprite | model) + metrics for the given actions."""
import bpy, sys, os
import numpy as np
from PIL import Image

blend = sys.argv[sys.argv.index("--blend") + 1]
out = os.path.abspath(sys.argv[sys.argv.index("--out") + 1])
ACT_IDS = [int(a) for a in sys.argv[sys.argv.index("--actions") + 1].split(",")]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from targets import targets
from vd import ACTIONS_PEOPLE

bpy.ops.wm.open_mainfile(filepath=os.path.abspath(blend))
sc = bpy.context.scene
sc.render.engine = "CYCLES"; sc.cycles.samples = 16; sc.cycles.device = "CPU"
NAMES = [f"{a:02d}_{ACTIONS_PEOPLE[a]}" for a in ACT_IDS]
src = bpy.data.texts["render_uo_layer.py"].as_string()
import re
src = re.sub(r'(?m)^LAYER = "clothing"', 'LAYER = "body"', src, count=1)             # the settings line, not the header
src = re.sub(r'(?m)^ONLY = \[\]', "ONLY = %r" % NAMES, src, count=1)
src = re.sub(r'(?m)^EXACT_BODY = True', "EXACT_BODY = False", src, count=1)           # the 3D model itself, not the original
src = src.replace('WRITE_VD = True', 'WRITE_VD = False').replace('OUT_DIR = "//uo_render/"', 'OUT_DIR = %r' % (out + "/"))
exec(compile(src, "render_uo_layer.py", "exec"))
BG = np.array([48, 52, 60], float)


def comp(rgba):
    a = rgba[..., 3:4] / 255.0
    return BG * (1 - a) + rgba[..., :3] * a


os.makedirs(out, exist_ok=True)
for a, name in zip(ACT_IDS, NAMES):
    T = targets(a)
    m = T[..., 3].max((0, 1)) > 0
    ys, xs = np.nonzero(m)
    y0, y1, x0, x1 = max(ys.min() - 6, 0), min(ys.max() + 7, 120), max(xs.min() - 6, 0), min(xs.max() + 7, 136)
    frames, ious, errs = [], [], []
    for i in range(len(T)):
        cols = []
        for d in range(5):
            r = np.array(Image.open(os.path.join(out, "body", "frames", name, "dir%d" % d, "%02d.png" % i)).convert("RGBA")).astype(float)
            s = T[i, d].astype(float)
            ma, mb = r[..., 3] > 127, s[..., 3] > 127
            ious.append((ma & mb).sum() / max((ma | mb).sum(), 1))
            both = ma & mb
            if both.any():
                errs.append(np.abs(r[..., :3][both] - s[..., :3][both]).mean())
            cols.append(np.concatenate([comp(s)[y0:y1, x0:x1], comp(r)[y0:y1, x0:x1]], 0))
            cols.append(np.full((cols[-1].shape[0], 2, 3), 90.0))
        im = Image.fromarray(np.concatenate(cols[:-1], 1).astype(np.uint8))
        frames.append(im.resize((im.width * 3, im.height * 3), Image.NEAREST))
    frames[0].save(os.path.join(out, f"compare_{name}.gif"), save_all=True, append_images=frames[1:],
                   duration=125 if len(frames) > 1 else 1000, loop=0)
    print("gif", name, "silhouette IoU %.3f" % np.mean(ious), "mean colour error %.1f/255" % np.mean(errs), flush=True)
