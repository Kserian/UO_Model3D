"""final_poses_v6.pkl = v6pre with the de-jittered actions + quality table (Polish headers like v5)."""
import pickle, numpy as np
from vd import ACTIONS_PEOPLE
pre = pickle.load(open("final_poses_v6pre.pkl", "rb")); v5 = pickle.load(open("final_poses_v5.pkl", "rb"))
out = {a: dict(r) for a, r in pre.items()}
for f in ("posefit_J1.pkl", "posefit_J2.pkl"):
    for a, r in pickle.load(open(f, "rb")).items():
        out[a] = dict(r, src=pre[a].get("src", "v5") + "+dejitter")
pickle.dump(out, open("final_poses_v6.pkl", "wb"))
L = ["| # | akcja | IoU najgorszy kier. (śr.) | min | IoU średnie | limity (max) | v5 IoU najgorszy | v5 IoU średnie |", "|---|---|---|---|---|---|---|---|"]
for a in range(35):
    r = out[a]["iou"]; o = v5[a]["iou"]
    L.append(f"| {a} | {ACTIONS_PEOPLE[a]} | {r[:,0].mean():.3f} | {r[:,0].min():.3f} | {r[:,1].mean():.3f} | {out[a]['limits'].max():.4f} | {o[:,0].mean():.3f} | {o[:,1].mean():.3f} |")
w = np.mean([out[a]["iou"][:, 0].mean() for a in range(35)]); w5 = np.mean([v5[a]["iou"][:, 0].mean() for a in range(35)])
m = np.mean([out[a]["iou"][:, 1].mean() for a in range(35)]); m5 = np.mean([v5[a]["iou"][:, 1].mean() for a in range(35)])
L.append(f"| | **średnio** | **{w:.3f}** | | **{m:.3f}** | | {w5:.3f} | {m5:.3f} |")
open("quality_v6.md", "w").write("\n".join(L) + "\n")
print("\n".join(L[-3:]))
