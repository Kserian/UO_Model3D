"""v13 skeleton: the 19 UO bones (same rest pose, so every existing action still works) + twist bones, 15 finger bones
per hand and a toe bone per foot (55 bones). Skin weights come straight from the MakeHuman weights.

Finger bones: local Z points to the palm, so a positive rotation about local X curls the finger into the fist.
Toe bone: positive rotation about local X lifts the toes."""
import json, numpy as np
from mhlib import MH
from shape13 import Shape

SIDES = (".L", ".R")
FING = ["finger%d-%d" % (f, s) for f in range(1, 6) for s in range(1, 4)]
# fist: curl angle (rad) per segment at curl = 1 (fingers 2-5) and thumb = 1
FIST = {1: 1.25, 2: 1.55, 3: 1.05}
THUMB = {1: 0.35, 2: 0.55, 3: 0.6}


def skin_bone_of(b):
    side = "." + b.split(".")[-1] if b.endswith(SIDES) else ""
    base = b[:-2] if side else b
    if base == "upperarm02": return "upper_arm_twist" + side
    if base == "lowerarm02": return "forearm_twist" + side
    if base in FING: return b
    if base.startswith("toe"): return "toe" + side
    return Shape.part_of(b)


def names13(uo_bones):
    out = list(uo_bones)
    for s in SIDES:
        out += ["upper_arm_twist" + s, "forearm_twist" + s]
    for s in SIDES:
        out += [f + s for f in FING]
    out += ["toe" + s for s in SIDES]
    return out


def frame_from(head, tail, z_hint):
    """Blender-like bone matrix: Y along the bone, Z as close as possible to z_hint, X = Y x Z"""
    y = tail - head; L = np.linalg.norm(y); y = y / L
    z = z_hint - y * (z_hint @ y); z /= np.linalg.norm(z)
    x = np.cross(y, z)
    M = np.eye(4); M[:3, 0] = x; M[:3, 1] = y; M[:3, 2] = z; M[:3, 3] = head
    return M, L


class Skel13:
    def __init__(self, S, R19, parent19, uo_bones, V_full):
        """S: Shape; R19/parent19: UO rest matrices (armature space) + parents; V_full: shaped verts incl. helpers"""
        sk = json.load(open(MH + "default.mhskel"))
        JD = {k: V_full[v].mean(0) for k, v in sk["joints"].items()}
        bh = lambda b: JD[sk["bones"][b]["head"]]; bt = lambda b: JD[sk["bones"][b]["tail"]]
        self.names = names13(uo_bones); ix = {n: i for i, n in enumerate(self.names)}; self.ix = ix
        B = len(self.names); R = np.zeros((B, 4, 4)); par = np.full(B, -1); L = np.zeros(B)
        R[:19] = R19; par[:19] = parent19
        for i in range(19):
            L[i] = 0                                          # unused for the UO bones
        for s in SIDES:
            for tw, pb in (("upper_arm_twist", "upper_arm"), ("forearm_twist", "forearm")):
                P = R19[uo_bones.index(pb + s)]
                ln = self.uo_len(pb + s, R19, uo_bones, V_full)
                M = P.copy(); M[:3, 3] = P[:3, 3] + P[:3, 1] * ln * 0.5
                R[ix[tw + s]] = M; par[ix[tw + s]] = uo_bones.index(pb + s); L[ix[tw + s]] = ln * 0.5
            # palm normal: knuckles bulge to the back of the hand when the MakeHuman fingers are slightly bent
            w = bh("wrist" + s); m2 = bh("finger2-1" + s); m5 = bh("finger5-1" + s)
            n = np.cross(m2 - w, m5 - w); n /= np.linalg.norm(n)
            back = np.zeros(3)
            for f in (2, 3, 4, 5):
                a, c = bh("finger%d-1" % f + s), bt("finger%d-3" % f + s); mid = bh("finger%d-2" % f + s)
                d = (c - a) / np.linalg.norm(c - a); back += (mid - a) - d * ((mid - a) @ d)
            if n @ back > 0:
                n = -n                                        # n now points to the palm
            self.palm = getattr(self, "palm", {}); self.palm[s] = n
            for f in FING:
                b = f + s; M, ln = frame_from(bh(b), bt(b), n)
                R[ix[b]] = M; L[ix[b]] = ln
                seg = int(f[-1])
                par[ix[b]] = ix["hand" + s] if seg == 1 else ix[f[:-1] + str(seg - 1) + s]
            toes1 = [bh("toe%d-1" % t + s) for t in range(1, 6)]
            tips = [bt("toe1-2" + s)] + [bt("toe%d-3" % t + s) for t in range(2, 6)]
            M, ln = frame_from(np.mean(toes1, 0), np.mean(tips, 0), np.array([0.0, 0.0, 1.0]))
            R[ix["toe" + s]] = M; L[ix["toe" + s]] = ln; par[ix["toe" + s]] = uo_bones.index("foot" + s)
        self.R, self.parent, self.L = R, par, L
        # skin weights
        Wmh = json.load(open(MH + "default_weights.mhw"))["weights"]
        N = len(S.P); SW = np.zeros((N, B))
        for b, lst in Wmh.items():
            j = ix[skin_bone_of(b)]
            for vi, wv in lst:
                SW[vi, j] += wv
        SW = SW[S.used]
        SW /= np.maximum(SW.sum(1, keepdims=True), 1e-9)
        self.SW = SW

    @staticmethod
    def uo_len(b, R19, uo_bones, V_full):
        """UO bone length from the child head (connected chain)"""
        child = {"upper_arm": "forearm", "forearm": "hand"}[b[:-2]] + b[-2:]
        return np.linalg.norm(R19[uo_bones.index(child)][:3, 3] - R19[uo_bones.index(b)][:3, 3])

    def extra_bases(self, curl, thumb, toe):
        """basis rotations (3x3) of the 36 extra bones for given curl / thumb / toe per side (dicts side -> value)"""
        out = {}
        for s in SIDES:
            out["upper_arm_twist" + s] = np.eye(3); out["forearm_twist" + s] = np.eye(3)
            for f in FING:
                fi, seg = int(f[6]), int(f[-1])
                a = (THUMB[seg] * thumb[s]) if fi == 1 else (FIST[seg] * curl[s])
                out[f + s] = rotx(a)
            out["toe" + s] = rotx(toe[s])
        return out


def rotx(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
