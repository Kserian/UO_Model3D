# A bow held the same way in every action: grip (the middle of the bow) in the fist, shaft as calibrated, string side towards the body.
# The calibrated keys of bow.L (weapon_motion.json) come from silhouettes of a thin line: the shaft's tilt towards / away from the camera and the roll about the shaft are not determined by
# them (in 18_attack_bow the shaft jumps by ~87 degrees between two frames while the hand hardly moves), and the pivot sits up to 10 cm from the fist. Here, for every pose of bow.L:
#  - the shaft is parallel to the body (pelvis -> neck), straight, in every action (PARALLEL False: the calibrated direction, UPRIGHT actions along UP),
#  - the string side of the bow (the side the limb tips curve to) faces the back of the chest (taken perpendicular to the shaft): the bow stands in the body's own plane in every action
#    (from the front it is seen edge-on; held out in front the string comes to the archer, the limb tips curve away from the leg when the bow hangs at the side),
#  - the handle of the bow (its middle, the belly-most part - the bounds' axis lies a hand's width towards the string) goes to the centre of the fingers of hand.L.
#  - in AIM actions (held out) the string side faces the archer along the arm.
# Run on a bow that is bound to bow.L (uo_bind_item.py, PART = "bow"), the bow selected.
import bpy, json, os, sys
from mathutils.bvhtree import BVHTree
import numpy as np
from mathutils import Matrix, Quaternion, Vector

PARALLEL = True                      # the shaft stays upright in every action (like in the walk), it follows the body (pelvis -> neck) only once the body leans more than FREE_LEAN (False = the calibrated direction, except UPRIGHT actions)
CLEAR_CONE = 90.0                    # degrees: in the CALIBRATED actions the shaft is tilted away from the calibrated direction (at most this much) until the bow stays out of the body and in front of it
CLEAR_GAP = 0.025                    # m: the bow keeps this far from the skin (beyond 12 cm from the fist)
IN_FRONT = 0.10                      # m: every part of the bow is at least this far in front of the chest's centre (not under the armpit, not behind the back)
CONE_BY = {7: 90.0, 8: 90.0, 16: 50.0, 17: 40.0, 30: 35.0}   # action -> degrees: the shaft is tilted at most this much (around the direction of the rule) until the bow stays out of the posed body
CONE_ACTIONS = list(CONE_BY)
ORIGINAL_POS = [23, 24, 25]          # mounted walk / run / stand: the bow sits where the original bow sprites are (the calibrated pose), not at the fist of our body: the arms of our rider differ from the original body
SHOULDER_SIDE = [23, 24, 25]         # the string side of these faces the shoulder of the holding arm (3D), perpendicular to the shaft
CONE_FRAMES = {17: [3]}              # clearance only for these frames of the action (the others are fine as fitted)
WALK_LEAN = {15: 12.0}               # action -> degrees: the bow hangs slanted in the hand, its top towards the body's midline, the bottom out, the string facing the body
SMOOTH_FRAMES = {16: {3: (2, 4)}}    # action -> {frame: (a, b)}: the pose of that frame is the mean of the frames a and b (a frame whose clearance search leaned away)
SHIFT_BY = {}   # action -> m: the bow may also be moved sideways away from the body (a seated rider's thigh is in the way of a hanging bow)
IN_FRONT_ACTIONS = [7, 8]            # of these the bow must also stay ahead of the chest (held in front, not under the armpit)
ROLL_ONLY = [17, 27]             # actions whose roll about the shaft (one constant angle for the action) is chosen by the sprites of the original bow, the shaft being as chosen by the rules
ROLL_FIT = [17, 18, 23, 24, 25, 26, 27]                      # actions whose roll about the shaft is fitted to the sprites of the original bow (env UO_BOW_WP + UO_BOW_VD, recipe "orig"); the shaft is the calibrated one
CALIBRATED = [7, 8, 17, 18, 23, 24, 25, 26, 27, 28, 29]                  # one-frame ready stances: the shaft keeps the direction calibrated on the original bows (a vertical bow would go through the thigh of the crouch)
AWAY_FROM_HEAD = {21: 10.0, 22: 10.0}          # action -> degrees: once the body lies, the shaft is turned this much so that its end nearest to the head moves away from it (the falls: the bow lay on the face)
FACING = "pelvis"                    # bone whose back the string faces (not the chest: in the war stance 7 the torso is turned ~70 deg against the legs and the bow turned with it)
FULL_LEAN = 60.0                     # from this lean of the body (degrees) the bow lies along it
FREE_LEAN = 35.0                     # degrees of lean of the body (crouch, step) the bow does not follow
UPRIGHT = [18]                       # with PARALLEL False: UO action numbers where the shaft is made vertical instead of the calibrated direction
UP = (0.0, -0.12, 1.0)               # world axes at direction 0: Y is forward (-Y), Z up
AIM = [17, 18, 19, 23, 24, 25, 26, 27, 28]                       # actions where the bow is held out along the aim line: the string side faces the archer along the arm (fist -> shoulder), not the back of the chest
FIST_SHIFT = 0.0                     # m along the shaft from the fingers' centre (+ = towards the tip) if the grip should sit higher / lower in the fist

rig = bpy.data.objects["UO_Rig"]
WM = json.loads(bpy.data.texts["weapon_motion.json"].as_string())["bow.L"]
item = [o for o in bpy.context.selected_objects if o.type == "MESH"][0]
sc = bpy.context.scene
body_obj = bpy.data.objects["UO_Body"]
FINGERS = [b.name for b in rig.data.bones if b.name.startswith("finger") and b.name.endswith(".L")]


def frame(a, b):
    """right-handed orthonormal frame (columns): first column along a, second towards b"""
    a = np.asarray(a, float); a /= np.linalg.norm(a)
    b = np.asarray(b, float); b = b - (b @ a) * a; b /= np.linalg.norm(b)
    return np.c_[a, b, np.cross(a, b)]


rig.data.pose_position = "REST"
bpy.context.view_layer.update()
M = np.array(rig.matrix_world)[:3, :3]
H0 = M @ np.array(Matrix(rig.data.bones[WM["parent"]].matrix_local).to_3x3())            # hand.L axes at rest -> world
P = np.array([item.matrix_world @ v.co for v in item.data.vertices])
C0 = M @ np.array(Matrix(rig.data.bones[FACING].matrix_local).to_3x3()); C0 = C0 / np.linalg.norm(C0, axis=0)
d = H0 @ np.asarray(WM["dir"], float); d /= np.linalg.norm(d)                             # the class line (shaft, tip up) at rest
t = (P - P.mean(0)) @ d
L = np.ptp(t)
mid = P[np.abs(t - np.median(t)) < 0.1 * L].mean(0)
ends = P[(t > t.min() + 0.8 * L) | (t < t.min() + 0.2 * L)].mean(0)
c = ends - mid; c -= (c @ d) * d
cl = (P - mid) @ (c / np.linalg.norm(c))                                                   # coordinate along the string side
ts = (P - P.mean(0)) @ d
hs = (np.abs(ts - np.median(ts)) < 0.06 * L) & (cl < cl[np.abs(ts - np.median(ts)) < 0.06 * L].min() + 0.06)   # the handle: the belly-most part of the middle (not the string across it)
hc = P[hs].mean(0) + c / np.linalg.norm(c) * 0.025                                         # + half the grip's thickness
head0 = np.array(rig.matrix_world @ rig.data.bones["bow.L"].head_local)
o_h = H0.T @ (hc - head0)                                                                    # handle centre from the bone's head, in hand axes: it goes into the fist, not the axis of the bounds
print("uo_bow_hold: handle %.1f cm along the shaft, %.1f cm towards the string from the bone head" % (100 * (hc - head0) @ d, 100 * (hc - head0) @ (c / np.linalg.norm(c))))
u_src = frame(np.asarray(WM["dir"], float), H0.T @ c)                                      # shaft and string side in hand axes
print("uo_bow_hold: string side %s (hand axes), shaft %.2f m" % (np.round(H0.T @ c / np.linalg.norm(c), 2), L))


def clear_of_body(D0, Hw, F, _unused, cone=90.0, in_front=True, an_=-1, fr_=-1, max_shift=0.0):
    """candidate shaft directions on cones around D0 (0..cone degrees, every 8, 12 azimuths) and, with max_shift, the bow moved sideways away from the body (0..max_shift m, every 3 cm):
    the one with the least penetration of the bow into the body skin (vertices of the bow beyond 12 cm from the fist keep CLEAR_GAP off it), a bow that must be IN_FRONT of the chest,
    plus a small cost per degree of tilt and per cm of shift. Returns (D, string side, shift vector)"""
    evb = body_obj.evaluated_get(bpy.context.evaluated_depsgraph_get()); mb = evb.to_mesh(); mb.calc_loop_triangles()
    Bv = [np.array(evb.matrix_world @ v.co) for v in mb.vertices]
    tri = [tuple(t.vertices) for t in mb.loop_triangles]
    tree = BVHTree.FromPolygons([tuple(v) for v in Bv], tri)
    evb.to_mesh_clear()
    fwd = -to_back_of(np.array([0.0, 0.0, 1.0])); fwd[2] = 0.0; fwd /= np.linalg.norm(fwd)    # the way the pelvis faces
    chest_c = np.array(rig.matrix_world @ rig.pose.bones["chest"].head)
    pel_c = np.array(rig.matrix_world @ rig.pose.bones["pelvis"].head)
    out_dir = F - pel_c; out_dir[2] = 0.0; out_dir = out_dir / np.linalg.norm(out_dir) if np.linalg.norm(out_dir) > 1e-6 else np.array([1.0, 0, 0])   # away from the body's axis
    shift_vs = [np.zeros(3)] + ([out_dir * k_ * np.array([np.cos(az_), 0, 0]) for k_, az_ in []] if False else [])
    if max_shift > 0:                                                                          # any horizontal direction, 8 around, every 3 cm
        rot_ = lambda v, t_: np.array([v[0] * np.cos(t_) - v[1] * np.sin(t_), v[0] * np.sin(t_) + v[1] * np.cos(t_), 0.0])
        shift_vs += [rot_(out_dir, np.radians(az_)) * k_ for k_ in np.arange(0.03, max_shift + 1e-6, 0.03) for az_ in range(0, 360, 45)]
    sub = P[::max(1, len(P) // 1200)]
    off = sub - hc
    far = np.linalg.norm(off, axis=1) > 0.12
    e1 = np.cross(D0, [0, 0, 1.0]); e1 = e1 / np.linalg.norm(e1) if np.linalg.norm(e1) > 1e-6 else np.array([1.0, 0, 0]); e2 = np.cross(D0, e1)
    best = None
    for ang in [0.0] + list(np.arange(8.0, cone + 0.1, 8.0)):
        for az in ([0.0] if ang == 0 else np.arange(0, 360, 30)):
            a, b = np.radians(ang), np.radians(az)
            D = D0 * np.cos(a) + np.sin(a) * (e1 * np.cos(b) + e2 * np.sin(b))
            tb = to_back_of(D)
            Qc = frame(Hw.T @ D, Hw.T @ tb) @ u_src.T
            rel = (Hw @ Qc @ (H0.T @ off.T)).T
            for sv_ in shift_vs:
                k_sh = float(np.linalg.norm(sv_))
                pos = F + sv_ + rel
                pen = 0.0
                for p_ in pos[far]:
                    loc, nor, _, dist = tree.find_nearest(Vector(p_))
                    if loc is not None:
                        sd = (Vector(p_) - Vector(loc)).dot(nor)                                   # > 0 outside the skin
                        pen += max(0.0, CLEAR_GAP - sd)
                behind = float(np.maximum(0.0, IN_FRONT - (pos - chest_c) @ fwd).sum()) / len(pos) if in_front else 0.0
                cost = pen * 100.0 + behind * 100.0 + 0.05 * ang + 20.0 * k_sh
                if best is None or cost < best[0]:
                    best = (cost, D, tb, ang, pen, sv_)
    print("uo_bow_hold: clearance action %d frame %d: shaft tilted %.0f deg from the rule, moved %.0f cm sideways, skin gap shortfall %.3f" % (an_, fr_, best[3], 100 * np.linalg.norm(best[5]), best[4]))
    return best[1], best[2], best[5]


def to_back_of(D):
    tb = Cw @ C0.T @ np.array([0.0, 1.0, 0.0]); tb = tb - (tb @ D) * D
    return tb / max(np.linalg.norm(tb), 1e-9)


pb = rig.pose.bones["bow.L"]; pb.rotation_mode = "QUATERNION"
rig.data.pose_position = "POSE"
keep = rig.animation_data.action
W = lambda p: np.array(rig.matrix_world @ p)
n = 0
AIM_SIDE = {}                                                                                # AIM action -> its mean shoulder line (horizontal): the roll of the bow does not wave from frame to frame
for an in AIM:
    act = [a for a in bpy.data.actions if a.get("uo_action") == an][0]; rig.animation_data.action = act; acc = np.zeros(3)
    for i in range(int(act["uo_frames"])):
        sc.frame_set(1 + 3 * i); bpy.context.view_layer.update()
        v = W(rig.pose.bones["upper_arm.R"].head) - W(rig.pose.bones["upper_arm.L"].head); v[2] = 0.0
        acc += v / np.linalg.norm(v)
    AIM_SIDE[an] = acc / np.linalg.norm(acc)

ORI = {}                                                                                       # (action, frame) -> (shaft direction, string side) fitted to the sprites of the original bow
if os.environ.get("UO_BOW_WP") and os.environ.get("UO_BOW_VD"):
    sys.path.insert(0, os.environ["UO_SCRIPTS"])
    import weapon_fit
    VW = weapon_fit.Views(os.environ["UO_BOW_WP"], os.environ["UO_BOW_VD"])
    s_orig = float(os.environ.get("UO_BOW_LEN", 0.86)) / L                                     # the original bow is smaller than ours: compared at its size, about the handle
    sub_ = P[::max(1, len(P) // 400)]; off_h = H0.T @ (sub_ - hc).T
    RD = {}                                                                                    # the body is turned per UO direction (the camera stays): world matrix of the rig for every direction
    for d_ in range(5):
        rig["uo_direction"] = d_; rig.update_tag(); sc.frame_set(sc.frame_current); bpy.context.view_layer.update(); RD[d_] = np.array(rig.matrix_world)
    rig["uo_direction"] = 0; rig.update_tag(); sc.frame_set(sc.frame_current); bpy.context.view_layer.update()
    R0inv = np.linalg.inv(RD[0]); RR = {d_: RD[d_] @ R0inv for d_ in range(5)}
    gold = np.pi * (3 - np.sqrt(5)); k_ = np.arange(500); zz = 1 - 2 * (k_ + 0.5) / 500; rr = np.sqrt(1 - zz * zz)
    SPH = np.c_[rr * np.cos(gold * k_), rr * np.sin(gold * k_), zz]; SPH = SPH[SPH[:, 2] >= -0.2]    # candidate shaft directions (the bow is symmetric: +D and -D look alike), about 10 degrees apart
    PRIOR = 2.0                                                                                # px: penalty when the string side does not face the archer

    LAM_T = 0.06                                                                               # px per degree: the shaft turns smoothly from frame to frame (the sprites alone left the 3-4th frame leaning towards the head)
    LAM_TILT = 0.015                                                                           # px per degree of tilt from the vertical: weak, the original bow is upright when it is not swung

    def make_cost(Hw, HC, side0, views):
        def side_for(D):
            e1 = side0 - (side0 @ D) * D
            return e1 / np.linalg.norm(e1) if np.linalg.norm(e1) > 1e-6 else np.cross(D, [1.0, 0, 0]) / max(np.linalg.norm(np.cross(D, [1.0, 0, 0])), 1e-9)

        def cost(D):
            sd = side_for(D)
            Qc = frame(Hw.T @ D, Hw.T @ sd) @ u_src.T
            pos = HC + (Hw @ Qc @ off_h * s_orig).T; pos1 = np.c_[pos, np.ones(len(pos))]
            tot = 0.0
            for k in views:
                pix = (pos1 @ RR[int(VW.key[k][1])].T) @ VW.PX[k, :2].T
                xi = np.clip(pix[:, 0].astype(int), 0, VW.W - 1); yi = np.clip(pix[:, 1].astype(int), 0, VW.H - 1)
                d1 = np.minimum(VW.DT[k][yi, xi], 15.0).mean()
                op = VW.pts[k, :VW.npts[k]]
                d2 = np.minimum(np.sqrt(((op[:, None, :] - pix[None, :, :]) ** 2).sum(-1)).min(1), 15.0).mean()
                tot += 0.5 * (d1 + d2)
            return tot + LAM_TILT * np.degrees(np.arccos(np.clip(abs(D[2]), -1, 1)))
        return cost, side_for

    ang_between = lambda A, B_: np.degrees(np.arccos(np.clip(abs(float(A @ B_)), -1, 1)))
    for an in ROLL_FIT:
        act = [a for a in bpy.data.actions if a.get("uo_action") == an][0]; rig.animation_data.action = act
        nfr = int(act["uo_frames"]); ctx = []
        for i in range(nfr):
            sc.frame_set(1 + 3 * i); pb.rotation_quaternion = Quaternion(); pb.location = (0, 0, 0); bpy.context.view_layer.update()
            Hw = M @ np.array(rig.pose.bones[WM["parent"]].matrix.to_3x3()); Hw = Hw / np.linalg.norm(Hw, axis=0)
            pp = WM["poses"]["%d,%d" % (an, i)]; r = Vector(pp[:3]); ang_ = r.length
            q0 = Quaternion(r / ang_, ang_) if ang_ > 1e-9 else Quaternion()
            HC = W(pb.head) + Hw @ np.asarray(pp[3:], float) + Hw @ (np.array(q0.to_matrix()) @ o_h)    # where the original bow's handle is (the calibrated pose), not the fist
            views = [k for k in range(VW.n) if VW.key[k][0] == an and VW.key[k][2] == i]
            side0_ = (W(rig.pose.bones["upper_arm.L"].head) - HC) if an in SHOULDER_SIDE else AIM_SIDE[an]
            side0_ = side0_ / np.linalg.norm(side0_)
            ctx.append(make_cost(Hw, HC, side0_, views) + (len(views),))
        Cs = np.array([[c_[0](D) for D in SPH] for c_ in ctx])                                   # (frames, candidate shafts)
        DPc = Cs.copy(); back = np.zeros(Cs.shape, int)
        TR = np.array([[ang_between(A, B_) for B_ in SPH] for A in SPH]) * LAM_T                 # transition cost between two candidate shafts
        for i in range(1, nfr):
            tot = DPc[i - 1][:, None] + TR; back[i] = tot.argmin(0); DPc[i] = Cs[i] + tot.min(0)
        j = int(DPc[-1].argmin()); path = [j]
        for i in range(nfr - 1, 0, -1):
            j = back[i][j]; path.append(j)
        Ds = [SPH[j].copy() for j in path[::-1]]
        for it_ in range(3):                                                                     # refine every frame around its shaft, with the neighbours' turn in the cost
            for i in range(nfr):
                cost_i = ctx[i][0]
                def tot_(D, i=i):
                    t_ = cost_i(D)
                    if i > 0: t_ += LAM_T * ang_between(D, Ds[i - 1])
                    if i < nfr - 1: t_ += LAM_T * ang_between(D, Ds[i + 1])
                    return t_
                cur = tot_(Ds[i])
                for rad in (np.radians(6.0), np.radians(3.0), np.radians(1.5)):
                    improved = True
                    while improved:
                        improved = False
                        e1 = np.cross(Ds[i], [0.0, 0, 1.0]); e1 = e1 / np.linalg.norm(e1) if np.linalg.norm(e1) > 1e-6 else np.array([1.0, 0, 0]); e2 = np.cross(Ds[i], e1)
                        for dx in (-1, 0, 1):
                            for dy in (-1, 0, 1):
                                if dx == dy == 0:
                                    continue
                                Dn = Ds[i] + rad * (dx * e1 + dy * e2); Dn /= np.linalg.norm(Dn); c_ = tot_(Dn)
                                if c_ < cur - 1e-6:
                                    cur, Ds[i], improved = c_, Dn, True
        for i in range(nfr):
            D_ = Ds[i] if Ds[i][2] >= 0 else -Ds[i]
            ORI[(an, i)] = (D_, ctx[i][1](D_))
            print("uo_bow_hold: fit to the original bow, action %d frame %d: shaft tilt %.0f deg from vertical, chamfer %.1f px over %d views%s" % (an, i, np.degrees(np.arccos(np.clip(D_[2], -1, 1))), ctx[i][0](D_), ctx[i][2], "" if i == 0 else ", turn from the previous frame %.0f deg" % ang_between(Ds[i], Ds[i - 1])))
rig.animation_data.action = keep
STATE = {}; ROLL_PHI = {}; n_ = [0]


def run_pass(dry):
    global Cw
    for act in [a for a in bpy.data.actions if "uo_action" in a]:
        an = int(act["uo_action"])
        if dry and an not in ROLL_ONLY and an not in SMOOTH_FRAMES:
            continue
        rig.animation_data.action = act; prev = None
        for i in range(int(act["uo_frames"])):
            p = WM["poses"].get("%d,%d" % (an, i))
            if p is None:
                continue
            sc.frame_set(1 + 3 * i)                                                                # evaluates the old keys of bow.L; the hand's pose is what is wanted here
            pb.rotation_quaternion = Quaternion(); pb.location = (0, 0, 0); bpy.context.view_layer.update()
            Hw = M @ np.array(rig.pose.bones[WM["parent"]].matrix.to_3x3()); Hw = Hw / np.linalg.norm(Hw, axis=0)   # hand.L axes posed -> world
            r = Vector(p[:3]); ang = r.length
            q0 = Quaternion(r / ang, ang) if ang > 1e-9 else Quaternion()
            HC_ = W(pb.head) + Hw @ np.asarray(p[3:], float) + Hw @ (np.array(q0.to_matrix()) @ o_h)    # the handle of the original bow (calibrated pose)
            body = W(rig.pose.bones["neck"].head) - W(rig.pose.bones["pelvis"].head)
            Cw = M @ np.array(rig.pose.bones[FACING].matrix.to_3x3()); Cw = Cw / np.linalg.norm(Cw, axis=0)
            lean = 0.0
            if PARALLEL:                                                                           # upright; along the body once it leans over (smoothstep 35 -> 60 deg, a fall / death: along the body)
                bn = body / np.linalg.norm(body); lean = np.degrees(np.arccos(np.clip(bn[2], -1, 1)))
                side = bn - bn[2] * np.array([0.0, 0.0, 1.0])
                x = float(np.clip((lean - FREE_LEAN) / (FULL_LEAN - FREE_LEAN), 0.0, 1.0)); a = np.radians(lean * x * x * (3 - 2 * x))
                body = np.array([0.0, 0.0, 1.0]) * np.cos(a) + (side / np.linalg.norm(side) * np.sin(a) if np.linalg.norm(side) > 1e-6 else 0.0)
            D = Hw @ (np.array(q0.to_matrix()) @ np.asarray(WM["dir"], float)) if an in CALIBRATED else body if PARALLEL else np.asarray(UP, float) if an in UPRIGHT else Hw @ (np.array(q0.to_matrix()) @ np.asarray(WM["dir"], float))
            D = D / np.linalg.norm(D)
            F = np.mean([W(rig.pose.bones[b].head) for b in FINGERS] + [W(rig.pose.bones[b].tail) for b in FINGERS], 0) + D * FIST_SHIFT
            if an in ORIGINAL_POS:
                F = HC_.copy()
            if an in AWAY_FROM_HEAD and lean > FREE_LEAN:
                x = float(np.clip((lean - FREE_LEAN) / (FULL_LEAN - FREE_LEAN), 0.0, 1.0)); x = x * x * (3 - 2 * x)
                hv = W(rig.pose.bones["head"].head) - F
                ax = np.cross(D, hv)
                if np.linalg.norm(ax) > 1e-6:
                    ax /= np.linalg.norm(ax); th = np.radians(AWAY_FROM_HEAD[an]) * x
                    sg = 1.0 if D @ hv > 0 else -1.0                                                 # the end of the bow (+D or -D) that is nearer to the head
                    def rot(v, t): return v * np.cos(t) + np.cross(ax, v) * np.sin(t) + ax * (ax @ v) * (1 - np.cos(t))
                    D = min((rot(D, th), rot(D, -th)), key=lambda v: sg * (v @ hv)); D = D / np.linalg.norm(D)
            to_body = Cw @ C0.T @ np.array([0.0, 1.0, 0.0])                                        # the back of FACING (the body faces -Y at rest)
            to_body -= (to_body @ D) * D; to_body /= max(np.linalg.norm(to_body), 1e-9)
            if an in AIM:                                                                           # held out along the aim line: the string comes to the archer along the shoulder line (left -> right shoulder),
                sh = AIM_SIDE[an].copy()                                                            # the same in every frame (the torso twists during the shot, the bow must not follow it)
                sh -= (sh @ D) * D
                if np.linalg.norm(sh) > 1e-3:
                    to_body = sh / np.linalg.norm(sh)
            if lean > FREE_LEAN:                                                                    # a fall: the string side faces the body (the belly of the bow away from the character)
                x = float(np.clip((lean - FREE_LEAN) / (FULL_LEAN - FREE_LEAN), 0.0, 1.0)); x = x * x * (3 - 2 * x)
                tc = W(rig.pose.bones["chest"].head) - F; tc -= (tc @ D) * D
                if np.linalg.norm(tc) > 1e-3:
                    to_body = (1 - x) * to_body + x * tc / np.linalg.norm(tc)
            to_body -= (to_body @ D) * D
            if np.linalg.norm(to_body) < 1e-3:
                to_body = np.array([0.0, 1.0, 0.0])
            if an in WALK_LEAN:                                                                     # carried at the side: slanted, top towards the body's midline, string towards the body
                inw = W(rig.pose.bones["pelvis"].head) - F; inw[2] = 0.0; inw /= max(np.linalg.norm(inw), 1e-9)
                a_ = np.radians(WALK_LEAN[an]); D = D * np.cos(a_) + inw * np.sin(a_); D /= np.linalg.norm(D)
                to_body = inw - (inw @ D) * D; to_body /= np.linalg.norm(to_body)
            if (an, i) in ORI:                                                                      # shaft and string side fitted to the original bow sprites
                D, to_body = ORI[(an, i)]
            smoothed_ = False
            if an in SMOOTH_FRAMES and i in SMOOTH_FRAMES[an] and not dry and an in STATE and all(k_ in STATE[an] for k_ in SMOOTH_FRAMES[an][i]):
                fa_, fb_ = SMOOTH_FRAMES[an][i]                                                     # the pose of a frame that leaned away: the mean of its neighbours
                D = STATE[an][fa_][2] + STATE[an][fb_][2]; D /= np.linalg.norm(D)
                to_body = STATE[an][fa_][3] + STATE[an][fb_][3]; to_body -= (to_body @ D) * D; to_body /= np.linalg.norm(to_body)
                smoothed_ = True
            if an in CONE_ACTIONS and not smoothed_ and (an not in CONE_FRAMES or i in CONE_FRAMES[an]):                                                                  # the least tilt from the calibrated direction at which the bow stays out of the posed body
                D, to_body, sh_ = clear_of_body(D, Hw, F, lambda D_, T_: to_back_of(D_), CONE_BY[an], an in IN_FRONT_ACTIONS, an, i, SHIFT_BY.get(an, 0.0))
                F = F + sh_
            if dry:
                STATE.setdefault(an, {})[i] = (Hw.copy(), HC_.copy(), D.copy(), to_body.copy())
                continue
            if an in ROLL_PHI:                                                                      # the roll chosen by the original sprites: the string side turned about the shaft
                e1_ = to_body - (to_body @ D) * D; e1_ /= np.linalg.norm(e1_)
                to_body = np.cos(ROLL_PHI[an]) * e1_ + np.sin(ROLL_PHI[an]) * np.cross(D, e1_)
            Q = frame(Hw.T @ D, Hw.T @ to_body) @ u_src.T                                       # turn of the bone in hand axes: shaft -> D, string side -> the body
            q = Matrix(Q.tolist()).to_quaternion()
            if prev is not None and q.dot(prev) < 0:
                q.negate()
            prev = q
            pb.rotation_quaternion = q
            bpy.context.view_layer.update()
            h = W(pb.head)                                                                         # the bone's head with the location 0
            pb.location = tuple(float(x) for x in Hw.T @ (F - Hw @ (Q @ o_h) - h))                                  # hand axes = the bone's axes: the shift that puts the grip in the fist
            pb.keyframe_insert("location", frame=1 + 3 * i, group="bow.L")
            pb.keyframe_insert("rotation_quaternion", frame=1 + 3 * i, group="bow.L")
            n_[0] += 1


run_pass(True)                                                                                 # dry: the shaft and string side by the rules, for the actions whose roll is chosen by the original sprites
if STATE and "VW" in globals():
    PHI = np.radians(np.arange(0.0, 360.0, 30.0))
    for an, fr in STATE.items():
        if an not in ROLL_ONLY:
            continue
        tot = np.zeros(len(PHI))
        for i, (Hw_, HC_, D_, sd_) in fr.items():
            views = [k for k in range(VW.n) if VW.key[k][0] == an and VW.key[k][2] == i]
            e1_ = sd_ - (sd_ @ D_) * D_; e1_ /= np.linalg.norm(e1_); e2_ = np.cross(D_, e1_)
            for j, ph in enumerate(PHI):
                sd2 = np.cos(ph) * e1_ + np.sin(ph) * e2_
                Qc = frame(Hw_.T @ D_, Hw_.T @ sd2) @ u_src.T
                pos = HC_ + (Hw_ @ Qc @ off_h * s_orig).T; pos1 = np.c_[pos, np.ones(len(pos))]
                for k in views:
                    pix = (pos1 @ RR[int(VW.key[k][1])].T) @ VW.PX[k, :2].T
                    xi = np.clip(pix[:, 0].astype(int), 0, VW.W - 1); yi = np.clip(pix[:, 1].astype(int), 0, VW.H - 1)
                    d1 = np.minimum(VW.DT[k][yi, xi], 15.0).mean()
                    op = VW.pts[k, :VW.npts[k]]
                    d2 = np.minimum(np.sqrt(((op[:, None, :] - pix[None, :, :]) ** 2).sum(-1)).min(1), 15.0).mean()
                    tot[j] += 0.5 * (d1 + d2)
        prior = 0.02 * np.array([min(np.degrees(x), 360 - np.degrees(x)) for x in PHI])          # the roll of the rule is kept unless the sprites clearly ask for another
        jb = int((tot + prior).argmin()); ROLL_PHI[an] = float(PHI[jb])
        print("uo_bow_hold: roll fit action %d: chamfer sum by roll (deg:px) %s -> %.0f deg" % (an, " ".join("%d:%.0f" % (np.degrees(x), t_) for x, t_ in zip(PHI, tot)), np.degrees(PHI[jb])))
run_pass(False)
n = n_[0]
print("uo_bow_hold: %d poses re-keyed" % n)

# ---- the string drawn by the second hand: the string vertices (mesh attribute uo_string, set by uo_make_item.py "inflate") are weighted to a bone "string.pull" (child of bow.L) in a
# triangular profile along the string: the nock follows the fingers of hand.R when the hand is at the face (DRAW_NEAR..DRAW_FAR m from the head), the ends stay on the limbs.
DRAW_ACTIONS = [18, 27]
FLEX = 0.10                            # share of the pull the limb tips follow: the tips move 10 % of the pull towards the hand (the bow flexes, the string ends stay on the tips)
STRING_WIDTH = 0.016                   # m: half width of the string across the bow
STRING_BAND = 0.022                    # m: thin vertices within this much of the string line are the string
DRAW_FAR, DRAW_NEAR = 0.30, 0.16       # m, hand.R to head: no pull / full draw
attr = item.data.attributes.get("uo_string")
if attr is not None:
    sv = np.array([i for i, a_ in enumerate(attr.data) if a_.value > 0.5])
    if len(sv) > 20:                                                                           # thin things are not only the string (limb edges, the wrapping of the grip): the string is the straight line
        mid_t = np.median(ts[sv]); mids = sv[np.abs(ts[sv] - mid_t) < 0.1 * L]                  # on the string side of the limbs, found in the middle of the bow where nothing else is that far out
        line = np.percentile(cl[mids], 95)
        bdir = np.cross(d, c / np.linalg.norm(c)); bco = (P - P.mean(0)) @ bdir                 # across the bow: the string is a thread (|b| < 1 cm), the knot / binding at the top of the limb is wider
        sv = sv[(cl[sv] > line - STRING_BAND) & (np.abs(bco[sv]) < STRING_WIDTH)]
        from scipy.spatial import cKDTree                                                        # a ring of the thread must not be split (half moves with the hand, half stays: a fan of dark strips):
        flagged = np.array([i for i, a_ in enumerate(attr.data) if a_.value > 0.5])               # every thin vertex within 8 mm of a string vertex belongs to the string, too
        near = cKDTree(P[sv]).query(P[flagged])[0] < 0.008
        sv = np.union1d(sv, flagged[near])
        print("uo_bow_hold: string line %.1f cm towards the string side, %d string vertices" % (100 * line, len(sv)))
    sv = [int(i) for i in sv]
    if len(sv) > 20:
        ts_ = ts[sv]; tm = float(np.median(ts_)); half = float(np.abs(ts_ - tm).max()) + 1e-6
        nock = P[sv][np.abs(ts_ - tm) < 0.03 * L].mean(0)
        rig.data.pose_position = "REST"; bpy.context.view_layer.update()
        bpy.context.view_layer.objects.active = rig
        bpy.ops.object.mode_set(mode="EDIT")
        hand_e = rig.data.edit_bones[WM["parent"]]
        if "string.pull" not in rig.data.edit_bones:
            eb = rig.data.edit_bones.new("string.pull"); eb.parent = rig.data.edit_bones["bow.L"]; eb.use_connect = False
            eb.length = 0.05; eb.matrix = Matrix.Translation(rig.matrix_world.inverted() @ Vector(nock)) @ hand_e.matrix.to_3x3().normalized().to_4x4()
        bpy.ops.object.mode_set(mode="OBJECT")
        rig.data.bones["string.pull"].use_deform = True; rig.data.bones["string.pull"].inherit_scale = "NONE"
        gp = item.vertex_groups.get("string.pull") or item.vertex_groups.new(name="string.pull"); gb = item.vertex_groups["bow.L"]
        svs = set(sv); th_ = float((hc - P.mean(0)) @ d)
        import bmesh                                                                           # long sliver faces (the string strip is triangulated with fans, a mesh of thin triangles between the string and the limb tips)
        bm = bmesh.new(); bm.from_mesh(item.data); bm.verts.ensure_lookup_table()              # are collinear at rest and open into a dark sheet when the string is pulled: removed
        bad = []
        for f_ in bm.faces:
            ids = [v_.index for v_ in f_.verts]; ns = sum(1 for k_ in ids if k_ in svs)
            if ns == 0:
                continue
            ln = max((P[ids[a_]] - P[ids[b_]]) @ (P[ids[a_]] - P[ids[b_]]) for a_ in range(len(ids)) for b_ in range(a_))
            if ln > 0.08 ** 2:
                bad.append(f_)
        bmesh.ops.delete(bm, geom=bad, context="FACES_ONLY"); bm.to_mesh(item.data); bm.free(); item.data.update()
        print("uo_bow_hold: %d long faces of the string removed" % len(bad))
        for i in sv:                                                                           # the string: the nock follows the hand fully, the ends follow the limb tips (FLEX)
            w = FLEX + (1.0 - FLEX) * float(max(0.0, 1.0 - abs(ts[i] - tm) / half) ** 1.5)
            gp.add([i], w, "REPLACE"); gb.add([i], 1.0 - w, "REPLACE")
        for i in range(len(P)):                                                                # the limbs bend: their pull grows with the square of the distance from the handle, 0 in the grip
            if i in svs:
                continue
            w = FLEX * min(1.0, abs(ts[i] - th_) / (L / 2)) ** 2
            if w > 0.002:
                gp.add([i], w, "REPLACE"); gb.add([i], 1.0 - w, "REPLACE")
        rig.data.pose_position = "POSE"
        ps = rig.pose.bones["string.pull"]; ps.rotation_mode = "QUATERNION"
        FR = [b.name for b in rig.data.bones if b.name.startswith("finger") and b.name.endswith(".R")]
        for act in [a for a in bpy.data.actions if "uo_action" in a]:
            an = int(act["uo_action"]); rig.animation_data.action = act
            frames = range(int(act["uo_frames"])) if an in DRAW_ACTIONS else [0]
            for i in frames:
                sc.frame_set(1 + 3 * i); ps.location = (0, 0, 0); ps.rotation_quaternion = Quaternion(); bpy.context.view_layer.update()
                loc = (0.0, 0.0, 0.0)
                if an in DRAW_ACTIONS:
                    FRh = np.mean([W(rig.pose.bones[b].head) for b in FR], 0)
                    d = float(np.linalg.norm(FRh - W(rig.pose.bones["head"].head)))
                    g = float(np.clip((DRAW_FAR - d) / (DRAW_FAR - DRAW_NEAR), 0.0, 1.0)); g = g * g * (3 - 2 * g)
                    Bw = np.array(rig.pose.bones["bow.L"].matrix.to_3x3()); Bw = M @ Bw; Bw = Bw / np.linalg.norm(Bw, axis=0)
                    loc = tuple(float(x) for x in Bw.T @ (g * (FRh - W(ps.head))))
                    print("uo_bow_hold: string action %d frame %d: hand.R %.2f m from the head, pull %.2f (%.2f m)" % (an, i, d, g, g * np.linalg.norm(FRh - W(ps.head))))
                ps.location = loc
                ps.keyframe_insert("location", frame=1 + 3 * i, group="string.pull")
                ps.keyframe_insert("rotation_quaternion", frame=1 + 3 * i, group="string.pull")
        rig.animation_data.action = keep
        print("uo_bow_hold: string: %d vertices weighted to string.pull" % len(sv))
rig.animation_data.action = keep
