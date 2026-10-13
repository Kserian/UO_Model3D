"""A flail (haft + chain + ball): the haft stays rigid in the hand, the chain and the ball swing with the motion of the hand (own simulation, per action).

    python uo_flail.py ITEM.blend [OUT.blend] [--out flail_sim.npz] [--actions 09_attack_1h_slash,...|all] [--set NAME=VALUE ...]

ITEM.blend = a weapon made by uo_make_item.py ("weapon": {"part": "weapon1h", ...}): rigid on weapon1h.R, laid along the hand line with the butt at the hand and the
ball at the far end. uo_make_item.py runs this for a recipe with "flail": {...} (its settings).
1. Parts along the weapon axis (rest pose; s = m from the butt): the haft is the thin solid part at the butt (few vertices per cm), the chain the thin part with many
   vertices (links), the ball the wide end (radius > BALL_R); HAFT_END / BALL_START (m) override.  BALL_SCALE scales the ball about its point on the chain.
   CHAIN_SCALE stretches the chain along the axis (the ball moves with it).
2. The chain is SEGMENTS rigid pieces between nodes on the axis, the ball one more rigid piece from the last node to its centre. Per vertex: attribute uo_flail_s (s)
   and uo_flail_part (0 haft, 1 chain, 2 ball); the object gets the custom property uo_flail (JSON: the rest nodes in armature space, ...).
3. Simulation (Verlet, armature space of direction 0; the direction is a turn about z, which does not change gravity): node 0 is the end of the haft, carried by
   the bone weapon1h.R; the others fall (GRAVITY), lose speed (DAMP per s), keep their distances (ITER passes, the ball MASS x a link) and stay out of the body
   (capsules of pelvis, spine, chest, neck, head, thighs, shins, left arm; GAP). A UO frame lasts FRAME_TIME s; the hand moves smoothly between the scene frames
   (STEP per UO frame, interpolated). A looping action (walk, run, stand, idle) runs CYCLES times, the last one is kept; any other starts after PREROLL s
   hanging still in its first pose. The nodes per action and frame go to flail_sim.npz next to the item ("<action>_<frame>": (n, 3) armature space),
   render_uo_layer.py moves the chain and ball by them (rotation of each piece = the turn of its segment carried down the chain from the haft: no twist jumps).
Calibration against an original flail .vd: flail_fit.py (docs/qa/flail.md).
"""
import json, os, sys
import numpy as np
import bpy
from mathutils import Matrix, Vector, Quaternion

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from bpy_compat import action_fcurves  # noqa: E402,F401

HAFT_END = 0.0        # m from the butt where the chain starts; 0 = found from the mesh
BALL_START = 0.0      # m from the butt where the ball starts; 0 = found
BALL_R = 0.07         # m: a cross-section wider than this (95th percentile radius) is the ball
BALL_SCALE = 1.0      # the ball scaled about the point where the chain holds it
CHAIN_SCALE = 1.0     # the chain stretched along the axis (the ball moves on)
HAFT_SCALE = 1.0      # the haft stretched along the axis from the butt (the chain and the ball move on)
STIFF = 0.0           # 1/s: each piece of the chain is pulled towards the line of the one before it (the first: the haft); 0 = a free chain. The original flail is drawn
                      # with a chain that mostly keeps the line of the haft
SEGMENTS = 6          # rigid pieces of the chain
FRAME_TIME = 0.1      # s per UO frame
SUB = 12              # simulation steps per scene frame
GRAVITY = 9.81
DAMP = 1.5            # 1/s: velocity lost (air, the friction of the links)
MASS = 6.0            # the ball's mass in links
ITER = 20
GAP = 0.02            # m outside the body capsules
BALL_GAP = 0.0        # m: extra radius of the ball node against the body (0 = from the ball's size x 0.6)
INELASTIC = True      # the push out of the body does not turn into speed (with it, the ball bounced off the head, the chest and the saddle: 2-5 x faster than the original
                      # in eat, salute, mounted walk, the bow attacks)
WEAPON_BONE_ACTIONS = ""   # actions ("18,23,26") in which the haft is carried by weapon1h.R (its turn fitted to the original weapons) instead of HOLD; needs HAND_SMOOTH > 0
                      # (the renderer draws the haft with the stored carrier). Measured: mounted 1H attack (26): with the hand the haft crossed the body, with weapon1h.R it swings outside
ALIGN_ACTIONS = ""    # actions in which the haft continues the line of the forearm (the hand's turn kept otherwise, the grip in the hand): a swing or a raised fist. Mounted 1H
                      # attack (26): the original flail is the arm's extension and the ball flies out far forward; with weapon1h.R the haft pointed into the body. Area spell (17):
                      # the original holds it up along the raised forearm; with the hand it turned about the arm's axis (user, 2026-10-13)
UP_ACTIONS = ""       # actions in which the haft stands upright in the hand (salute, eat: user, 2026-10-13)
HANG_ACTIONS = ""     # actions in which the chain does not swing: every frame it hangs straight down from the end of the haft, along the haft when the haft is upright, the ball
                      # beside it on the outer side (salute, eat: "static, the chain hangs along the haft"; the free chain whirled by the head)
ACTION_SET = ""       # per-action settings of the simulation: "26:STIFF=40,DAMP=2;9:DAMP=3" (STIFF, DAMP, FRAME_TIME, ALIGN_FWD, GRIP_TWIST)
ALIGN_FWD = 0.0       # ALIGN_ACTIONS / UP_ACTIONS: the forearm's line (the upright) tipped towards the front of the body by this (0 = none; 1 = half way at right angles).
                      # Eat (34): upright from the hand at the hip the haft went up through the side of the torso in frame 0 (user, 2026-10-13)
GRIP_TWIST = 0.0      # deg: the haft turned about the hand's axis through the grip in the actions carried by the hand. Walk (0, 1: ACTION_SET "1:GRIP_TWIST=20"): the original
                      # haft points out to the side, ours pointed forward and in, so seen from behind the ball hung in front of the belly, hidden; in every action it made the
                      # attacks worse (slash ball +4.9 px), so per action only
HAND_SMOOTH = 0       # passes of smoothing of the hand's turn over the frames of an action (about the grip; loops wrap): the turn of our wrist is fitted to silhouettes and
                      # shakes in some actions (mounted walk: the end of the haft jumped 0.3-0.5 m a frame); the haft is drawn with the smoothed turn too
RIGID = ""            # actions (numbers, "9,23") in which the flail is held gathered: the chain hangs settled in the first pose and then moves rigidly with the hand
                      # (the original draws the ball by the haft in riding, salute, eat, spells; a free chain there whirled); "all" = every action
PREROLL = 1.5         # s hanging in the first pose before a one-shot action
CYCLES = 3
STEP = 3
LOOP = {0, 1, 2, 3, 4, 5, 6, 7, 8, 15, 23, 24, 25}
BONE = "weapon1h.R"    # the weapon line the haft was laid on (uo_place_weapon.py, weapon_motion.json)
HOLD = "weapon1h.R"    # the bone the haft is bound to (and carried by): "hand.R" rebinds it rigidly to the hand. On weapon1h.R the far end of a long haft jumped 0.4-0.8 m
                       # between frames in some actions (mounted walk, eat): that bone is fitted per frame to short original weapons, its small turns are big at 0.5 m
CAPSULES = ("pelvis", "spine", "chest", "neck", "head", "thigh.L", "shin.L", "thigh.R", "shin.R", "upper_arm.L", "forearm.L")


GRIP = []


def rest_axis(rig):
    """butt point and direction of the weapon line (armature space), as uo_place_weapon.py laid the weapon"""
    wm = json.loads(bpy.data.texts["weapon_motion.json"].as_string())[BONE]
    H = np.array(rig.data.bones[wm["parent"]].matrix_local)
    piv = (H @ np.append(wm["pivot"], 1))[:3]; d = H[:3, :3] @ np.array(wm["dir"]); d /= np.linalg.norm(d)
    return piv, d


def prepare(ob, rig):
    Mo = np.linalg.inv(np.array(rig.matrix_world)) @ np.array(ob.matrix_world)         # object -> armature
    co = np.array([v.co for v in ob.data.vertices]); V = co @ Mo[:3, :3].T + Mo[:3, 3]
    piv, d = rest_axis(rig); GRIP[:] = [piv]
    s0 = (V - piv) @ d; butt = piv + d * s0.min(); s = (V - butt) @ d
    radial = np.linalg.norm((V - butt) - np.outer(s, d), axis=1)
    L = s.max(); nb = 60; edges = np.linspace(0, L, nb + 1); k = np.clip((s / L * nb).astype(int), 0, nb - 1)
    cnt = np.bincount(k, minlength=nb); rr = np.array([np.percentile(radial[k == i], 95) if (k == i).any() else 0 for i in range(nb)])
    if BALL_START > 0:
        sb = BALL_START
    else:                                                                    # the ball: the wide cross-sections in the far half (spike tips at the very end are narrow)
        wide = np.nonzero((rr > BALL_R) & (np.arange(nb) >= nb // 2))[0]
        sb = edges[wide.min()] if len(wide) else L
    if HAFT_END > 0:
        sh = HAFT_END
    else:                                                                    # the haft: thin and plain (few vertices); the chain: thin with many (links)
        thin = np.nonzero(rr[:int(sb / L * nb)] <= BALL_R)[0]
        dens = cnt[thin]; lo = np.median(dens[:max(3, len(dens) // 6)]); hi = np.median(dens)
        cut = (lo * hi) ** 0.5
        i = 0
        while i < len(thin) - 2 and cnt[thin[i]] > cut:                    # past a pommel / knob at the butt
            i += 1
        while i < len(thin) - 2 and not (cnt[thin[i]] > cut and cnt[thin[i + 1]] > cut):
            i += 1
        sh = edges[thin[i]]
    part = np.where(s >= sb, 2, np.where(s >= sh, 1, 0))
    ball = V[part == 2]; tip = butt + d * sb
    if HAFT_SCALE != 1.0:                                                    # longer / shorter haft from the butt: the chain and the ball move on
        ext = sh * (HAFT_SCALE - 1); m0 = part == 0
        V[m0] += np.outer(s[m0] * (HAFT_SCALE - 1), d); V[~m0] += d * ext; sh += ext; sb += ext; tip = butt + d * sb
        s = (V - butt) @ d
    if CHAIN_SCALE != 1.0:                                                   # longer / shorter chain: the chain stretched, the ball moved on
        m = part >= 1; ext = (sb - sh) * (CHAIN_SCALE - 1)
        sc = np.clip((s - sh) / max(sb - sh, 1e-6), 0, 1)
        V[m] += np.outer(np.where(part[m] == 2, ext, sc[m] * ext), d); sb += ext; tip = butt + d * sb
    if BALL_SCALE != 1.0:
        m = part == 2; V[m] = tip + (V[m] - tip) * BALL_SCALE
    s = (V - butt) @ d
    bc = V[part == 2].mean(0) if (part == 2).any() else tip
    nodes = [butt + d * (sh + (sb - sh) * j / SEGMENTS) for j in range(SEGMENTS + 1)] + [bc]
    Mi = np.linalg.inv(Mo)
    ob.data.vertices.foreach_set("co", (V @ Mi[:3, :3].T + Mi[:3, 3]).astype(np.float32).ravel())
    ob.data.update()
    for name, val, typ in (("uo_flail_s", s, "FLOAT"), ("uo_flail_part", part, "INT")):
        a = ob.data.attributes.get(name) or ob.data.attributes.new(name, typ, "POINT")
        a.data.foreach_set("value", val.astype(np.float32 if typ == "FLOAT" else np.int32))
    br = float(np.percentile(np.linalg.norm(V[part == 2] - bc, axis=1), 70)) if (part == 2).any() else 0.05
    ob["uo_flail"] = json.dumps(dict(nodes=np.round(nodes, 6).tolist(), haft_end=float(sh), ball_start=float(sb), ball_r=br, bone=HOLD, grip=np.round(piv, 6).tolist()))
    if HOLD != BONE:                                  # rebind rigidly to HOLD
        for gname in [g.name for g in ob.vertex_groups]:
            ob.vertex_groups.remove(ob.vertex_groups[gname])
        ob.vertex_groups.new(name=HOLD).add(list(range(len(ob.data.vertices))), 1.0, "REPLACE")
    ob["uo_no_body_gap"] = 1                                                # rigid pieces: the renderer must not bend them round the limbs
    print("uo_flail: %s: haft 0-%.3f m, chain %.3f-%.3f m (%d pieces), ball %.3f-%.3f m (radius %.3f m, x%.2f), %d / %d / %d vertices"
          % (ob.name, sh, sh, sb, SEGMENTS, sb, s.max(), br, BALL_SCALE, (part == 0).sum(), (part == 1).sum(), (part == 2).sum()))
    return np.array(nodes), br


def capsules(rig, body):
    """rest capsules (armature space): bone head / tail and the median distance of the skin the bone dominates"""
    me = body.data; Mb = np.linalg.inv(np.array(rig.matrix_world)) @ np.array(body.matrix_world)
    V = np.array([v.co for v in me.vertices]) @ Mb[:3, :3].T + Mb[:3, 3]
    gn = {g.index: g.name for g in body.vertex_groups}
    dom = [gn[max(v.groups, key=lambda g: g.weight).group] if len(v.groups) else "" for v in me.vertices]
    out = []
    for n in CAPSULES:
        b = rig.data.bones.get(n)
        if b is None:
            continue
        h, t = np.array(b.head_local), np.array(b.tail_local)
        P = V[np.array([x == n for x in dom])]
        if not len(P):
            continue
        ab = t - h; u = np.clip(((P - h) @ ab) / (ab @ ab), 0, 1)
        r = float(np.percentile(np.linalg.norm(P - (h + u[:, None] * ab), axis=1), 60))
        out.append((n, h, t, r))
    return out


def seg_push(X, caps, mats, rad):
    """points X out of the posed capsules (each from the one it is deepest in)"""
    for n, h, t, r in caps:
        M = mats[n]; A = M[:3, :3] @ h + M[:3, 3]; B = M[:3, :3] @ t + M[:3, 3]
        ab = B - A; u = np.clip(((X - A) @ ab) / max(ab @ ab, 1e-9), 0, 1); C = A + u[:, None] * ab
        dv = X - C; dist = np.linalg.norm(dv, axis=1); pen = r + rad - dist
        m = pen > 0
        if m.any():
            X[m] += dv[m] / np.maximum(dist[m], 1e-9)[:, None] * pen[m, None]
    return X


def pose_mats(rig, names):
    """skinning matrices (armature space) of the bones in the current frame"""
    out = {}
    for n in names:
        pb = rig.pose.bones[n]; out[n] = np.array(pb.matrix) @ np.linalg.inv(np.array(pb.bone.matrix_local))
    return out


def interp(M0, M1, t):
    q0 = Matrix(M0.tolist()).to_quaternion(); q1 = Matrix(M1.tolist()).to_quaternion()
    if q0.dot(q1) < 0:
        q1 = -q1
    R = np.array(q0.slerp(q1, t).to_matrix())
    out = np.eye(4); out[:3, :3] = R; out[:3, 3] = (1 - t) * M0[:3, 3] + t * M1[:3, 3]
    return out


def simulate(rig, act, nodes, br, caps):
    """the nodes in every UO frame of the action (armature space); the hand between two UO frames is interpolated (slerp), the body is that of the nearer frame"""
    sc = bpy.context.scene
    a = int(act["uo_action"]); nf = int(act["uo_frames"])
    rig.animation_data.action = act; rig["uo_direction"] = 0
    loc = dict(STIFF=STIFF, DAMP=DAMP, FRAME_TIME=FRAME_TIME, ALIGN_FWD=ALIGN_FWD, GRIP_TWIST=GRIP_TWIST)
    for part_ in ACTION_SET.split(";"):
        if ":" in part_ and int(part_.split(":")[0]) == a:
            for kv in part_.split(":")[1].split(","):
                k_, v_ = kv.split("="); loc[k_.strip()] = float(v_)
    names = list(dict.fromkeys([HOLD, BONE, "forearm.R", "spine"] + [c[0] for c in caps]))
    keys = []
    nums = lambda s: {int(x) for x in s.split(",") if x.strip()}
    use_w = HAND_SMOOTH > 0 and a in nums(WEAPON_BONE_ACTIONS)
    mode = "align" if a in nums(ALIGN_ACTIONS) else "up" if a in nums(UP_ACTIONS) else "weapon" if use_w else "hand"
    hd = (nodes[1] - nodes[0]) / np.linalg.norm(nodes[1] - nodes[0])          # the haft's direction at rest (grip -> chain)
    fy0 = np.array(rig.data.bones["forearm.R"].matrix_local)[:3, 1]
    ha = np.array(rig.data.bones[HOLD].matrix_local)[:3, 1]; ha /= np.linalg.norm(ha)
    Tw = np.eye(4)
    if loc["GRIP_TWIST"]:                                                    # the haft turned about the hand's axis through the grip (rest space)
        Rt = np.array(Matrix.Rotation(np.radians(loc["GRIP_TWIST"]), 3, Vector(ha.tolist())))
        Tw[:3, :3] = Rt; Tw[:3, 3] = GRIP[0] - Rt @ GRIP[0]
    for i in range(nf):
        sc.frame_set(1 + i * STEP); k = pose_mats(rig, names)
        Mh = k[HOLD]; g_ = Mh[:3, :3] @ GRIP[0] + Mh[:3, 3]                 # where the hand holds the grip
        if mode == "weapon":                                                 # the turn of weapon1h.R, the grip where the hand holds it (the bone also moves away from the hand:
            R = k[BONE][:3, :3]                                              # in the mounted 1H attack the haft left the hand)
        elif mode in ("align", "up"):
            dh = Mh[:3, :3] @ hd
            to = k["forearm.R"][:3, :3] @ fy0 if mode == "align" else np.array([0.0, 0.0, 1.0])
            if loc["ALIGN_FWD"]:                                             # tipped towards the front of the body (where the enemy is; eat: off the torso)
                fw = -(k["spine"][:3, :3] @ np.array([0.0, 1.0, 0.0])); fw[2] = 0; fw /= max(np.linalg.norm(fw), 1e-9)
                to = to / np.linalg.norm(to) + loc["ALIGN_FWD"] * fw
            R = np.array(Vector(dh.tolist()).rotation_difference(Vector((to / np.linalg.norm(to)).tolist())).to_matrix()) @ Mh[:3, :3]
        else:
            R = (Mh @ Tw)[:3, :3]
        M = np.eye(4); M[:3, :3] = R; M[:3, 3] = g_ - R @ GRIP[0]; k[HOLD] = M
        keys.append(k)
    loop = a in LOOP and nf > 1
    if HAND_SMOOTH > 0 and nf > 2:                                          # the hand's turn smoothed over the frames, about the grip
        grip = GRIP[0]
        Q = [Matrix(k[HOLD][:3, :3].tolist()).to_quaternion() for k in keys]
        for j in range(1, nf):
            if Q[j].dot(Q[j - 1]) < 0:
                Q[j] = -Q[j]
        Qv = np.array([[q.w, q.x, q.y, q.z] for q in Q])
        for _ in range(HAND_SMOOTH):
            prv = np.roll(Qv, 1, 0); nxt = np.roll(Qv, -1, 0)
            if not loop:
                prv[0] = Qv[0]; nxt[-1] = Qv[-1]
            prv *= np.sign((prv * Qv).sum(1))[:, None]; nxt *= np.sign((nxt * Qv).sum(1))[:, None]
            Qv = 0.25 * prv + 0.5 * Qv + 0.25 * nxt; Qv /= np.linalg.norm(Qv, axis=1)[:, None]
        for j in range(nf):
            M = keys[j][HOLD]; R = np.array(Quaternion(Qv[j]).to_matrix()); g = M[:3, :3] @ grip + M[:3, 3]
            Ms = np.eye(4); Ms[:3, :3] = R; Ms[:3, 3] = g - R @ grip; keys[j] = dict(keys[j]); keys[j][HOLD] = Ms
    n = len(nodes)
    w = np.ones(n); w[0] = 0.0; w[-1] = 1.0 / MASS                          # inverse masses: node 0 is carried by the haft
    rest = np.linalg.norm(np.diff(nodes, axis=0), axis=1)
    rad = np.full(n, 0.01); rad[-1] = BALL_GAP or br * 0.6
    sub = STEP * SUB; dt = loc["FRAME_TIME"] / sub; g = np.array([0, 0, -GRAVITY]); keep = np.exp(-loc["DAMP"] * dt)
    kb = 1 - np.exp(-loc["STIFF"] * dt)

    def step(M, X, Xp, mats):
        Xn = X + (X - Xp) * keep + g * dt * dt * (w > 0)[:, None]
        Xn[0] = M[:3, :3] @ nodes[0] + M[:3, 3]
        hit = np.zeros_like(Xn)
        for _ in range(ITER):
            for k in range(n - 1):
                dv = Xn[k + 1] - Xn[k]; dist = np.linalg.norm(dv); ws = w[k] + w[k + 1]
                if dist < 1e-9 or ws == 0:
                    continue
                corr = (dist - rest[k]) / dist / ws * dv
                Xn[k] += w[k] * corr; Xn[k + 1] -= w[k + 1] * corr
            before = Xn[1:].copy(); Xn[1:] = seg_push(Xn[1:], caps, mats, rad[1:] + GAP); hit[1:] += Xn[1:] - before
        if kb > 0:                                                           # bending: each piece pulled towards the line of the one before (the first: the haft)
            prev = M[:3, :3] @ hd
            for k in range(n - 1):
                tgt = Xn[k] + prev * rest[k]
                Xn[k + 1] += kb * (tgt - Xn[k + 1])
                dv = Xn[k + 1] - Xn[k]; Xn[k + 1] = Xn[k] + dv / max(np.linalg.norm(dv), 1e-9) * rest[k]
                prev = (Xn[k + 1] - Xn[k]) / rest[k]
        if INELASTIC:                                                        # a push out of the body takes the speed into the body away instead of adding a bounce
            return Xn, X + hit
        return Xn, X

    M0 = keys[0][HOLD]; X = (M0[:3, :3] @ nodes.T).T + M0[:3, 3]; Xp = X.copy()
    if not loop:                                                             # settle: hanging still in the first pose
        for _ in range(int(PREROLL / dt)):
            X, Xp = step(M0, X, Xp, keys[0])
    out = {}
    if a in nums(HANG_ACTIONS):                                              # static: the chain hangs straight down from the end of the haft, the ball beside the haft outside
        sp0 = np.array(rig.data.bones["spine"].head_local)
        for i in range(nf):
            M = keys[i][HOLD]; X = np.zeros_like(nodes); X[0] = M[:3, :3] @ nodes[0] + M[:3, 3]
            sp = keys[i]["spine"][:3, :3] @ sp0 + keys[i]["spine"][:3, 3]
            side = (M[:3, :3] @ GRIP[0] + M[:3, 3]) - sp; side[2] = 0; side /= max(np.linalg.norm(side), 1e-9)
            for j in range(n - 1):
                dv = side + np.array([0, 0, -0.35]) if j == 0 else np.array([0, 0, -1.0])
                X[j + 1] = X[j] + dv / np.linalg.norm(dv) * rest[j]
            out["%d_%d" % (a, i)] = X; out["%d_%d_M" % (a, i)] = M
        return out
    rig_set = set(range(35)) if RIGID == "all" else {int(x) for x in RIGID.split(",") if x.strip()}
    if a in rig_set:                                                         # gathered: settled in the first pose, then rigid on the hand
        for _ in range(int(PREROLL / dt)):
            X, Xp = step(M0, X, Xp, keys[0])
        L = np.linalg.inv(M0); Xl = (L[:3, :3] @ X.T).T + L[:3, 3]
        for i in range(nf):
            M = keys[i][HOLD]; out["%d_%d" % (a, i)] = (M[:3, :3] @ Xl.T).T + M[:3, 3]
            if HAND_SMOOTH > 0:
                out["%d_%d_M" % (a, i)] = M
        return out
    cycles = CYCLES if loop else 1
    for c in range(cycles):
        for i in range(nf):
            if c == cycles - 1:
                out["%d_%d" % (a, i)] = X.copy()
                if HAND_SMOOTH > 0:
                    out["%d_%d_M" % (a, i)] = keys[i][HOLD]
            if i == nf - 1 and not loop:
                break
            j = (i + 1) % nf
            for s_ in range(sub):
                M = interp(keys[i][HOLD], keys[j][HOLD], s_ / sub)
                X, Xp = step(M, X, Xp, keys[i] if s_ < sub / 2 else keys[j])
    return out


def main(src, dst, npz, only, sets):
    g = globals()
    for k, v in sets:
        g[k] = type(g[k])(v) if not isinstance(g[k], (tuple, set)) else g[k]
    bpy.ops.wm.open_mainfile(filepath=src)
    rig = bpy.data.objects["UO_Rig"]; body = bpy.data.objects["UO_Body"]
    rig.data.pose_position = "REST"; bpy.context.view_layer.update()
    ob = next(o for o in bpy.data.collections["Clothing"].all_objects if o.type == "MESH" and not o.hide_render)
    if "uo_flail" in ob and dst is None:
        prm = json.loads(ob["uo_flail"]); nodes = np.array(prm["nodes"]); br = prm["ball_r"]; GRIP[:] = [np.array(prm["grip"])]
    else:
        nodes, br = prepare(ob, rig)
    caps = capsules(rig, body)
    rig.data.pose_position = "POSE"
    acts = [x for x in bpy.data.actions if x.get("uo_action") is not None]
    if only and only != ["all"]:
        acts = [x for x in acts if x.name in only]
    table = {"rest": nodes}
    for act in acts:
        table.update(simulate(rig, act, nodes, br, caps))
    rig.data.pose_position = "REST"
    if dst:
        bpy.ops.wm.save_as_mainfile(filepath=dst)
        print("uo_flail: saved", dst)
    np.savez_compressed(npz, **table)
    print("uo_flail: wrote %s (%d frames, %d actions)" % (npz, len(table) - 1, len(acts)))


if __name__ == "__main__":
    args = sys.argv[1:]; sets = []; pos = []; npz = None; only = None; i = 0
    while i < len(args):
        if args[i] == "--set":
            sets.append(tuple(args[i + 1].split("=", 1))); i += 2
        elif args[i] == "--out":
            npz = args[i + 1]; i += 2
        elif args[i] == "--actions":
            only = args[i + 1].split(","); i += 2
        elif args[i] == "--sim-only":
            pos.append(None); i += 1
        else:
            pos.append(args[i]); i += 1
    src = pos[0]; dst = pos[1] if len(pos) > 1 else src
    main(src, dst, npz or os.path.join(os.path.dirname(os.path.abspath(dst or src)), "flail_sim.npz"), only, sets)
    sys.stdout.flush()
