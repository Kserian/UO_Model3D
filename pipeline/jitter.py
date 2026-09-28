"""Frame-to-frame rotation changes per joint (degrees); flags spikes where a joint goes A->B->A (jitter)."""
import sys, pickle, numpy as np
from scipy.spatial.transform import Rotation as Rot
from fit import BALL_IDX
from body import JOINTS
from vd import ACTIONS_PEOPLE
P = pickle.load(open(sys.argv[1], "rb"))
names = [JOINTS[j][0] for j in BALL_IDX]
cyc = {0, 1, 2, 3, 23, 24}
for a in sorted(P):
    b = P[a]["poses"]["ball"]; F = len(b)
    if F < 3: continue
    R = [Rot.from_rotvec(b[:, k]) for k in range(b.shape[1])]
    worst = []
    for k, n in enumerate(names):
        r = R[k]
        idx = list(range(F)) + ([0] if a in cyc else [])
        step = np.degrees([(r[idx[t + 1]] * r[idx[t]].inv()).magnitude() for t in range(len(idx) - 1)])
        skip = np.degrees([(r[idx[t + 2]] * r[idx[t]].inv()).magnitude() for t in range(len(idx) - 2)])
        # jitter: two big steps whose net change is small
        jit = [min(step[t], step[t + 1]) - skip[t] / 2 for t in range(len(skip))]
        worst.append((max(jit) if jit else 0, n, int(np.argmax(jit)) + 1 if jit else 0, step.max()))
    worst.sort(reverse=True)
    print(f"{a:2d} {ACTIONS_PEOPLE[a]:24s}", "  ".join(f"{n}@f{f}: jit {j:.0f} (max step {s:.0f})" for j, n, f, s in worst[:3]))
