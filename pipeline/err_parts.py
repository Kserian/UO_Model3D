"""Attribute silhouette errors to body parts: red = sprite-only px (nearest model part), blue = model-only px."""
import sys, pickle, numpy as np, jax, jax.numpy as jnp
from scipy.ndimage import distance_transform_edt
from posefit_mesh import *
from posefit_mesh import _posed_j
from vd import ACTIONS_PEOPLE
P = pickle.load(open(sys.argv[1], "rb"))
ACTS = [int(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [a for a in range(35) if a not in MOUNTED]
groups = ["head", "neck", "chest", "spine", "pelvis", "upperarm", "forearm", "hand", "thigh", "shin", "foot"]
Wn = np.asarray(md["W"]); bones = md["bones"]
def grp(b):
    n = b.split(".")[0]
    for g in groups:
        if n.startswith(g): return g
    return {"shoulder": "upperarm", "clavicle": "chest"}.get(n, n)
bg = [grp(b) for b in bones]
G = sorted(set(bg)); gi = {g: i for i, g in enumerate(G)}
vlab = np.array([gi[bg[j]] for j in Wn.argmax(1)])
tlab = vlab[tris[:, 0]]
print("groups", G)

def raster_lab(Pt, lab):
    mn = np.floor(Pt.min(1)).astype(int); mx = np.ceil(Pt.max(1)).astype(int)
    size = np.clip(mx - mn, 0, 12)
    a, b, c = Pt[:, 0], Pt[:, 1], Pt[:, 2]
    den = (b[:, 1] - c[:, 1]) * (a[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (a[:, 1] - c[:, 1])
    ok = np.abs(den) > 1e-12
    img = np.full((CANVAS_H, CANVAS_W), -1)
    for dy in range(int(size[:, 1].max()) + 1):
        for dx in range(int(size[:, 0].max()) + 1):
            t = np.nonzero(ok & (dx <= size[:, 0]) & (dy <= size[:, 1]))[0]
            px = mn[t, 0] + dx; py = mn[t, 1] + dy; cx, cy = px + 0.5, py + 0.5
            aa, bb, cc, dd = a[t], b[t], c[t], den[t]
            l0 = ((bb[:, 1] - cc[:, 1]) * (cx - cc[:, 0]) + (cc[:, 0] - bb[:, 0]) * (cy - cc[:, 1])) / dd
            l1 = ((cc[:, 1] - aa[:, 1]) * (cx - cc[:, 0]) + (aa[:, 0] - cc[:, 0]) * (cy - cc[:, 1])) / dd
            l2 = 1 - l0 - l1
            k = (l0 >= -1e-4) & (l1 >= -1e-4) & (l2 >= -1e-4) & (px >= 0) & (py >= 0) & (px < CANVAS_W) & (py < CANVAS_H)
            img[py[k], px[k]] = lab[t[k]]
    return img

red = np.zeros((35, len(G))); blue = np.zeros((35, len(G))); area = np.zeros(35)
for a in ACTS:
    T = targets(a); masks = T[..., 3] > 127; F = len(T)
    hidden = (horse_masks(a, F) & ~masks) if a in HORSE_OF else np.zeros_like(masks)
    for i in range(F):
        X = np.asarray(_posed_j({k: jnp.asarray(v[i]) for k, v in P[a]["poses"].items()}))
        for d in range(5):
            L = raster_lab(np.asarray(project(jnp.asarray(X), d))[tris], tlab)
            L[hidden[i, d]] = -1
            mk = L >= 0; s = masks[i, d]
            area[a] += s.sum()
            b = mk & ~s
            np.add.at(blue[a], L[b], 1)
            r = s & ~mk
            if r.any():
                _, (iy, ix) = distance_transform_edt(~mk, return_indices=True)
                np.add.at(red[a], L[iy[r], ix[r]], 1)
tot_r = red.sum(0); tot_b = blue.sum(0)
print("%-10s %8s %8s   (pixels, all listed actions)" % ("part", "sprite+", "model+"))
for g in G:
    print("%-10s %8d %8d" % (g, tot_r[gi[g]], tot_b[gi[g]]))
print("per action worst part (sprite-only):")
for a in ACTS:
    j = red[a].argmax(); k = blue[a].argmax()
    print(f"{a:2d} {ACTIONS_PEOPLE[a]:22s} red {red[a].sum()/area[a]:.3f} ({G[j]} {red[a,j]/area[a]:.3f})  blue {blue[a].sum()/area[a]:.3f} ({G[k]} {blue[a,k]/area[a]:.3f})")
