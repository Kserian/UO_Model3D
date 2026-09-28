"""Before/after preview: sprite | v8 overlay | new overlay for one frame, 5 directions, with labels."""
import sys, pickle, numpy as np, jax.numpy as jnp
from PIL import Image, ImageDraw
from posefit_mesh import *
from posefit_mesh import _posed_j
a, i, out = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
A = pickle.load(open("final_poses_v8.pkl", "rb")); B = pickle.load(open(sys.argv[4], "rb"))
T = targets(a); m = T[..., 3] > 127; F = len(T)
hm = horse_masks(a, F) if a in HORSE_OF else np.zeros_like(m)
hid = hm & ~m
ys, xs = np.nonzero((m[i] | hm[i]).any(0)); y0, y1, x0, x1 = max(ys.min() - 3, 0), min(ys.max() + 4, 120), max(xs.min() - 3, 0), min(xs.max() + 4, 136)
def over(P):
    X = _posed_j({k: jnp.asarray(v[i]) for k, v in P[a]["poses"].items()}); row = []; ious = []
    for d in range(5):
        mk = raster_vec(np.asarray(project(X, d))[tris], CANVAS_W, CANVAS_H) & ~hid[i, d]
        img = np.full((120, 136, 3), 30.0); img[hm[i, d]] = (70, 55, 40)
        img[mk & m[i, d]] = 200; img[m[i, d] & ~mk] = (230, 60, 60); img[mk & ~m[i, d]] = (70, 120, 255)
        row.append(img[y0:y1, x0:x1]); ious.append((mk & m[i, d]).sum() / max((mk | m[i, d]).sum(), 1))
    return row, np.mean(ious)
spr = []
for d in range(5):
    s = T[i, d].astype(float); al = s[..., 3:4] / 255; bg = np.full((120, 136, 3), 30.0); bg[hm[i, d]] = (70, 55, 40)
    spr.append((bg * (1 - al) + s[..., :3] * al)[y0:y1, x0:x1])
ra, ia = over(A); rb, ib = over(B)
sep = np.full((y1 - y0, 2, 3), 90.0)
row = lambda L: np.concatenate(sum([[x, sep] for x in L], [])[:-1], 1)
rows = [row(spr), row(ra), row(rb)]
W_ = rows[0].shape[1]; hs = np.full((2, W_, 3), 90.0)
img = np.concatenate([rows[0], hs, rows[1], hs, rows[2]], 0).astype(np.uint8)
S_ = 4; im = Image.fromarray(img).resize((img.shape[1] * S_, img.shape[0] * S_), Image.NEAREST)
lab = Image.new("RGB", (im.width + 230, im.height), (30, 30, 30)); lab.paste(im, (230, 0)); dr = ImageDraw.Draw(lab)
h = (y1 - y0 + 2) * S_
for k, t in enumerate(["oryginal UO", f"v8  IoU {ia:.3f}", f"nowe  IoU {ib:.3f}"]):
    dr.text((10, k * h + h // 2 - 6), t, fill=(235, 235, 235))
dr.text((10, lab.height - 40), "szary = zgodne", fill=(200, 200, 200)); dr.text((10, lab.height - 26), "czerwony = tylko sprite", fill=(230, 90, 90)); dr.text((10, lab.height - 12), "niebieski = tylko model", fill=(110, 150, 255))
lab.save(out)
