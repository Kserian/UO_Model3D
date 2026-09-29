import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
import json, numpy as np
MH = os.path.join(HERE, "mh", "")
def load_mh(muscle=0.6, male=1.0):
    V, F, grp = [], [], None
    for line in open(MH + "base.obj"):
        if line.startswith("v "): V.append([float(x) for x in line.split()[1:4]])
        elif line.startswith("g "): grp = line.split()[1]
        elif line.startswith("f ") and grp == "body": F.append([int(t.split("/")[0]) - 1 for t in line.split()[1:]])
    V = np.array(V)
    def target(fn, w):
        for line in open(MH + fn):
            if line[0].isdigit():
                p = line.split(); V[int(p[0])] += w * np.array([float(x) for x in p[1:4]])
    target("male.target", male)
    if muscle: target("universal-male-young-maxmuscle-averageweight.target", muscle)
    P = V[:, [0, 2, 1]] * np.array([1.0, -1.0, 1.0]) * 0.1          # MH: Y up, dm, faces +Z -> Blender Z up, m, faces -Y
    sk = json.load(open(MH + "default.mhskel"))
    J = {k: P[v].mean(0) for k, v in sk["joints"].items()}
    bones = {b: (J[d["head"]], J[d["tail"]], d["parent"]) for b, d in sk["bones"].items()}
    W = json.load(open(MH + "default_weights.mhw"))["weights"]
    return P, F, bones, W
