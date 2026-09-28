"""final_poses_v10.pkl = v10pre with the de-jittered actions + quality table (Polish headers like v5)."""
import pickle, numpy as np
from vd import ACTIONS_PEOPLE
pre = pickle.load(open("final_poses_v10pre.pkl", "rb")); v6 = pickle.load(open("final_poses_v9_ref.pkl", "rb"))
out = {a: dict(r) for a, r in pre.items()}
for f in ("posefit_K11.pkl",):
    for a, r in pickle.load(open(f, "rb")).items():
        out[a] = dict(r, src=pre[a].get("src", "v9") + "+dejitter")
pickle.dump(out, open("final_poses_v10.pkl", "wb"))
L = ["| # | akcja | IoU najgorszy kier. (śr.) | min | IoU średnie | limity (max) | v9 IoU najgorszy | v9 IoU średnie |", "|---|---|---|---|---|---|---|---|"]
for a in range(35):
    r = out[a]["iou"]; o = v6[a]["iou"]
    L.append(f"| {a} | {ACTIONS_PEOPLE[a]} | {r[:,0].mean():.3f} | {r[:,0].min():.3f} | {r[:,1].mean():.3f} | {out[a]['limits'].max():.4f} | {o[:,0].mean():.3f} | {o[:,1].mean():.3f} |")
w = np.mean([out[a]["iou"][:, 0].mean() for a in range(35)]); w5 = np.mean([v6[a]["iou"][:, 0].mean() for a in range(35)])
m = np.mean([out[a]["iou"][:, 1].mean() for a in range(35)]); m5 = np.mean([v6[a]["iou"][:, 1].mean() for a in range(35)])
L.append(f"| | **średnio** | **{w:.3f}** | | **{m:.3f}** | | {w5:.3f} | {m5:.3f} |")
open("quality_v10.md", "w").write("\n".join(L) + "\n")
print("\n".join(L[-3:]))
