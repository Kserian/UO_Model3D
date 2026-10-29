"""Per-frame horizontal shifts that put a rendered beard where the original beard of the same frame sits; the input of render_uo_layer.py ITEM_MOTION.

    python uo_beard_shift.py ORIG_FRAMES BEARD_FRAMES ZONE_FRAMES OUT.json [--bone head] [--pivot X Y Z] [--max 3] [--window 3]

ORIG_FRAMES: `vdtool.py extract` of the original animation; BEARD_FRAMES: a first render of the beard (ITEM_MOTION with no "shift": it hangs from the head point, translation only); ZONE_FRAMES: the jaw
zone render (uo_jaw_zone.py). For every frame: dx = centre of mass (column) of the original beard below the zone - centre of mass of ours, median-filtered over `window` frames, whole pixels, at most
`max`. The centre of mass of the whole beard does not depend on what the head hides at the top (the top edge does: moving the beard changed it, and the fit chased its own tail). No dy: the
vertical position is the 3D one. A second render with the written file applies the shift to the 3D item BEFORE the head, the hands and the arms hide it, so they cut it in the right place.
"""
import argparse, json, sys, importlib.util, os
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("orig"); ap.add_argument("beard"); ap.add_argument("zone"); ap.add_argument("out")
ap.add_argument("--bone", default="head"); ap.add_argument("--pivot", type=float, nargs=3, default=[0.014, -0.205, 1.64])
ap.add_argument("--max", type=int, default=3); ap.add_argument("--window", type=int, default=3)
a = ap.parse_args()
spec = importlib.util.spec_from_file_location("hy", os.path.join(os.path.dirname(os.path.abspath(__file__)), "uo_hybrid_beard.py"))
sys.argv = ["x", "a", "b", "c", "d"]                      # uo_hybrid_beard parses its own arguments on import
hy = importlib.util.module_from_spec(spec); spec.loader.exec_module(hy)
mb = json.load(open(os.path.join(a.beard, "meta.json"))); mz = json.load(open(os.path.join(a.zone, "meta.json"))); mo = json.load(open(os.path.join(a.orig, "meta.json")))
W, H = mb["canvas"]; ax, ay = mb["anchor"]
out = {}
for blk in mb["blocks"]:
    act, d = blk["action"], blk["dir"]; n = len(blk["frames"])
    if n == 0:
        continue
    diffs = []
    for i in range(n):
        B, _ = hy.load(a.beard, act, d, i); O, _ = hy.load(a.orig, act, d, i); Z, _ = hy.load(a.zone, act, d, i)
        if B is None or O is None or Z is None:
            diffs.append(None); continue
        Bc = hy.on_canvas(B, mb, W, H, ax, ay); Oc = hy.on_canvas(O, mo, W, H, ax, ay); Zc = hy.on_canvas(Z, mz, W, H, ax, ay)[..., 3] > 0
        lo = (Oc[..., 3] > 0) & ~Zc; lb = Bc[..., 3] > 0
        diffs.append(np.array([np.nonzero(lo)[1].mean() - np.nonzero(lb)[1].mean(), 0.0]) if lo.sum() >= 4 and lb.sum() >= 4 else None)
    sm = hy.median3(diffs, a.window)
    known = [x for x in sm if x is not None]
    fill = np.median(known, 0) if known else np.zeros(2)
    out["%d:%d" % (act, d)] = [[int(c) for c in np.clip(np.rint(fill if x is None else x), -a.max, a.max)] for x in sm]
json.dump(dict(bone=a.bone, pivot=a.pivot, shift=out), open(a.out, "w"))
v = np.array([s for l in out.values() for s in l])
print("uo_beard_shift: %d blocks, dx mean %+.2f std %.2f, |dx| >= 3: %.0f%%" % (len(out), v[:, 0].mean(), v[:, 0].std(), 100 * (np.abs(v[:, 0]) >= 3).mean()))
