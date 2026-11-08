# A harp (or any one-hand instrument held by a thin pillar) for the right hand, and for both hands when the body stands still.
# Run inside the base .blend (uo_make_item.py does it for a recipe with "harp": {...}) after uo_import_item.py (KIND = "") and uo_materials.py; the harp is the selected / only mesh
# of the collection Clothing, modelled upright (pipeline/harp_prepare_model.py makes it: Z up along the thin arm = the pillar, its axis x = y = 0, the sound box arm on the +X side, Y is the depth).
#
# One hand (every action not in TWO_HAND): the right hand holds the pillar (the thin arm) at GRIP of its height, from behind: the pillar upright at the back, the rest of the harp
#   (the sound box) pointing forward. The orientation is the chest's (it does not swing about with the arm like a sword), the grip point is the pivot of the right fist.
# Both hands (TWO_HAND: stand, fidgets, idles, eat ... the actions where the body does not travel): the right hand still holds the pillar (the pivot of weapon1h.R on the
#   pillar), the harp is turned about that grip (and slid a little along the pillar) so that the LEFT hand touches it: the pivot of the left fist is a few mm to 4 cm from the
#   surface of the harp, never inside the wood, the harp does not go through the body (the hands excepted), stays near upright and near the one-hand pose (tilt only as much
#   as the hands need). Per frame, then continuous in time (the pose of a frame starts from the previous one). The arms are the ORIGINAL animation's: only the harp moves.
# The harp rides on a new root bone `harp` (armature space = the pose of the harp, keyed in all 35 actions); the mesh is rigid on it (a part of the item .blend, the model is untouched).
import bpy, json, math, sys, os
import numpy as np
from mathutils import Matrix, Vector, Quaternion

HEIGHT = 0.68         # m: total height of the finished harp (the model is scaled uniformly to it); the left hand is 0.5-0.6 m from the right one in the standing poses, the harp has to reach it
WIDEN = 1.25          # the model is stretched along X (away from the pillar) by this factor before it is scaled to HEIGHT: a wider harp reaches the left hand without being taller than the torso
THICKEN = 0.019       # m: the shell is pushed out along its normals by this much after scaling (a 2 cm frame is 0.7 px at 36 px/m and vanishes)
GRIP = 0.5            # the right hand holds the pillar at this fraction of its height (0.5 = the middle)
YAW = 0.0             # deg: turn of the harp about the vertical in the one-hand actions (0 = the sound box points straight forward, the pillar is at the back)
TWO_HAND = [4, 5, 6, 25, 33, 34]       # actions in which both hands hold the harp (UO numbers)
STEADY = [0, 1, 2, 3, 23, 24]          # walking and running (on foot, mounted): the harp keeps ONE orientation (the mean of the chest's over the action: upright, sound box forward), only the grip follows the hand: no swaying
TOUCH = (0.0, 0.04)   # m: distance of the left fist's pivot from the harp's surface (outside the wood): from .. to .. (the fist is ~4 cm thick)
TILT_MAX = 0.62       # rad: the pillar's angle from vertical that costs 1 (0.62 = 35 deg)
CLEAR_PARALLEL = 0.025  # m: in the PARALLEL poses the harp keeps this far from the body
BODY_CLEAR = 0.012    # m: harp points closer than this to the body (not the hands) count as inside it
LEAN_WALK = [0, 1]    # walk, walk armed (user): held NORMALLY by the pillar in the right fist (the usual hold: pillar upright, the rest forward), but leaned away from the legs, outward: WALK_LEAN deg about
                      # the forward axis (the top of the pillar goes out), and tipped towards the ground: WALK_PITCH deg (the far end of the harp goes down). More lean when the legs would touch it.
WALK_LEAN = 12.0
WALK_PITCH = 20.0
WALK_PEN = 8          # body points (of 750) that may be inside the harp in the walk; the lean grows (5 deg steps, up to 35) until that holds
YAW_OUT = {17: -12.0, 26: -12.0}   # area spell, mounted 1H attack (user: "wychylona na zewnatrz", an extension of the arm): the usual hold (pillar upright, the sound box forward) turned by a FEW degrees about the
                      # axis of the held side, the pillar (negative = the sound box swings outward, away from the body, towards the arm)
FLAT_DIE = [21, 22]   # both deaths (user): held in the hand, as far from the body as it goes, lying flat (plane horizontal), the sound box pointing away from the body
FIST_FREE = {33: 0.3, 34: 0.3}   # rad per action: in salute and eat (user: the harp was not in the hand) the pillar stays within this angle of the axis of the right fist (a fist round a rod holds it along its own axis)
FIST_DEFAULT = 0.9    # the other two-hand poses: only a loose limit (a stricter one turned the triangle edge-on in stand: it read as a bar)      # rad: in the two-hand poses the pillar may differ this much from the axis of the right fist (a fist round a rod holds it along its own axis); beyond that it costs
FRONT = [4, 25]       # two-hand poses in which the harp is IN FRONT of the body (its middle ahead of the chest), as in the ordinary stand (user: mounted stand like stand)
PARALLEL = [4, 25]      # stand, mounted stand (user: "rownolegle do brzucha", no tilt, no collisions): the harp's plane parallel to the belly (within ~10 deg), the pillar within ~8 deg of vertical, 2.5 cm clear of the body; the right hand may hold the pillar higher or lower
FRONT_PLANE = [4, 5, 6, 25, 33, 34]   # two-hand poses in which the triangle faces the front (its plane across the line of sight), not edge-on
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
    if WIDEN != 1.0:
        ob.data.transform(Matrix.Scale(WIDEN, 4, Vector((1, 0, 0))))                  # about the pillar axis x = 0
    ctr = np.array([0.0, 0.0, zmin])
    S0 = np.eye(4); S0[:3, :3] *= sc_k; S0[:3, 3] = -sc_k * ctr                     # floor under the pillar at the origin, pillar HEIGHT tall
    grip_c = np.array([0.0, 0.0, GRIP * HEIGHT])                                      # grip point on the pillar axis (canonical, scaled)
    # ---- one-hand placement C0: the pillar upright on the pivot of the right hand, the sound box pointing FORWARD (the body faces -Y at rest)
    hb = rig.data.bones[WM["parent"]]
    H = mat4(rig.matrix_world @ hb.matrix_local)
    piv = (H @ np.append(WM["pivot"], 1.0))[:3]
    z = np.array([0.0, 0.0, 1.0]); fwd = np.array([0.0, -1.0, 0.0])
    R2 = np.array([fwd, np.cross(z, fwd), z]).T                                      # columns: model X (sound box) -> forward, model Y -> the body's left, model Z (pillar) -> up
    R2 = Ro.from_rotvec(z * math.radians(YAW)).as_matrix() @ R2
    C1 = np.eye(4); C1[:3, :3] = R2
    C1[:3, 3] = piv - R2 @ grip_c                                                     # grip point of the pillar on the pivot of the hand
    C0 = C1 @ S0                                                                      # model coordinates -> rest world
    assert np.allclose(mat4(ob.matrix_world), np.eye(4), atol=1e-6), "the imported harp should be baked in world space"
    if THICKEN > 0:
        ob.data.calc_normals() if hasattr(ob.data, "calc_normals") else None
        for v in ob.data.vertices:
            v.co = v.co + v.normal * (THICKEN / sc_k)
    ob.data.transform(Matrix(C0.tolist()))
    bpy.context.view_layer.update()
    V = np.array([v.co[:] for v in ob.data.vertices])
    log("rest placement: pillar %.2f m upright, grip %.0f%% of it at the pivot of the right hand (%.2f %.2f %.2f), sound box forward (yaw %+.0f deg); harp spans x %.2f..%.2f y %.2f..%.2f z %.2f..%.2f" % (
        HEIGHT, 100 * GRIP, *piv, YAW, V[:, 0].min(), V[:, 0].max(), V[:, 1].min(), V[:, 1].max(), V[:, 2].min(), V[:, 2].max()))
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
    meta = {}; report = []
    H0 = H[:3, :3]; a_loc = H0 @ np.array(WM["dir"]); a_loc /= np.linalg.norm(a_loc)  # the axis of the right fist in the rest pose (the way a sword's blade goes)
    zup = np.array([0.0, 0.0, 1.0]); fwd0 = np.array([0.0, -1.0, 0.0])

    def Rm4(R):
        M = np.eye(4); M[:3, :3] = R; return M

    def orient(Rdes, gf):
        """the harp with the axes (model X, Y, Z -> columns of Rdes) and its grip point on the right fist: maps the rest-placed mesh to its place"""
        return trans(gf) @ Rm4(Rdes @ R2.T) @ trans(-piv)

    for a in sorted(acts):
        act = acts[a]; rig.animation_data.action = act; n = int(act["uo_frames"]); prev = None
        Dsteady = None
        if a in STEADY or a in LEAN_WALK:                                             # the mean orientation of the chest over the whole action (a walk twists the chest +-13 deg with the steps)
            rots = []
            for i in range(n):
                sc.frame_set(1 + STEP * i); bpy.context.view_layer.update(); rots.append(delta("chest")[:3, :3])
            Dsteady = Ro.from_matrix(np.array(rots)).mean().as_matrix()
        frames = []
        for i in range(n):
            sc.frame_set(1 + STEP * i); bpy.context.view_layer.update()
            gf = hand_pt("hand.R", pR); af = delta("hand.R")[:3, :3] @ a_loc; af /= np.linalg.norm(af)
            Dc = Dsteady if Dsteady is not None else delta("chest")[:3, :3]
            chest = np.array(rig.pose.bones["chest"].head)                       # armature space = world at direction 0
            frames.append(dict(gf=gf, af=af, Dc=Dc, chest=chest, fc=delta("chest")[:3, :3] @ fwd0))
        # the walk: lean outward (and tip to the ground) as set; more lean when the harp would touch the legs (the same for every frame of the action)
        lean = WALK_LEAN
        if a in LEAN_WALK:
            trees = []
            for i in range(0, n, 2):
                sc.frame_set(1 + STEP * i); bpy.context.view_layer.update(); trees.append((i, cKDTree(body_pts(bpy.context.evaluated_depsgraph_get()))))

            def walk_R(fr, ln):
                return fr["Dc"] @ Ro.from_rotvec(np.array([1.0, 0, 0]) * math.radians(WALK_PITCH)).as_matrix() @ Ro.from_rotvec(fwd0 * math.radians(ln)).as_matrix() @ R2
            while True:
                pen = 0
                for i, tr in trees:
                    Dk = orient(walk_R(frames[i], lean), frames[i]["gf"])
                    dd, _ = tr.query((Dk[:3, :3] @ P0[::4].T).T + Dk[:3, 3]); pen += int((dd < BODY_CLEAR).sum())
                pen /= len(trees)
                if pen <= WALK_PEN or lean >= 35.0:
                    break
                lean += 5.0
            log("walk, action %d: held by the pillar, leaned %.0f deg outward, tipped %.0f deg towards the ground (body points inside: %.0f of %d)" % (a, lean, WALK_PITCH, pen, len(P0[::4])))
        zprev = None
        for i in range(n):
            fr = frames[i]; gf, af, Dc = fr["gf"], fr["af"], fr["Dc"]
            if a in LEAN_WALK:
                D = orient(walk_R(fr, lean), gf)
            elif a in FLAT_DIE:
                h = af - (af @ zup) * zup
                if np.linalg.norm(h) < 0.3:
                    h = Dc @ np.array([1.0, 0, 0]); h -= (h @ zup) * zup
                Zp = h / np.linalg.norm(h)
                away = (gf - fr["chest"]); away[2] = 0
                Xp = np.cross(zup, Zp)
                if Xp @ away < 0 or (zprev is not None and Zp @ zprev < 0 and Xp @ away < 0.0):
                    Zp, Xp = -Zp, -Xp
                zprev = Zp
                D = orient(np.column_stack([Xp, zup, Zp]), gf)
            else:                                                                     # one hand: orientation of the chest (upright, the sound box forward), grip on the right fist; a few degrees about the pillar where set
                D = orient(Dc @ Ro.from_rotvec(zup * math.radians(YAW_OUT.get(a, 0.0))).as_matrix() @ R2, gf)
            if a not in TWO_HAND:
                keys[(a, i)] = D; meta[(a, i)] = dict(af=af, gf=gf); continue
            sc.frame_set(1 + STEP * i); bpy.context.view_layer.update()
            dg = bpy.context.evaluated_depsgraph_get()
            Lp = hand_pt("hand.L", pL); BP = body_pts(dg)
            ctx = dict(af=af, fc=fr["fc"], chest=fr["chest"], front=(a in FRONT), plane=(a in FRONT_PLANE), parallel=(a in PARALLEL), fist_free=FIST_FREE.get(a, FIST_DEFAULT))
            X, info = solve_frame(D, P0, N0, piv, R2, Lp, BP, prev, ctx)
            prev = info["w"]
            keys[(a, i)] = X; meta[(a, i)] = dict(af=af, gf=gf, chest=fr["chest"], fc=fr["fc"], **{k: v for k, v in info.items() if k != "w"})
            report.append((a, i, info))
    # ---- report: what every action does (the numbers the user's requests are checked with)
    ex, ey, ez = (R2 @ np.array(v) for v in ([1.0, 0, 0], [0, 1.0, 0], [0, 0, 1.0]))
    for a in sorted(acts):
        n = int(acts[a]["uo_frames"]); K = [keys[(a, i)] for i in range(n)]
        Zw = np.array([k[:3, :3] @ ez for k in K]); Yw = np.array([k[:3, :3] @ ey for k in K]); Xw = np.array([k[:3, :3] @ ex for k in K])
        tilt = np.degrees(np.arccos(np.clip(Zw[:, 2], -1, 1))); plane = np.degrees(np.arccos(np.clip(np.abs(Yw[:, 2]), -1, 1)))
        yaw = np.degrees(np.arctan2(Xw[:, 0], -Xw[:, 1]))
        extra = ""
        if a in TWO_HAND:
            rows = [meta[(a, i)] for i in range(n)]
            extra = " | TWO HANDS: left fist %.1f..%.1f cm from the wood, pillar %.0f..%.0f deg off the right fist's axis, body points inside %d%s" % (
                100 * min(r["touch"] for r in rows), 100 * max(r["touch"] for r in rows), min(r["fist"] for r in rows), max(r["fist"] for r in rows), max(r["pen"] for r in rows),
                (", harp ahead of the chest by %.0f..%.0f cm" % (100 * min(r["ahead"] for r in rows), 100 * max(r["ahead"] for r in rows))) if a in FRONT else "")
            extra += ", plane faces the front to %.0f..%.0f deg" % (min(r["facing"] for r in rows), max(r["facing"] for r in rows))
        elif a in YAW_OUT:
            extra = " | OUTWARD: the usual hold turned %+.0f deg about the pillar (sound box yaw above)" % YAW_OUT[a]
        elif a in FLAT_DIE:
            cen = [np.mean((K[i][:3, :3] @ P0[::6].T).T + K[i][:3, 3], axis=0) for i in range(n)]
            dist = [np.linalg.norm((cen[i] - meta[(a, i)]["gf"])[:2]) for i in range(n)]
            extra = " | FLAT: harp's middle %.0f..%.0f cm from the hand (horizontal), grip on the fist" % (100 * min(dist), 100 * max(dist))
        elif a in LEAN_WALK:
            extra = " | WALK: normal hold, leaned outward and tipped to the ground (see above)"
        log("action %2d %-22s plane from horizontal %.0f..%.0f deg, pillar from vertical %.0f..%.0f deg, sound box yaw %+.0f..%+.0f deg%s" % (
            a, acts[a].name[3:], plane.min(), plane.max(), tilt.min(), tilt.max(), yaw.min(), yaw.max(), extra))
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
    ob["uo_harp"] = json.dumps(dict(height=HEIGHT, grip=GRIP, yaw=YAW, two_hand=TWO_HAND, steady=STEADY, lean_walk=LEAN_WALK, yaw_out=YAW_OUT, flat_die=FLAT_DIE, front=FRONT))
    log("%s -> rigid on the bone harp, keyed in %d actions (%d frames)" % (ob.name, len(acts), len(keys)))


def solve_frame(D, P0, N0, piv, R2, Lp, BP, prev_w, ctx):
    """pose of the harp (4x4, armature space) for one frame: turned about the right grip (and slid along the pillar) so that the left fist touches it, the pillar stays along the axis of the
    right fist, the harp stays near upright (in front of the chest for the poses in FRONT) and out of the body; returns (X, info)"""
    from scipy.spatial import cKDTree
    from scipy.spatial.transform import Rotation as Ro
    from scipy.optimize import minimize
    B = D                                                                             # one-hand pose (maps the rest-placed harp to its place in this frame)
    P1 = (B[:3, :3] @ P0.T).T + B[:3, 3]; N1 = (B[:3, :3] @ N0.T).T
    g = B[:3, :3] @ piv + B[:3, 3]                                                    # the grip point (the pivot of the hand) in this frame
    u0 = B[:3, :3] @ (R2 @ np.array([0, 0, 1.0])); u0 /= np.linalg.norm(u0)            # the pillar axis in the one-hand pose
    n0 = B[:3, :3] @ (R2 @ np.array([0, 1.0, 0]))                                     # the normal of the harp's plane in the one-hand pose
    far = np.linalg.norm(P1 - g, axis=1) > 0.12                                       # the left hand goes to a place other than the right one
    Pf, Nf = P1[far], N1[far]
    tree = cKDTree(BP)
    sub = np.arange(0, len(P1), 3)
    af, fc, chest = ctx["af"], ctx["fc"], ctx["chest"]

    def apply(p, P, Nn=None):
        R = Ro.from_rotvec(p[:3]).as_matrix()
        Q = (P - g) @ R.T + g + (R @ u0) * p[3] + (R @ n0) * p[4]                       # p[3]: slide along the pillar, p[4]: the pillar sits this far to the side of the fist's centre (along the plane's normal)
        return Q if Nn is None else (Q, Nn @ R.T)

    def touch_of(p):
        Q, Nq = apply(p, Pf, Nf)
        dd = np.linalg.norm(Q - Lp, axis=1); k = int(dd.argmin())
        sd = float((Lp - Q[k]) @ Nq[k])                                               # >0: the pivot is outside the wood
        return (dd[k] if sd >= 0 else -dd[k]), Q[k]

    def fist_of(p):
        u = Ro.from_rotvec(p[:3]).as_matrix() @ u0
        return math.acos(min(1.0, abs(float(u @ af))))                                # the pillar may point either way along the fist

    def ahead_of(p):
        c = apply(p, P1[sub]).mean(0)
        return float((c - chest) @ fc)

    def cost(p, with_body=True, prev=prev_w):
        t, _ = touch_of(p)
        lo, hi = TOUCH
        Jt = (max(0.0, lo - t) / 0.005) ** 2 + (max(0.0, t - hi) / 0.008) ** 2
        R = Ro.from_rotvec(p[:3]).as_matrix()
        u = R @ u0
        tilt = math.acos(max(-1, min(1, u[2])))
        Ju = (tilt / TILT_MAX) ** 2 + 10.0 * (max(0.0, tilt - 1.25) / 0.1) ** 2           # beyond ~70 deg the harp would hang upside down
        if ctx["parallel"]:
            Ju += 4.0 * (max(0.0, tilt - 0.14) / 0.05) ** 2                               # stand: not tilted
        gp = GRIP * HEIGHT - p[3]                                                      # where the right fist is on the pillar (m from its foot) after the slide
        Jw = 0.1 * (np.linalg.norm(p[:3]) / 1.0) ** 2 + (p[3] / 0.25) ** 2 * 0.1 + (max(0.0, 0.08 * HEIGHT - gp) / 0.02) ** 2 + (max(0.0, gp - 0.95 * HEIGHT) / 0.02) ** 2 + (max(0.0, abs(p[4]) - 0.03) / 0.01) ** 2
        Jf = (max(0.0, fist_of(p) - ctx["fist_free"]) / 0.15) ** 2                              # held in the fist: the pillar along its axis
        Jp = 0.0
        if with_body:
            Q = apply(p, P1[sub]); dd, _ = tree.query(Q)
            Jp = 0.6 * float((dd < (CLEAR_PARALLEL if ctx["parallel"] else BODY_CLEAR)).sum()) / (1.2 if ctx["parallel"] else 10.0)
        Jr = 0.0
        if ctx["front"]:                                                              # in front of the chest (as in the ordinary stand)
            Jr += (max(0.0, 0.16 - ahead_of(p)) / 0.05) ** 2
        if ctx["parallel"]:                                                           # parallel to the belly: the plane's normal along the body's forward axis
            nn = R @ n0
            Jr += 6.0 * (max(0.0, math.acos(min(1.0, abs(float(nn @ fc)))) - 0.17) / 0.06) ** 2
        if ctx["plane"]:                                                              # the triangle faces the front, not edge-on
            nn = R @ n0
            Jr += 3.0 * (max(0.0, 0.8 - abs(float(nn @ fc))) / 0.15) ** 2
        Jt_ = 0.0 if prev is None else (np.linalg.norm(p[:3] - prev[:3]) / 0.15) ** 2 + ((p[3] - prev[3]) / 0.05) ** 2
        return Jt + Ju + Jw + Jf + Jp + Jr + Jt_

    # coarse search: random rotations + zero, cheap terms first
    rng = np.random.default_rng(SEED)
    if prev_w is not None:                                                            # later frames of an action: track the previous solution (the harp does not jump about)
        cand = np.vstack([prev_w[None, :], prev_w[None, :] + rng.normal(0, [0.1, 0.1, 0.1, 0.03, 0.01], (30, 5))])
    else:
        cand = np.zeros((1, 5))
        rv = Ro.random(4000, random_state=SEED).as_rotvec()
        rv = rv * np.minimum(1.0, 2.8 / np.maximum(np.linalg.norm(rv, axis=1, keepdims=True), 1e-9))
        cand = np.vstack([cand, np.c_[rv, rng.uniform(-0.3, 0.3, len(rv)), rng.uniform(-0.03, 0.03, len(rv))]])
    cheap = np.array([cost(c, with_body=False) for c in cand])
    best = cand[np.argsort(cheap)[:12]]
    sols = []
    for c in best:
        r = minimize(cost, c, method="Nelder-Mead", options=dict(xatol=2e-3, fatol=1e-3, maxiter=600, initial_simplex=np.vstack([c] + [c + np.eye(5)[k] * (0.08 if k < 3 else (0.03 if k == 3 else 0.01)) for k in range(5)])))
        sols.append((r.fun, r.x))
    f_, p = min(sols, key=lambda s: s[0])
    if prev_w is not None and touch_of(p)[0] > TOUCH[1] + 0.02:                       # tracking lost the contact: search again from scratch (the temporal term still pulls towards the last pose)
        return solve_frame(D, P0, N0, piv, R2, Lp, BP, None, ctx)
    R = Ro.from_rotvec(p[:3]).as_matrix()
    X = np.eye(4); X[:3, :3] = R; X[:3, 3] = g - R @ g + (R @ u0) * p[3] + (R @ n0) * p[4]
    X = X @ B                                                                         # first the one-hand pose, then the turn about the grip
    t, _ = touch_of(p)
    Q = apply(p, P1[sub]); dd, _ = tree.query(Q)
    u = R @ u0
    info = dict(w=p, touch=t, tilt=math.degrees(math.acos(max(-1, min(1, u[2])))), pen=int((dd < BODY_CLEAR).sum()), dev=math.degrees(np.linalg.norm(p[:3])), cost=f_,
                fist=math.degrees(fist_of(p)), ahead=ahead_of(p), facing=math.degrees(math.acos(min(1.0, abs(float((R @ n0) @ fc))))))
    return X, info


main()
