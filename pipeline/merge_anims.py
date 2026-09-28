"""Merge per-action pose fits into anim_fit.pkl and write a quality table (worst-view silhouette IoU per frame)."""
import pickle, numpy as np, jax, jax.numpy as jnp
from body import *; from fit import *; from targets import targets
from vd import ACTIONS_PEOPLE
SOURCES = [("anim_fit_run1.pkl", [4, 5, 6, 16, 17, 20, 21, 30, 31, 32, 34]),
           ("anim_fit2a.pkl", [0, 1, 2, 3, 7, 9, 10, 11, 15, 18, 33]),
           ("anim_fit2b.pkl", [8, 12, 13, 14, 19, 22]),
           ("anim_fit2c.pkl", [23, 24, 25, 26, 27, 28, 29])]
sf = pickle.load(open("shape_fit.pkl", "rb"))
S = params_to_shape({k: jnp.asarray(v) for k, v in sf["params"]["shape"].items()}, {k: jnp.asarray(v) for k, v in sf["fixed"].items()})
@jax.jit
def sil(pp):
    P, R = fk(S, pose_from_params(pp)); return jnp.stack([render_sil(S, P, R, d) for d in range(5)])
final, rows = {}, []
for f, acts in SOURCES:
    r = pickle.load(open(f, "rb"))
    for a in acts:
        final[a] = dict(poses=r[a]["poses"])
        T = targets(a); w = []
        for i in range(len(T)):
            o = np.asarray(sil({k: jnp.asarray(v[i]) for k, v in r[a]["poses"].items()})) > 0.5
            s = T[i][..., 3] > 127
            w.append(min((o[d] & s[d]).sum() / max((o[d] | s[d]).sum(), 1) for d in range(5)))
        final[a]["worst_iou"] = w
        rows.append((a, ACTIONS_PEOPLE[a], len(T), np.mean(w), np.min(w)))
assert sorted(final) == list(range(35)), sorted(final)
pickle.dump(final, open("anim_fit.pkl", "wb"))
with open("quality_table.md", "w") as fh:
    fh.write("| # | akcja | klatek | IoU średnie (najgorszy kierunek) | IoU min |\n|---|---|---|---|---|\n")
    for a, n, F, m, mn in sorted(rows):
        fh.write(f"| {a} | {n} | {F} | {m:.2f} | {mn:.2f} |\n")
print(open("quality_table.md").read())
