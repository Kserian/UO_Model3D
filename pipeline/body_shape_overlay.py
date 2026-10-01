"""Overlay PNG: model silhouette before / after a rest-shape displacement D against the sprite (grey = both, red = sprite only, blue = model only).

    python body_shape_overlay.py pose.npz D.npz OUT.png [a,d,i ...]      e.g.  9,1,2  21,3,0
"""
import sys
import numpy as np
from PIL import Image
import body_shape_lib as L

S = L.Scene(sys.argv[1]); D = np.load(sys.argv[2])["D"]; out = sys.argv[3]
want = [tuple(int(x) for x in a.split(",")) for a in sys.argv[4:]] or [(4, 0, 0), (9, 1, 2), (17, 2, 3), (21, 3, 2), (0, 4, 1)]
idx = {tuple(k): j for j, k in enumerate(S.key)}
rows = []
for k in want:
    f = idx[k]; g = S.G[f]; tiles = []
    for DD in (None, D):
        m = L.model_mask(S, f, DD)[0]
        im = np.zeros(g.shape + (3,), np.uint8); im[g & m] = (200, 200, 200); im[g & ~m] = (255, 40, 40); im[m & ~g] = (60, 90, 255)
        tiles.append(im)
    rows.append(np.hstack(tiles))
Image.fromarray(np.vstack(rows)).resize((rows[0].shape[1] * 4, sum(r.shape[0] for r in rows) * 4), Image.NEAREST).save(out)
