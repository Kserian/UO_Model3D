"""render_overlay.py <render root (…/body)> action out.png : grey both, red sprite-only, blue render-only, brown = horse sprite"""
import sys, os, numpy as np
from PIL import Image
from targets import targets
from vd import ACTIONS_PEOPLE
root, a, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
T = targets(a); m = T[..., 3] > 127; F = len(T)
hm = None
if a >= 23 and a <= 29:
    from posefit_mesh import horse_masks
    hm = horse_masks(a, F)
name = f"{a:02d}_{ACTIONS_PEOPLE[a]}"
rows = []
for i in range(F):
    row = []
    for d in range(5):
        r = np.array(Image.open(os.path.join(root, "frames", name, "dir%d" % d, "%02d.png" % i)))[..., 3] > 127
        img = np.full((120, 136, 3), 30, np.uint8)
        if hm is not None: img[hm[i, d]] = (70, 55, 40)
        img[r & m[i, d]] = 200; img[m[i, d] & ~r] = (230, 60, 60); img[r & ~m[i, d]] = (70, 120, 255)
        row.append(img); row.append(np.full((120, 2, 3), 90, np.uint8))
    rows.append(np.concatenate(row[:-1], 1))
im = Image.fromarray(np.concatenate(rows, 0)); im.resize((im.width * 2, im.height * 2), Image.NEAREST).save(out)
