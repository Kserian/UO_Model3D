# A harp (or any one-hand instrument held by a thin pillar) for the right hand, and for both hands when the body stands still.
# Run inside the base .blend (uo_make_item.py does it for a recipe with "harp": {...}) after uo_import_item.py (KIND = "") and uo_materials.py; the harp is the selected / only mesh
# of the collection Clothing, modelled upright (pipeline/make_harp_model.py: Z up along the pillar, the pillar axis x = y = 0, the soundbox leans to +X, Y is the depth).
#
# One hand (every action not in TWO_HAND): the pillar lies on the grip line of weapon1h.R (the calibrated motion of the right hand's 1H weapons), at GRIP of its height,
#   the harp turned about the pillar by ROLL degrees from the roll of a sword: it moves like a 1H weapon.
# Both hands (TWO_HAND: stand, fidgets, idles, eat ... the actions where the body does not travel): the right hand still holds the pillar (the pivot of weapon1h.R on the
#   pillar), the harp is turned about that grip (and slid a little along the pillar) so that the LEFT hand touches it: the pivot of the left fist is a few mm to 4 cm from the
#   surface of the harp, never inside the wood, the harp does not go through the body (the hands excepted), stays near upright and near the one-hand pose (tilt only as much
#   as the hands need). Per frame, then continuous in time (the pose of a frame starts from the previous one). The arms are the ORIGINAL animation's: only the harp moves.
# The harp rides on a new root bone `harp` (armature space = the pose of the harp, keyed in all 35 actions); the mesh is rigid on it (a part of the item .blend, the model is untouched).
import bpy, json, math, sys, os
import numpy as np
from mathutils import Matrix, Vector, Quaternion

HEIGHT = 0.54         # m: total height of the finished harp (the model of make_harp_model.py is 0.54 m: scaled uniformly if different); a hand harp, not taller than the torso
GRIP = 0.5            # the right hand holds the pillar at this fraction of its height (0.5 = the middle)
ROLL = 45.0           # deg: turn of the harp about the pillar in the one-hand actions, from the roll of a sword (+X of the model -> the flat side of a sword)
TWO_HAND = [4, 5, 6, 25, 33, 34]       # actions in which both hands hold the harp (UO numbers)
TOUCH = (0.0, 0.055)  # m: distance of the left fist's pivot from the harp's surface (outside the wood): from .. to .. (the fist is ~4 cm thick)
TILT_MAX = 0.62       # rad: the pillar's angle from vertical that costs 1 (0.62 = 35 deg)
BODY_CLEAR = 0.012    # m: harp points closer than this to the body (not the hands) count as inside it
SEED = 11
REPORT = True

rig = bpy.data.objects["UO_Rig"]; body = bpy.data.objects["UO_Body"]
sc = bpy.context.scene
STEP = 3


def log(*a):
    print("uo_harp:", *a)


def mat4(m):
    return np.array(m, float)


def rot_about(axis, ang):
    from scipy.spatial.transform import Rotation as Ro
    R = np.eye(4); R[:3, :3] = Ro.from_rotvec(np.array(axis, float) / np.linalg.norm(axis) * ang).as_matrix(); return R


def trans(v):
    T = np.eye(4); T[:3, 3] = v; return T


def main():
    from scipy.spatial import cKDTree
    from scipy.spatial.transform import Rotation as Ro
    rig.data.pose_position = "REST"; bpy.context.view_layer.update()
    assert np.allclose(mat4(rig.matrix_world), np.eye(4), atol=1e-6), "the rig object is moved: direction 0 expected"
    WM = json.loads(bpy.data.texts["weapon_motion.json"].as_string())["weapon1h.R"]
    obs = [o for o in bpy.data.collections["Clothing"].all_objects if o.type == "MESH"]
    assert len(obs) == 1, "one harp mesh expected, got %d" % len(obs)
    ob = obs[0]
    # ---- the harp in model coordinates -> metres, pillar scaled to HEIGHT
    V = np.array([(ob.matrix_world @ v.co)[:] for v in ob.data.vertices])
    zmin, zmax = V[:, 2].min(), V[:, 2].max()
    sc_k = HEIGHT / (zmax - zmin) * 1.0
    ctr = np.array([0.0, 0.0, zmin])
    S0 = np.eye(4); S0[:3, :3] *= sc_k; S0[:3, 3] = -sc_k * ctr                     # floor under the pillar at the origin, pillar HEIGHT tall
    grip_c = np.array([0.0, 0.0, GRIP * HEIGHT])                                      # grip point on the pillar axis (canonical, scaled)
    # ---- one-hand placement C0: pillar on the grip line of weapon1h.R at rest
    hb = rig.data.bones[WM["parent"]]
    H = mat4(rig.matrix_world @ hb.matrix_local)
    piv = (H @ np.append(WM["pivot"], 1.0))[:3]; d = H[:3, :3] @ np.array(WM["dir"]); d /= np.linalg.norm(d)
    RO = WM["roll"]; ref = str(RO["ref"])
    e1 = np.array(RO["e1"]); dloc = np.array(WM["dir"]) / np.linalg.norm(WM["dir"])
    Rd = Ro.from_rotvec(dloc * RO["offsets"].get(ref, 0.0)).as_matrix()
    ru = H[:3, :3] @ (Rd @ e1); ru -= (ru @ d) * d; ru /= np.linalg.norm(ru)
    z = np.array([0.0, 0.0, 1.0])
    ax = np.cross(z, d); s_, c_ = np.linalg.norm(ax), z @ d
    R1 = np.eye(3) if s_ < 1e-9 else Ro.from_rotvec(ax / s_ * math.atan2(s_, c_)).as_matrix()
    x1 = R1 @ np.array([1.0, 0, 0])
    ang = math.atan2(d @ np.cross(x1, ru), x1 @ ru) + math.radians(ROLL)
    R2 = Ro.from_rotvec(d * ang).as_matrix() @ R1
    C1 = np.eye(4); C1[:3, :3] = R2
    C1[:3, 3] = piv - R2 @ grip_c                                                     # grip point of the pillar on the pivot of the hand
    C0 = C1 @ S0                                                                      # model coordinates -> rest world
    assert np.allclose(mat4(ob.matrix_world), np.eye(4), atol=1e-6), "the imported harp should be baked in world space"
    ob.data.transform(Matrix(C0.tolist()))
    bpy.context.view_layer.update()
    V = np.array([v.co[:] for v in ob.data.vertices])
    log("rest placement: pillar %.2f m, grip %.0f%% of it at the pivot of weapon1h.R (%.2f %.2f %.2f), roll %+.0f deg; harp spans x %.2f..%.2f y %.2f..%.2f z %.2f..%.2f" % (
        HEIGHT, 100 * GRIP, *piv, ROLL, V[:, 0].min(), V[:, 0].max(), V[:, 1].min(), V[:, 1].max(), V[:, 2].min(), V[:, 2].max()))
    # ---- surface samples (rest world) with normals, for the contact and body tests
    import bmesh
    bm = bmesh.new(); bm.from_mesh(ob.data); bmesh.ops.triangulate(bm, faces=bm.faces)
    tri = np.array([[v.co[:] for v in f.verts] for f in bm.faces]); nrm = np.array([f.normal[:] for f in bm.faces]); bm.free()
    area = 0.5 * np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)
    rng = np.random.default_rng(SEED)
    NS = 3000
    pick = rng.choice(len(tri), NS, p=area / area.sum())
    r1, r2 = rng.random(NS), rng.random(NS); sw = r1 + r2 > 1; r1[sw], r2[sw] = 1 - r1[sw], 1 - r2[sw]
    P0 = tri[pick, 0] + r1[:, None] * (tri[pick, 1] - tri[pick, 0]) + r2[:, None] * (tri[pick, 2] - tri[pick, 0]); N0 = nrm[pick]
    # ---- the poses of every frame: hands, weapon bone, posed body
    names = [g.name for g in body.vertex_groups]
    W_ = np.zeros((len(body.data.vertices), len(names)), np.float32)
    for v in body.data.vertices:
        for g in v.groups:
            W_[v.index, g.group] = g.weight
    dom = [names[i] for i in W_.argmax(1)]
    keep_body = np.array([not (n.startswith("hand") or n.startswith("finger")) for n in dom])
    acts = {int(a["uo_action"]): a for a in bpy.data.actions if "uo_action" in a}
    rig.data.pose_position = "POSE"; rig["uo_direction"] = 0
    pR = np.array(WM["pivot"]); pL = np.array([-pR[0], pR[1], pR[2]])
    wb = rig.data.bones["weapon1h.R"]

    def delta(bn):
        b = rig.data.bones[bn]; return mat4(rig.pose.bones[bn].matrix) @ np.linalg.inv(mat4(b.matrix_local))

    def body_pts(dg):
        eb = body.evaluated_get(dg); me = eb.to_mesh()
        co = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", co); eb.to_mesh_clear()
        return co.reshape(-1, 3)[keep_body].astype(float)

    def hand_pt(bn, p):
        b = rig.data.bones[bn]
        return (delta(bn) @ (mat4(b.matrix_local) @ np.append(p, 1.0)))[:3]

    keys = {}                                                                         # (action, frame) -> 4x4 world delta of the harp (armature space)
    prev = None; report = []
    for a in sorted(acts):
        act = acts[a]; rig.animation_data.action = act; n = int(act["uo_frames"]); prev = None
        for i in range(n):
            sc.frame_set(1 + STEP * i); bpy.context.view_layer.update()
            D = delta("weapon1h.R")
            if a not in TWO_HAND:
                keys[(a, i)] = D; continue
            dg = bpy.context.evaluated_depsgraph_get()
            Lp = hand_pt("hand.L", pL); Rp = hand_pt("hand.R", pR); BP = body_pts(dg)
            X, info = solve_frame(D, P0, N0, piv, R2, Lp, BP, prev)
            prev = info["w"]
            keys[(a, i)] = X
            report.append((a, i, info))
    # ---- report
    if REPORT:
        for a in sorted({r[0] for r in report}):
            rows = [r[2] for r in report if r[0] == a]
            log("action %2d %-22s %d frames: touch %.1f..%.1f cm (signed, outside +), tilt %.0f..%.0f deg, body points inside %d, off-pose %.0f deg" % (
                a, acts[a].name[3:], len(rows), 100 * min(r["touch"] for r in rows), 100 * max(r["touch"] for r in rows), min(r["tilt"] for r in rows), max(r["tilt"] for r in rows),
                max(r["pen"] for r in rows), max(r["dev"] for r in rows)))
    # ---- the bone and the keys
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    if "harp" not in rig.data.edit_bones:
        eb = rig.data.edit_bones.new("harp"); eb.parent = None; eb.head = (0, 0, 0); eb.tail = (0, 0.1, 0); eb.roll = 0.0
    bpy.ops.object.mode_set(mode="OBJECT")
    bone = rig.data.bones["harp"]; bone.inherit_scale = "NONE"; bone.use_deform = True
    assert np.allclose(mat4(bone.matrix_local), np.eye(4), atol=1e-6), "bone harp: rest matrix not identity"
    pb = rig.pose.bones["harp"]; pb.rotation_mode = "QUATERNION"
    keep_action = rig.animation_data.action
    for a in sorted(acts):
        act = acts[a]; rig.animation_data.action = act; lastq = None
        for i in range(int(act["uo_frames"])):
            M = Matrix(keys[(a, i)].tolist()); loc, q, sca = M.decompose()
            if lastq is not None and q.dot(lastq) < 0:
                q.negate()
            lastq = q
            pb.location = loc; pb.rotation_quaternion = q; pb.scale = (1, 1, 1)
            f = 1 + STEP * i
            pb.keyframe_insert("location", frame=f, group="harp"); pb.keyframe_insert("rotation_quaternion", frame=f, group="harp"); pb.keyframe_insert("scale", frame=f, group="harp")
    rig.animation_data.action = keep_action
    # ---- bind: rigid on the bone harp
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    ob.select_set(True); bpy.context.view_layer.objects.active = ob
    body_bones = {g.name for g in body.vertex_groups}
    for g in [g for g in ob.vertex_groups if g.name in body_bones or g.name == "harp"]:
        ob.vertex_groups.remove(g)
    g = ob.vertex_groups.new(name="harp"); g.add(list(range(len(ob.data.vertices))), 1.0, "REPLACE")
    rig.data.pose_position = "REST"; bpy.context.view_layer.update()
    mw = ob.matrix_world.copy(); ob.parent = rig; ob.matrix_parent_inverse = rig.matrix_world.inverted(); ob.matrix_world = mw
    arm = next((m for m in ob.modifiers if m.type == "ARMATURE"), None) or ob.modifiers.new("Armature", "ARMATURE")
    arm.object = rig; arm.use_vertex_groups = True; arm.use_bone_envelopes = False
    ob["uo_no_body_gap"] = 1                                                          # rigid: the renderer never bends it around the limbs
    ob["uo_harp"] = json.dumps(dict(height=HEIGHT, grip=GRIP, roll=ROLL, two_hand=TWO_HAND))
    log("%s -> rigid on the bone harp, keyed in %d actions (%d frames)" % (ob.name, len(acts), len(keys)))


def solve_frame(D, P0, N0, piv, R2, Lp, BP, prev_w):
    """pose of the harp (4x4, armature space) for one frame: turned about the grip so that the left fist touches it; returns (X, info)"""
    from scipy.spatial import cKDTree
    from scipy.spatial.transform import Rotation as Ro
    from scipy.optimize import minimize
    B = D                                                                             # one-hand pose (maps the rest-placed harp to its place in this frame)
    P1 = (B[:3, :3] @ P0.T).T + B[:3, 3]; N1 = (B[:3, :3] @ N0.T).T
    g = B[:3, :3] @ piv + B[:3, 3]                                                    # the grip point (the pivot of the hand) in this frame
    u0 = B[:3, :3] @ (R2 @ np.array([0, 0, 1.0])); u0 /= np.linalg.norm(u0)            # the pillar axis in the one-hand pose
    far = np.linalg.norm(P1 - g, axis=1) > 0.12                                       # the left hand goes to a place other than the right one
    Pf, Nf = P1[far], N1[far]
    tree = cKDTree(BP)
    sub = np.arange(0, len(P1), 3)

    def apply(p, P, Nn=None):
        R = Ro.from_rotvec(p[:3]).as_matrix()
        Q = (P - g) @ R.T + g + (R @ u0) * p[3]
        return Q if Nn is None else (Q, Nn @ R.T)

    def touch_of(p):
        Q, Nq = apply(p, Pf, Nf)
        dd = np.linalg.norm(Q - Lp, axis=1); k = int(dd.argmin())
        sd = float((Lp - Q[k]) @ Nq[k])                                               # >0: the pivot is outside the wood
        return (dd[k] if sd >= 0 else -dd[k]), Q[k]

    def cost(p, with_body=True, prev=prev_w):
        t, _ = touch_of(p)
        lo, hi = TOUCH
        Jt = (max(0.0, lo - t) / 0.005) ** 2 + (max(0.0, t - hi) / 0.01) ** 2
        u = Ro.from_rotvec(p[:3]).as_matrix() @ u0
        tilt = math.acos(max(-1, min(1, u[2])))
        Ju = (tilt / TILT_MAX) ** 2 + 10.0 * (max(0.0, tilt - 1.25) / 0.1) ** 2           # beyond ~70 deg the harp would hang upside down
        Jw = 0.25 * (np.linalg.norm(p[:3]) / 1.0) ** 2 + (p[3] / 0.20) ** 2 * 0.2
        Jp = 0.0
        if with_body:
            Q = apply(p, P1[sub]); dd, _ = tree.query(Q); Jp = 0.6 * float((dd < BODY_CLEAR).sum()) / 10.0
        Jt_ = 0.0 if prev is None else (np.linalg.norm(p[:3] - prev[:3]) / 0.15) ** 2 + ((p[3] - prev[3]) / 0.05) ** 2
        return Jt + Ju + Jw + Jp + Jt_

    # coarse search: random rotations + zero, cheap terms first
    rng = np.random.default_rng(SEED)
    if prev_w is not None:                                                            # later frames of an action: track the previous solution (the harp does not jump about)
        cand = np.vstack([prev_w[None, :], prev_w[None, :] + rng.normal(0, [0.1, 0.1, 0.1, 0.03], (30, 4))])
    else:
        cand = np.zeros((1, 4))
        rv = Ro.random(2500, random_state=SEED).as_rotvec()
        rv = rv * np.minimum(1.0, 2.6 / np.maximum(np.linalg.norm(rv, axis=1, keepdims=True), 1e-9))
        cand = np.vstack([cand, np.c_[rv, rng.uniform(-0.2, 0.2, len(rv))]])
    cheap = np.array([cost(c, with_body=False) for c in cand])
    best = cand[np.argsort(cheap)[:10]]
    sols = []
    for c in best:
        r = minimize(cost, c, method="Nelder-Mead", options=dict(xatol=2e-3, fatol=1e-3, maxiter=500, initial_simplex=np.vstack([c] + [c + np.eye(4)[k] * (0.08 if k < 3 else 0.03) for k in range(4)])))
        sols.append((r.fun, r.x))
    f_, p = min(sols, key=lambda s: s[0])
    if prev_w is not None and touch_of(p)[0] > TOUCH[1] + 0.02:                       # tracking lost the contact: search again from scratch (the temporal term still pulls towards the last pose)
        return solve_frame(D, P0, N0, piv, R2, Lp, BP, None)
    R = Ro.from_rotvec(p[:3]).as_matrix()
    X = np.eye(4); X[:3, :3] = R; X[:3, 3] = g - R @ g + (R @ u0) * p[3]
    X = X @ B                                                                         # first the one-hand pose, then the turn about the grip
    # the key is the delta from the rest-placed mesh: X maps mesh (rest world) -> posed world
    t, _ = touch_of(p)
    Q = apply(p, P1[sub]); dd, _ = tree.query(Q)
    u = R @ u0
    info = dict(w=p, touch=t, tilt=math.degrees(math.acos(max(-1, min(1, u[2])))), pen=int((dd < BODY_CLEAR).sum()), dev=math.degrees(np.linalg.norm(p[:3])), cost=f_)
    return X, info


main()
