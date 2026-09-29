"""v13 body shape generator (pure numpy, no Blender): MakeHuman male -> UO proportions with tunable multipliers.

Same construction as mh_stage1.py (limb segment transforms, torso height map, neck, head, blended with the MakeHuman
part weights), plus parameters on top of the measured values:
  limb girth at the proximal / distal end (linear along the bone), two radial axes (side / front-back),
  torso width / depth / centre per height level, neck width / depth, head scale.
build(params) -> (N,3) vertices in UO_Body local space (rest pose of the v12 skeleton).
"""
import json, numpy as np
from scipy.spatial import cKDTree
from mhlib import load_mh, MH

LIMBS = ["upper_arm", "forearm", "hand", "thigh", "shin", "foot"]
NLEV = 7
PARTS = ["pelvis", "spine", "chest", "neck", "head"] + [p + s for s in (".L", ".R") for p in ("clavicle", "upper_arm", "forearm", "hand", "thigh", "shin", "foot")]
PI = {p: i for i, p in enumerate(PARTS)}


def default_params():
    p = {}
    for l in LIMBS:
        p[l] = np.array([1.0, 1.0, 1.0, 1.0])            # girth proximal side, distal side, proximal front, distal front
    p["tw"] = np.ones(NLEV); p["td"] = np.ones(NLEV); p["tc"] = np.zeros(NLEV)   # torso width, depth, centre shift (m)
    p["neck"] = np.array([1.0, 1.0]); p["head"] = np.array([1.0])
    p["head3"] = np.array([1.0, 1.0, 1.0])               # head width, depth, height on top of the head scale
    p["footl"] = np.array([1.0])                          # foot length
    return p


OLD_KEYS = ["foot", "forearm", "hand", "head", "neck", "shin", "tc", "td", "thigh", "tw", "upper_arm"]


def load_params(fn):
    """json with {"p": {key: values}} or the old {"x": [...]} layout"""
    j = json.load(open(fn)); p = default_params()
    if "p" in j:
        for k, val in j["p"].items(): p[k] = np.array(val, float)
    else:
        i = 0
        for k in OLD_KEYS:
            n = np.size(p[k]); p[k] = np.array(j["x"][i:i + n], float); i += n
    return p


def save_params(fn, p, **extra):
    json.dump(dict(p={k: np.ravel(val).tolist() for k, val in p.items()}, **extra), open(fn, "w"), indent=0)


def flat(p):
    return np.concatenate([np.ravel(p[k]) for k in sorted(p)])


def unflat(x, like=None):
    like = like or default_params(); out = {}; i = 0
    for k in sorted(like):
        n = np.size(like[k]); out[k] = np.array(x[i:i + n], float).reshape(np.shape(like[k])); i += n
    return out


class Shape:
    def __init__(self, U, BV, BDOM, bones, muscle=0.6):
        """U: (19,2,3) UO bone head/tail rest (body space) in the order of `bones`; BV / BDOM: v12 basis mesh + dominant group"""
        U = {b: (U[i][0], U[i][1]) for i, b in enumerate(bones)}
        self.U = U
        P, F, B, W = load_mh(muscle=muscle)
        self.P = P
        body_verts = sorted({i for f in F for i in f}); self.used = np.array(body_verts)
        PW = np.zeros((len(P), len(PARTS)))
        for b, lst in W.items():
            j = PI[self.part_of(b)]
            for vi, w in lst:
                PW[vi, j] += w
        noW = np.nonzero(PW.sum(1) < 1e-6)[0]
        if len(noW):
            kd = cKDTree(P[body_verts]); _, nn = kd.query(P[noW])
            PW[noW] = PW[np.array(body_verts)[nn]]
        PW /= np.maximum(PW.sum(1, keepdims=True), 1e-9)
        self.PW = PW
        MDOM = np.array([PARTS[i] for i in PW.argmax(1)])
        remap = {o: n for n, o in enumerate(body_verts)}
        self.faces = [[remap[i] for i in f] for f in F]
        J = lambda b, e="head": B[b][0] if e == "head" else B[b][1]
        self.J = J
        TORSO = ("pelvis", "spine", "chest", "clavicle.L", "clavicle.R")
        self.mh_top = P[body_verts, 2].max(); self.uo_top = BV[:, 2].max()
        self.mh_hip = 0.5 * (J("upperleg01.L")[2] + J("upperleg01.R")[2]); self.uo_hip = 0.5 * (U["thigh.L"][0][2] + U["thigh.R"][0][2])
        self.mh_sh = 0.5 * (J("upperarm01.L")[2] + J("upperarm01.R")[2]); self.uo_sh = 0.5 * (U["upper_arm.L"][0][2] + U["upper_arm.R"][0][2])
        self.mh_hj = J("head")[2]
        # ------------------------------------------------ limbs (measured girth from the v12 mesh, like stage 1)
        CAP = {"upper_arm": (0.35, 0.75, 0.10), "forearm": (0.25, 0.75, 0.09), "hand": (0.2, 0.7, 0.07),
               "thigh": (0.3, 0.8, 0.13), "shin": (0.2, 0.8, 0.10), "foot": (0.2, 0.8, 0.08)}
        self.LIMB = {}
        X = P[body_verts]
        for part in PARTS:
            base = part.split(".")[0]
            if base not in CAP:
                continue
            am, bm = self.seg_mh(part, MDOM, body_verts); au, bu = U[part]
            R = rot_between(bm - am, bu - au)
            s_len = np.linalg.norm(bu - au) / np.linalg.norm(bm - am)
            du = (bu - au) / np.linalg.norm(bu - au)
            # second radial axis: 'front' = the body -Y direction made perpendicular to the bone, 'side' = the rest
            fr = np.array([0.0, -1.0, 0.0]) - du * (-du[1]);
            if np.linalg.norm(fr) < 0.3:
                fr = np.array([0.0, 0.0, 1.0]) - du * du[2]
            fr /= np.linalg.norm(fr); sd = np.cross(du, fr)
            t0, t1, cap = CAP[base]
            Y = (X - am) @ R.T; t = Y @ du; Y = au + Y + np.outer(t, du) * (s_len - 1)
            rm, tm = radial(Y, au, bu); ru, tu = radial(BV, au, bu)
            km = (tm > t0) & (tm < t1) & (rm < cap); ku = (tu > t0) & (tu < t1) & (ru < cap)
            s_rad = float(np.median(ru[ku]) / max(np.median(rm[km]), 1e-6)) if km.sum() > 5 and ku.sum() > 5 else 1.0
            s_rad = float(np.clip(s_rad, 0.7, 1.8))
            self.LIMB[part] = (am, au, R, du, s_len, s_rad, np.linalg.norm(bu - au), sd, fr)
        # ------------------------------------------------ torso levels
        armw = sum(PW[:, PI[p]] for p in self.LIMB if p.startswith(("upper_arm", "forearm", "hand")))
        tm_idx = np.array([i for i in body_verts if MDOM[i] in TORSO and armw[i] < 0.05])
        d = np.full(len(BV), np.inf)
        for s in (".L", ".R"):
            for b in ("upper_arm", "forearm"):
                r, t = radial(BV, *U[b + s]); d = np.minimum(d, np.where((t > -0.1) & (t < 1.1), r, np.inf))
        tu_idx = np.nonzero(d > 0.08)[0]
        tu_idx = tu_idx[np.isin(BDOM[tu_idx], ["pelvis", "spine", "chest", "thigh.L", "thigh.R"])]
        self.LEV = np.linspace(self.uo_hip - 0.02, self.uo_sh - 0.02, NLEV)
        zt_m = self.torso_z(P[tm_idx, 2])
        SX, SY, CY, MC = [], [], [], []
        for z in self.LEV:
            mm = np.abs(zt_m - z) < 0.03; uu = np.abs(BV[tu_idx, 2] - z) < 0.03
            xm = np.percentile(np.abs(P[tm_idx[mm], 0]), 95); xu = np.percentile(np.abs(BV[tu_idx[uu], 0]), 95)
            ym = P[tm_idx[mm], 1]; yu = BV[tu_idx[uu], 1]
            SX.append(xu / xm); SY.append((np.percentile(yu, 97) - np.percentile(yu, 3)) / (np.percentile(ym, 97) - np.percentile(ym, 3)))
            MC.append(0.5 * (np.percentile(ym, 97) + np.percentile(ym, 3))); CY.append(0.5 * (np.percentile(yu, 97) + np.percentile(yu, 3)))
        self.SX, self.SY, self.CY, self.MC = map(np.array, (SX, SY, CY, MC))
        # ------------------------------------------------ head
        hu = np.nonzero(BDOM == "head")[0]; hm = np.array([i for i in body_verts if MDOM[i] == "head"])
        hu_top = BV[hu, 2].max(); hm_top = P[hm, 2].max()
        wu = np.percentile(np.abs(BV[hu[BV[hu, 2] > hu_top - 0.12], 0]), 97); wm = np.percentile(np.abs(P[hm[P[hm, 2] > hm_top - 0.11], 0]), 97)
        self.s_head = float(np.clip(wu / wm, 0.8, 1.6))
        self.cyu = 0.5 * (np.percentile(BV[hu, 1], 97) + np.percentile(BV[hu, 1], 3)); self.cym = 0.5 * (np.percentile(P[hm, 1], 97) + np.percentile(P[hm, 1], 3))
        # parts that actually move each vertex
        self.sel = {p: np.nonzero(PW[:, PI[p]] > 1e-6)[0] for p in PARTS}
        self.sel_all = dict(self.sel)
        self.sel = {p: s[np.isin(s, self.used)] for p, s in self.sel.items()}

    @staticmethod
    def part_of(b):
        side = "." + b.split(".")[-1] if b.endswith((".L", ".R")) else ""
        if b.startswith(("root", "spine05", "pelvis")): return "pelvis"
        if b.startswith(("spine04", "spine03")): return "spine"
        if b.startswith(("spine02", "spine01", "breast")): return "chest"
        if b.startswith(("clavicle", "shoulder01")): return "clavicle" + side
        if b.startswith("neck"): return "neck"
        if b.startswith("upperarm"): return "upper_arm" + side
        if b.startswith("lowerarm"): return "forearm" + side
        if b.startswith(("wrist", "metacarpal", "finger")): return "hand" + side
        if b.startswith("upperleg"): return "thigh" + side
        if b.startswith("lowerleg"): return "shin" + side
        if b.startswith(("foot", "toe")): return "foot" + side
        return "head"

    def seg_mh(self, part, MDOM, body_verts):
        J = self.J; P = self.P
        s = part[-2:]; base = part[:-2]
        if base == "upper_arm": return J("upperarm01" + s), J("lowerarm01" + s)
        if base == "forearm": return J("lowerarm01" + s), J("wrist" + s)
        if base == "hand": return J("wrist" + s), J("finger3-3" + s, "tail")
        if base == "thigh": return J("upperleg01" + s), J("lowerleg01" + s)
        if base == "shin": return J("lowerleg01" + s), J("foot" + s)
        if base == "foot":
            fv = np.array([i for i in body_verts if MDOM[i] == "foot" + s])
            tip = P[fv[np.argmin(P[fv, 1])]]
            return J("foot" + s), np.array([J("foot" + s)[0], tip[1], tip[2]])
        raise KeyError(part)

    def torso_z(self, z):
        return zmap(z, np.array([self.mh_hip, self.mh_sh]), np.array([self.uo_hip, self.uo_sh]))

    # ------------------------------------------------ transforms
    def T_limb(self, part, X, g):
        am, au, R, du, s_len, s_rad, L, sd, fr = self.LIMB[part]
        Y = (X - am) @ R.T
        t = Y @ du
        Yr = Y - np.outer(t, du)
        if part.startswith("foot"):
            s_len = s_len * g[4]
        tt = np.clip(t * s_len / L, 0, 1)
        gs = s_rad * (g[0] + (g[1] - g[0]) * tt); gf = s_rad * (g[2] + (g[3] - g[2]) * tt)
        a = Yr @ sd; b = Yr @ fr
        return au + np.outer(t * s_len, du) + np.outer(a * gs, sd) + np.outer(b * gf, fr)

    def T_torso(self, X, p):
        z = self.torso_z(X[:, 2])
        sx = np.interp(z, self.LEV, self.SX * p["tw"]); sy = np.interp(z, self.LEV, self.SY * p["td"])
        cm = np.interp(z, self.LEV, self.MC); cu = np.interp(z, self.LEV, self.CY + p["tc"])
        return np.stack([X[:, 0] * sx, cu + (X[:, 1] - cm) * sy, z], 1)

    def T_head(self, X, p):
        s = self.s_head * p["head"][0]; h3 = p["head3"]
        return np.stack([X[:, 0] * s * h3[0], self.cyu + (X[:, 1] - self.cym) * s * h3[1], self.uo_top + (X[:, 2] - self.mh_top) * s * h3[2]], 1)

    def T_neck(self, X, p):
        s = self.s_head * p["head"][0] * p["head3"][2]
        hb = self.uo_top - (self.mh_top - self.mh_hj) * s
        z = zmap(X[:, 2], np.array([self.mh_sh, self.mh_hj]), np.array([self.uo_sh, hb]))
        tw, td, tc = p["tw"][-1], p["td"][-1], p["tc"][-1]
        return np.stack([X[:, 0] * self.SX[-1] * tw * p["neck"][0], self.CY[-1] + tc + (X[:, 1] - self.MC[-1]) * self.SY[-1] * td * p["neck"][1], z], 1)

    def build(self, p=None, full=False):
        p = p or default_params()
        P = self.P; OUT = np.zeros_like(P)
        for part in PARTS:
            s = (self.sel_all if full else self.sel)[part]
            if not len(s):
                continue
            w = self.PW[s, PI[part]]
            base = part.split(".")[0]
            if part in self.LIMB: Y = self.T_limb(part, P[s], np.r_[p[base], p["footl"]] if base == "foot" else p[base])
            elif part == "neck": Y = self.T_neck(P[s], p)
            elif part == "head": Y = self.T_head(P[s], p)
            else: Y = self.T_torso(P[s], p)
            OUT[s] += w[:, None] * Y
        return OUT if full else OUT[self.used]


def zmap(z, zs_m, zs_u):
    return np.where(z < zs_m[0], zs_u[0] + (z - zs_m[0]) * (zs_u[1] - zs_u[0]) / (zs_m[1] - zs_m[0]),
                    np.where(z > zs_m[-1], zs_u[-1] + (z - zs_m[-1]) * (zs_u[-1] - zs_u[-2]) / (zs_m[-1] - zs_m[-2]), np.interp(z, zs_m, zs_u)))


def rot_between(a, b):
    a = a / np.linalg.norm(a); b = b / np.linalg.norm(b)
    v = np.cross(a, b); c = float(a @ b)
    if np.linalg.norm(v) < 1e-9:
        return np.eye(3)
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + vx + vx @ vx * (1 / (1 + c))


def radial(X, a, b):
    d = (b - a) / np.linalg.norm(b - a)
    rel = X - a
    t = rel @ d
    return np.linalg.norm(rel - np.outer(t, d), axis=1), t / np.linalg.norm(b - a)
