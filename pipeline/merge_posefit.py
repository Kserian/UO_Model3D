"""Pick, per action, the best plausible pose set among all fitting runs (mesh-based IoU, anatomical limits)."""
import pickle, os, sys
import numpy as np
from posefit_mesh import evaluate
from vd import ACTIONS_PEOPLE
anim = pickle.load(open("anim_fit.pkl", "rb")); ref = pickle.load(open("refine_mesh.pkl", "rb"))
ridx = {s: i for i, s in enumerate(ref["samples"])}
BASE = os.environ.get("UO_BASE")          # previous iteration's final poses (instead of the first-pass fits)


def old(a):
    if BASE:
        return {k: np.asarray(v) for k, v in pickle.load(open(BASE, "rb"))[a]["poses"].items()}
    F = anim[a]["poses"]["trans"].shape[0]
    return {n: np.stack([ref["poses"][n][ridx[(a, i)]] if (a, i) in ridx else anim[a]["poses"][n][i] for i in range(F)]) for n in ("ball", "hinge", "trans")}
files = [f for f in sys.argv[1:] if os.path.exists(f)]
runs = {f: pickle.load(open(f, "rb")) for f in files}
CACHE = os.environ.get("UO_CACHE", "merge_cache.pkl")
OUTF = os.environ.get("UO_FINAL", "final_poses.pkl")
cache = pickle.load(open(CACHE, "rb")) if os.path.exists(CACHE) else {}
final, table = {}, []
for a in range(35):
    cands = []
    if ("old", a) not in cache:
        r, lim = evaluate(a, old(a)); cache[("old", a)] = (r, lim)
    r, lim = cache[("old", a)]
    cands.append(("old", old(a), r, lim))
    for f, res in runs.items():
        if a in res:
            cands.append((f, res[a]["poses"], res[a]["iou"], res[a]["limits"]))
    ok = [c for c in cands if c[3].max() < 0.01] or cands
    best = max(ok, key=lambda c: c[2][:, 0].mean())
    final[a] = dict(poses=best[1], iou=best[2], limits=best[3], src=best[0])
    table.append((a, ACTIONS_PEOPLE[a], best[0], best[2][:, 0].mean(), best[2][:, 0].min(), best[2][:, 1].mean(), best[3].max(),
                  cands[0][2][:, 0].mean(), cands[0][3].max()))
pickle.dump(cache, open(CACHE, "wb"))
pickle.dump(final, open(OUTF, "wb"))
with open(os.environ.get("UO_TABLE", "quality_v4.md"), "w") as fh:
    fh.write("| # | akcja | IoU najgorszy kier. (śr.) | min | IoU średnie | limity (max) | wcześniej IoU | wcześniej limity |\n|---|---|---|---|---|---|---|---|\n")
    for a, n, src, m, mn, mm, lm, om, olm in table:
        fh.write(f"| {a} | {n} | {m:.3f} | {mn:.3f} | {mm:.3f} | {lm:.4f} | {om:.3f} | {olm:.3f} |\n")
        print(f"{a:2d} {n:24s} src={os.path.basename(src):16s} worst {m:.3f} min {mn:.3f} mean {mm:.3f} lim {lm:.4f} | old {om:.3f} lim {olm:.2f}")
