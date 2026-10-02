"""Joins the per-pixel geometry of the 3D body (light_raster.py) with the original UO body frames: one table of pixels that both cover (outline excluded).

    from light_data import load; D = load(["part_0.npz", ...])
D: dict of arrays (one entry per pixel): action, dir, frame, y, x, N (3), P (3), uv (2), part, lit, ao, rgb (3 uint8, the ORIGINAL pixel), edge (distance in px to the
original silhouette, 1 = outline pixel), plus `parts` and `L`.
"""
import json, os
import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
ORIG = os.path.join(HERE, "..", "client", "body_0x190_frames")


def load(files):
    meta = json.load(open(os.path.join(ORIG, "meta.json")))
    names = {b["action"]: "%02d_%s" % (b["action"], b["name"]) for b in meta["blocks"]}
    files_of = {(b["action"], b["dir"]): [f["file"] for f in b["frames"]] for b in meta["blocks"]}
    out = {k: [] for k in ("action", "dir", "frame", "y", "x", "N", "P", "uv", "part", "lit", "ao", "rgb", "edge")}
    parts, L = None, None
    for fn in files:
        z = np.load(fn)
        parts, L = z["parts"], z["L"]
        key, fr = z["key"], z["frame"]
        starts = np.searchsorted(fr, np.arange(len(key)))
        ends = np.searchsorted(fr, np.arange(len(key)), side="right")
        for k, (a, d, i) in enumerate(key):
            fl = files_of.get((int(a), int(d)))
            if not fl or i >= len(fl):
                continue
            im = np.array(Image.open(os.path.join(ORIG, "frames", names[int(a)], "dir%d" % d, fl[i])).convert("RGBA"))
            m = im[..., 3] > 0
            if not m.any():
                continue
            dist = ndimage.distance_transform_cdt(m, metric="taxicab")
            s = slice(starts[k], ends[k])
            y, x = z["y"][s].astype(int), z["x"][s].astype(int)
            ok = m[y, x]
            for name, arr in (("y", y), ("x", x), ("N", z["N"][s].astype(np.float32)), ("P", z["P"][s].astype(np.float32)), ("uv", z["uv"][s].astype(np.float32)),
                              ("part", z["part"][s]), ("lit", z["lit"][s]), ("ao", z["ao"][s])):
                out[name].append(arr[ok])
            out["rgb"].append(im[y[ok], x[ok], :3]); out["edge"].append(dist[y[ok], x[ok]].astype(np.int8))
            n = int(ok.sum())
            out["action"].append(np.full(n, a, np.int8)); out["dir"].append(np.full(n, d, np.int8)); out["frame"].append(np.full(n, i, np.int16))
    D = {k: np.concatenate(v) for k, v in out.items()}
    D["parts"], D["L"] = parts, L
    return D
