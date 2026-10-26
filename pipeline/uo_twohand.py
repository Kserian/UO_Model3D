"""A two-handed weapon (mace, maul, hammer) carried by BOTH hands: its motion is worked out from the hands of the posed body instead of the calibration of a halberd.

    python uo_twohand.py ITEM.blend [OUT.blend] [--set NAME=VALUE ...] [--actions 08_combat_idle_2h,...] [--report FILE.json]

ITEM.blend = a weapon made by uo_make_item.py with "weapon": {"part": "polearm", ...} (rigid on the bone polearm.L, shaft along the class line, the ball up; the ball and
its radius are in the object property uo_head, uo_spikes.py). uo_make_item.py runs this for a recipe with "twohand": {...} (its settings, upper-case names below).
The calibrated motion of polearm.L (weapon_motion.json) is a halberd carried by the left hand: in 31 of 35 actions the right hand is 50-100 cm off its line, the
shaft turns by its own fit per frame. Here the shaft is laid through the grips of BOTH fists (PIVOT of polearm.L in hand.L, of weapon1h.R in hand.R: where the original
sword / halberd lies in the fist) and the bone polearm.L is keyed so that the weapon sits there; nothing else of the rig changes.
Per frame:
 1. d = the line from the lower fist to the upper one (UPPER: the hand that is nearer the head, per action; the original 2H attacks hold the weapon with the right hand
    on top, the rest with the left). The upper fist sits GRIP_BELOW m below the bottom of the ball (5 px = 0.14 m), MOUNTED_EXTRA lower in the mounted actions
    (the hands lower on the shaft). If the fists are too far apart for the shaft, the upper grip moves up / down along it; if they are closer than SEP_MIN, the line of
    the neighbouring frames is kept.
 2. The turn about the shaft follows the chest (its sideways or forward axis projected on the plane across the shaft, blended): the ball does not spin.
 3. Where the fists do not define the line (step 4, falls, mounted) d is smoothed over the frames of the action (SMOOTH frames, circular for looping actions).
 4. Frames in which the fists cannot hold the weapon together (closer than SEP_MIN, farther than the shaft allows: the spells) take the direction of the calibrated halberd
    line of that frame (weapon_motion.json: the original weapons' own motion, through the left hand), blended in over SEP_BLEND m. An action in which that is most of the frames (FISTS_MIN_SHARE) uses
    the calibrated direction throughout, so that the weapon does not jump between the two lines.
 5. Falls (FALL_ACTIONS): the shaft turns from the hold into the axis of the body (pelvis -> head, the ball towards the head) as the body tips over, so the weapon
    lies along the body; it is lifted when it would dig into the floor.
 6. Mounted actions (MOUNTED_ACTIONS): the line of step 1 is moved to the nearest direction in which the weapon clears the horse proxy of the frame (shaft CLEAR_SHAFT,
    ball and spike tips CLEAR_BALL) and leans away from the horse (the ball on the side of the upper hand: at least OUT_MIN of the shaft's direction across the horse).
The bone is keyed in every UO action (location + quaternion, frames 1 + 3 i), the old keys of the bone are replaced (the calibrated rotations are kept in the action property
uo_polearm_cal, so that running the script again starts from the calibration, not from its own result).
"""
import json, math, os, sys
import numpy as np
import bpy
from mathutils import Matrix, Vector, Quaternion

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from bpy_compat import action_fcurves  # noqa: E402

BONE = "polearm.L"
GRIP_BELOW = 0.14        # m: the upper fist below the bottom of the ball (5 px at 36 px/m)
MOUNTED_EXTRA = 0.12     # m: lower in the mounted actions (23-29)
GRIP_EXTRA = ""          # "1:0.14,3:0.14": per action, m lower on the shaft than GRIP_BELOW (user, 2026-10: walk and run armed 5 px lower)
BUTT_MIN = 0.09          # m: in BUTT_ACTIONS the lower fist stays this far from the butt so that the end of the weapon still shows out of the hand (the fist is ~4.5 cm; the default HAND_END covers the butt)
BUTT_ACTIONS = ""        # "7,8,9": the actions that use BUTT_MIN instead of HAND_END
FRONT_ACTIONS = ""       # "1,3": the weapon is moved forward (away from the body, along the front of the chest) by the least amount at which the shaft does not enter the posed body
FRONT_CLEAR = 0.015      # m: the shaft stays this far outside the skin (the parts within FRONT_SKIP of a fist are left alone: the fists hold it there)
FRONT_SKIP = 0.14        # m
FRONT_MAX = 0.20         # m: the largest shift forward
UPPER = "L"              # the upper hand of the actions not in UPPER_R
UPPER_R = "8,12,13,15"   # actions whose upper hand is the right one (the original 2H weapon is held with the right hand above the left one)
SEP_MIN = 0.18           # m: fists closer than this do not define a line
SMOOTH = 0.7             # sigma in frames of the smoothing of the shaft direction (0 = none)
HAND_END = 0.05          # m: the lower fist stays this far from the butt, the upper one this far below the ball
FISTS_MIN_SHARE = 0.8    # an action in which the fists hold the weapon together in a smaller share of the frames uses the calibrated direction in all of them
SEP_BLEND = 0.10         # m: over this much of fist distance the weapon changes from the line of the fists to the calibrated direction
FALL_ACTIONS = "21,22"
FALL_FROM = 20.0         # deg of body tilt (pelvis -> head against the vertical) where the shaft starts to turn into the body axis
FALL_TO = 60.0           # deg: from here the shaft lies along the body
FLOOR = 0.04             # m: the lowest point of the weapon in a fall (the shaft is lifted to it)
MOUNTED_ACTIONS = "23,24,25,26,27,28,29"
CLEAR_SHAFT = 0.05       # m: the shaft stays this far from the horse proxy
CLEAR_BALL = 0.04        # m: the ball and the tips of the spikes stay this far from it
OUT_MIN = 0.35           # the ball points to the side of the upper hand: shaft direction . outward axis >= this (0.35 = 20 deg from the horse's mid plane)
MOUNT_DEV = 1.0          # weight (per rad) of the turn away from the line of the fists
REPORT = ""


def log(*a):
    print("uo_twohand:", *a)


def smooth_dirs(D, sigma, cyclic):
    """unit vectors (n, 3) smoothed in time (Gaussian on the vectors, renormalised)"""
    n = len(D)
    if sigma <= 0 or n < 3:
        return D
    k = np.arange(-3, 4); w = np.exp(-0.5 * (k / sigma) ** 2)
    out = np.zeros_like(D)
    for i in range(n):
        acc = np.zeros(3); tot = 0.0
        for kk, ww in zip(k, w):
            j = i + kk
            if cyclic:
                j %= n
            elif j < 0 or j >= n:
                continue
            acc += ww * D[j]; tot += ww
        out[i] = acc / tot
    return out / np.linalg.norm(out, axis=1, keepdims=True)


def unit(v):
    return v / np.linalg.norm(v)


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def slerp(a, b, t):
    """unit vectors a -> b by the fraction t along the shorter arc"""
    c = float(np.clip(a @ b, -1, 1)); th = math.acos(c)
    if th < 1e-6:
        return a
    if abs(math.pi - th) < 1e-3:                           # opposite: turn about any axis across
        ax = np.cross(a, [0, 0, 1.0]); ax = ax / np.linalg.norm(ax) if np.linalg.norm(ax) > 1e-6 else np.array([1.0, 0, 0])
        return a * math.cos(math.pi * t) + np.cross(ax, a) * math.sin(math.pi * t)
    return (a * math.sin((1 - t) * th) + b * math.sin(t * th)) / math.sin(th)


def horse_bvh(a, i):
    from mathutils.bvhtree import BVHTree
    o = bpy.data.objects.get("Horse_a%d_f%d" % (a, i))
    if o is None:
        return None
    V = [o.matrix_world @ v.co for v in o.data.vertices]
    return BVHTree.FromPolygons(V, [list(p.vertices) for p in o.data.polygons])


def signed_dist(bvh, p):
    loc, nor, idx, dist = bvh.find_nearest(Vector(p))
    if loc is None:
        return 9.0
    return dist if (Vector(p) - loc).dot(nor) >= 0 else -dist


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    paths, only, report, sets, i = [], None, REPORT, {}, 0
    while i < len(argv):
        if argv[i] == "--actions":
            only = argv[i + 1].split(","); i += 2
        elif argv[i] == "--report":
            report = argv[i + 1]; i += 2
        elif argv[i] == "--set":
            k, v = argv[i + 1].split("=", 1); sets[k] = v; i += 2
        else:
            paths.append(argv[i]); i += 1
    blend = os.path.abspath(paths[0]); outp = os.path.abspath(paths[1]) if len(paths) > 1 else blend
    for k, v in sets.items():
        if k not in globals():
            raise SystemExit("unknown setting %s" % k)
        globals()[k] = v if isinstance(globals()[k], str) else type(globals()[k])(v)
    upper_r = {int(x) for x in UPPER_R.split(",") if x}
    front_set = {int(x) for x in FRONT_ACTIONS.split(",") if x}
    butt_set = {int(x) for x in BUTT_ACTIONS.split(",") if x}
    extra = {int(k): float(v) for k, v in (kv.split(":") for kv in GRIP_EXTRA.split(",") if kv)}
    falls = {int(x) for x in FALL_ACTIONS.split(",") if x}
    mounted_set = {int(x) for x in MOUNTED_ACTIONS.split(",") if x}
    bpy.ops.wm.open_mainfile(filepath=blend)
    rig = bpy.data.objects["UO_Rig"]; sc = bpy.context.scene; body = bpy.data.objects["UO_Body"]
    WM = json.loads(bpy.data.texts["weapon_motion.json"].as_string())
    DIR = Vector(WM[BONE]["dir"]).normalized()
    PIV_L = Vector(WM[BONE]["pivot"]); PIV_R = Vector(WM["weapon1h.R"]["pivot"])
    item = next((o for o in bpy.data.collections["Clothing"].all_objects if o.type == "MESH" and BONE in o.vertex_groups), None)
    if item is None:
        raise SystemExit("no item bound to %s in Clothing" % BONE)
    # the weapon in the rest pose: s = distance along the shaft from the bone origin
    rig.data.pose_position = "REST"; bpy.context.view_layer.update()
    rb = rig.pose.bones[BONE]; O_rest = rb.matrix.translation.copy(); D_rest = (rb.matrix.to_3x3() @ DIR).normalized()
    s_v = np.array([(item.matrix_world @ v.co - O_rest).dot(D_rest) for v in item.data.vertices])
    s_min, s_max = float(s_v.min()), float(s_v.max())
    head = item.get("uo_head")
    if head is None:
        raise SystemExit("the item has no uo_head (run uo_spikes.py: the ball is needed for the grip)")
    s_butt = s_min                                             # the butt is the lowest vertex: z = 0
    s_ball = s_butt + float(head[2])                           # s of the bottom of the ball
    s_cen = s_butt + float(head[0]); r_ball = float(head[1]); tip_len = float(head[3] - head[0])
    sep_max = s_ball - 0.03 - s_butt - HAND_END
    log("weapon: butt s = %.3f m, ball bottom s = %.3f m, ball r %.3f m, top s = %.3f m (length %.3f m); the fists can be %.2f m apart at most" % (
        s_butt, s_ball, r_ball, s_max, s_max - s_butt, sep_max))
    rig.data.pose_position = "POSE"
    acts = sorted([a for a in bpy.data.actions if "uo_action" in a], key=lambda a: a["uo_action"])
    if only:
        acts = [a for a in acts if a.name in only or str(a["uo_action"]) in only]
    pb = rig.pose.bones
    x0_loc = Vector((1, 0, 0)); x0_loc = (x0_loc - DIR * x0_loc.dot(DIR)).normalized()
    A = np.array([x0_loc, DIR.cross(x0_loc), DIR]).T          # local frame of the weapon (columns) in bone-local coordinates
    data = {}; cal_err = 0.0
    # the calibrated rotation of the bone in every frame (the keys of the file as it came; kept in the action property uo_polearm_cal so that a second run does not read its own keys)
    cal_keys = {}; fresh = set()
    for act in acts:
        a = int(act["uo_action"]); n = int(act["uo_frames"])
        if "uo_polearm_cal" not in act:
            fresh.add(a)
            fcs = {(f.data_path, f.array_index): f for f in action_fcurves(act) if f.data_path == 'pose.bones["%s"].rotation_quaternion' % BONE}
            if len(fcs) != 4:
                raise SystemExit("action %s has no rotation keys of %s" % (act.name, BONE))
            act["uo_polearm_cal"] = [[fcs[(f'pose.bones["{BONE}"].rotation_quaternion', k)].evaluate(1 + 3 * i) for k in range(4)] for i in range(n)]
        cal_keys[a] = [list(q) for q in act["uo_polearm_cal"]]
    # pass 1: the body per frame
    for act in acts:
        a = int(act["uo_action"]); n = int(act["uo_frames"]); rig.animation_data.action = act
        rows = []
        for i in range(n):
            sc.frame_set(1 + 3 * i); bpy.context.view_layer.update()
            W = rig.matrix_world
            hl = W @ pb["hand.L"].matrix; hr = W @ pb["hand.R"].matrix; ch = W @ pb["chest"].matrix
            tl = (W @ pb["thigh.L"].matrix).translation; tr = (W @ pb["thigh.R"].matrix).translation
            cal = np.array(hl.to_3x3().normalized() @ (Quaternion(cal_keys[a][i]).to_matrix() @ DIR))   # the direction of the calibrated halberd line in this frame (the turn of the bone, then the hand's own)
            if a in fresh:                                    # the file as it came: the formula must give the direction the bone really has
                got = np.array((rig.matrix_world @ pb[BONE].matrix).to_3x3() @ DIR); got /= np.linalg.norm(got)
                cal_err = max(cal_err, math.degrees(math.acos(float(np.clip(got @ cal / np.linalg.norm(cal), -1, 1)))))
            fwd = None; bvh = None
            if a in front_set:                                # the front of the chest (horizontal) and the posed skin
                from mathutils.bvhtree import BVHTree
                lat = (W @ pb["upper_arm.L"].matrix).translation - (W @ pb["upper_arm.R"].matrix).translation
                lat.z = 0; fwd = np.array(lat.normalized().cross(Vector((0, 0, 1))))
                dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh()
                bvh = BVHTree.FromPolygons([ev.matrix_world @ v.co for v in me.vertices], [list(pl.vertices) for pl in me.polygons]); ev.to_mesh_clear()
            rows.append(dict(fwd=fwd, bvh=bvh, gL=np.array(hl @ PIV_L), gR=np.array(hr @ PIV_R), fist=cal.astype(float), chest_x=np.array(ch.to_3x3().col[0]), chest_y=np.array(ch.to_3x3().col[1]),
                             head=np.array((W @ pb["head"].matrix).translation), pelvis=np.array((W @ pb["pelvis"].matrix).translation),
                             left=np.array(tl - tr)))
        data[a] = rows
    if fresh:
        log("calibrated halberd direction rebuilt from the keys: at most %.2f deg off the bone" % cal_err)
        if cal_err > 1.0:
            raise SystemExit("the calibrated direction does not match the bone")
    # pass 2: the weapon per frame
    plan = {}
    stats = {}
    for act in acts:
        a = int(act["uo_action"]); rows = data[a]; n = len(rows)
        upper = "R" if a in upper_r else UPPER
        cyc = a in (0, 1, 2, 3, 4, 5, 6, 7, 8, 15, 23, 24, 25)
        is_mounted = a in mounted_set
        sep = np.zeros(n); GU = np.zeros((n, 3)); Dboth = np.zeros((n, 3)); Dfist = np.zeros((n, 3))
        for i, r in enumerate(rows):
            gu, gl = (r["gR"], r["gL"]) if upper == "R" else (r["gL"], r["gR"])
            v = gu - gl; sep[i] = np.linalg.norm(v)
            Dboth[i] = v / max(sep[i], 1e-6); GU[i] = gu
            Dfist[i] = unit(r["fist"])
        # how much the fists define the line: 1 inside [SEP_MIN, sep_max], blended out over SEP_BLEND outside
        wb = smoothstep((sep - SEP_MIN) / SEP_BLEND) * (1 - smoothstep((sep - sep_max) / SEP_BLEND))
        if wb.mean() < FISTS_MIN_SHARE and wb.min() < 0.5:    # an action in which the fists mostly cannot hold the weapon together (spells, swings with the arms wide): one steady line (the axis of the fist), no switching between two lines
            wb = np.zeros(n)
        D0 = np.array([unit(slerp(Dfist[i], Dboth[i], wb[i])) for i in range(n)])
        D = D0.copy()
        notes = []
        if a in falls:
            tilt = np.array([math.degrees(math.acos(np.clip(unit(r["head"] - r["pelvis"])[2], -1, 1))) for r in rows])
            wf = smoothstep((tilt - FALL_FROM) / (FALL_TO - FALL_FROM))
            for i, r in enumerate(rows):
                D[i] = slerp(D0[i], unit(r["head"] - r["pelvis"]), wf[i])
            notes.append("along the body from %d of %d frames" % (int((wf > 0.99).argmax()) if (wf > 0.99).any() else n, n))
        want = np.full(n, s_ball - GRIP_BELOW - (MOUNTED_EXTRA if is_mounted else 0.0) - extra.get(a, 0.0))
        Dsm = smooth_dirs(D, SMOOTH, cyc)
        if a in falls or is_mounted:
            D = Dsm
        else:                                                 # where the fists define the line it is exact (smoothing it pulled the lower fist 10-25 cm off the shaft in the fast swings); smoothed only where they do not
            D = np.array([unit(slerp(Dsm[i], D[i], wb[i] ** 2)) for i in range(n)])
        if is_mounted:
            D, info = mounted_dirs(a, rows, GU, D, want, s_butt, s_ball, s_cen, r_ball, tip_len, upper)
            D = smooth_dirs(D, SMOOTH, cyc)
            notes.append(info)
        s_up = np.zeros(n)
        for i in range(n):
            if wb[i] > 0.5 and not is_mounted and a not in falls:         # both fists on the shaft: the lower one stays on it
                lo = s_butt + (BUTT_MIN if a in butt_set else HAND_END) + sep[i]; hi = s_ball - 0.03
                s_up[i] = min(max(want[i], lo), max(hi, lo))
            else:
                s_up[i] = want[i]
        O = GU - D * s_up[:, None]                            # bone origin: the upper fist is s_up along the shaft
        if a in front_set:                                    # forward by the least shift at which the shaft is outside the skin
            shift = np.zeros(n)
            for i, r in enumerate(rows):
                ss = np.arange(s_butt, s_ball, 0.04)
                for dlt in np.arange(0.0, FRONT_MAX + 1e-9, 0.005):
                    lo_g = r["gR"] if upper == "L" else r["gL"]
                    pts = [q for q in (O[i] + D[i] * x + r["fwd"] * dlt for x in ss)
                           if np.linalg.norm(q - GU[i]) > FRONT_SKIP and np.linalg.norm(q - lo_g) > FRONT_SKIP]
                    if all(signed_dist(r["bvh"], p) >= FRONT_CLEAR for p in pts):
                        break
                shift[i] = dlt
            shift = np.max([shift, np.roll(shift, 1) * 0.5, np.roll(shift, -1) * 0.5], axis=0) if a in (0, 1, 2, 3, 4, 5, 6, 7, 8, 15, 23, 24, 25) else shift
            O = O + np.array([r["fwd"] for r in rows]) * shift[:, None]
            notes.append("forward %.0f-%.0f mm to leave the body (%s)" % (1000 * shift.min(), 1000 * shift.max(), " ".join("%.0f" % (1000 * x) for x in shift)))
        if a in falls:                                        # not into the floor
            for i in range(n):
                pts = [O[i] + D[i] * s for s in (s_butt, s_cen)]
                lift = FLOOR - min(p[2] for p in pts)
                if lift > 0:
                    O[i][2] += lift
        Rw = []
        for i, r in enumerate(rows):
            cx, cy = unit(r["chest_x"]), unit(r["chest_y"])                # the turn about the shaft follows the chest: its sideways axis, or its forward axis when the shaft
            px, py = 1 - (cx @ D[i]) ** 2, 1 - (cy @ D[i]) ** 2             # lies across the chest (blended by how far each is from the shaft's direction: continuous)
            ref = cx * px ** 2 + cy * py ** 2 * 1.0
            x = unit(ref - D[i] * (ref @ D[i]))
            B = np.array([x, np.cross(D[i], x), D[i]]).T
            Rw.append(B @ A.T)
        plan[a] = (O, Rw, D)
        if a in falls:
            ang = [math.degrees(math.acos(np.clip(D[i] @ unit(rows[i]["head"] - rows[i]["pelvis"]), -1, 1))) for i in range(n)]
            notes.append("last frame %.0f deg from the body axis" % ang[-1])
        gl_ = np.array([(r["gR"] if upper == "L" else r["gL"]) for r in rows])           # the lower fist: how far from the shaft line
        off = np.linalg.norm(np.cross(gl_ - GU, D), axis=1)
        held = wb > 0.5
        prot = (s_up - np.where(held, sep, 0.0) - s_butt) * 100 if held.any() else None        # how far the end of the weapon sticks out beyond the lower fist (cm)
        turn = np.degrees(np.arccos(np.clip((D[1:] * D[:-1]).sum(1), -1, 1))) if n > 1 else np.zeros(1)
        tl_ = np.degrees(np.arccos(np.clip(D[:, 2], -1, 1)))
        stats[a] = dict(frames=n, upper=upper, sep_cm=[float(sep.min() * 100), float(sep.max() * 100)], max_turn_deg=float(turn.max()) if len(turn) else 0.0,
                        butt_beyond_fist_cm=[float(prot[held].min()), float(prot[held].max())] if held.any() else None, axis_err_last_deg=float(ang[-1]) if a in falls else None, fists_define=float(wb.mean()), lower_fist_off_cm=[float(off[held].mean() * 100), float(off[held].max() * 100)] if held.any() else None, tilt_deg=[float(tl_.min()), float(tl_.max())], notes=notes)
        log("action %2d %-22s upper %s sep %.0f-%.0f cm (fists define the line in %.0f%%), turn per frame <= %.0f deg, tilt %.0f-%.0f deg, lower fist %s off the shaft, end beyond the fist %s %s" % (
            a, act.name[3:], upper, stats[a]["sep_cm"][0], stats[a]["sep_cm"][1], 100 * wb.mean(), stats[a]["max_turn_deg"], *stats[a]["tilt_deg"],
            "%.1f / %.1f cm" % tuple(stats[a]["lower_fist_off_cm"]) if stats[a]["lower_fist_off_cm"] else "-",
            "%.0f-%.0f cm" % tuple(stats[a]["butt_beyond_fist_cm"]) if stats[a]["butt_beyond_fist_cm"] else "-", "; ".join(notes)))
    # pass 3: key the bone
    bone = pb[BONE]; bone.rotation_mode = "QUATERNION"
    for act in acts:
        a = int(act["uo_action"]); n = int(act["uo_frames"]); rig.animation_data.action = act
        for fc in [f for f in action_fcurves(act) if f.data_path.startswith('pose.bones["%s"]' % BONE)]:
            act.fcurves.remove(fc)
        O, Rw, _ = plan[a]
        prev = None
        for i in range(n):
            sc.frame_set(1 + 3 * i); bpy.context.view_layer.update()
            M = Matrix.Identity(4)
            for r in range(3):
                for c in range(3):
                    M[r][c] = Rw[i][r][c]
            M.translation = Vector(O[i])
            bone.matrix = M
            q = bone.rotation_quaternion.copy()
            if prev is not None and q.dot(prev) < 0:
                q.negate()
            bone.rotation_quaternion = q; prev = q.copy()
            bone.keyframe_insert("location", frame=1 + 3 * i, group=BONE)
            bone.keyframe_insert("rotation_quaternion", frame=1 + 3 * i, group=BONE)
    # check: what Blender evaluates against the target
    maxerr = 0.0
    for act in acts:
        a = int(act["uo_action"]); n = int(act["uo_frames"]); rig.animation_data.action = act
        O, Rw, D = plan[a]
        for i in range(n):
            sc.frame_set(1 + 3 * i); bpy.context.view_layer.update()
            M = rig.matrix_world @ bone.matrix
            e = (np.array(M.translation) - O[i])
            d_got = np.array(M.to_3x3() @ DIR)
            maxerr = max(maxerr, float(np.linalg.norm(e)), float(np.linalg.norm(d_got / np.linalg.norm(d_got) - D[i])))
    log("check: the keyed bone differs from the target by at most %.4f (m / unit vector)" % maxerr)
    if maxerr > 0.01:
        raise SystemExit("keyed bone does not match the target")
    if report:
        json.dump(stats, open(report, "w"), indent=1)
    bpy.ops.wm.save_as_mainfile(filepath=outp)
    log("saved", outp)


def mounted_dirs(a, rows, GU, D0, want, s_butt, s_ball, s_cen, r_ball, tip_len, upper):
    """per frame the direction nearest to D0 in which the weapon clears the horse proxy and leans away from the horse (outwards = the side of the upper hand)"""
    n = len(rows); out = D0.copy(); worst = 0.0; moved = 0
    for i, r in enumerate(rows):
        bvh = horse_bvh(a, i)
        if bvh is None:
            continue
        lat = np.array([r["left"][0], r["left"][1], 0.0]); lat = unit(lat) * (1 if upper == "L" else -1)       # outwards: to the left of the rider for the left hand
        gu = GU[i]; su = want[i]
        sh_s = np.arange(s_butt, s_ball + 1e-6, 0.06)
        spike = [np.array(v) for v in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0))]

        def cost(d):
            x = np.cross(d, [0, 0, 1.0]); x = x / np.linalg.norm(x) if np.linalg.norm(x) > 1e-6 else np.array([1.0, 0, 0]); y = np.cross(d, x)
            pen = 0.0
            for s in sh_s:                                    # the clearance grows with the distance from the grip (the hand itself may be next to the horse)
                pen += max(0.0, CLEAR_SHAFT * smoothstep((abs(s - su) - 0.1) / 0.3) - signed_dist(bvh, gu + d * (s - su)))
            c = gu + d * (s_cen - su)
            pen += 2.0 * max(0.0, r_ball + CLEAR_BALL - signed_dist(bvh, c))
            for ax in (d, x, -x, y, -y):
                pen += max(0.0, CLEAR_BALL - signed_dist(bvh, c + ax * tip_len * 0.9))
            dev = math.acos(np.clip(d @ D0[i], -1, 1))
            return 30.0 * pen + MOUNT_DEV * dev + 2.0 * max(0.0, OUT_MIN - d @ lat) + 1.0 * max(0.0, -d[2]), pen
        best = (cost(D0[i])[0], D0[i])
        cands = []
        for tilt in range(0, 131, 10):
            for az in range(0, 360, 15):
                t = math.radians(tilt); p = math.radians(az)
                cands.append(np.array([math.sin(t) * math.cos(p), math.sin(t) * math.sin(p), math.cos(t)]))
        for d in cands:
            c = cost(d)[0]
            if c < best[0]:
                best = (c, d)
        d_best = best[1]                                      # refine around the best
        for step in (6.0, 3.0, 1.5):
            base = d_best; ax1 = np.cross(base, [0, 0, 1.0]); ax1 = ax1 / np.linalg.norm(ax1) if np.linalg.norm(ax1) > 1e-6 else np.array([1.0, 0, 0]); ax2 = np.cross(base, ax1)
            for u in (-2, -1, 0, 1, 2):
                for v in (-2, -1, 0, 1, 2):
                    d = unit(base + math.tan(math.radians(step)) * (u * ax1 + v * ax2))
                    c = cost(d)[0]
                    if c < best[0]:
                        best = (c, d)
            d_best = best[1]
        out[i] = d_best
        moved += int(math.degrees(math.acos(np.clip(d_best @ D0[i], -1, 1))) > 3)
        worst = max(worst, cost(d_best)[1])
    return out, "horse: %d of %d frames turned away from the line of the fists, worst intrusion %.0f mm" % (moved, n, 1000 * worst)


main()
