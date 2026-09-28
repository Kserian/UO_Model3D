"""v6 merge: base = v5 (+ die actions with the floor term). Search results replace an action when the mean worst-view
IoU improves; floor-polish results replace it when the IoU is (nearly) unchanged (<= 0.003 lower) but less sinks
below the floor. Output: final_poses_v6pre.pkl (then jitter_fix.py -> final)."""
import pickle, numpy as np, jax.numpy as jnp
from posefit_mesh import GROUND, MOUNTED
from posefit_mesh import _posed_j
base = pickle.load(open("final_poses_v6base.pkl", "rb"))
out = {a: dict(r) for a, r in base.items()}


def sink(p):
    F = p["trans"].shape[0]
    return max(float(GROUND - np.asarray(_posed_j({k: jnp.asarray(v[i]) for k, v in p.items()}))[:, 2].min()) for i in range(F))


for f in ("posefit_L1.pkl", "posefit_L2.pkl"):
    for a, r in pickle.load(open(f, "rb")).items():
        o = out[a]
        if r["limits"].max() < 0.01 and r["iou"][:, 0].mean() > o["iou"][:, 0].mean() + 1e-4:
            print(f"{a:2d} search  {o['iou'][:,0].mean():.3f} -> {r['iou'][:,0].mean():.3f}  ({f})")
            out[a] = dict(r, src=f)
        else:
            print(f"{a:2d} search  kept {o['iou'][:,0].mean():.3f} (cand {r['iou'][:,0].mean():.3f})")
for a, r in pickle.load(open("posefit_P3.pkl", "rb")).items():
    o = out[a]
    s0, s1 = sink(o["poses"]), sink(r["poses"])
    ok = r["limits"].max() < 0.01 and r["iou"][:, 1].mean() >= o["iou"][:, 1].mean() - 0.003 and s1 < s0 - 0.003
    print(f"{a:2d} floor   sink {s0*100:.1f} -> {s1*100:.1f} cm  IoU {o['iou'][:,1].mean():.3f} -> {r['iou'][:,1].mean():.3f}  {'ACCEPT' if ok else 'keep'}")
    if ok:
        out[a] = dict(r, src="posefit_P3.pkl")
pickle.dump(out, open("final_poses_v6pre.pkl", "wb"))
print("saved final_poses_v6pre.pkl")
