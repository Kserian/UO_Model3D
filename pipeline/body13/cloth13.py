"""cloth chain rigs for v13: a skirt ring (chains around the pelvis) and a cloak (chains down the back).
Each chain is a string of bones; a bone swings about its local X (out / in, radial) and Z (sideways).
Template meshes are generated around the rest body and weighted to the chains (angle x height blend)."""
import numpy as np
from skel13 import frame_from


def rotxz(ax, az):
    cx, sx, cz, sz = np.cos(ax), np.sin(ax), np.cos(az), np.sin(az)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]]); Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rx @ Rz


def section_radius(V, center, z, phis, slab=0.02, margin=0.012):
    """max radius of the body around `center` at height z per direction (angular bins), smoothed"""
    sel = np.abs(V[:, 2] - z) < slab
    rel = V[sel, :2] - center[:2]
    ang = np.arctan2(rel[:, 1], rel[:, 0]); rad = np.linalg.norm(rel, axis=1)
    nb = 72; bins = ((ang + np.pi) / (2 * np.pi) * nb).astype(int) % nb
    rmax = np.zeros(nb)
    np.maximum.at(rmax, bins, rad)
    # fill empty bins, smooth circularly
    if (rmax > 0).any():
        idx = np.nonzero(rmax > 0)[0]
        allb = np.arange(nb)
        rmax = np.interp(allb, np.r_[idx - nb, idx, idx + nb], np.r_[rmax[idx], rmax[idx], rmax[idx]])
    k = np.array([1, 2, 3, 2, 1], float); k /= k.sum()
    rmax = np.convolve(np.r_[rmax[-2:], rmax, rmax[:2]], k, "valid")
    pb = ((np.asarray(phis) + np.pi) / (2 * np.pi) * nb) % nb
    return np.interp(pb, np.arange(nb + 1), np.r_[rmax, rmax[0]]) + margin


class ChainRig:
    """generic: chains[k] = list of rest points (S+1, 3), out[k] = outward hint per chain; parent bone name"""
    def __init__(self, prefix, chains, outward, parent):
        self.prefix, self.parent = prefix, parent
        self.nc, self.ns = len(chains), len(chains[0]) - 1
        self.names, self.R, self.L, self.par = [], [], [], []
        for k, pts in enumerate(chains):
            for s in range(self.ns):
                M, ln = frame_from(pts[s], pts[s + 1], outward[k])
                self.names.append("%s_%d_%d" % (prefix, k, s + 1)); self.R.append(M); self.L.append(ln)
                self.par.append(parent if s == 0 else len(self.names) - 2)
        self.R = np.array(self.R); self.L = np.array(self.L); self.Rinv = np.linalg.inv(self.R)
        self.chains = chains

    def bone(self, k, s):
        return k * self.ns + s

    def pose(self, x, P_parent, R_parent):
        """x: (nc*ns*2) swing angles -> skin matrices (armature space) of the chain bones"""
        n = len(self.names); P = np.zeros((n, 4, 4)); a = x.reshape(n, 2)
        base = P_parent @ np.linalg.inv(R_parent)
        for b in range(n):
            M = np.eye(4); M[:3, :3] = rotxz(a[b, 0], a[b, 1])
            p = self.par[b]
            P[b] = (base if isinstance(p, str) else P[p] @ self.Rinv[p]) @ self.R[b] @ M
        return P @ self.Rinv


def skirt(V, pelvis_head, z_top, z_hem, nc=8, ns=3, flare=0.03, cols_per=4, rows_per=4, margin=0.012, keep=None,
          arc=None, prefix="skirt", parent="pelvis", center=None):
    """cloth ring around the body from z_top down to z_hem (arc=None: closed skirt; arc=(a0, a1) radians: open, e.g. a
    cloak around the back); returns rig, verts, faces, weights, top ring.
    keep: body vertices used for the envelope (torso + legs, not the arms)"""
    if keep is not None:
        V = V[keep]
    if center is None:
        center = np.array([pelvis_head[0], np.median(V[np.abs(V[:, 2] - z_top) < 0.03, 1]), 0.0])
    zs = np.linspace(z_top, z_hem, ns + 1)
    closed = arc is None
    th = (-np.pi / 2 + 2 * np.pi * np.arange(nc) / nc) if closed else np.linspace(arc[0], arc[1], nc)
    def rad_at(phis, z_list):
        out = []; prev = None
        for j, z in enumerate(z_list):
            r = section_radius(V, center, z, phis, margin=margin)
            if prev is not None:
                r = np.maximum(r, prev)
            r = r + flare * (z_top - z) / max(z_top - z_hem, 1e-6)
            out.append(r); prev = r
        return np.array(out)
    rc = rad_at(th, zs)
    chains = [np.array([[center[0] + rc[j, k] * np.cos(th[k]), center[1] + rc[j, k] * np.sin(th[k]), zs[j]] for j in range(ns + 1)]) for k in range(nc)]
    outward = [np.array([np.cos(t), np.sin(t), 0.0]) for t in th]
    rig = ChainRig(prefix, chains, outward, parent)
    M_ = nc * cols_per if closed else (nc - 1) * cols_per + 1
    R_ = ns * rows_per
    phis = (-np.pi / 2 + 2 * np.pi * np.arange(M_) / M_) if closed else np.linspace(arc[0], arc[1], M_)
    zr = np.linspace(z_top, z_hem, R_ + 1)
    rr = rad_at(phis, zr)
    verts = np.array([[center[0] + rr[j, c] * np.cos(phis[c]), center[1] + rr[j, c] * np.sin(phis[c]), zr[j]] for j in range(R_ + 1) for c in range(M_)])
    cols = M_ if closed else M_ - 1
    faces = [[j * M_ + c, j * M_ + (c + 1) % M_, (j + 1) * M_ + (c + 1) % M_, (j + 1) * M_ + c] for j in range(R_) for c in range(cols)]
    W = np.zeros((len(verts), len(rig.names)))
    for j in range(R_ + 1):
        t = j / rows_per
        for c in range(M_):
            u = c / cols_per; k0 = int(np.floor(u)) % nc if closed else min(int(np.floor(u)), nc - 2)
            k1 = (k0 + 1) % nc; fu = u - k0 if not closed else u - np.floor(u)
            for k, wk in ((k0, 1 - fu), (k1, fu)):
                s = min(int(np.floor(t)), ns - 1); ft = t - s
                if ft < 0.5 and s > 0:
                    a_ = 0.5 + ft; W[j * M_ + c, rig.bone(k, s)] += wk * a_; W[j * M_ + c, rig.bone(k, s - 1)] += wk * (1 - a_)
                elif ft > 0.5 and s < ns - 1:
                    a_ = 1.5 - ft; W[j * M_ + c, rig.bone(k, s)] += wk * a_; W[j * M_ + c, rig.bone(k, s + 1)] += wk * (1 - a_)
                else:
                    W[j * M_ + c, rig.bone(k, s)] += wk
    return rig, verts, np.array(faces), W, np.arange(M_)


def cloak(V, R_chest, z_top, z_hem, x_half, nc=5, ns=4, cols_per=3, rows_per=3, margin=0.02):
    """cloak down the back (+Y side of the body) from the shoulders (z_top) to z_hem, width 2*x_half at the top"""
    xs = np.linspace(-x_half, x_half, nc)
    zs = np.linspace(z_top, z_hem, ns + 1)
    def back_y(x, z):
        sel = (np.abs(V[:, 2] - z) < 0.03) & (np.abs(V[:, 0] - x) < 0.04)
        return (V[sel, 1].max() if sel.any() else V[:, 1].max()) + margin
    chains = []
    for x in xs:
        pts = []; ymax = -np.inf
        for j, z in enumerate(zs):
            ymax = max(ymax, back_y(x, z)); pts.append([x * (1 + 0.25 * j / ns), ymax + 0.02 * j, z])
        chains.append(np.array(pts))
    outward = [np.array([0.0, 1.0, 0.0])] * nc
    rig = ChainRig("cloak", chains, outward, "chest")
    M_ = (nc - 1) * cols_per + 1; R_ = ns * rows_per
    verts = []; W = []
    for j in range(R_ + 1):
        t = j / rows_per
        for c in range(M_):
            u = c / cols_per; k0 = min(int(np.floor(u)), nc - 2); fu = u - k0
            s = min(int(np.floor(t)), ns - 1); ft = t - s
            p0 = chains[k0][s] + (chains[k0][s + 1] - chains[k0][s]) * ft; p1 = chains[k0 + 1][s] + (chains[k0 + 1][s + 1] - chains[k0 + 1][s]) * ft
            verts.append(p0 * (1 - fu) + p1 * fu)
            w = np.zeros(len(rig.names))
            for k, wk in ((k0, 1 - fu), (k0 + 1, fu)):
                if ft < 0.5 and s > 0:
                    a = 0.5 + ft; w[rig.bone(k, s)] += wk * a; w[rig.bone(k, s - 1)] += wk * (1 - a)
                elif ft > 0.5 and s < ns - 1:
                    a = 1.5 - ft; w[rig.bone(k, s)] += wk * a; w[rig.bone(k, s + 1)] += wk * (1 - a)
                else:
                    w[rig.bone(k, s)] += wk
            W.append(w)
    faces = [[j * M_ + c, j * M_ + c + 1, (j + 1) * M_ + c + 1, (j + 1) * M_ + c] for j in range(R_) for c in range(M_ - 1)]
    return rig, np.array(verts), np.array(faces), np.array(W), np.arange(M_)


KINDS = {449: ("skirt", 0.12, 0.10), 455: ("skirt", 0.12, 0.50), 469: ("skirt", 0.12, 0.10), 447: ("skirt", 0.12, 0.10),
         448: ("skirt", 0.12, 0.10), 468: ("cloak", -0.02, 0.18)}


def body_shell(K, V, faces, keep, thick):
    """part of the body skin (vertices `keep`), pushed out along the normals, with the body skin weights"""
    F4 = np.array([f if len(f) == 4 else list(f) + [f[-1]] for f in faces])
    a, b, c, e = V[F4[:, 0]], V[F4[:, 1]], V[F4[:, 2]], V[F4[:, 3]]
    fn = np.cross(c - a, e - b); n = np.zeros_like(V)
    for k in range(4): np.add.at(n, F4[:, k], fn)
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    idx = np.nonzero(keep)[0]; remap = -np.ones(len(V), int); remap[idx] = np.arange(len(idx))
    SF = [[remap[i] for i in f] for f in faces if keep[list(f)].all()]
    SF = [f if len(f) == 4 else f + [f[-1]] for f in SF]
    return V[idx] + n[idx] * thick, np.array(SF), K.SW[idx]


import os as _os
CLOAK_ARC = tuple(float(x) for x in _os.environ.get("CLOAK_ARC", "0,180").split(","))
CLOAK_MARGIN = float(_os.environ.get("CLOAK_MARGIN", "0.035"))


def make_cloth(K, V, kind, zt, zh, faces=None):
    """cloth template: bone chains + (with faces) a top part that hugs the body (skirt: waistband, cloak: yoke over the
    shoulders), weighted to the body bones. rig.wnames = weight columns (chain bones, then body bones)"""
    arms = [K.ix[n] for n in K.names if n.startswith(("upper_arm", "forearm", "hand", "finger", "clavicle"))]
    keep = K.SW[:, arms].sum(1) < 0.3
    ph = K.R[K.ix["pelvis"]][:3, 3]; sp = K.R[K.ix["spine"]][:3, 3]
    dom = np.array([K.names[j] for j in K.SW.argmax(1)])
    if kind == "skirt":
        z0 = sp[2] + zt
        out = skirt(V, ph, z0, zh, keep=keep) + ("pelvis",)
        sel = np.isin(dom, ["pelvis", "spine", "chest"]) & (V[:, 2] > z0 - 0.015) & (V[:, 2] < z0 + 0.07)
        thick = 0.014
    else:
        sh = K.R[K.ix["upper_arm.L"]][:3, 3]
        keep_c = keep | ((K.SW[:, arms].sum(1) >= 0.3) & (V[:, 2] > sh[2] - 0.12))
        ctr = np.array([0.0, K.R[K.ix["neck"]][1, 3], 0.0])
        out = skirt(V, ph, sh[2] + zt, zh, nc=7, ns=4, keep=keep_c, arc=(np.radians(CLOAK_ARC[0]), np.radians(CLOAK_ARC[1])),
                    prefix="cloak", parent="chest", center=ctr, margin=CLOAK_MARGIN, flare=0.05) + ("chest",)
        yn = K.R[K.ix["neck"]][1, 3]; zn = K.R[K.ix["neck"]][2, 3]; zh_ = K.R[K.ix["head"]][2, 3]
        sel = np.isin(dom, ["chest", "clavicle.L", "clavicle.R", "neck", "spine", "upper_arm.L", "upper_arm.R",
                            "upper_arm_twist.L", "upper_arm_twist.R"]) & (V[:, 2] > sh[2] + zt - 0.03) & (V[:, 2] < zh_ - 0.015)
        sel &= (V[:, 1] > -0.03) | (V[:, 2] > sh[2] + 0.03)
        thick = 0.022
    rig, CV, CF, CW, top, par = out
    rig.wnames = list(rig.names)
    if faces is None:
        return rig, CV, CF, CW, top, par
    SV, SF, SW = body_shell(K, V, faces, sel, thick)
    if len(SF) == 0:
        return rig, CV, CF, CW, top, par
    nc = len(rig.names)
    W = np.zeros((len(CV) + len(SV), nc + len(K.names)))
    W[:len(CV), :nc] = CW; W[len(CV):, nc:] = SW
    rig.wnames = list(rig.names) + list(K.names)
    CF4 = np.array([list(f) for f in CF])
    return rig, np.vstack([CV, SV]), np.vstack([CF4, SF + len(CV)]), W, top, par


