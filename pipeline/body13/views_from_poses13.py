"""views npz with 55-bone skin matrices from refit poses: views_from_poses13.py shape.json poses.json out.npz"""
import sys, json, numpy as np
from shape13 import Shape, load_params
from skel13 import Skel13
from posefit13 import Frame13
from fk import rig_world
r = np.load("rig_poses.npz"); v = np.load("views_all.npz"); bones = list(r["bones"]); P = json.load(open(sys.argv[2]))
S = Shape(v["U"], v["BV"], v["BDOM"], bones); Vf = S.build(load_params(sys.argv[1]), full=True)
K = Skel13(S, r["R"], r["parent"], bones, Vf)
fk = {tuple(k): n for n, k in enumerate(r["keys"])}
W = np.zeros((len(v["keys"]), len(K.names), 4, 4)); cache = {}
for n, (a, i, d) in enumerate(v["keys"]):
    if (a, i) not in cache:
        f = fk[(a, i)]
        fr = Frame13(K, None, None, None, None, r["Brel"], None, None, [], r["loc"][f], r["quat"][f])
        cache[(a, i)] = fr.skin(np.array(P["%d,%d" % (a, i)]["x"]))
    W[n] = rig_world(d) @ cache[(a, i)]
out = {k: v[k] for k in v.files}; out["W"] = W
np.savez_compressed(sys.argv[3], **out); print("ok", W.shape)
