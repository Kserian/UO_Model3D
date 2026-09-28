import numpy as np
import jax
import jax.numpy as jnp
import optax
from body import *

POS_KEYS = ["hip_w", "hip_drop", "thigh", "shin", "ankle_h", "spine0", "abd", "chest_len", "neck_len",
            "sh_x", "sh_z", "uarm", "farm", "hand", "pelvis_r", "abd_r", "chest_r", "head_r", "neck_r",
            "uarm_r", "farm_r", "hand_r", "thigh_r", "shin_r", "foot_len", "foot_r"]
FIXED_KEYS = ["scale"]

# hinge axes (in parent-local rest frame of the joint)
_sa, _ca = np.sin(ARM_REST_ANGLE), np.cos(ARM_REST_ANGLE)
_sl, _cl = np.sin(LEG_REST_ANGLE), np.cos(LEG_REST_ANGLE)
HINGE = {
    JI["elbow.L"]: np.array([_ca, 0, _sa]), JI["elbow.R"]: np.array([_ca, 0, -_sa]),
    JI["knee.L"]: np.array([_cl, 0, _sl]), JI["knee.R"]: np.array([_cl, 0, -_sl]),
}
HINGE_IDX = sorted(HINGE)
BALL_IDX = [j for j in range(NJ) if j not in HINGE]
HINGE_AX = jnp.asarray(np.stack([HINGE[j] for j in HINGE_IDX]), jnp.float32)


def shape_to_params(S):
    p = {}
    for k, v in S.items():
        if k in FIXED_KEYS:
            continue
        p[k] = jnp.log(v) if k in POS_KEYS else v
    return p


CENTER_KEYS = ["pelvis_c", "abd_c", "chest_c", "head_c"]


def params_to_shape(p, fixed):
    S = dict(fixed)
    for k, v in p.items():
        S[k] = jnp.exp(v) if k in POS_KEYS else v
        if k in CENTER_KEYS:  # bilateral symmetry: torso/head centres on the mid-plane
            S[k] = S[k].at[0].set(0.0)
    return S


# anatomical plausibility bounds (metres); (key, component or None, lo, hi)
BOUNDS = [
    ("neck_y", None, -0.08, 0.02), ("sh_y", None, -0.05, 0.05),
    ("chest_len", None, 0.15, 0.30), ("abd", None, 0.10, 0.25), ("spine0", None, 0.05, 0.15),
    ("pelvis_c", 1, -0.03, 0.03), ("pelvis_c", 2, -0.04, 0.08),
    ("pelvis_r", 0, 0.12, 0.22), ("pelvis_r", 1, 0.08, 0.15), ("pelvis_r", 2, 0.08, 0.15),
    ("abd_c", 1, -0.04, 0.02), ("abd_c", 2, 0.03, 0.15),
    ("abd_r", 0, 0.11, 0.20), ("abd_r", 1, 0.08, 0.15), ("abd_r", 2, 0.08, 0.16),
    ("chest_c", 1, -0.04, 0.02), ("chest_c", 2, 0.05, 0.20),
    ("chest_r", 0, 0.14, 0.26), ("chest_r", 1, 0.09, 0.16), ("chest_r", 2, 0.10, 0.20),
    ("head_c", 1, -0.06, 0.02), ("head_c", 2, 0.06, 0.14),
    ("head_r", 0, 0.07, 0.11), ("head_r", 1, 0.09, 0.13), ("head_r", 2, 0.10, 0.14),
    ("neck_len", None, 0.06, 0.16), ("neck_r", None, 0.04, 0.09),
    ("hand_r", 0, 0.02, 0.045), ("hand_r", 1, 0.035, 0.06), ("hand_r", 2, 0.07, 0.10),
    ("hand", None, 0.15, 0.24), ("foot_len", None, 0.22, 0.30), ("foot_r", 0, 0.03, 0.05), ("foot_r", 1, 0.03, 0.05),
    ("heel_y", None, 0.0, 0.07), ("ankle_h", None, 0.06, 0.12),
    ("uarm", None, 0.22, 0.34), ("farm", None, 0.20, 0.32), ("thigh", None, 0.34, 0.50), ("shin", None, 0.38, 0.48),
    ("hip_w", None, 0.085, 0.13), ("hip_drop", None, 0.03, 0.10), ("sh_x", None, 0.15, 0.24), ("sh_z", None, 0.12, 0.25),
    ("uarm_r", 0, 0.045, 0.085), ("uarm_r", 1, 0.04, 0.075), ("farm_r", 0, 0.04, 0.07), ("farm_r", 1, 0.03, 0.055),
    ("thigh_r", 0, 0.07, 0.10), ("thigh_r", 1, 0.05, 0.085), ("shin_r", 0, 0.05, 0.085), ("shin_r", 1, 0.035, 0.06),
    ("theta", None, 0.35, 0.75),
]


def bounds_penalty(S):
    pen = 0.0
    for k, i, lo, hi in BOUNDS:
        x = S[k] if i is None else S[k][i]
        pen += (jax.nn.relu(lo - x) ** 2 + jax.nn.relu(x - hi) ** 2) * 1e4
    # keep a crotch gap: thighs must not overlap at the hips
    pen += jax.nn.relu(S["thigh_r"][0] - (S["hip_w"] - 0.005)) ** 2 * 1e4
    return pen


TORSO_JOINTS = [JI[n] for n in ("spine", "chest", "neck", "head")]


def pose_from_params(pp):
    rot = jnp.zeros((NJ, 3), jnp.float32)
    rot = rot.at[jnp.array(BALL_IDX)].set(pp["ball"])
    rot = rot.at[jnp.array(HINGE_IDX)].set(pp["hinge"][:, None] * HINGE_AX)
    return dict(rot=rot, trans=pp["trans"])


def init_pose_params(kind="stand"):
    ball = np.zeros((len(BALL_IDX), 3), np.float32)
    bi = {j: i for i, j in enumerate(BALL_IDX)}
    ball[bi[JI["shoulder.L"]]] = [0, 0.55, 0]
    ball[bi[JI["shoulder.R"]]] = [0, -0.55, 0]
    hinge = np.zeros(len(HINGE_IDX), np.float32)
    hi = {j: i for i, j in enumerate(HINGE_IDX)}
    hinge[hi[JI["elbow.L"]]] = -0.2
    hinge[hi[JI["elbow.R"]]] = -0.2
    hinge[hi[JI["knee.L"]]] = 0.05
    hinge[hi[JI["knee.R"]]] = 0.05
    return dict(ball=jnp.asarray(ball), hinge=jnp.asarray(hinge), trans=jnp.zeros(3, jnp.float32))


def hinge_limit_penalty(h):
    hi = {j: i for i, j in enumerate(HINGE_IDX)}
    pen = 0.0
    for side in ("L", "R"):
        e = h[hi[JI["elbow." + side]]]
        k = h[hi[JI["knee." + side]]]
        pen += jax.nn.relu(e) ** 2 + jax.nn.relu(-2.6 - e) ** 2
        pen += jax.nn.relu(-k) ** 2 + jax.nn.relu(k - 2.6) ** 2
    return pen


def foot_min_z(S, P, R):
    (_, _), (ca, cb, ra, rb) = primitives(S, P, R)
    # foot cones are the last two entries of each side block; take all cones' lowest points
    z = jnp.concatenate([ca[:, 2] - ra, cb[:, 2] - rb])
    return jnp.min(z)


def torso_prior(pp):
    bi = {j: i for i, j in enumerate(BALL_IDX)}
    return sum(jnp.sum(pp["ball"][bi[j]] ** 2) for j in TORSO_JOINTS)


def frame_loss(S, pp, alpha, ground_w, pix=None, torso_w=0.0):
    """alpha: (5,H,W) target coverage."""
    pose = pose_from_params(pp)
    P, R = fk(S, pose)
    occ = jnp.stack([render_sil(S, P, R, d, pix=pix) for d in range(5)])
    data = jnp.mean((occ - alpha) ** 2) * 100.0
    reg = 1e-3 * jnp.sum(pp["ball"] ** 2) + 1.0 * hinge_limit_penalty(pp["hinge"]) + torso_w * torso_prior(pp)
    mz = foot_min_z(S, P, R)
    ground = ground_w * (mz ** 2) * 100.0 + 10.0 * jax.nn.relu(-mz - 0.01) ** 2 * 100
    return data + reg + ground, data


def shape_prior(S, S0):
    # keep symmetric-ish sane values; weak pull toward init to break degeneracy
    pen = 0.0
    for k in POS_KEYS:
        pen += 0.02 * jnp.sum((jnp.log(S[k]) - jnp.log(S0[k])) ** 2)
    return pen + bounds_penalty(S)


def crop_box(alpha_np, margin=8):
    """alpha_np (...,H,W) -> (y0,y1,x0,x1) bbox of union of nonzero pixels + margin."""
    m = alpha_np.reshape(-1, *alpha_np.shape[-2:]).max(0) > 0
    ys, xs = np.nonzero(m)
    y0, y1 = max(0, ys.min() - margin), min(m.shape[0], ys.max() + 1 + margin)
    x0, x1 = max(0, xs.min() - margin), min(m.shape[1], xs.max() + 1 + margin)
    return y0, y1, x0, x1
