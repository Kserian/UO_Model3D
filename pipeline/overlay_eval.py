"""Overlay: grey = both, red = sprite only, blue = model only (skinned mesh raster), per frame x direction."""
import sys, pickle, numpy as np
from PIL import Image
from posefit_mesh import posed, project, raster_vec, tris, horse_masks, HORSE_OF
from targets import targets
import jax.numpy as jnp
from body import CANVAS_W, CANVAS_H
res = pickle.load(open(sys.argv[1], "rb")); a = int(sys.argv[2]); out = sys.argv[3]
T = targets(a); F = len(T); masks = T[..., 3] > 127
hidden = (horse_masks(a, F) & ~masks) if a in HORSE_OF else np.zeros_like(masks)
m = masks.any((0, 1)); ys, xs = np.nonzero(m); y0, y1, x0, x1 = max(ys.min() - 4, 0), min(ys.max() + 5, CANVAS_H), max(xs.min() - 4, 0), min(xs.max() + 5, CANVAS_W)
rows = []
for i in range(F):
    X = np.asarray(posed({k: jnp.asarray(v[i]) for k, v in res[a]["poses"].items()}))
    row = []
    for d in range(5):
        mk = raster_vec(np.asarray(project(jnp.asarray(X), d))[tris], CANVAS_W, CANVAS_H) & ~hidden[i, d]
        s = masks[i, d]
        img = np.full((CANVAS_H, CANVAS_W, 3), 30, np.uint8)
        img[hidden[i, d]] = (70, 55, 40)
        img[mk & s] = (200, 200, 200); img[s & ~mk] = (235, 60, 60); img[mk & ~s] = (70, 120, 255)
        row.append(img[y0:y1, x0:x1]); row.append(np.full((y1 - y0, 2, 3), 90, np.uint8))
    rows.append(np.concatenate(row[:-1], 1))
im = Image.fromarray(np.concatenate(rows, 0)); im.resize((im.width * 3, im.height * 3), Image.NEAREST).save(out)
