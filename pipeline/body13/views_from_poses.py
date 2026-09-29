"""views npz with skin matrices from refit poses: views_from_poses.py poses.json out.npz"""
import sys, json, numpy as np
from posefit import rotvec
from fk import qmat, rig_world
r = np.load("rig_poses.npz"); v = np.load("views_all.npz"); P = json.load(open(sys.argv[1]))
R, par, Brel = r["R"], r["parent"], r["Brel"]; Rinv = np.linalg.inv(R); B = len(R)
fk = {tuple(k): n for n, k in enumerate(r["keys"])}
W = v["W"].copy()
for n, (a, i, d) in enumerate(v["keys"]):
    x = np.array(P["%d,%d" % (a, i)]["x"]); f = fk[(a, i)]
    rr = x[:3 * B].reshape(B, 3); dl = x[3 * B:3 * B + 3]; g = x[3 * B + 3:].reshape(B, 2) if len(x) > 3 * B + 3 else np.zeros((B, 2))
    Pm = np.zeros((B, 4, 4))
    for b in range(B):
        M = np.eye(4); M[:3, :3] = qmat(r["quat"][f, b]) @ rotvec(rr[b]); M[:3, 3] = r["loc"][f, b] + (dl if b == 0 else 0)
        Pm[b] = (R[b] if par[b] < 0 else Pm[par[b]] @ Rinv[par[b]] @ R[b]) @ M
    Gm = np.tile(np.eye(4), (B, 1, 1)); Gm[:, 0, 0] = np.exp(g[:, 0]); Gm[:, 2, 2] = np.exp(g[:, 1])
    W[n] = rig_world(d) @ Pm @ Gm @ Rinv @ Brel
out = {k: v[k] for k in v.files}; out["W"] = W
np.savez_compressed(sys.argv[2], **out); print("ok", len(W))
