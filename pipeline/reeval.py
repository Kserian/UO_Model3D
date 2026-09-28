"""Re-evaluate pose files with the current UO_DELTA (true raster IoU) -> merged dict with fresh iou/limits."""
import sys, pickle
from posefit_mesh import evaluate
out = {}
for f in sys.argv[1:-1]:
    for a, r in pickle.load(open(f, "rb")).items():
        iou, lim = evaluate(a, r["poses"])
        out[a] = dict(r, iou=iou, limits=lim, src=f)
        print(a, f, "%.3f %.3f" % (iou[:, 0].mean(), iou[:, 1].mean()), flush=True)
pickle.dump(out, open(sys.argv[-1], "wb"))
