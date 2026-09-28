"""Build a smooth rest-pose body surface from the fitted primitives: SDF smooth-union + marching cubes."""
import numpy as np
from skimage import measure
import jax.numpy as jnp
from body import fk, zero_pose, JI, ARM_REST_ANGLE

PART_BONE = {}  # primitive name -> bone name (for skin weights)


def sd_ellipsoid(p, c, R, r):
    q = (p - c) @ R  # into local frame
    k0 = np.linalg.norm(q / r, axis=-1)
    k1 = np.linalg.norm(q / (r * r), axis=-1)
    return k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)


def sd_round_cone(p, a, b, r1, r2):
    ba = b - a
    l2 = ba @ ba
    rr = r1 - r2
    a2 = l2 - rr * rr
    il2 = 1.0 / l2
    pa = p - a
    y = pa @ ba
    z = y - l2
    x2 = np.sum((pa * l2 - np.outer(y, ba)) ** 2, -1)
    y2 = y * y * l2
    z2 = z * z * l2
    k = np.sign(rr) * rr * rr * x2
    d3 = (np.sqrt(np.maximum(x2 * a2 * il2, 0)) + y * rr) * il2 - r1
    d = np.where(np.sign(z) * a2 * z2 > k, np.sqrt(x2 + z2) * il2 - r2,
                 np.where(np.sign(y) * a2 * y2 < k, np.sqrt(x2 + y2) * il2 - r1, d3))
    return d


def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1 - h) + a * h - k * h * (1 - h)


def rot_x(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rot_y(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def body_parts(S):
    """List of (name, bone, sdf_fn) for the rest pose (A-pose)."""
    S = {k: np.asarray(v, np.float64) for k, v in S.items()}
    P, _ = fk({k: jnp.asarray(v, jnp.float32) for k, v in S.items()}, zero_pose())
    P = np.asarray(P, np.float64)
    I = np.eye(3)
    sa, ca = np.sin(ARM_REST_ANGLE), np.cos(ARM_REST_ANGLE)
    parts = []

    def ell(name, bone, c, r, R=I):
        parts.append((name, bone, lambda p, c=c, r=r, R=R: sd_ellipsoid(p, c, R, r)))

    def cone(name, bone, a, b, r1, r2):
        parts.append((name, bone, lambda p, a=a, b=b, r1=r1, r2=r2: sd_round_cone(p, a, b, r1, r2)))

    pel, sp, ch, nk, hd = (P[JI[n]] for n in ("pelvis", "spine", "chest", "neck", "head"))
    ell("pelvis", "pelvis", pel + S["pelvis_c"], S["pelvis_r"])
    ell("abdomen", "spine", sp + S["abd_c"], S["abd_r"])
    ell("chest", "chest", ch + S["chest_c"], S["chest_r"])
    cone("neck", "neck", nk, hd, S["neck_r"], S["neck_r"] * 0.9)
    hc, hr = hd + S["head_c"], S["head_r"]
    ell("head", "head", hc, hr)
    # --- anatomical detail (fixed relative to fitted sizes; small, mostly inside the fitted silhouette)
    ell("jaw", "head", hc + np.array([0, -0.35 * hr[1], -0.45 * hr[2]]), hr * np.array([0.75, 0.62, 0.5]))
    cone("nose", "head", hc + np.array([0, -0.80 * hr[1], 0.05 * hr[2]]),
         hc + np.array([0, -1.02 * hr[1], -0.22 * hr[2]]), 0.10 * hr[0], 0.16 * hr[0])
    ell("brow", "head", hc + np.array([0, -0.62 * hr[1], 0.20 * hr[2]]), hr * np.array([0.62, 0.30, 0.16]))
    for sx in (1, -1):
        ell("ear" + str(sx), "head", hc + np.array([sx * 0.93 * hr[0], 0.05 * hr[1], 0.02 * hr[2]]),
            hr * np.array([0.14, 0.24, 0.32]))
    cr, cc = S["chest_r"], ch + S["chest_c"]
    for sx, side in ((1, "L"), (-1, "R")):
        ell("pec." + side, "chest", cc + np.array([sx * 0.42 * cr[0], -0.55 * cr[1], 0.05 * cr[2]]),
            np.array([0.46 * cr[0], 0.48 * cr[1], 0.38 * cr[2]]))
        sh = P[JI["shoulder." + side]]
        ell("delt." + side, "upper_arm." + side, sh + np.array([sx * 0.25, 0, -0.35]) * S["uarm_r"][0],
            np.array([1.15, 1.2, 1.35]) * S["uarm_r"][0], rot_y(sx * ARM_REST_ANGLE * 0.5))
        ell("trap." + side, "chest", (sh + nk) / 2 + np.array([0, 0.25 * cr[1], -0.02]),
            np.array([0.55 * np.linalg.norm(sh - nk), 0.45 * cr[1], 0.28 * cr[2]]))
        ell("glute." + side, "pelvis", pel + S["pelvis_c"] + np.array([sx * 0.45 * S["pelvis_r"][0], 0.45 * S["pelvis_r"][1], -0.25 * S["pelvis_r"][2]]),
            S["pelvis_r"] * np.array([0.52, 0.62, 0.62]))
        ua = (P[JI["shoulder." + side]], P[JI["elbow." + side]])
        cone("uarm." + side, "upper_arm." + side, ua[0], ua[1], *S["uarm_r"])
        fa = (P[JI["elbow." + side]], P[JI["wrist." + side]])
        cone("farm." + side, "forearm." + side, fa[0], fa[1], *S["farm_r"])
        d = np.array([sx * sa, 0, -ca])
        Rh = rot_y(sx * ARM_REST_ANGLE).T
        Rh = np.array([[ca, 0, -sx * sa], [0, 1, 0], [sx * sa, 0, ca]])
        w = P[JI["wrist." + side]]
        # palm: flattened in the arm plane (thin along Y), thumb pointing forward
        ell("hand." + side, "hand." + side, w + d * S["hand"] * 0.45, S["hand_r"], Rh)
        tb = w + d * S["hand"] * 0.25 + np.array([0, -S["hand_r"][1] * 1.2, 0])
        cone("thumb." + side, "hand." + side, w + d * 0.02 + np.array([0, -S["hand_r"][1] * 0.5, 0]),
             tb + d * S["hand"] * 0.25, S["hand_r"][1] * 0.75, S["hand_r"][1] * 0.6)
        th = (P[JI["hip." + side]], P[JI["knee." + side]])
        cone("thigh." + side, "thigh." + side, th[0], th[1], *S["thigh_r"])
        sh_ = (P[JI["knee." + side]], P[JI["ankle." + side]])
        cone("shin." + side, "shin." + side, sh_[0], sh_[1], *S["shin_r"])
        ell("calf." + side, "shin." + side, sh_[0] * 0.72 + sh_[1] * 0.28 + np.array([0, 0.35 * S["shin_r"][0], 0]),
            np.array([0.85, 0.9, 2.6]) * S["shin_r"][0])
        a = P[JI["ankle." + side]]
        heel = a + np.array([0.0, S["heel_y"], -S["ankle_h"] + S["foot_r"][0]])
        toe = a + np.array([0.0, -S["foot_len"] + S["heel_y"] + S["foot_r"][1], -S["ankle_h"] + S["foot_r"][1]])
        cone("foot." + side, "foot." + side, heel, toe, *S["foot_r"])
    return parts, P


BLEND_K = {"default": 0.03, "abdomen": 0.08, "chest": 0.08, "neck": 0.05, "head": 0.03,
           "nose": 0.008, "ear1": 0.006, "ear-1": 0.006, "thumb.L": 0.01, "thumb.R": 0.01, "brow": 0.015,
           "jaw": 0.02, "pec.L": 0.04, "pec.R": 0.04, "trap.L": 0.05, "trap.R": 0.05,
           "glute.L": 0.04, "glute.R": 0.04, "uarm.L": 0.04, "uarm.R": 0.04, "thigh.L": 0.035, "thigh.R": 0.035}


def body_sdf(parts, pts):
    d = None
    per = []
    for name, bone, f in parts:
        di = f(pts)
        per.append(di)
        k = BLEND_K.get(name, BLEND_K["default"])
        d = di if d is None else smin(d, di, k)
    return d, np.stack(per)


def build_mesh(S, res=0.006):
    parts, P = body_parts(S)
    lo = np.array([-1.0, -0.4, -0.05])
    hi = np.array([1.0, 0.4, 2.2])
    # tighten box using joints
    lo = np.minimum(lo, P.min(0) - 0.3)
    hi = np.maximum(hi, P.max(0) + 0.3)
    n = np.ceil((hi - lo) / res).astype(int) + 1
    g = np.stack(np.meshgrid(*[lo[i] + np.arange(n[i]) * res for i in range(3)], indexing="ij"), -1).reshape(-1, 3)
    d = np.empty(len(g))
    for i in range(0, len(g), 400000):
        d[i:i + 400000], _ = body_sdf(parts, g[i:i + 400000])
    vol = d.reshape(n)
    v, f, nrm, _ = measure.marching_cubes(vol, 0.0, spacing=(res, res, res))
    v = v + lo
    return v, f[:, ::-1], parts, P
