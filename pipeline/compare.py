"""Render the rigged model through UO_Camera and build side-by-side GIFs: original sprite | 3D model."""
import bpy, sys, os
import numpy as np
from PIL import Image

blend = sys.argv[sys.argv.index("--blend") + 1]
out = sys.argv[sys.argv.index("--out") + 1]
acts = [int(a) for a in sys.argv[sys.argv.index("--actions") + 1].split(",")]
os.makedirs(out, exist_ok=True)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from targets import targets
from vd import ACTIONS_PEOPLE

bpy.ops.wm.open_mainfile(filepath=os.path.abspath(blend))
sc = bpy.context.scene
sc.render.engine = "CYCLES"; sc.cycles.samples = 16; sc.cycles.device = "CPU"
sc.render.resolution_x, sc.render.resolution_y = 136, 120
sc.render.film_transparent = True
sc.cycles.filter_width = float(sys.argv[sys.argv.index("--filter") + 1]) if "--filter" in sys.argv else 1.0
MATTE = "--no-matte" not in sys.argv


def uo_matte(rgba):
    """UO sprites: anti-aliased render over black, then 1-bit alpha -> dark edge pixels."""
    a = rgba[..., 3:4] / 255.0
    out = rgba.copy()
    out[..., :3] = rgba[..., :3] * a
    out[..., 3] = np.where(a[..., 0] >= 0.5, 255, 0)
    # UO art has a dark 1-px outline (outer ring ~0.38 of the next ring's brightness)
    m = out[..., 3] > 0
    inner = m.copy()
    inner[1:] &= m[:-1]; inner[:-1] &= m[1:]; inner[:, 1:] &= m[:, :-1]; inner[:, :-1] &= m[:, 1:]
    ring = m & ~inner
    out[ring, :3] *= OUTLINE
    return out


OUTLINE = float(sys.argv[sys.argv.index("--outline") + 1]) if "--outline" in sys.argv else 0.38
rig = bpy.data.objects["UO_Rig"]
tmp = os.path.abspath(os.path.join(out, "_tmp.png"))
ZOOM = 3
BG = np.array([48, 52, 60], float)


def comp(rgba):
    a = rgba[..., 3:4] / 255.0
    return BG * (1 - a) + rgba[..., :3] * a


for a in acts:
    name = f"{a:02d}_{ACTIONS_PEOPLE[a]}"
    act = bpy.data.actions.get(name)
    if act is None:
        continue
    rig.animation_data.action = act
    T = targets(a)
    F = len(T)
    # crop to union bbox of sprites (+ margin)
    m = T[..., 3].max((0, 1)) > 0
    ys, xs = np.nonzero(m)
    y0, y1, x0, x1 = max(ys.min() - 6, 0), min(ys.max() + 7, 120), max(xs.min() - 6, 0), min(xs.max() + 7, 136)
    frames = []
    ious = []
    errs = []
    for i in range(F):
        cols = []
        for d in range(5):
            rig["uo_direction"] = d
            rig.update_tag()
            sc.frame_set(1 + i * 3)
            sc.render.filepath = tmp
            bpy.ops.render.render(write_still=True)
            r = np.array(Image.open(tmp).convert("RGBA")).astype(float)
            if MATTE:
                r = uo_matte(r)
            s = T[i, d].astype(float)
            ma, mb = r[..., 3] > 127, s[..., 3] > 127
            ious.append((ma & mb).sum() / max((ma | mb).sum(), 1))
            both = ma & mb
            if both.any():
                errs.append(np.abs(r[..., :3][both] - s[..., :3][both]).mean())
            pair = np.concatenate([comp(s)[y0:y1, x0:x1], comp(r)[y0:y1, x0:x1]], 0)
            cols.append(pair)
            cols.append(np.full((pair.shape[0], 2, 3), 90.0))
        img = np.concatenate(cols[:-1], 1).astype(np.uint8)
        im = Image.fromarray(img)
        frames.append(im.resize((im.width * ZOOM, im.height * ZOOM), Image.NEAREST))
    dur = 125 if F > 1 else 1000
    frames[0].save(os.path.join(out, f"compare_{name}.gif"), save_all=True, append_images=frames[1:], duration=dur, loop=0)
    frames[0].save(os.path.join(out, f"compare_{name}_f0.png"))
    print("gif", name, "silhouette IoU %.3f" % np.mean(ious), "mean colour error %.1f/255" % np.mean(errs), flush=True)
