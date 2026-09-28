"""zoom.py poses.pkl a i out.png : row 1 = sprite (5 dirs), row 2 = overlay (grey both, red sprite only, blue model only)"""
import sys, pickle, numpy as np, jax.numpy as jnp
from PIL import Image
from posefit_mesh import *
from posefit_mesh import _posed_j
P = pickle.load(open(sys.argv[1], "rb")); a, i = int(sys.argv[2]), int(sys.argv[3]); out = sys.argv[4]
T = targets(a); m = T[..., 3] > 127; F = len(T)
hid = (horse_masks(a, F) & ~m) if a in HORSE_OF else np.zeros_like(m)
X = _posed_j({k: jnp.asarray(v[i]) for k, v in P[a]["poses"].items()})
ys, xs = np.nonzero(m[i].any(0)); y0, y1, x0, x1 = max(ys.min() - 5, 0), min(ys.max() + 6, 120), max(xs.min() - 5, 0), min(xs.max() + 6, 136)
top, bot = [], []
for d in range(5):
    s = T[i, d].astype(float); bg = np.array([40, 40, 48.0]); al = s[..., 3:4] / 255
    top.append((bg * (1 - al) + s[..., :3] * al)[y0:y1, x0:x1])
    mk = raster_vec(np.asarray(project(X, d))[tris], CANVAS_W, CANVAS_H) & ~hid[i, d]
    img = np.full((120, 136, 3), 30.0); img[hid[i, d]] = (70, 55, 40)
    img[mk & m[i, d]] = 200; img[m[i, d] & ~mk] = (230, 60, 60); img[mk & ~m[i, d]] = (70, 120, 255)
    bot.append(img[y0:y1, x0:x1])
sep = np.full((y1 - y0, 2, 3), 90.0)
row = lambda L: np.concatenate(sum([[x, sep] for x in L], [])[:-1], 1)
im = Image.fromarray(np.concatenate([row(top), np.full((2, row(top).shape[1], 3), 90.0), row(bot)], 0).astype(np.uint8))
im.resize((im.width * 4, im.height * 4), Image.NEAREST).save(out)
