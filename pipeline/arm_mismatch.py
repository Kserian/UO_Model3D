"""Arm-region mismatch per (action, frame): pixels only the model has that belong to an arm part (upper_arm / forearm / hand / clavicle) + pixels only the sprite has whose nearest
model pixel is an arm part, summed over 5 directions (px).   python arm_mismatch.py lab.npz [--top 30]   (lab.npz from body_part_raster.py)"""
import sys, os
import numpy as np
from scipy.ndimage import distance_transform_edt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from body_part_qa import originals
z = np.load(sys.argv[1]); lab, key, parts = z["lab"], z["key"], [str(p) for p in z["parts"]]
top = int(sys.argv[sys.argv.index("--top") + 1]) if "--top" in sys.argv else 30
arm = np.array([p.split(".")[0] in ("upper_arm", "forearm", "hand", "clavicle") for p in parts])
O = originals(); res = {}
for i, k in enumerate(key):
    l = lab[i]; m = l >= 0; o = O[tuple(k)]
    a_only = (m & ~o) & arm[np.where(m, l, 0)]
    _, idx = distance_transform_edt(~m, return_indices=True)
    near = l[idx[0], idx[1]]
    s_only = (o & ~m) & arm[np.where(near >= 0, near, 0)] & (near >= 0)
    r = res.setdefault((int(k[0]), int(k[2])), [0, 0]); r[0] += a_only.sum(); r[1] += s_only.sum()
rows = sorted(((v[0] + v[1], k, v) for k, v in res.items()), reverse=True)
for t, k, v in rows[:top]: print("action %2d frame %d: arm mismatch %3d px (model+ %d, sprite+ %d)" % (k[0], k[1], t, v[0], v[1]))
print("mean per frame %.1f" % np.mean([t for t, _, _ in rows]))
