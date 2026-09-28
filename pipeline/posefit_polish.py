"""Joint polish of whole actions from a base pose file (all loss terms incl. the ground term)."""
import sys, os, time, pickle
import numpy as np
from posefit_mesh import *
from posefit_mesh import _posed_j

BASE = sys.argv[sys.argv.index("--base") + 1]
OUT = sys.argv[sys.argv.index("--out") + 1]
ITERS = int(os.environ.get("UO_ITERS", "300"))
ACTS = [int(a) for a in sys.argv[1:] if a.isdigit() and sys.argv[sys.argv.index(a) - 1] not in ("--base", "--out")]
base = pickle.load(open(BASE, "rb"))
for a in ACTS:
    t0 = time.time()
    init = {k: np.asarray(v) for k, v in base[a]["poses"].items()}
    if os.environ.get("UO_CLAV") and "clav" not in init:          # add clavicle offsets (start at 0)
        init["clav"] = np.zeros((init["trans"].shape[0], 2, 3), np.float32)
    batch, masks = fit_action(a, init, iters=ITERS, lr=float(os.environ.get("UO_LR", "0.004")), log=False)
    r, lim = evaluate(a, batch, masks)
    res = pickle.load(open(OUT, "rb")) if os.path.exists(OUT) else {}
    res[a] = dict(poses=batch, iou=r, limits=lim)
    pickle.dump(res, open(OUT, "wb"))
    X = [np.asarray(_posed_j({k: jnp.asarray(v[i]) for k, v in batch.items()}))[:, 2].min() for i in range(len(r))]
    r0 = base[a]["iou"]
    print(f"action {a:2d} worstIoU {r0[:,0].mean():.3f} -> {r[:,0].mean():.3f}  mean {r0[:,1].mean():.3f} -> {r[:,1].mean():.3f}"
          f"  lowest z {min(X):+.3f}  max limit {lim.max():.4f}  {time.time()-t0:.0f}s", flush=True)
