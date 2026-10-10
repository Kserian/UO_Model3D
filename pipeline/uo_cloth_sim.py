"""Cloth simulation for loose garments (robe, dress, skirt, kilt), on top of the kinematic result: the hanging cloth settles, swings and COLLIDES with the posed body.

    python uo_cloth_sim.py ITEM.blend [--actions 00_walk_unarmed,02_run_unarmed,...|all] [--out cloth_sim.npz] [--jobs 4] [key=value ...]

ITEM.blend = the item prepared and bound (uo_make_item.py: item.blend with PART robe / skirt, custom property uo_cloth). Per action and frame the kinematic target is what the renderer
would draw without a simulation: the item as the skeleton skins it + the push of the legs (cloth_lib.hull_push, the same call and settings as render_uo_layer.cloth_push). A copy of the item
(a plain mesh) is simulated with Blender's Cloth: every vertex is held by a spring ("goal", the pin weight) to the target of the current frame, 1 at the waist and above (the cloth follows
the body there), falling to GOAL at the hem (the hanging part is free to swing and fold), and the cloth collides with the posed UO_Body (legs, arms, hands). The result is saved as the
DIFFERENCE between the simulation and the target (cloth_sim.npz next to the item, keys "<action>_<frame>"): render_uo_layer.py adds it to the leg push (CLOTH_SIM = 1), then BODY_GAP
pushes whatever is still inside the body out, as before. Mounted actions (23-29) are not simulated (the hem follows the legs there).

Every action is simulated on its own: PREROLL frames in its first pose (looping actions: the pose of the loop), looping actions (walk, run, stand, combat idle) CYCLES cycles and the last one is
kept, so the loop closes without a jump. Settings (key=value): goal (0.4), upper (1.0), ramp (0.30 m from the waist down to GOAL), quality (8), mass (0.3), tension / compression (15), shear (5), bending (0.5),
damp_air (1), tdamp (5), dist (0.005), preroll (40), cycles (3), self_collision (0), friction (0), arm_goal (0.7; -1 = sleeves as the rest above the waist; 0-1 = their own goal), arm_x (0.19 m from the middle: where the sleeves start), arm_zmin (the sleeves are the vertices above this height; default 0.05 m below the waist: long bell sleeves that hang below it need e.g. 0.55), thick (0.02 m: the outer thickness of the body as a collider; a fast leg tunnels through the cloth with a thin one: leg pixels through the robe in the run 466 at 0.005 m, 196 at 0.02, 147 with dist 0.02 too but 3 x slower), in_max (0.01 m: below the waist the cloth may move at most this much TOWARDS the axis of the pelvis against the target: the target already holds it just outside the legs' reach, and a
simulated hem that lagged inwards let a foot come out through it in the run; < 0 = no limit), max_move (0.12 m: the most the cloth may differ from the kinematic target, soft limit; 0 = none). Measured on the replica of the original robe 469 (robe_cloth_sim_test.py, hybrid=1):
lower-body IoU walk 0.754 -> 0.765, run 0.731 -> 0.735 against the kinematic result (docs/qa/robe_physics.md); the simulation alone (no goal) collapses in walk and run.
"""
import json, os, sys, time
import numpy as np
import bpy

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import cloth_lib as cl                                                      # noqa: E402
from bpy_compat import action_fcurves                                       # noqa: E402 (Blender 5.x: no Action.fcurves)

STEP = 3
LOOP = {0, 1, 2, 3, 4, 5, 6, 7, 8}
CFG = dict(goal=0.4, upper=1.0, ramp=0.30, quality=8, mass=0.3, tension=15.0, compression=15.0, shear=5.0, bending=0.5, damp_air=1.0, tdamp=5.0, dist=0.005, preroll=40, cycles=3,
           self_collision=0, friction=0.0, arm_goal=0.7, arm_x=0.19, arm_zmin=-9.0, max_move=0.12, thick=0.02, in_max=0.01)


def run_parallel(blend, out, only, jobs, extra):
    """the actions are independent: split them over `jobs` processes (the same script) and merge the results"""
    import subprocess, tempfile
    bpy.ops.wm.open_mainfile(filepath=blend)
    names = [a.name for a in sorted([a for a in bpy.data.actions if "uo_action" in a], key=lambda a: int(a["uo_action"])) if not 23 <= int(a["uo_action"]) <= 29 and (only is None or a.name in only)]
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
    blend = os.path.abspath(args.pop(0)); out = None; only = None; cfg = dict(CFG); jobs = 1; extra = []
    while args:
        a = args.pop(0)
        if a == "--out":
            out = os.path.abspath(args.pop(0))
        elif a == "--actions":
            v = args.pop(0); only = None if v == "all" else set(v.split(","))
        elif a == "--jobs":
            jobs = int(args.pop(0))
        elif "=" in a:
            k, v = a.split("=", 1); cfg[k] = float(v); extra.append(a)
    out = out or os.path.join(os.path.dirname(blend), "cloth_sim.npz")
    if jobs > 1:
        return run_parallel(blend, out, only, jobs, extra)
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc = bpy.context.scene; rig = bpy.data.objects["UO_Rig"]; body = bpy.data.objects["UO_Body"]
    items = [o for o in bpy.data.collections["Clothing"].all_objects if o.type == "MESH" and o.get("uo_cloth") and json.loads(o["uo_cloth"]).get("type") != "cloak"]
    if not items:
        raise SystemExit("no loose garment (custom property uo_cloth) in the Clothing collection")
    item = items[0]; prm = json.loads(item["uo_cloth"]); nv = len(item.data.vertices)
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

    def hull_push_now():
        dg = bpy.context.evaluated_depsgraph_get(); evr = rig.evaluated_get(dg)
        skin = {n: Mr0 @ np.array(evr.pose.bones[n].matrix) @ inv_local[n] @ np.linalg.inv(Mr0) for n in names}
        heads = np.array([(skin[names[k]] @ np.append(caps.head[j], 1))[:3] for j, k in enumerate(caps.idx)])
        tails = np.array([(skin[names[k]] @ np.append(caps.tail[j], 1))[:3] for j, k in enumerate(caps.idx)])
        if prm.get("hull") == "rel":
            return cl.hull_push_rel(Vr, skin["pelvis"], heads[sel], tails[sel], caps.radius[sel], caps.head[sel], caps.tail[sel], centre_xy=tuple(prm["centre"]), kappa=prm["kappa"],
                                    z_top=prm["z_top"], z_hem=prm["z_hem"], ramp=prm.get("ramp", 0.15), drop=prm.get("drop", 1.0))
        return cl.hull_push(Vr, skin["pelvis"], heads[sel], tails[sel], caps.radius[sel], centre_xy=tuple(prm["centre"]), margin=prm["margin"], kappa=prm["kappa"],
                            z_top=prm["z_top"], z_hem=prm["z_hem"], ramp=prm.get("ramp", 0.15), drop=prm.get("drop", 1.0))

    def kinematic():
        """the item as the renderer draws it before the simulation: skinned + the push of the legs, world coordinates"""
        dg = bpy.context.evaluated_depsgraph_get(); ev = item.evaluated_get(dg)
        c = np.empty(nv * 3, np.float32); ev.data.vertices.foreach_get("co", c)
        M = np.array(item.matrix_world)
        return c.reshape(-1, 3).astype(np.float64) @ M[:3, :3].T + M[:3, 3] + hull_push_now()

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
    if cfg["arm_goal"] >= 0:                                                    # sleeves: free to drape over the arm (collision with the arm), not rigid on the skeleton
        reg = item.data.attributes.get("uo_region")
        if reg is not None:                                                     # a conformed item (uo_conform_item.py) knows its sleeves: 1 / 2 the sleeves, 3 / 4 their roots
            rv = np.empty(nv, np.int32); reg.data.foreach_get("value", rv); arm = rv > 0
        else:
            arm = (np.abs(Vr[:, 0] - np.median(Vr[:, 0])) > cfg["arm_x"]) & (z > (cfg["arm_zmin"] if cfg["arm_zmin"] > -9 else prm["z_top"] - 0.05))
        w = np.where(arm, cfg["arm_goal"], w)
        print("uo_cloth_sim: %d vertices of the sleeves (%s) get goal %.2f" % (int(arm.sum()), "uo_region of the conformed item" if reg is not None else "|x| > %.2f m above the waist" % cfg["arm_x"], cfg["arm_goal"]), flush=True)
    pin = sim.vertex_groups.new(name="goal")
    for wv in np.unique(np.round(w, 3)):
        pin.add([int(i) for i in np.nonzero(np.round(w, 3) == wv)[0]], float(wv), "REPLACE")
    cm = sim.modifiers.new("Cloth", "CLOTH"); st = cm.settings
    st.quality = int(cfg["quality"]); st.mass = cfg["mass"]; st.tension_stiffness = cfg["tension"]; st.compression_stiffness = cfg["compression"]; st.shear_stiffness = cfg["shear"]
    st.bending_stiffness = cfg["bending"]; st.air_damping = cfg["damp_air"]; st.tension_damping = st.compression_damping = st.shear_damping = cfg["tdamp"]
    st.vertex_group_mass = "goal"; st.pin_stiffness = 1.0
    cs = cm.collision_settings; cs.use_collision = True; cs.distance_min = cfg["dist"]; cs.collision_quality = 4; cs.use_self_collision = bool(cfg["self_collision"])
    if cfg["self_collision"]:
        cs.self_distance_min = 0.004
    body.modifiers.new("Collision", "COLLISION"); body.collision.thickness_outer = cfg["thick"]; body.collision.use_culling = False; body.collision.damping = 0.5; body.collision.cloth_friction = cfg["friction"]

    res = {}
    acts = sorted([a for a in bpy.data.actions if "uo_action" in a], key=lambda a: int(a["uo_action"]))
    for act in acts:
        a = int(act["uo_action"])
        if 23 <= a <= 29 or (only is not None and act.name not in only):
            continue
        t0 = time.time(); rig.animation_data.action = act; rig["uo_direction"] = 0
        nfr = int(act["uo_frames"]); loop = a in LOOP
        period = nfr * STEP if loop else (nfr - 1) * STEP + 1
        for fc in action_fcurves(act):
            for m in list(fc.modifiers):
                fc.modifiers.remove(m)
            m = fc.modifiers.new("CYCLES"); m.mode_before = "REPEAT" if loop else "NONE"; m.mode_after = "REPEAT" if loop else "NONE"
        sim.hide_viewport = True
        T = []; AX = []                                                       # the axis of the pelvis in every frame (centre, up)
        for i in range(nfr):                                                  # the kinematic target of every UO frame (the simulated copy is hidden: only the item and the rig count)
            sc.frame_set(1 + i * STEP); rig.update_tag(); bpy.context.view_layer.update()
            item.hide_viewport = False; bpy.context.view_layer.update()
            T.append(kinematic())
            evr = rig.evaluated_get(bpy.context.evaluated_depsgraph_get()); Pm = np.array(rig.matrix_world) @ np.array(evr.pose.bones["pelvis"].matrix)
            AX.append((Pm[:3, 3].copy(), Pm[:3, 1] / np.linalg.norm(Pm[:3, 1])))     # the pelvis bone points up its spine: its Y axis
            item.hide_viewport = True
        sim.hide_viewport = False; bpy.context.view_layer.update()

        # the target of every UO frame is a shape key of the simulated copy (1 on its own frame, 0 on the others, linear in between = the mix of two neighbours in between): the pin of Blender's
        # cloth (goal) follows what the modifiers BEFORE it make of the mesh, and only an ANIMATED shape key reaches it (coordinates or key values written in a frame handler, as this script did
        # before, leave the pinned vertices on the first target: measured in Blender 4.2 and 5.2, docs/qa/robe_physics.md)
        if sim.data.shape_keys:
            if sim.data.shape_keys.animation_data:
                sim.data.shape_keys.animation_data_clear()
            sim.shape_key_clear()
        sim.shape_key_add(name="Basis", from_mix=False)
        sim.data.shape_keys.key_blocks["Basis"].data.foreach_set("co", T[0].astype(np.float32).ravel())
        keys = []
        for j in range(nfr):
            kb = sim.shape_key_add(name="t%d" % j, from_mix=False); kb.data.foreach_set("co", T[j].astype(np.float32).ravel()); keys.append(kb)
        pre = int(cfg["preroll"]); cyc = int(cfg["cycles"]) if loop else 1
        f0 = 1 - pre; f1 = 1 + period * cyc if loop else 1 + (nfr - 1) * STEP
        for ui in range(int(np.floor((f0 - 1) / STEP)), int(np.ceil((f1 - 1) / STEP)) + 1):
            idx = ui % nfr if loop else min(max(ui, 0), nfr - 1)
            for j, kb in enumerate(keys):
                kb.value = 1.0 if j == idx else 0.0; kb.keyframe_insert("value", frame=1 + ui * STEP)
        for fc in action_fcurves(sim.data.shape_keys.animation_data.action):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
        sc.frame_start = f0; sc.frame_end = f1; cm.point_cache.frame_start = f0; cm.point_cache.frame_end = f1
        sc.frame_set(f0)
        base = 1 + (cyc - 1) * period if loop else 1
        want = {base + i * STEP: i for i in range(nfr)}
        for f in range(f0, f1 + 1):
            sc.frame_set(f)
            if f in want:
                ev = sim.evaluated_get(bpy.context.evaluated_depsgraph_get())
                c = np.empty(nv * 3, np.float32); ev.data.vertices.foreach_get("co", c)
                i = want[f]; d = c.reshape(-1, 3).astype(np.float64) - T[i]
                if cfg["in_max"] >= 0:                                           # below the waist: not more than in_max towards the axis of the pelvis (a foot through a lagging hem)
                    c0, up = AX[i]; rr = T[i] - c0; rr = rr - np.outer(rr @ up, up); ru = rr / np.maximum(np.linalg.norm(rr, axis=1, keepdims=True), 1e-9)
                    din = (d * ru).sum(1); low = Vr[:, 2] < prm["z_top"] - 0.05
                    cut = np.where(low & (din < -cfg["in_max"]), -cfg["in_max"] - din, 0.0); d = d + cut[:, None] * ru
                if cfg["max_move"] > 0:                                          # the cloth never wanders further than this from the body (a fast fall or blow lets it lag far behind and leaves the body bare)
                    n = np.maximum(np.linalg.norm(d, axis=1), 1e-9); d = d * (cfg["max_move"] * np.tanh(n / cfg["max_move"]) / n)[:, None]
                res["%d_%d" % (a, i)] = d.astype(np.float32)
        d = np.array([np.linalg.norm(res["%d_%d" % (a, i)], axis=1).max() for i in range(nfr)])
        print("action %2d %-26s %d frames, loop %s, %.0f s, largest cloth move %.2f m" % (a, act.name, nfr, loop, time.time() - t0, d.max()), flush=True)
    np.savez_compressed(out, **res)
    print("wrote", out, "(%d frames)" % len(res))


if __name__ == "__main__":
    main()
