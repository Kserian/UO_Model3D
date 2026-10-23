"""Cloth simulation for loose garments (robe, dress, skirt, kilt), on top of the kinematic result: the hanging cloth settles, swings and COLLIDES with the posed body.

    python uo_cloth_sim.py ITEM.blend [--actions 00_walk_unarmed,02_run_unarmed,...|all] [--out cloth_sim.npz] [--jobs 4] [key=value ...]

ITEM.blend = the item prepared and bound (uo_make_item.py: item.blend with PART robe / skirt, custom property uo_cloth). Per action and frame the kinematic target is what the renderer
would draw without a simulation: the item as the skeleton skins it + the push of the legs (cloth_lib.hull_push, the same call and settings as render_uo_layer.cloth_push). A copy of the item
(a plain mesh) is simulated with Blender's Cloth: every vertex is held by a spring ("goal", the pin weight) to the target of the current frame, 1 at the waist and above (the cloth follows
the body there), falling to GOAL at the hem (the hanging part is free to swing and fold), and the cloth collides with the posed UO_Body (legs, arms, hands). The result is saved as the
DIFFERENCE between the simulation and the target (cloth_sim.npz next to the item, keys "<action>_<frame>"): render_uo_layer.py adds it to the leg push (CLOTH_SIM = 1), then BODY_GAP
pushes whatever is still inside the body out, as before. Mounted actions (23-29) are not simulated (the hem follows the legs there), nor the falls 21, 22 when the scene has uo_cloth_lie > 0.

Every action is simulated on its own: PREROLL frames in its first pose (looping actions: the pose of the loop), looping actions (walk, run, stand, combat idle) CYCLES cycles and the last one is
kept, so the loop closes without a jump. Settings (key=value): fabric (silk, cotton, wool, denim, leather: mass, stiffness, bending, damping at once; the keys below override it), cull (0; 1 = the collider is single sided: the cloth collision respects the collider's normals, Blender: improves penetration recovery), usenormal (0; 1 = collision impulses along the collider's normals), cq (4; collision quality of Blender's cloth: iterations of the contact solver), env (0; kappa of a last pass that keeps the simulated cloth inside-out of the shadow of the legs, cloth_lib.hull_push on the simulated points: a leg in full stride does not come out of the hem), env_margin (0.02 m beyond the legs' reach), env_tent (0 = no tent: the cloth above is not pulled out), mounted (0; 1 = the riding actions 23-29 are simulated too: the target is the rider's, the hanging part lies along the legs as render_uo_layer.py CLOTH_MOUNTED does, and the cloth collides with the horse proxy Horse_a<action>_f<frame>; horse=0: no collision with the horse, the renderer's HORSE_HOLDOUT only cuts the cloth where the horse is in front), pushw (1; the pin holds skinned + pushw x the push of the legs: 0 = the cloth hangs from the pelvis and the legs push it out by collision only, the result is still stored against the full target), gravity (1; x the scene's gravity: a heavier fall of the free cloth), bscale (1; x the bending stiffness: like the damping it is not scaled with the vertex mass, with mscale 0.033 the cloth is ~30 x too stiff against its weight and the hem a leg lifted does not fall back: walk +0.26 m cotton, +0.47 m wool, silk +0.04), dscale (1; x the damping (air and internal): damping is not scaled with the mass of a vertex, so with mscale 0.033 take dscale 0.033 too, or the cloth is ~30 x over-damped and does not fall back after a leg lifts it), mscale (1; x the mass of a vertex: Blender's presets assume ~0.3 kg per vertex, a 24k-vertex robe hangs with ~0.01 kg = mscale 0.033; free cloth, goal 0.2, thick 0.006, dist 0.002), goal (0.4), upper (1.0), ramp (0.30 m from the waist down to GOAL), quality (8), mass (0.3 per vertex), density (kg/m2 of the cloth; > 0 = the mass of a vertex is density x area of the item / vertices, so a fine mesh weighs what the fabric weighs; the fabrics set it, 0 = mass as given), tension / compression (15), shear (5), bending (0.5),
damp_air (1), tdamp (5), dist (0.005), preroll (40), cycles (3), self_collision (0), friction (0), arm_goal (0.7; -1 = sleeves as the rest above the waist; 0-1 = their own goal), arm_x (0.19 m from the middle: where the sleeves start), arm_zmin (the sleeves are the vertices above this height; default 0.05 m below the waist: long bell sleeves that hang below it need e.g. 0.55), thick (0.02 m: the outer thickness of the body as a collider; a fast leg tunnels through the cloth with a thin one: leg pixels through the robe in the run 466 at 0.005 m, 196 at 0.02, 147 with dist 0.02 too but 3 x slower), smooth (0 m; > 0 = the simulation's move averaged over this distance in space, 2 passes: neighbouring pleats that cross each other in the simulation opened slits
through which the legs showed; 0.04 m on a robe made by a cloth simulator: leg pixels through the robe in walk 44 -> 12), in_max (0.01 m: below the waist the cloth may move at most this much TOWARDS the axis of the pelvis against the target: the target already holds it just outside the legs' reach, and a
simulated hem that lagged inwards let a foot come out through it in the run; < 0 = no limit), max_move (0.12 m: the most the cloth may differ from the kinematic target, soft limit; 0 = none). Measured on the replica of the original robe 469 (robe_cloth_sim_test.py, hybrid=1):
lower-body IoU walk 0.754 -> 0.765, run 0.731 -> 0.735 against the kinematic result; the simulation alone (no goal) collapses in walk and run.
"""
import json, math, os, sys, time
import numpy as np
import bpy

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import cloth_lib as cl                                                      # noqa: E402
from bpy_compat import action_fcurves                                       # noqa: E402 (Blender 5.x: no Action.fcurves)

STEP = 3
MOUNTED = False                                                                 # key mounted=1: the riding actions 23-29 are simulated too (against the horse of the frame)
LOOP = {0, 1, 2, 3, 4, 5, 6, 7, 8}
FABRIC = {            # mass / stiffness / bending / damping per fabric, after Blender's cloth presets (scripts/presets/cloth: Cotton, Denim, Leather, Silk; wool is ours, between cotton and denim).
                      # The in-plane stiffness (tension, compression, shear) is 5 for all of them, not the presets' 15-80: with the leg-hull target stretched under the legs (edges up to 2 x),
                      # a stiffer cloth is pulled up towards the waist by the pin and does not fall back (cotton at 15: the hem +0.26 m in the walk, wool at 25: +0.47 m, at 5: +0.04 m); mass, bending
                      # and damping are what tell the fabrics apart. Stiffer values can be given as keys (tension=...).
    "silk":    dict(mass=0.15, tension=5.0, compression=5.0, shear=5.0, bending=0.05, tdamp=1.0),
    "cotton":  dict(mass=0.3,  tension=5.0, compression=5.0, shear=5.0, bending=0.5,  tdamp=5.0),
    "wool":    dict(mass=0.5,  tension=5.0, compression=5.0, shear=5.0, bending=2.0,  tdamp=10.0),
    "denim":   dict(mass=1.0,  tension=5.0, compression=5.0, shear=5.0, bending=10.0, tdamp=25.0),
    "leather": dict(mass=0.4,  tension=5.0, compression=5.0, shear=5.0, bending=150.0, tdamp=25.0),
}
CFG = dict(goal=0.4, upper=1.0, ramp=0.30, quality=8, mass=0.3, tension=15.0, compression=15.0, shear=5.0, bending=0.5, damp_air=1.0, tdamp=5.0, density=0.0, mscale=1.0, dscale=1.0, bscale=1.0, cq=4.0, cull=0.0, usenormal=0.0, mounted=0.0, horse=1.0, env=0.0, env_margin=0.02, env_tent=0.0, pushw=1.0, gravity=1.0, dist=0.005, preroll=40, cycles=3,
           self_collision=0, friction=0.0, wind=0.0, goal_run=0.1, ground=1.0, swing=0.6, swing_top=0.25, wind_noise=1.0, band=0.1, hem_goal=0.0, ramp_cloak=0.2, arm_goal=0.7, arm_x=0.19, arm_zmin=-9.0, max_move=0.12, thick=0.02, in_max=0.01, smooth=0.0)


LIFT = {2, 3, 23, 24, 25, 26, 27, 28, 29}                                                   # cloak: the actions in which the lower cape is pulled (weakly) to the lifted shape of uo_cloak_motion.py (the run, the ride); elsewhere it hangs under its own weight
MOTION = {}                                                                          # cloak: {"a_i": world displacement} of uo_cloak_motion.py when cloak_motion.npz is next to the item
PITCH = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "cloak_pitch.json")))     # cloak: swing back about the shoulders per action and frame (original cloak 468)
WIND = {0: 0.25, 1: 0.25, 15: 0.25, 23: 0.3, 2: 0.8, 3: 0.8, 24: 1.0, 26: 0.35, 27: 0.35, 28: 0.35, 29: 0.35}   # cloak: wind from the front (the cape is blown back) per action: a gentle breath in walking, hard in running and
                                                                                                                  # fast riding, 0 where the body stands still; multiplied by the key wind (the strength of Blender's wind field)


def is_cloak():
    """the item is a cape (uo_bind_item.py PART cloak): pinned at the shoulders, blown by the wind of WIND, simulated in every action including riding and falls"""
    return any(o.type == "MESH" and json.loads(o["uo_cloth"]).get("type") == "cloak" for o in bpy.data.collections["Clothing"].all_objects if o.get("uo_cloth"))


def skip(a):
    """actions not simulated: riding (the hem follows the legs there) and the falls when the item lies along the legs (render_uo_layer.py CLOTH_LIE, scene property uo_cloth_lie); a cloak is simulated everywhere"""
    if is_cloak():
        return False
    return (23 <= a <= 29 and not MOUNTED) or (a in (21, 22) and float(bpy.context.scene.get("uo_cloth_lie", 0)) > 0)


def run_parallel(blend, out, only, jobs, extra):
    """the actions are independent: split them over `jobs` processes (the same script) and merge the results"""
    import subprocess, tempfile
    bpy.ops.wm.open_mainfile(filepath=blend)
    names = [a.name for a in sorted([a for a in bpy.data.actions if "uo_action" in a], key=lambda a: int(a["uo_action"])) if not skip(int(a["uo_action"])) and (only is None or a.name in only)]
    groups = [names[k::jobs] for k in range(jobs)]
    tmp = tempfile.mkdtemp(prefix="uo_cloth_sim_"); procs = []
    for k, g in enumerate(groups):
        if g:
            procs.append((k, subprocess.Popen([sys.executable, os.path.abspath(__file__), blend, "--actions", ",".join(g), "--out", os.path.join(tmp, "p%d.npz" % k)] + extra,
                                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)))
    merged = {}
    for k, p in procs:
        txt = p.communicate()[0]
        print("".join(l + "\n" for l in txt.splitlines() if l.startswith(("action", "uo_cloth_sim"))), end="", flush=True)
        f = os.path.join(tmp, "p%d.npz" % k)
        if not os.path.exists(f):
            raise SystemExit("worker %d failed:\n%s" % (k, txt[-1500:]))
        z = np.load(f); merged.update({n: z[n] for n in z.files})
    np.savez_compressed(out, **merged)
    print("wrote", out, "(%d frames, %d processes)" % (len(merged), len(procs)))


def main():
    args = sys.argv[1:]
    blend = os.path.abspath(args.pop(0)); out = None; only = None; cfg = dict(CFG); jobs = 1; extra = []; own = {}
    while args:
        a = args.pop(0)
        if a == "--out":
            out = os.path.abspath(args.pop(0))
        elif a == "--actions":
            v = args.pop(0); only = None if v == "all" else set(v.split(","))
        elif a == "--jobs":
            jobs = int(args.pop(0))
        elif a.startswith("fabric="):
            fab = a.split("=", 1)[1]; extra.append(a)
            if fab not in FABRIC:
                raise SystemExit("fabric %s unknown: %s" % (fab, ", ".join(FABRIC)))
            cfg.update(FABRIC[fab])
        elif "=" in a:
            k, v = a.split("=", 1); own[k] = float(v); extra.append(a)
    global MOUNTED
    cfg.update(own); MOUNTED = bool(cfg["mounted"])                                                             # fabric preset first, then the settings named one by one
    out = out or os.path.join(os.path.dirname(blend), "cloth_sim.npz")
    mf = os.path.join(os.path.dirname(blend), "cloak_motion.npz")
    if os.path.exists(mf) and not cfg.get("nomotion"):
        z = np.load(mf); MOTION.update({k: z[k] for k in z.files}); print("uo_cloth_sim: pin target = the motion of uo_cloak_motion.py (%s, %d frames)" % (mf, len(MOTION)), flush=True)
    if jobs > 1:
        return run_parallel(blend, out, only, jobs, extra)
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc = bpy.context.scene; rig = bpy.data.objects["UO_Rig"]; body = bpy.data.objects["UO_Body"]
    items = [o for o in bpy.data.collections["Clothing"].all_objects if o.type == "MESH" and o.get("uo_cloth")]
    if not items:
        raise SystemExit("no loose garment (custom property uo_cloth) in the Clothing collection")
    item = items[0]; prm = json.loads(item["uo_cloth"]); nv = len(item.data.vertices); cloak = prm.get("type") == "cloak"
    if cloak:                                                                  # a cape flies far from the body: no limit on how far from the target; no legs hull (in_max)
        for k, v in (("max_move", 0.0), ("in_max", -1.0)):
            if k not in own:
                cfg[k] = v
    print("uo_cloth_sim: item %s, %d vertices, hem %.2f m, waist %.2f m" % (item.name, nv, prm["z_hem"], prm["z_top"]), flush=True)
    for o in bpy.data.objects:
        if o.type == "MESH" and o not in (body, item) and "Clothing" not in [c.name for c in o.users_collection]:
            o.hide_viewport = True
    for o in items[1:]:
        o.hide_viewport = True
    rig.data.pose_position = "POSE"

    # --- legs as capsules, as render_uo_layer.cloth_ctx builds them ---------------------------------------------------------------------------------------------------------
    names = list(cl.Capsules.NAMES) + ["pelvis", "chest"]
    Mr0 = np.array(rig.matrix_world)
    rest_h = np.array([(Mr0 @ np.append(np.array(rig.data.bones[n].head_local), 1))[:3] for n in names])
    rest_t = np.array([(Mr0 @ np.append(np.array(rig.data.bones[n].tail_local), 1))[:3] for n in names])
    rig.data.pose_position = "REST"; bpy.context.view_layer.update()
    me = body.data
    co = np.empty(len(me.vertices) * 3, np.float32); (me.shape_keys.key_blocks[0].data if me.shape_keys else me.vertices).foreach_get("co", co)
    Mb = np.array(body.matrix_world); Vb = co.reshape(-1, 3).astype(np.float64) @ Mb[:3, :3].T + Mb[:3, 3]
    gn = {g.index: g.name for g in body.vertex_groups}
    dom = np.array([gn[max(v.groups, key=lambda g: g.weight).group] if v.groups else "" for v in me.vertices])
    caps = cl.Capsules(names, rest_h, rest_t, Vb, dom)
    inv_local = {n: np.linalg.inv(np.array(rig.data.bones[n].matrix_local)) for n in names}
    sel = np.array(["pelvis" not in names[k] for k in caps.idx])
    # the item at rest (the coordinates cloth_push works with)
    co = np.empty(nv * 3, np.float32); item.data.vertices.foreach_get("co", co)
    Mi = np.array(item.matrix_basis); Vr = co.reshape(-1, 3).astype(np.float64) @ Mi[:3, :3].T + Mi[:3, 3]
    rig.data.pose_position = "POSE"; bpy.context.view_layer.update()

    def leg_state():
        dg = bpy.context.evaluated_depsgraph_get(); evr = rig.evaluated_get(dg)
        skin = {n: Mr0 @ np.array(evr.pose.bones[n].matrix) @ inv_local[n] @ np.linalg.inv(Mr0) for n in names}
        heads = np.array([(skin[names[k]] @ np.append(caps.head[j], 1))[:3] for j, k in enumerate(caps.idx)])
        tails = np.array([(skin[names[k]] @ np.append(caps.tail[j], 1))[:3] for j, k in enumerate(caps.idx)])
        return skin, heads, tails

    def envelope(X):
        """the simulated cloth never pokes out of the shadow of the legs (cloth_lib.hull_push on the simulated points, in the rest frame of the pelvis): a leg in full stride does not come out of the hem"""
        skin, heads, tails = leg_state(); S = skin["pelvis"]
        Xr = (np.c_[X, np.ones(len(X))] @ np.linalg.inv(S).T)[:, :3]
        return X + cl.hull_push(Xr, S, heads[sel], tails[sel], caps.radius[sel], centre_xy=tuple(prm["centre"]), margin=cfg["env_margin"], kappa=cfg["env"], z_top=prm["z_top"], z_hem=prm["z_hem"],
                                ramp=prm.get("ramp", 0.15), drop=prm.get("drop", 1.0), use_tent=bool(cfg["env_tent"]))

    def hull_push_now():
        skin, heads, tails = leg_state()
        if prm.get("hull") == "rel":
            return cl.hull_push_rel(Vr, skin["pelvis"], heads[sel], tails[sel], caps.radius[sel], caps.head[sel], caps.tail[sel], centre_xy=tuple(prm["centre"]), kappa=prm["kappa"],
                                    z_top=prm["z_top"], z_hem=prm["z_hem"], ramp=prm.get("ramp", 0.15), drop=prm.get("drop", 1.0))
        return cl.hull_push(Vr, skin["pelvis"], heads[sel], tails[sel], caps.radius[sel], centre_xy=tuple(prm["centre"]), margin=prm["margin"], kappa=prm["kappa"],
                            z_top=prm["z_top"], z_hem=prm["z_hem"], ramp=prm.get("ramp", 0.15), drop=prm.get("drop", 1.0))

    state = {"a": 0}

    def mounted_lie():
        """what render_uo_layer.cloth_push gives the hanging part in the mounted actions (CLOTH_MOUNTED = 1): it follows the legs of the skin under it, rest-world coordinates"""
        dg = bpy.context.evaluated_depsgraph_get(); evr = rig.evaluated_get(dg)
        skin = {n: Mr0 @ np.array(evr.pose.bones[n].matrix) @ inv_local[n] @ np.linalg.inv(Mr0) for n in names}
        Vh = np.c_[Vr, np.ones(nv)]; Pp = (Vh @ skin["pelvis"].T)[:, :3]; d0 = np.zeros_like(Vr)
        if all(("uo_leg_" + nm) in item.data.attributes for nm in cl.Capsules.NAMES):
            for nm in cl.Capsules.NAMES:
                w = np.empty(nv, np.float32); item.data.attributes["uo_leg_" + nm].data.foreach_get("value", w)
                d0 += w[:, None] * ((Vh @ skin[nm].T)[:, :3] - Pp)
        else:
            side = np.clip(Vr[:, 0] / 0.06, -1, 1) * 0.5 + 0.5; ws = np.clip((0.58 - Vr[:, 2]) / 0.15, 0, 1)[:, None]
            leg = lambda sd: (1 - ws) * (Vh @ skin["thigh." + sd].T)[:, :3] + ws * (Vh @ skin["shin." + sd].T)[:, :3]
            d0 = np.clip((prm["z_top"] - Vr[:, 2]) / 0.2, 0, 1)[:, None] * ((1 - side)[:, None] * leg("L") + side[:, None] * leg("R") - Pp)
        return d0

    def kinematic():
        """the item as the renderer draws it before the simulation: skinned + the push of the legs, world coordinates; and the target the pin holds: skinned + pushw x the push"""
        dg = bpy.context.evaluated_depsgraph_get(); ev = item.evaluated_get(dg)
        c = np.empty(nv * 3, np.float32); ev.data.vertices.foreach_get("co", c)
        M = np.array(item.matrix_world)
        sk = c.reshape(-1, 3).astype(np.float64) @ M[:3, :3].T + M[:3, 3]
        if cloak and MOTION and state["a"] in LIFT:                             # hybrid: the pin pulls to the smooth motion of uo_cloak_motion.py (cloak_motion.npz next to the item); the solver adds the lag, the weight and the soft folds
            m = MOTION.get("%d_%d" % (state["a"], state["i"]))
            if m is not None and len(m) == len(sk):
                return sk, sk + m
        if cloak:                                                               # a cape hangs from the shoulders as the skin of the chest moves them; no push of the legs. The pin of the hanging part pulls
            rows = PITCH["actions"].get(str(state["a"]))                        # (weakly) to the cape swung back about the shoulders as in the original cloak 468 (cloak_pitch.json, x swing): the gait
            if not rows or cfg["swing"] <= 0:                                   # sets how far the wind lifts it, the cloth makes the folds and meets the body and the horse
                return sk, sk
            d0, d1 = (np.radians(x) * cfg["swing"] for x in rows[min(state["i"], len(rows) - 1)])
            d0 *= cfg["swing_top"]                                              # the cape lifts from the lower back: the shoulders and the upper back stay on the body
            skin, _, _ = leg_state()
            d = cl.cloak_bend(Vr, prm["z_top"], prm["z_hem"], prm["y_top"], d0, d1)
            return sk, sk + d @ skin["chest"][:3, :3].T
        if 23 <= state["a"] <= 29:                                              # riding: the hanging part lies along the legs (the same d0 as render_uo_layer.cloth_push), the pin holds all of it
            push = mounted_lie()
            return sk + push, sk + push
        push = hull_push_now()
        return sk + push, sk + cfg["pushw"] * push

    # --- the simulated copy -------------------------------------------------------------------------------------------------------------------------------------------
    sim_me = item.data.copy()
    sim = bpy.data.objects.new("uo_sim", sim_me); sc.collection.objects.link(sim)
    if sim_me.shape_keys:
        sim.shape_key_clear()
    for g in list(sim.vertex_groups):
        sim.vertex_groups.remove(g)
    item.hide_viewport = True; item.hide_render = True
    z = Vr[:, 2]
    w = np.where(z >= prm["z_top"] - 0.02, cfg["upper"], 1.0 - (1.0 - cfg["goal"]) * np.clip((prm["z_top"] - z) / cfg["ramp"], 0.0, 1.0))
    w = np.where(z >= prm["z_top"] - 0.02, cfg["upper"], np.minimum(w, cfg["upper"]))
    if cloak:                                                                   # pinned along the shoulder line (the top band), free below it
        w = np.where(z >= prm["z_top"] - cfg["band"], 1.0, cfg["hem_goal"] + (1.0 - cfg["hem_goal"]) * np.clip(1.0 - (prm["z_top"] - cfg["band"] - z) / cfg["ramp_cloak"], 0.0, 1.0))
    elif cfg["arm_goal"] >= 0:                                                  # sleeves: free to drape over the arm (collision with the arm), not rigid on the skeleton
        reg = item.data.attributes.get("uo_region")
        if reg is not None:                                                     # a conformed item (uo_conform_item.py) knows its sleeves: 1 / 2 the sleeves, 3 / 4 their roots
            rv = np.empty(nv, np.int32); reg.data.foreach_get("value", rv); arm = rv > 0
        else:
            arm = (np.abs(Vr[:, 0] - np.median(Vr[:, 0])) > cfg["arm_x"]) & (z > (cfg["arm_zmin"] if cfg["arm_zmin"] > -9 else prm["z_top"] - 0.05))
        w = np.where(arm, cfg["arm_goal"], w)
        print("uo_cloth_sim: %d vertices of the sleeves (%s) get goal %.2f" % (int(arm.sum()), "uo_region of the conformed item" if reg is not None else "|x| > %.2f m above the waist" % cfg["arm_x"], cfg["arm_goal"]), flush=True)
    pin = sim.vertex_groups.new(name="goal")

    def set_goal(w):
        for wv in np.unique(np.round(w, 3)):
            pin.add([int(i) for i in np.nonzero(np.round(w, 3) == wv)[0]], float(wv), "REPLACE")

    def cloak_goal(hg):
        """pinned along the shoulder line (the top band), the rest free (hg: how far the lower cape is held to the target: 0.01 hangs under its own weight, 0.1 follows the lift of the run and the ride)"""
        return np.where(z >= prm["z_top"] - cfg["band"], 1.0, hg + (1.0 - hg) * np.clip(1.0 - (prm["z_top"] - cfg["band"] - z) / cfg["ramp_cloak"], 0.0, 1.0))
    set_goal(w)
    cm = sim.modifiers.new("Cloth", "CLOTH"); st = cm.settings
    area = sum(pl.area for pl in item.data.polygons)
    mass = cfg["density"] * area / nv if cfg["density"] > 0 else cfg["mass"] * cfg["mscale"]
    print("uo_cloth_sim: mass %.6f kg per vertex (%s; area %.2f m2, %d vertices)" % (mass, "density %.2f kg/m2" % cfg["density"] if cfg["density"] > 0 else "as given", area, nv), flush=True)
    st.quality = int(cfg["quality"]); st.mass = mass; st.tension_stiffness = cfg["tension"]; st.compression_stiffness = cfg["compression"]; st.shear_stiffness = cfg["shear"]
    st.bending_stiffness = cfg["bending"] * cfg["bscale"]; st.air_damping = cfg["damp_air"] * cfg["dscale"]; st.tension_damping = st.compression_damping = st.shear_damping = cfg["tdamp"] * cfg["dscale"]
    st.vertex_group_mass = "goal"; st.pin_stiffness = 1.0
    cs = cm.collision_settings; cs.use_collision = not cfg.get("nocollide"); cs.distance_min = cfg["dist"]; cs.collision_quality = int(cfg["cq"]); cs.use_self_collision = bool(cfg["self_collision"])
    if cfg["self_collision"]:
        cs.self_distance_min = 0.004
    body.modifiers.new("Collision", "COLLISION"); body.collision.thickness_outer = cfg["thick"]; body.collision.use_culling = bool(cfg["cull"]); body.collision.use_normal = bool(cfg["usenormal"]); body.collision.damping = 0.5; body.collision.cloth_friction = cfg["friction"]

    sc.gravity = (0.0, 0.0, -9.81 * cfg["gravity"])
    if cloak and cfg["ground"] > 0:                                             # the ground: a fallen body drags the cape onto it, it lies there instead of hanging in the air
        bpy.ops.mesh.primitive_plane_add(size=8.0, location=(0.0, 0.0, 0.0)); gr = bpy.context.active_object; gr.name = "uo_ground"
        gr.modifiers.new("Collision", "COLLISION"); gr.collision.thickness_outer = cfg["thick"]; gr.collision.cloth_friction = 5.0; gr.collision.use_culling = False
    wind = None
    if cloak and cfg["wind"] > 0:                                               # the wind of walking / running / riding: blows from the front, along +Y (the back of the rest frame)
        import math
        bpy.ops.object.effector_add(type="WIND", location=(0.0, -2.0, 1.0)); wind = bpy.context.active_object; wind.name = "uo_wind"
        wind.rotation_euler = (-math.pi / 2, 0.0, 0.0); wind.field.shape = "PLANE"; wind.field.noise = cfg["wind_noise"]; wind.field.use_max_distance = False
        st.effector_weights.wind = 1.0
    res = {}
    acts = sorted([a for a in bpy.data.actions if "uo_action" in a], key=lambda a: int(a["uo_action"]))
    for act in acts:
        a = int(act["uo_action"])
        if skip(a) or (only is not None and act.name not in only):
            continue
        t0 = time.time(); rig.animation_data.action = act; rig["uo_direction"] = 0; state["a"] = a
        if cloak:
            lift = a in LIFT
            set_goal(cloak_goal(cfg["goal_run"] if lift else cfg["hem_goal"]))
        nfr = int(act["uo_frames"]); loop = a in LOOP
        period = nfr * STEP if loop else (nfr - 1) * STEP + 1
        for fc in action_fcurves(act):
            for m in list(fc.modifiers):
                fc.modifiers.remove(m)
            m = fc.modifiers.new("CYCLES"); m.mode_before = "REPEAT" if loop else "NONE"; m.mode_after = "REPEAT" if loop else "NONE"
        sim.hide_viewport = True
        T = []; TP = []; AX = []                                                       # the axis of the pelvis in every frame (centre, up)
        for i in range(nfr):                                                  # the kinematic target of every UO frame (the simulated copy is hidden: only the item and the rig count)
            sc.frame_set(1 + i * STEP); rig.update_tag(); bpy.context.view_layer.update()
            item.hide_viewport = False; bpy.context.view_layer.update()
            state["i"] = i; k, kp = kinematic(); T.append(k); TP.append(kp)
            evr = rig.evaluated_get(bpy.context.evaluated_depsgraph_get()); Pm = np.array(rig.matrix_world) @ np.array(evr.pose.bones["pelvis"].matrix)
            AX.append((Pm[:3, 3].copy(), Pm[:3, 1] / np.linalg.norm(Pm[:3, 1])))     # the pelvis bone points up its spine: its Y axis
            item.hide_viewport = True
        sim.hide_viewport = False; bpy.context.view_layer.update()

        # the target of every UO frame is a shape key of the simulated copy (1 on its own frame, 0 on the others, linear in between = the mix of two neighbours in between): the pin of Blender's
        # cloth (goal) follows what the modifiers BEFORE it make of the mesh, and only an ANIMATED shape key reaches it (coordinates or key values written in a frame handler, as this script did
        # before, leave the pinned vertices on the first target: measured in Blender 4.2 and 5.2)
        if sim.data.shape_keys:
            if sim.data.shape_keys.animation_data:
                sim.data.shape_keys.animation_data_clear()
            sim.shape_key_clear()
        sim.shape_key_add(name="Basis", from_mix=False)
        sim.data.shape_keys.key_blocks["Basis"].data.foreach_set("co", TP[0].astype(np.float32).ravel())
        keys = []
        for j in range(nfr):
            kb = sim.shape_key_add(name="t%d" % j, from_mix=False); kb.data.foreach_set("co", TP[j].astype(np.float32).ravel()); keys.append(kb)
        pre = int(cfg["preroll"]); cyc = int(cfg["cycles"]) if loop else 1
        f0 = 1 - pre; f1 = 1 + period * cyc if loop else 1 + (nfr - 1) * STEP
        for ui in range(int(np.floor((f0 - 1) / STEP)), int(np.ceil((f1 - 1) / STEP)) + 1):
            idx = ui % nfr if loop else min(max(ui, 0), nfr - 1)
            for j, kb in enumerate(keys):
                kb.value = 1.0 if j == idx else 0.0; kb.keyframe_insert("value", frame=1 + ui * STEP)
        for fc in action_fcurves(sim.data.shape_keys.animation_data.action):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
        horses = []
        if 23 <= a <= 29 and cfg["horse"] > 0:                                  # riding: the horse proxy of the UO frame is a collider while that frame lasts (hidden objects do not collide: visibility keyed, constant)
            horses = [(j, bpy.data.objects.get("Horse_a%d_f%d" % (a, j))) for j in range(nfr)]
            horses = [(j, h) for j, h in horses if h is not None]
            for j, h in horses:
                if not any(m.type == "COLLISION" for m in h.modifiers):
                    h.modifiers.new("Collision", "COLLISION")
                h.collision.thickness_outer = cfg["thick"]; h.collision.use_culling = bool(cfg["cull"]); h.collision.use_normal = bool(cfg["usenormal"]); h.collision.damping = 0.5; h.collision.cloth_friction = cfg["friction"]
                h.animation_data_create()
                for ui in range(int(np.floor((f0 - 1) / STEP)), int(np.ceil((f1 - 1) / STEP)) + 1):
                    h.hide_viewport = min(max(ui, 0), nfr - 1) != j; h.keyframe_insert("hide_viewport", frame=1 + ui * STEP - 1)
                for fc in action_fcurves(h.animation_data.action):
                    for kp in fc.keyframe_points:
                        kp.interpolation = "CONSTANT"
            print("uo_cloth_sim: action %d: %d horse colliders" % (a, len(horses)), flush=True)
        sc.frame_start = f0; sc.frame_end = f1; cm.point_cache.frame_start = f0; cm.point_cache.frame_end = f1
        sc.frame_set(f0)
        if wind is not None:                                                    # strength of the action, a gust per gait cycle in the looping ones
            wind.animation_data_clear()
            S = WIND.get(a, 0.0) * cfg["wind"]
            for f in range(f0, f1 + 1, STEP):
                wind.field.strength = S * (1.0 + (0.35 * math.sin(2 * math.pi * (f - 1) / period) if loop else 0.0)); wind.field.keyframe_insert("strength", frame=f)
            print("uo_cloth_sim: action %d: wind %.2f" % (a, S), flush=True)
        base = 1 + (cyc - 1) * period if loop else 1
        want = {base + i * STEP: i for i in range(nfr)}
        for f in range(f0, f1 + 1):
            sc.frame_set(f)
            if cfg.get("trace"):
                ev = sim.evaluated_get(bpy.context.evaluated_depsgraph_get()); c = np.empty(nv * 3, np.float32); ev.data.vertices.foreach_get("co", c); c = c.reshape(-1, 3)
                if cfg.get("trace") == 2 and f == f1:
                    bev = body.evaluated_get(bpy.context.evaluated_depsgraph_get()); bc = np.empty(len(bev.data.vertices) * 3, np.float32); bev.data.vertices.foreach_get("co", bc); Mb2 = np.array(body.matrix_world)
                    np.savez(out + ".trace.npz", c=c, T=T[0], Vr=Vr, body=bc.reshape(-1, 3) @ Mb2[:3, :3].T + Mb2[:3, 3], arm=np.array(0))
                lo = Vr[:, 2] < 0.4; print("trace f%d: hem z mean %.3f (rest %.3f), radius %.3f (rest %.3f), key sum %.2f" % (f, c[lo, 2].mean(), Vr[lo, 2].mean(), np.hypot(c[lo, 0], c[lo, 1]).mean(), np.hypot(Vr[lo, 0], Vr[lo, 1]).mean(), sum(k.value for k in keys)), flush=True)
            if f in want:
                ev = sim.evaluated_get(bpy.context.evaluated_depsgraph_get())
                c = np.empty(nv * 3, np.float32); ev.data.vertices.foreach_get("co", c)
                i = want[f]; c = c.reshape(-1, 3).astype(np.float64)
                if cfg["env"] > 0:
                    c = envelope(c)
                d = c - T[i]
                if cfg["in_max"] >= 0:                                           # below the waist: not more than in_max towards the axis of the pelvis (a foot through a lagging hem)
                    c0, up = AX[i]; rr = T[i] - c0; rr = rr - np.outer(rr @ up, up); ru = rr / np.maximum(np.linalg.norm(rr, axis=1, keepdims=True), 1e-9)
                    din = (d * ru).sum(1); low = Vr[:, 2] < prm["z_top"] - 0.05
                    cut = np.where(low & (din < -cfg["in_max"]), -cfg["in_max"] - din, 0.0); d = d + cut[:, None] * ru
                if cfg["max_move"] > 0:                                          # the cloth never wanders further than this from the body (a fast fall or blow lets it lag far behind and leaves the body bare)
                    n = np.maximum(np.linalg.norm(d, axis=1), 1e-9); d = d * (cfg["max_move"] * np.tanh(n / cfg["max_move"]) / n)[:, None]
                res["%d_%d" % (a, i)] = d.astype(np.float32)
        for j, h in horses:
            h.animation_data_clear(); h.hide_viewport = True
        d = np.array([np.linalg.norm(res["%d_%d" % (a, i)], axis=1).max() for i in range(nfr)])
        print("action %2d %-26s %d frames, loop %s, %.0f s, largest cloth move %.2f m" % (a, act.name, nfr, loop, time.time() - t0, d.max()), flush=True)
    if cfg["smooth"] > 0 and res:                                               # the move averaged in space (rest positions): pleats move together, they do not cut through each other
        from scipy.spatial import cKDTree
        from scipy.sparse import coo_matrix
        r = cfg["smooth"]; pr = cKDTree(Vr).query_pairs(r, output_type="ndarray")
        dd = np.linalg.norm(Vr[pr[:, 0]] - Vr[pr[:, 1]], axis=1); wk = np.exp(-(dd / (0.5 * r)) ** 2)
        K = coo_matrix((np.r_[wk, wk, np.ones(nv)], (np.r_[pr[:, 0], pr[:, 1], np.arange(nv)], np.r_[pr[:, 1], pr[:, 0], np.arange(nv)])), shape=(nv, nv)).tocsr()
        ks = np.asarray(K.sum(1)).ravel()
        for k in res:
            D = res[k].astype(np.float64)
            for _ in range(2):
                D = (K @ D) / ks[:, None]
            res[k] = D.astype(np.float32)
    np.savez_compressed(out, **res)
    print("wrote", out, "(%d frames)" % len(res))


if __name__ == "__main__":
    main()
