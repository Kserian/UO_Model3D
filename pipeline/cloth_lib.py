"""Quasi-static cloth for loose garments (robe, dress, skirt, kilt), numpy only.

A loose garment hangs from the waist, does not stick to the legs, and the legs push it out of their way - and no more than that. This is a per-frame solve, with no
memory of the previous frame (so there are no jumps between frames, and a frame can be solved on its own):
  1. the garment is posed by the skeleton as it is bound (the waist and above follow the body, the hanging part follows the pelvis and a little of the thighs),
  2. the legs are capsules (thigh, shin, foot) in that pose: whatever of the cloth is inside a capsule (+ GAP) is pushed out,
  3. the cloth keeps the length of its edges: when a leg pushes a part out, the cloth around it is pulled along (a stretched edge is corrected stiffly, a squeezed one hardly:
     cloth folds), the waist is pinned.
Steps 2 and 3 alternate ITERS times and finish with a collision pass, so no vertex is left inside a leg.
`solve` works on any garment (vertices, edges, pinned weights); `capsules` builds the legs for a pose from the rest bones and the skinning matrices of the pose
(pose_capture.py). Used by render_uo_layer.py (items with the custom property `uo_cloth`) and by robe_calib.py (calibration against the original robes).
"""
import numpy as np


def seg_closest(X, A, B):
    """closest point of the segment AB to every row of X, and the parameter t"""
    ab = B - A
    t = np.clip(((X - A) @ ab) / max(ab @ ab, 1e-12), 0.0, 1.0)
    return A + t[:, None] * ab, t


class Capsules:
    """legs as capsules: rest bone ends + radius (from the body skin around the bone), posed by skinning matrices"""
    NAMES = ("thigh.L", "shin.L", "foot.L", "thigh.R", "shin.R", "foot.R")

    def __init__(self, bones, rest_head, rest_tail, body_rest, body_dom, names=NAMES, percentile=50):
        bones = [str(b) for b in bones]
        self.idx = [bones.index(n) for n in names if n in bones]
        self.head = np.array([rest_head[i] for i in self.idx]); self.tail = np.array([rest_tail[i] for i in self.idx])
        self.radius = []
        for i in self.idx:
            v = body_rest[np.array([str(d) == bones[i] for d in body_dom])]
            if len(v) == 0:
                self.radius.append(0.05); continue
            ab = self.tail[len(self.radius)] - self.head[len(self.radius)]
            t = np.clip(((v - self.head[len(self.radius)]) @ ab) / (ab @ ab), 0, 1)
            self.radius.append(float(np.percentile(np.linalg.norm(v - (self.head[len(self.radius)] + t[:, None] * ab), axis=1), percentile)))
        self.radius = np.array(self.radius)

    def posed(self, skin):
        """end points (K, 3) of the capsules in the pose: skin = (B, 4, 4) skinning matrices (pose_capture.py)"""
        h = np.array([(skin[i] @ np.append(self.head[k], 1))[:3] for k, i in enumerate(self.idx)])
        t = np.array([(skin[i] @ np.append(self.tail[k], 1))[:3] for k, i in enumerate(self.idx)])
        return h, t


def collide(X, free, heads, tails, radius, gap):
    """push the free points out of the capsules (each point out of the capsule it is deepest in, along the way out from the axis)"""
    Y = X
    for _ in range(2):
        depth = np.zeros(len(Y)); out = np.zeros_like(Y)
        for A, B, r in zip(heads, tails, radius):
            C, _ = seg_closest(Y, A, B)
            d = Y - C; dist = np.linalg.norm(d, axis=1)
            pen = (r + gap) - dist
            m = pen > depth
            if m.any():
                dirn = d[m] / np.maximum(dist[m], 1e-9)[:, None]
                out[m] = dirn * pen[m, None]; depth[m] = pen[m]
        Y = Y + out * free[:, None]
    return Y


def solve(X0, edges, rest_len, free, heads, tails, radius, gap=0.012, iters=30, k_stretch=0.9, k_squeeze=0.15, omega=1.0, collide_every=1):
    """X0 (n, 3) the garment as the skeleton poses it, edges (m, 2), rest_len (m,), free (n,) 0 = pinned .. 1 = free; capsules of the legs (posed).
    Returns the solved positions. A stretched edge is corrected with k_stretch, a squeezed one with k_squeeze (per iteration, shared by both ends by their `free`)."""
    X = collide(X0, free, heads, tails, radius, gap)
    e0, e1 = edges[:, 0], edges[:, 1]
    w0, w1 = free[e0], free[e1]; ws = np.maximum(w0 + w1, 1e-12)
    ok = (w0 + w1) > 0
    cnt = np.maximum(np.bincount(np.r_[e0[ok], e1[ok]], minlength=len(X)), 1).astype(float)
    for it in range(iters):
        d = X[e1] - X[e0]; l = np.linalg.norm(d, axis=1)
        c = (l - rest_len) / np.maximum(l, 1e-9)
        c = np.where(c > 0, c * k_stretch, c * k_squeeze) * ok
        dX = np.zeros_like(X)
        np.add.at(dX, e0, (w0 / ws * c)[:, None] * d); np.add.at(dX, e1, -(w1 / ws * c)[:, None] * d)
        X = X + omega * dX / cnt[:, None] * 2.0
        if (it + 1) % collide_every == 0:
            X = collide(X, free, heads, tails, radius, gap)
    return collide(X, free, heads, tails, radius, gap)


# ----------------------------------------------------------------------------------------------------------------------------------------------------------------
# Leg hull: the hanging cloth is pushed out, around the vertical axis of the waist, to where the legs reach - the "shadow" of the legs at every height, not their contact.
# Measured on the original robes (docs/qa/robe_physics.md): the hem of a robe follows the legs in stride, and a robe never pokes out of the hem line of the legs.
# For every height z of the garment (in the rest frame of the pelvis) and every angle around the axis, h(angle, z) = the farthest reach of the legs in that direction at that
# height (the support function of the circles in which the capsules of the legs cut the plane); a vertex at radius rho < h + MARGIN is pushed out by KAPPA * (h + MARGIN - rho).
# One field per frame, looked up for any mesh (no topology needed), smooth in angle and height, no iteration, no memory of the frame before.

def sample_capsules(heads, tails, radius, step=0.03):
    """spheres along the capsules: centres (m, 3), radii (m,)"""
    C, R = [], []
    for A, B, r in zip(heads, tails, radius):
        n = max(int(np.linalg.norm(B - A) / step), 1) + 1
        t = np.linspace(0, 1, n)[:, None]
        C.append(A + t * (B - A)); R.append(np.full(n, r))
    return np.concatenate(C), np.concatenate(R)


def hull_field(centres, radii, zs, centre_xy, nth=48):
    """h[nth, len(zs)]: reach of the leg circles at every angle and height; 0 where no leg is at that height. centres in the rest frame of the pelvis"""
    th = np.linspace(0, 2 * np.pi, nth, endpoint=False)
    U = np.stack([np.cos(th), np.sin(th)], 1)
    H = np.zeros((nth, len(zs)))
    q_all = centres[:, :2] - np.asarray(centre_xy)
    for k, z in enumerate(zs):
        hz = centres[:, 2] - z
        m = np.abs(hz) < radii
        if not m.any():
            continue
        rho = np.sqrt(radii[m] ** 2 - hz[m] ** 2)
        H[:, k] = (U @ q_all[m].T + rho[None, :]).max(1)
    return th, H


def smooth_field(H, passes_th=3, passes_z=2):
    for _ in range(passes_th):
        H = 0.25 * np.roll(H, 1, 0) + 0.5 * H + 0.25 * np.roll(H, -1, 0)
    for _ in range(passes_z):
        P = np.pad(H, ((0, 0), (1, 1)), mode="edge")
        H = 0.25 * P[:, :-2] + 0.5 * P[:, 1:-1] + 0.25 * P[:, 2:]
    return H


def tent(hm, zs, z_top, rho_top, drop=0.15):
    """the cloth is one sheet from the waist: where it must reach out at a low height, every height above it must reach out too, on the straight line from the waist (rho_top at z_top)
    to that point - a tent, not a bulge at the hem. hm[nth, nz]: required radius (0 = nothing required), zs ascending"""
    out = hm.copy()
    for k in range(len(zs)):
        for j in range(k):                                           # lower heights
            w = (z_top - zs[k]) / max(z_top - zs[j], 1e-9)
            line = rho_top + (hm[:, j] - rho_top) * w
            out[:, k] = np.where(hm[:, j] > rho_top, np.maximum(out[:, k], line), out[:, k])
    # below a point where the cloth is pushed it hangs down from there (gravity): its radius does not step back in, it narrows by `drop` m per m of height at most
    for k in range(len(zs) - 2, -1, -1):
        out[:, k] = np.where(out[:, k + 1] > rho_top, np.maximum(out[:, k], out[:, k + 1] - drop * (zs[k + 1] - zs[k])), out[:, k])
    return out


def hull_push(Vrest, S_pelvis, heads, tails, radius, centre_xy=(0.0, -0.02), margin=0.03, kappa=0.6, z_top=1.02, z_hem=0.05, ramp=0.15, nth=48, nz=36, use_tent=True, rho_top=None, drop=0.15):
    """displacement of the garment vertices (rest coordinates Vrest, rest frame of the pelvis), in the posed frame: apply it to the vertices posed by the pelvis"""
    Sinv = np.linalg.inv(S_pelvis)
    C, R = sample_capsules(heads, tails, radius)
    Cr = (np.c_[C, np.ones(len(C))] @ Sinv.T)[:, :3]
    zs = np.linspace(z_hem, z_top, nz)
    th, H = hull_field(Cr, R, zs, centre_xy, nth)
    H = smooth_field(H)
    u = Vrest[:, :2] - np.asarray(centre_xy); rho = np.linalg.norm(u, axis=1); ang = np.mod(np.arctan2(u[:, 1], u[:, 0]), 2 * np.pi)
    if use_tent:
        top = np.nonzero((Vrest[:, 2] > z_top - 0.14) & (Vrest[:, 2] <= z_top))[0]
        rt = rho_top if rho_top is not None else (float(np.median(rho[top])) if len(top) else 0.2)
        H = smooth_field(tent(np.where(H > 0, H + margin, 0.0), zs, z_top, rt, drop), 2, 1) - margin * (H > -1)
        H = np.where(H > margin + 1e-9, H, 0.0)
    fa = ang / (2 * np.pi) * nth; i0 = np.floor(fa).astype(int) % nth; i1 = (i0 + 1) % nth; wa = fa - np.floor(fa)
    fz = np.clip((Vrest[:, 2] - z_hem) / (z_top - z_hem), 0, 1) * (nz - 1); k0 = np.minimum(np.floor(fz).astype(int), nz - 2); wz = fz - k0
    h = (H[i0, k0] * (1 - wa) * (1 - wz) + H[i1, k0] * wa * (1 - wz) + H[i0, k0 + 1] * (1 - wa) * wz + H[i1, k0 + 1] * wa * wz)
    free = np.clip((z_top - Vrest[:, 2]) / ramp, 0, 1)                  # nothing at the waist
    push = kappa * np.maximum(0.0, np.where(h > 0, h + margin, 0.0) - rho) * free
    d_rest = np.zeros((len(Vrest), 3)); d_rest[:, :2] = push[:, None] * u / np.maximum(rho, 1e-9)[:, None]
    return d_rest @ S_pelvis[:3, :3].T


def hang_matrix(S_pelvis, frac):
    """rotation of the pelvis with a fraction `frac` of its tilt taken out (0 = the pelvis as it is, 1 = the pelvis turned upright: only its turn about the vertical stays):
    hanging cloth is pulled down by gravity, not carried with a body that bends forward or lies down"""
    R = S_pelvis[:3, :3]
    u = R @ np.array([0.0, 0.0, 1.0]); u /= np.linalg.norm(u)
    ax = np.cross(u, [0.0, 0.0, 1.0]); s = np.linalg.norm(ax)
    if s < 1e-9:
        return R
    ang = np.arctan2(s, u[2]) * frac
    ax = ax / s
    K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
    Q = np.eye(3) + np.sin(ang) * K + (1 - np.cos(ang)) * K @ K
    return Q @ R


def cloak_bend(V, z_top, z_hem, y_top, d0, d1):
    """Cloak: displacement (rest frame) that tilts the hanging cape backwards (+Y) about the shoulder line by d0 radians at the shoulders and d1 at the hem, relative to its rest shape:
    every height s below z_top turns by phi(s) = d0 + (d1 - d0) s / L (L = z_top - z_hem) and the centre line is the integral of that turn, so the cape bends instead of swinging as a plank
    (cloak_fit_frames.py fits d0, d1 per action and frame on the original cloak 468, cloak_pitch.json)."""
    L = max(z_top - z_hem, 1e-3)
    s = np.clip(z_top - V[:, 2], 0.0, None)
    k = (d1 - d0) / L
    sc = np.minimum(s, L)                                           # below the hem the angle stays d1
    ph = d0 + k * sc
    if abs(k) > 1e-6:
        Cy = (np.cos(d0) - np.cos(ph)) / k; Cz = (np.sin(ph) - np.sin(d0)) / k
    else:
        Cy = sc * np.sin(d0); Cz = sc * np.cos(d0)
    tail = s - sc                                                   # straight continuation below the hem
    Cy = Cy + tail * np.sin(ph); Cz = Cz + tail * np.cos(ph)
    e = V[:, 1] - y_top
    Vn = np.empty_like(V)
    Vn[:, 0] = V[:, 0]
    Vn[:, 1] = y_top + Cy + e * np.cos(ph)
    Vn[:, 2] = z_top - Cz + e * np.sin(ph)
    out = Vn - V
    out[s <= 0] = 0.0
    return out


# Conformed garments (uo_conform_item.py: custom property uo_conform, point attribute uo_region): every frame each vertex is kept `gap` outside the skin of its own region
# (0 the body of a shirt, its skirt and collar: torso, legs, head and both arms, which pass in front of it; 1 / 2 a sleeve: the left / right arm + hand; 3 / 4 the root of a
# sleeve: its arm and the torso, the side of the chest comes out under a raised arm), pushed along the skin normal and spread over the item, so the skin never comes through
# it. A sleeve does not look at the torso: an arm pressed to the side of the torso is in its sleeve, between them.
_TORSO = {"pelvis", "spine", "chest", "neck", "clavicle.L", "clavicle.R", "head", "thigh.L", "shin.L", "foot.L", "thigh.R", "shin.R", "foot.R"}
_ARMS = {"upper_arm.L", "forearm.L", "hand.L", "upper_arm.R", "forearm.R", "hand.R"}
CONFORM_BONES = (_TORSO | _ARMS, {"upper_arm.L", "forearm.L", "hand.L"}, {"upper_arm.R", "forearm.R", "hand.R"},
                 _TORSO | {"upper_arm.L", "forearm.L", "hand.L"}, _TORSO | {"upper_arm.R", "forearm.R", "hand.R"})


def conform_masks(dom_bones):
    """triangle masks of the conform regions; dom_bones = the dominant bone name of every body triangle (finger bones count as the hand of their side)"""
    base = [("hand" + b[-2:]) if b.startswith("finger") else b for b in dom_bones]
    return [np.array([b in s for b in base]) for s in CONFORM_BONES]


def conform_push(X, bvhs, lab, E, deg, gap, iters=16, exact=6):
    """displacement that keeps every point X[i] `gap` outside the body part bvhs[lab[i]] (mathutils BVHTree, same space as X); smoothed over the item edges E"""
    from mathutils import Vector
    D = np.zeros_like(X); look = np.arange(len(X)); reach = 0.15
    for it in range(iters + exact):                                 # the last `exact` rounds are not smoothed: what is left is millimetres (a push along one face normal at a corner)
        P = X + D; need = np.zeros(len(X)); N = np.zeros_like(X); near = []
        for i in look:
            p = Vector(P[i]); loc, nrm, fi, dist = bvhs[lab[i]].find_nearest(p, reach)
            if loc is not None:
                near.append(i); sd = (p - loc).dot(nrm)
                if sd < gap:
                    need[i] = gap - sd; N[i] = nrm
        if it == 0:
            look = np.array(near, int); reach = gap + 0.08
        if not (need > 1e-4).any():
            break
        D += need[:, None] * N
        if it < iters - 1:
            for _ in range(2):
                acc = np.zeros_like(D)
                np.add.at(acc, E[:, 0], D[E[:, 1]]); np.add.at(acc, E[:, 1], D[E[:, 0]])
                D = np.where(deg[:, None] > 0, 0.5 * D + 0.5 * acc / np.maximum(deg, 1)[:, None], D)
            look = np.union1d(look, np.nonzero(np.abs(D).max(1) > 1e-5)[0])
    return D
