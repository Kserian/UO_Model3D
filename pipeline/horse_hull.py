"""Horse proxy meshes (visual hull from the 5 UO directions of each horse frame), in the rider's coordinate system.
Used as a HOLDOUT when rendering mounted actions: parts of the rider/clothing behind the horse disappear like in UO."""
import sys, pickle
import numpy as np
from scipy.ndimage import gaussian_filter
from skimage import measure
import jax.numpy as jnp
from body import camera, CANVAS_W, CANVAS_H, ANCHOR_X, ANCHOR_Y
from fit import params_to_shape
sys.path.insert(0, "../vdtool")
import vdtool

PX_OFF = 0.5
RES = 0.015
sf = pickle.load(open("shape_fit.pkl", "rb"))
S = params_to_shape({k: jnp.asarray(v) for k, v in sf["params"]["shape"].items()}, {k: jnp.asarray(v) for k, v in sf["fixed"].items()})
SC = float(S["scale"])
CAM = [tuple(np.asarray(c) for c in camera(S, d)) for d in range(5)]
_, horse = vdtool.read_vd("horse200.vd")

lo = np.array([-0.9, -1.8, -0.05]); hi = np.array([0.9, 1.8, 2.6])
n = np.ceil((hi - lo) / RES).astype(int)
axes = [lo[i] + (np.arange(n[i]) + 0.5) * RES for i in range(3)]


def mask(ha, i, d):
    blk = horse[ha * 5 + d]
    fr = blk["frames"][i]
    rgba = vdtool.frame_rgba(fr, blk["palette"])
    m = np.zeros((CANVAS_H + 200, CANVAS_W + 200), bool)          # generous canvas: the horse is big
    x0, y0 = ANCHOR_X + 100 - fr["cx"], ANCHOR_Y + 100 - (fr["cy"] + fr["h"])
    m[y0:y0 + fr["h"], x0:x0 + fr["w"]] = rgba[..., 3] > 0
    return m


RIDER_FRAME = None   # (action, frame) whose evidence carves the proxy; None = all users


def _users(ha, i, poses_by_action):
    if RIDER_FRAME is not None:
        return [RIDER_FRAME]
    users = {0: [23], 1: [24], 2: [25, 26, 27, 28, 29]}[ha]
    out = []
    for a in users:
        if a in poses_by_action:
            F = poses_by_action[a]["trans"].shape[0]
            out += [(a, k) for k in ([i] if ha in (0, 1) else range(F)) if k < F]
    return out


def rider_volume(ha, i, poses_by_action):
    """Union of the rider's posed body volumes over all mounted frames that use this horse frame (dilated)."""
    from scipy.ndimage import binary_dilation, binary_fill_holes
    from posefit_mesh import posed
    vol = np.zeros(n, bool)
    for a, k in _users(ha, i, poses_by_action):
            p = poses_by_action[a]
            X = np.asarray(posed({q: jnp.asarray(v[k]) for q, v in p.items()}))
            idx = np.floor((X - lo) / RES).astype(int)
            ok = np.all((idx >= 0) & (idx < n), 1)
            shell = np.zeros(n, bool); shell[idx[ok, 0], idx[ok, 1], idx[ok, 2]] = True
            shell = binary_dilation(shell, iterations=1)
            vol |= binary_fill_holes(shell)
    return binary_dilation(vol, iterations=1)


def rider_depth_maps(ha, i, poses_by_action):
    """For every mounted frame that uses this horse frame: (view, rider sprite mask, rider depth-toward-camera map)."""
    from posefit_mesh import posed, md
    from targets import targets
    tris = np.asarray(md["tris"])
    out = []
    for a, k in _users(ha, i, poses_by_action):
            p = poses_by_action[a]; T = targets(a)
            X = np.asarray(posed({q: jnp.asarray(v[k]) for q, v in p.items()}))
            for d in range(5):
                r, u = CAM[d]; f = np.cross(r, u)
                P2 = np.stack([ANCHOR_X + PX_OFF + SC * (X @ r), ANCHOR_Y - SC * (X @ u)], 1)[tris]
                Z = (X @ f)[tris]
                zb = np.full((CANVAS_H, CANVAS_W), -np.inf)
                mn = np.floor(P2.min(1)).astype(int); mx = np.ceil(P2.max(1)).astype(int)
                A, B, C = P2[:, 0], P2[:, 1], P2[:, 2]
                den = (B[:, 1] - C[:, 1]) * (A[:, 0] - C[:, 0]) + (C[:, 0] - B[:, 0]) * (A[:, 1] - C[:, 1])
                okt = np.abs(den) > 1e-12
                size = np.clip(mx - mn, 0, 8)
                for dy in range(9):
                    for dx in range(9):
                        t = np.nonzero(okt & (dx <= size[:, 0]) & (dy <= size[:, 1]))[0]
                        px = mn[t, 0] + dx; py = mn[t, 1] + dy; cx, cy = px + 0.5, py + 0.5
                        l0 = ((B[t, 1] - C[t, 1]) * (cx - C[t, 0]) + (C[t, 0] - B[t, 0]) * (cy - C[t, 1])) / den[t]
                        l1 = ((C[t, 1] - A[t, 1]) * (cx - C[t, 0]) + (A[t, 0] - C[t, 0]) * (cy - C[t, 1])) / den[t]
                        l2 = 1 - l0 - l1
                        m = (l0 >= -1e-4) & (l1 >= -1e-4) & (l2 >= -1e-4) & (px >= 0) & (py >= 0) & (px < CANVAS_W) & (py < CANVAS_H)
                        z = l0[m] * Z[t[m], 0] + l1[m] * Z[t[m], 1] + l2[m] * Z[t[m], 2]
                        np.maximum.at(zb, (py[m], px[m]), z)
                out.append((d, T[k, d][..., 3] > 127, zb))
    return out


def hull(ha, i, poses_by_action=None, erode=4):
    X, Y = np.meshgrid(axes[0], axes[1], indexing="ij")
    occ = np.ones(n, bool)
    ms = [mask(ha, i, d) for d in range(5)]
    for k, z in enumerate(axes[2]):
        P = np.stack([X, Y, np.full_like(X, z)], -1)
        keep = np.ones(X.shape, bool)
        for d in range(5):
            r, u = CAM[d]
            px = np.floor(ANCHOR_X + 100 + PX_OFF + SC * (P @ r)).astype(int)
            py = np.floor(ANCHOR_Y + 100 - SC * (P @ u)).astype(int)
            ok = (px >= 0) & (py >= 0) & (px < ms[d].shape[1]) & (py < ms[d].shape[0])
            inside = np.zeros(X.shape, bool)
            inside[ok] = ms[d][py[ok], px[ok]]
            keep &= inside
        occ[:, :, k] = keep
    from scipy.ndimage import binary_erosion
    if erode > 0:
        occ = binary_erosion(occ, iterations=erode)      # the hull of 5 same-elevation views is too fat / too tall
    elif erode < 0:                                      # fatter than the hull: the exact 2D horse mask clips it at render
        from scipy.ndimage import binary_dilation
        occ = binary_dilation(occ, iterations=-erode)
    if poses_by_action:
        occ &= ~rider_volume(ha, i, poses_by_action)      # the horse is never where the rider's body is
        # where the ORIGINAL rider sprite shows the rider, nothing of the horse is between the camera and the rider
        Xg, Yg, Zg = np.meshgrid(axes[0], axes[1], axes[2], indexing="ij")
        idx = np.nonzero(occ)
        Pv = np.stack([Xg[idx], Yg[idx], Zg[idx]], 1)
        carve = np.zeros(len(Pv), bool)
        for d, smask, zb in rider_depth_maps(ha, i, poses_by_action):
            r, u = CAM[d]; f = np.cross(r, u)
            px = np.floor(ANCHOR_X + PX_OFF + SC * (Pv @ r)).astype(int); py = np.floor(ANCHOR_Y - SC * (Pv @ u)).astype(int)
            ok = (px >= 0) & (py >= 0) & (px < CANVAS_W) & (py < CANVAS_H)
            vis = np.zeros(len(Pv), bool); vis[ok] = smask[py[ok], px[ok]]
            zr = np.full(len(Pv), -np.inf); zr[ok] = zb[py[ok], px[ok]]
            carve |= vis & (Pv @ f > zr + 0.02)         # voxel in front of a visible rider pixel
        occ[idx[0][carve], idx[1][carve], idx[2][carve]] = False
        print("   carved", int(carve.sum()), "voxels in front of the visible rider", flush=True)
    vol = gaussian_filter(occ.astype(np.float32), 1.0)
    v, f, _, _ = measure.marching_cubes(vol, 0.5, spacing=(RES, RES, RES))
    return v + lo, f[:, ::-1]


poses_by_action = {}
for f_ in sys.argv[1:]:
    poses_by_action.update({a: r["poses"] for a, r in pickle.load(open(f_, "rb")).items() if a in range(23, 30)})
print("rider poses for", sorted(poses_by_action))
HORSE_OF = {23: 0, 24: 1, 25: 2, 26: 2, 27: 2, 28: 2, 29: 2}
import os
ERODE = int(os.environ.get("UO_ERODE", "-2"))   # <0 = dilate; the exact 2D horse mask clips the proxy at render time
HULL_ACTS = [int(x) for x in os.environ.get("UO_HULL_ACTS", "23,24,25,26,27,28,29").split(",")]
HULL_OUT = os.environ.get("UO_HULL_OUT", "horse_hulls.pkl")
out = {}
for a in HULL_ACTS:
    F = poses_by_action[a]["trans"].shape[0]
    for k in range(F):
        RIDER_FRAME = (a, k)
        ha = HORSE_OF[a]
        v, f = hull(ha, k if ha in (0, 1) else 0, poses_by_action, erode=ERODE)
        out[(a, k)] = (v.astype(np.float32), f.astype(np.int32))
        print("rider action", a, "frame", k, "horse action", ha, "faces", len(f), flush=True)
pickle.dump(out, open(HULL_OUT, "wb"))
