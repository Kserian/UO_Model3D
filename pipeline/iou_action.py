"""Silhouette IoU per frame (mean of 5 directions) of one action from a body_part_raster.py npz vs the original frames.   python iou_action.py lab.npz ACTION [lab2.npz]"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from body_part_qa import originals
O = originals(); a = int(sys.argv[2]); zs = [np.load(p) for p in (sys.argv[1], *sys.argv[3:])]
for z in zs:
    lab, key = z["lab"], z["key"]; r = {}
    for i, k in enumerate(key):
        if k[0] != a: continue
        m = lab[i] >= 0; o = O[tuple(k)]; r.setdefault(k[2], []).append((m & o).sum() / max((m | o).sum(), 1))
    print(" ".join("f%d %.3f" % (f, np.mean(v)) for f, v in sorted(r.items())), "| mean %.4f" % np.mean([np.mean(v) for v in r.values()]))
