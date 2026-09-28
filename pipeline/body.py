"""Parametric humanoid (primitives on a skeleton) + orthographic soft-silhouette renderer in JAX.

Conventions (Blender-like): Z up, character faces -Y, character's left is +X. Units: metres.
UO file direction d is rendered with the character yawed by -d*45 deg about Z, seen by an
orthographic camera placed on the -Y side, elevated by angle theta.
"""
import numpy as np
import jax
import jax.numpy as jnp

CANVAS_W, CANVAS_H = 136, 120
ANCHOR_X, ANCHOR_Y = 68, 86

# ---------------------------------------------------------------- skeleton
# name, parent
JOINTS = [
    ("pelvis", -1), ("spine", 0), ("chest", 1), ("neck", 2), ("head", 3),
    ("shoulder.L", 2), ("elbow.L", 5), ("wrist.L", 6),
    ("shoulder.R", 2), ("elbow.R", 8), ("wrist.R", 9),
    ("hip.L", 0), ("knee.L", 11), ("ankle.L", 12),
    ("hip.R", 0), ("knee.R", 14), ("ankle.R", 15),
]
JI = {n: i for i, (n, _) in enumerate(JOINTS)}
NJ = len(JOINTS)
ARM_REST_ANGLE = np.radians(40.0)  # A-pose: arms rotated outward from vertical
LEG_REST_ANGLE = np.radians(6.0)   # legs slightly apart in the rest pose


def init_shape():
    s = dict(
        hip_w=0.10, hip_drop=0.06, thigh=0.42, shin=0.43, ankle_h=0.08,
        spine0=0.10, abd=0.16, chest_len=0.22, neck_y=0.0, neck_len=0.10,
        sh_x=0.20, sh_y=0.0, sh_z=0.18, uarm=0.30, farm=0.27, hand=0.18,
        # radii / ellipsoids  (x = width, y = depth, z = height half-axes)
        pelvis_c=np.array([0.0, 0.0, 0.03]), pelvis_r=np.array([0.17, 0.11, 0.11]),
        abd_c=np.array([0.0, -0.01, 0.08]), abd_r=np.array([0.15, 0.11, 0.12]),
        chest_c=np.array([0.0, -0.01, 0.12]), chest_r=np.array([0.20, 0.13, 0.16]),
        head_c=np.array([0.0, -0.02, 0.11]), head_r=np.array([0.085, 0.10, 0.12]),
        neck_r=0.06,
        uarm_r=np.array([0.065, 0.05]), farm_r=np.array([0.05, 0.04]), hand_r=np.array([0.03, 0.045, 0.085]),
        thigh_r=np.array([0.09, 0.06]), shin_r=np.array([0.065, 0.045]),
        foot_len=0.24, foot_r=np.array([0.045, 0.035]), heel_y=0.04,
        theta=np.radians(30.0), scale=36.0,
    )
    return {k: jnp.asarray(v, dtype=jnp.float32) for k, v in s.items()}


def rest_offsets(S):
    """Offset of each joint from its parent in the parent's (rest) frame."""
    sa, ca = jnp.sin(ARM_REST_ANGLE), jnp.cos(ARM_REST_ANGLE)
    z = jnp.zeros(())
    def v(x, y, zz):
        return jnp.stack([jnp.asarray(x, jnp.float32) + z, jnp.asarray(y, jnp.float32) + z, jnp.asarray(zz, jnp.float32) + z])
    sl, cl = jnp.sin(LEG_REST_ANGLE), jnp.cos(LEG_REST_ANGLE)
    hip_h = S["hip_drop"] + (S["thigh"] + S["shin"]) * cl + S["ankle_h"]
    off = [
        v(0, 0, hip_h),
        v(0, 0, S["spine0"]),
        v(0, 0, S["abd"]),
        v(0, S["neck_y"], S["chest_len"]),
        v(0, 0, S["neck_len"]),
        v(S["sh_x"], S["sh_y"], S["sh_z"]),
        v(S["uarm"] * sa, 0, -S["uarm"] * ca),
        v(S["farm"] * sa, 0, -S["farm"] * ca),
        v(-S["sh_x"], S["sh_y"], S["sh_z"]),
        v(-S["uarm"] * sa, 0, -S["uarm"] * ca),
        v(-S["farm"] * sa, 0, -S["farm"] * ca),
        v(S["hip_w"], 0, -S["hip_drop"]),
        v(S["thigh"] * sl, 0, -S["thigh"] * cl),
        v(S["shin"] * sl, 0, -S["shin"] * cl),
        v(-S["hip_w"], 0, -S["hip_drop"]),
        v(-S["thigh"] * sl, 0, -S["thigh"] * cl),
        v(-S["shin"] * sl, 0, -S["shin"] * cl),
    ]
    return jnp.stack(off)


def rodrigues(r):
    th = jnp.sqrt(jnp.sum(r * r) + 1e-12)
    k = r / th
    K = jnp.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return jnp.eye(3) + jnp.sin(th) * K + (1 - jnp.cos(th)) * (K @ K)


def fk(S, pose):
    """pose: dict(rot=(NJ,3) axis-angle local rotations, trans=(3,)). Returns joint world pos & rot."""
    off = rest_offsets(S)
    Rl = jax.vmap(rodrigues)(pose["rot"])
    Rw, Pw = [None] * NJ, [None] * NJ
    for j, (_, p) in enumerate(JOINTS):
        if p < 0:
            Rw[j] = Rl[j]
            Pw[j] = off[j] + pose["trans"]
        else:
            Rw[j] = Rw[p] @ Rl[j]
            Pw[j] = Pw[p] + Rw[p] @ off[j]
    return jnp.stack(Pw), jnp.stack(Rw)


def primitives(S, P, R):
    """Returns (ellipsoids: centers (Ne,3), covs (Ne,3,3)), (cones: a (Nc,3), b (Nc,3), ra, rb)."""
    ec, eC = [], []
    def ell(j, c, r):
        ec.append(P[j] + R[j] @ c)
        M = R[j] * r[None, :]
        eC.append(M @ M.T)
    sa, ca = jnp.sin(ARM_REST_ANGLE), jnp.cos(ARM_REST_ANGLE)
    ell(JI["pelvis"], S["pelvis_c"], S["pelvis_r"])
    ell(JI["spine"], S["abd_c"], S["abd_r"])
    ell(JI["chest"], S["chest_c"], S["chest_r"])
    ell(JI["head"], S["head_c"], S["head_r"])
    for side, sx in (("L", 1.0), ("R", -1.0)):
        w = JI["wrist." + side]
        # hand hangs along the forearm direction
        d = jnp.array([sx * sa, 0.0, -ca])
        c = d * S["hand"] * 0.5
        Rh = R[w] @ jnp.array([[ca, 0, sx * sa], [0, 1, 0], [-sx * sa, 0, ca]]).T
        ec.append(P[w] + R[w] @ c)
        M = Rh * S["hand_r"][None, :]
        eC.append(M @ M.T)
    ca_, cb_, ra_, rb_ = [], [], [], []
    def cone(a, b, r):
        ca_.append(a); cb_.append(b); ra_.append(r[0]); rb_.append(r[1])
    cone(P[JI["neck"]], P[JI["head"]], jnp.stack([S["neck_r"], S["neck_r"] * 0.9]))
    for side in ("L", "R"):
        cone(P[JI["shoulder." + side]], P[JI["elbow." + side]], S["uarm_r"])
        cone(P[JI["elbow." + side]], P[JI["wrist." + side]], S["farm_r"])
        cone(P[JI["hip." + side]], P[JI["knee." + side]], S["thigh_r"])
        cone(P[JI["knee." + side]], P[JI["ankle." + side]], S["shin_r"])
        a = JI["ankle." + side]
        heel = P[a] + R[a] @ jnp.stack([0.0, S["heel_y"], -S["ankle_h"] + S["foot_r"][0]])
        toe = P[a] + R[a] @ jnp.stack([0.0, -S["foot_len"] + S["heel_y"] + S["foot_r"][1], -S["ankle_h"] + S["foot_r"][1]])
        cone(heel, toe, S["foot_r"])
    return (jnp.stack(ec), jnp.stack(eC)), (jnp.stack(ca_), jnp.stack(cb_), jnp.stack(ra_), jnp.stack(rb_))


def camera(S, d):
    """Projection basis for file direction d: returns (right, up) in character space, scale."""
    yaw = -d * np.pi / 4
    th = S["theta"]
    # camera basis in world (camera on -Y side looking +Y, elevated)
    right_w = jnp.array([1.0, 0.0, 0.0])
    up_w = jnp.stack([0.0, jnp.sin(th), jnp.cos(th)])
    # character rotated by yaw -> express camera basis in character space (rotate by -yaw)
    c, s = np.cos(-yaw), np.sin(-yaw)
    Rz = jnp.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]], dtype=jnp.float32)
    return Rz @ right_w, Rz @ up_w


_yy, _xx = np.mgrid[0:CANVAS_H, 0:CANVAS_W].astype(np.float32)
PIX = jnp.asarray(np.stack([_xx + 0.5 - ANCHOR_X, -(_yy + 0.5 - ANCHOR_Y)], -1))  # screen coords, y up, px


def render_sil(S, P, R, d, tau=0.45, return_parts=False, pix=None):
    pix = PIX if pix is None else pix
    oh, ow = pix.shape[:2]
    (ec, eC), (ca, cb, ra, rb) = primitives(S, P, R)
    right, up = camera(S, d)
    B = jnp.stack([right, up]) * S["scale"]  # 2x3
    q = pix.reshape(-1, 2)
    # ellipsoids
    c2 = ec @ B.T
    C2 = jnp.einsum("ij,njk,lk->nil", B, eC, B)
    M = jnp.linalg.inv(C2)
    dq = q[None] - c2[:, None]
    Mq = jnp.einsum("nij,npj->npi", M, dq)
    rho = jnp.sqrt(jnp.sum(dq * Mq, -1) + 1e-9)
    g = jnp.sqrt(jnp.sum(Mq * Mq, -1) + 1e-9) / rho
    de = (rho - 1.0) / g
    # cones (interpolated-disc approximation)
    a2, b2 = ca @ B.T, cb @ B.T
    ab = b2 - a2
    h = jnp.sum(ab * ab, -1) + 1e-6
    t = jnp.clip(jnp.einsum("npk,nk->np", q[None] - a2[:, None], ab) / h[:, None], 0.0, 1.0)
    pt = a2[:, None] + t[..., None] * ab[:, None]
    rr = (ra + (rb - ra) * t.T).T * S["scale"]
    dc = jnp.sqrt(jnp.sum((q[None] - pt) ** 2, -1) + 1e-9) - rr
    dist = jnp.concatenate([de, dc], 0)
    occ_i = jax.nn.sigmoid(-dist / tau)
    occ = 1.0 - jnp.prod(1.0 - occ_i, 0)
    occ = occ.reshape(oh, ow)
    if return_parts:
        return occ, dist.reshape(-1, oh, ow)
    return occ


def zero_pose():
    return dict(rot=jnp.zeros((NJ, 3), jnp.float32), trans=jnp.zeros(3, jnp.float32))
