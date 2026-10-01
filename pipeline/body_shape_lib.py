"""Offline (numpy-only) body evaluation: skinning, rasteriser and silhouette scores from the data of body_pose_export.py.

    import body_shape_lib as L
    S = L.Scene("pose.npz"); D = np.zeros((S.N, 3))        # D: displacement of the REST vertices (m)
    print(L.score(S, D))                                     # mean IoU etc. over the 1050 frames

All geometry is in the canvas of the original UO frames (145x133, anchor (75,92), 36 px/m).
"""
import json, os
import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt

HERE = os.path.dirname(os.path.abspath(__file__))
ORIG = os.path.join(HERE, "..", "client", "body_0x190_frames")


def sprite_masks(keys):
    meta = json.load(open(os.path.join(ORIG, "meta.json"))); W, H = meta["canvas"]; out = {}
    for blk in meta["blocks"]:
        act = "%02d_%s" % (blk["action"], blk["name"])
        for i, fr in enumerate(blk["frames"]):
            p = os.path.join(ORIG, "frames", act, "dir%d" % blk["dir"], fr["file"])
            out[(blk["action"], blk["dir"], i)] = np.array(Image.open(p).convert("RGBA"))[..., 3] > 0 if os.path.exists(p) else np.zeros((H, W), bool)
    return np.array([out[tuple(k)] for k in keys])


class Scene:
    def __init__(self, npz):
        d = np.load(npz)
        self.rest, self.wi, self.ww, self.tris = d["rest"], d["wi"], d["ww"], d["tris"]
        self.M = d["M"].astype(np.float64); self.MW = d["MW"]; self.key = d["key"]
        self.Pm, self.Vm = d["Pm"], d["Vm"]; self.CW, self.CH = [int(x) for x in d["canvas"]]
        self.hd, self.hm = d["horse_depth"], d["horse_mask"]; self.bones = [str(b) for b in d["bones"]]
        self.N, self.F = len(self.rest), len(self.key)
        self.resid = {}
        if "resid_idx" in d.files:                                # Blender's evaluated mesh minus plain LBS (sparse), see body_pose_export.py
            fr, ix, vl = d["resid_frame"], d["resid_idx"], d["resid_val"]
            for f in np.unique(fr):
                k = fr == f; self.resid[int(f)] = (ix[k], vl[k].astype(np.float64))
        self.G = sprite_masks(self.key)
        self.ok = self.G.any((1, 2))
        # camera: world -> pixel (x, y) and depth, as a 3x4 matrix per frame (body-local -> pixel through skinning is applied first)
        self.VP = []
        for f in range(self.F):
            T = self.Pm @ self.Vm @ self.MW[f]
            self.VP.append(T)
        self.VP = np.array(self.VP)

    def posed(self, f, D=None, rest=None):
        """body-local posed vertices of frame f (LBS of rest (+D))"""
        R = self.rest if rest is None else rest
        if D is not None:
            R = R + D
        R4 = np.c_[R, np.ones(len(R))]
        Mb = self.M[f][self.wi]                                  # (N,K,4,4)
        X = np.einsum("nkij,nj->nki", Mb, R4)[..., :3]
        X = (X * self.ww[..., None]).sum(1)
        if f in self.resid:
            X = X.copy(); X[self.resid[f][0]] += self.resid[f][1]
        return X

    def linear(self, f):
        """3x3 linear part of the skinning at every vertex: posed displacement = A @ rest displacement"""
        return np.einsum("nk,nkij->nij", self.ww, self.M[f][self.wi][..., :3, :3])

    def project(self, f, X):
        """pixel xy (N,2) and camera depth (N,) of body-local points"""
        hv = np.c_[X, np.ones(len(X))] @ self.VP[f].T
        # VP = Pm @ Vm @ MW: homogeneous clip coordinates
        ndc = hv[:, :2] / hv[:, 3:4]
        xy = np.stack([(ndc[:, 0] + 1) * 0.5 * self.CW, (1 - ndc[:, 1]) * 0.5 * self.CH], 1)
        z = -(np.c_[X, np.ones(len(X))] @ (self.Vm @ self.MW[f]).T)[:, 2]
        return xy, z


def raster(xy, z, tris, CW, CH, label=None):
    """nearest-triangle label (default: triangle index) and depth per pixel, pixel-centre rule. Returns (label (H,W) int32 (-1 empty), depth)"""
    P = xy[tris]; Z = z[tris]
    lab = np.full((CH, CW), -1, np.int32); depth = np.full((CH, CW), np.inf)
    mn = np.floor(P.min(1)).astype(int); mx = np.ceil(P.max(1)).astype(int)
    A, B, C = P[:, 0], P[:, 1], P[:, 2]
    den = (B[:, 1] - C[:, 1]) * (A[:, 0] - C[:, 0]) + (C[:, 0] - B[:, 0]) * (A[:, 1] - C[:, 1])
    ok = np.abs(den) > 1e-12; size = np.clip(mx - mn, 0, 16)
    lt = np.arange(len(tris)) if label is None else label
    for dy in range(int(size[:, 1].max(initial=0)) + 1):
        for dx in range(int(size[:, 0].max(initial=0)) + 1):
            t = np.nonzero(ok & (dx <= size[:, 0]) & (dy <= size[:, 1]))[0]
            px_ = mn[t, 0] + dx; py_ = mn[t, 1] + dy; cx, cy = px_ + 0.5, py_ + 0.5
            l0 = ((B[t, 1] - C[t, 1]) * (cx - C[t, 0]) + (C[t, 0] - B[t, 0]) * (cy - C[t, 1])) / den[t]
            l1 = ((C[t, 1] - A[t, 1]) * (cx - C[t, 0]) + (A[t, 0] - C[t, 0]) * (cy - C[t, 1])) / den[t]
            kk = (l0 >= -1e-4) & (l1 >= -1e-4) & (1 - l0 - l1 >= -1e-4) & (px_ >= 0) & (py_ >= 0) & (px_ < CW) & (py_ < CH)
            zz = l0[kk] * Z[t[kk], 0] + l1[kk] * Z[t[kk], 1] + (1 - l0[kk] - l1[kk]) * Z[t[kk], 2]
            tt, yy, xx = t[kk], py_[kk], px_[kk]
            o = np.argsort(-zz); o = o[zz[o] < depth[yy[o], xx[o]]]
            depth[yy[o], xx[o]] = zz[o]; lab[yy[o], xx[o]] = lt[tt[o]]
    return lab, depth


def model_mask(S, f, D=None, rest=None):
    X = S.posed(f, D, rest); xy, z = S.project(f, X)
    lab, depth = raster(xy, z, S.tris, S.CW, S.CH)
    m = lab >= 0
    hide = S.hm[f] & (S.hd[f] < depth)
    m &= ~hide
    return m, lab, depth, X, xy, z


def score(S, D=None, frames=None, rest=None):
    fr = np.nonzero(S.ok)[0] if frames is None else np.asarray(frames)
    iou = np.zeros(len(fr)); out = np.zeros(len(fr)); miss = np.zeros(len(fr))
    for n, f in enumerate(fr):
        m = model_mask(S, f, D, rest)[0]; g = S.G[f]
        iou[n] = (m & g).sum() / max((m | g).sum(), 1); out[n] = (m & ~g).sum(); miss[n] = (g & ~m).sum()
    return dict(iou=float(iou.mean()), outside=float(out.mean()), missing=float(miss.mean()), per_frame=iou)
