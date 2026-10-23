"""Cloth simulation of a cape: it hangs from its two clasps, has weight, swings with the body and is pushed away by the body (and the horse) as by a normal collision.

    python uo_cape_sim.py ITEM.blend [--actions 04_stand,00_walk_unarmed,...|all] [--out cloth_sim.npz] [--jobs 4] [key=value ...]

ITEM.blend = the cape prepared by uo_make_cape.py (a sheet from uo_cape_sheet.py, placed by uo_cape_place.py, bound with uo_bind_item.py PART "cloak", custom property uo_cloth of type
"cape", point attribute uo_clasp: 1 = vertices of the left clasp, 2 = of the right one). Per action and frame the skeleton gives where the clasps are (the skin under them: the cape is bound
like a cloak, so the evaluated item has them where the body carries them). A copy of the cape (a plain mesh) is simulated with Blender's Cloth: ONLY the clasp vertices are pinned (to that
position, in the rigid pose of the cape the clasps give); everything else hangs free under gravity, held by the cloth's own tension, shear and bending, and collides with the posed UO_Body
(back, arms, hands, legs; the thin outer thickness of the skin and the collision distance of the cloth keep it a few mm off, the damping of the collider keeps the push soft) and, in the riding
actions, with the horse proxy of the frame. The result is the DIFFERENCE between the simulated cape and the bound one (cloth_sim.npz next to the item, keys "<action>_<frame>"):
render_uo_layer.py adds it (uo_cloth type "cape"), then BODY_GAP pushes whatever is still in the arms / legs / head out, as for every item.

Every action is simulated on its own: PREROLL frames in its first pose (looping actions: the pose of the loop), looping actions CYCLES cycles and the last one is kept, so the loop closes.
Settings (key=value): mass (kg per vertex, 0.3: the scale Blender's presets are made for; far smaller masses make the solver stiff and the cloth does not move: measured, a vertex of 6e-5 kg hung like a board; 0 = from density), density (kg/m2 of the cloth, used when mass = 0), tension / compression / shear (in-plane stiffness), bending, bscale, dscale,
tdamp, damp_air, quality (16: substeps per frame; a leg or a hand swung through the cloth in 8 and 12 tunnelled), cq (collision quality, 10), dist (0.01 m: collision distance of the cloth), thick (0.02 m: outer thickness of the body collider), friction (0), cull, usenormal,
preroll (40), cycles (3), gravity (1), mount_start (60 deg: riding actions start with the cape swung out to the back about the clasps, above the horse, and let it fall on it), lean_riding (55 deg: the cape streams back over the horse's croup), lean (5 deg: gravity tilted to the back, x LEAN_SCALE per action: the cape hangs off the back, trails more in a run and streams in a gallop), self_collision (0), horse (1: riding actions collide with the horse proxy of the first frame carried by the pelvis), pin (0 = the clasp vertices only; > 0 = also the top edge of the cape, this far
below it in m, softly: not used by default), max_move (0.45 m: the most the cape may differ from the bound item, soft limit; 0 = none), smooth (0 m: the move averaged in space).
"""
import json, os, sys, time
import numpy as np
import bpy
from mathutils import Matrix

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from bpy_compat import action_fcurves                                       # noqa: E402 (Blender 5.x: no Action.fcurves)

STEP = 3
LOOP = {0, 1, 2, 3, 4, 5, 6, 7, 8}
# how far the pull of gravity is tilted towards the back of the character (deg), per UO action: the cloth then hangs that many degrees off the back instead of lying on it (an accelerating
# frame: the cape of a walker trails, of a runner trails more, of a galloper streams behind); `lean` (key) is the value for standing and fighting, the table scales it
LEAN_SCALE = {0: 1.6, 1: 1.6, 2: 3.2, 3: 3.2}      # riding actions 23-29: `lean_riding`
CFG = dict(density=0.7, mass=0.3, tension=1000.0, compression=1000.0, shear=500.0, bending=10.0, bscale=1.0, dscale=1.0, tdamp=5.0, damp_air=1.0, quality=16, cq=10.0, dist=0.01, thick=0.02, friction=0.0,
           cull=0.0, usenormal=0.0, preroll=40, cycles=3, gravity=1.0, self_collision=0, horse=1.0, lean=5.0, lean_riding=55.0, mount_start=60.0, max_move=0.45, smooth=0.0, trace=0, nocollide=0, noshape=0)


def parse(extra):
    for kv in extra:
        k, v = kv.split("=", 1)
        if k not in CFG:
            raise SystemExit("unknown setting %s (known: %s)" % (k, ", ".join(CFG)))
        CFG[k] = float(v) if not isinstance(CFG[k], int) else int(float(v))


def run_parallel(blend, out, only, jobs, extra):
    import subprocess, tempfile
    bpy.ops.wm.open_mainfile(filepath=blend)
    names = [a.name for a in sorted([a for a in bpy.data.actions if "uo_action" in a], key=lambda a: int(a["uo_action"])) if only is None or a.name in only]
    groups = [names[k::jobs] for k in range(jobs)]
    tmp = tempfile.mkdtemp(prefix="uo_cape_sim_"); procs = []
    for k, g in enumerate(groups):
        if g:
            procs.append((k, subprocess.Popen([sys.executable, os.path.abspath(__file__), blend, "--actions", ",".join(g), "--out", os.path.join(tmp, "p%d.npz" % k)] + extra,
                                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)))
    merged = {}
    for k, p in procs:
        txt = p.communicate()[0]
        for line in txt.splitlines():
            if line.startswith(("action", "uo_cape_sim", "trace")):
                print(line, flush=True)
        if p.returncode:
            raise SystemExit("job %d failed:\n%s" % (k, txt[-3000:]))
        with np.load(os.path.join(tmp, "p%d.npz" % k)) as z:
            merged.update({key: z[key] for key in z.files})
    np.savez_compressed(out, **merged)
    print("wrote", out, "(%d frames)" % len(merged))


def kabsch(P, Q):
    """rigid motion (R, t) with R P + t ~ Q (least squares)"""
    pc, qc = P.mean(0), Q.mean(0)
    U, S, Vt = np.linalg.svd((P - pc).T @ (Q - qc))
    D = np.diag([1, 1, np.sign(np.linalg.det(Vt.T @ U.T))])
    R = Vt.T @ D @ U.T
    return R, qc - R @ pc


def main():
    argv = sys.argv[1:]
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    blend = os.path.abspath(argv.pop(0)); out = "cloth_sim.npz"; only = None; jobs = 1; extra = []
    while argv:
        a = argv.pop(0)
        if a == "--actions":
            v = argv.pop(0); only = None if v == "all" else v.split(",")
        elif a == "--out":
            out = os.path.abspath(argv.pop(0))
        elif a == "--jobs":
            jobs = int(argv.pop(0))
        else:
            extra.append(a)
    parse(extra); cfg = CFG
    if jobs > 1:
        return run_parallel(blend, out, only, jobs, extra)
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc = bpy.context.scene; rig = bpy.data.objects["UO_Rig"]; body = bpy.data.objects["UO_Body"]
    items = [o for o in bpy.data.collections["Clothing"].all_objects if o.type == "MESH" and o.get("uo_cloth") and json.loads(o["uo_cloth"]).get("type") == "cape"]
    if not items:
        raise SystemExit("no cape (custom property uo_cloth of type cape) in the Clothing collection")
    item = items[0]; nv = len(item.data.vertices)
    clasp = np.empty(nv, np.int32); item.data.attributes["uo_clasp"].data.foreach_get("value", clasp); pinned = np.nonzero(clasp > 0)[0]
    print("uo_cape_sim: cape %s, %d vertices, %d pinned (the clasps)" % (item.name, nv, len(pinned)), flush=True)
    for o in bpy.data.objects:
        if o.type == "MESH" and o not in (body, item) and "Clothing" not in [c.name for c in o.users_collection]:
            o.hide_viewport = True
    for o in items[1:]:
        o.hide_viewport = True

    def skinned():
        dg = bpy.context.evaluated_depsgraph_get(); ev = item.evaluated_get(dg)
        c = np.empty(nv * 3, np.float32); ev.data.vertices.foreach_get("co", c)
        M = np.array(item.matrix_world)
        return c.reshape(-1, 3).astype(np.float64) @ M[:3, :3].T + M[:3, 3]

    rig.data.pose_position = "REST"; bpy.context.view_layer.update(); R0 = skinned()          # the cape as placed (rest pose, world)
    rig.data.pose_position = "POSE"; bpy.context.view_layer.update()

    EDG = np.empty(len(item.data.edges) * 2, np.int32); item.data.edges.foreach_get("vertices", EDG); EDG = EDG.reshape(-1, 2)
    L0 = np.linalg.norm(R0[EDG[:, 0]] - R0[EDG[:, 1]], axis=1); BIG = L0 > 0.004
    sim_me = item.data.copy()
    sim = bpy.data.objects.new("uo_sim", sim_me); sc.collection.objects.link(sim)
    if sim_me.shape_keys:
        sim.shape_key_clear()
    for g in list(sim.vertex_groups):
        sim.vertex_groups.remove(g)
    item.hide_viewport = True; item.hide_render = True
    sim.matrix_world = np.eye(4).tolist()
    pin = sim.vertex_groups.new(name="goal"); pin.add([int(i) for i in pinned], 1.0, "REPLACE")
    area = sum(p.area for p in item.data.polygons)
    mass = cfg["mass"] if cfg["mass"] > 0 else cfg["density"] * area / nv
    print("uo_cape_sim: mass %.6f kg per vertex (%s; area %.2f m2, %d vertices)" % (mass, "as given" if cfg["mass"] > 0 else "density %.2f kg/m2" % cfg["density"], area, nv), flush=True)
    cm = sim.modifiers.new("Cloth", "CLOTH"); st = cm.settings
    st.quality = int(cfg["quality"]); st.mass = mass; st.tension_stiffness = cfg["tension"]; st.compression_stiffness = cfg["compression"]; st.shear_stiffness = cfg["shear"]
    st.bending_stiffness = cfg["bending"] * cfg["bscale"]; st.air_damping = cfg["damp_air"] * cfg["dscale"]
    st.tension_damping = st.compression_damping = st.shear_damping = cfg["tdamp"] * cfg["dscale"]
    st.vertex_group_mass = "goal"; st.pin_stiffness = 1.0
    cs = cm.collision_settings; cs.use_collision = not cfg["nocollide"]; cs.distance_min = cfg["dist"]; cs.collision_quality = int(cfg["cq"]); cs.use_self_collision = bool(cfg["self_collision"])
    if cfg["self_collision"]:
        cs.self_distance_min = 0.004
    body.modifiers.new("Collision", "COLLISION"); body.collision.thickness_outer = cfg["thick"]; body.collision.use_culling = bool(cfg["cull"]); body.collision.use_normal = bool(cfg["usenormal"])
    body.collision.damping = 0.5; body.collision.cloth_friction = cfg["friction"]

    res = {}
    acts = sorted([a for a in bpy.data.actions if "uo_action" in a], key=lambda a: int(a["uo_action"]))
    for act in acts:
        a = int(act["uo_action"])
        if only is not None and act.name not in only:
            continue
        t0 = time.time(); rig.animation_data.action = act; rig["uo_direction"] = 0
        th = np.radians(cfg["lean_riding"] if 23 <= a <= 29 else cfg["lean"] * LEAN_SCALE.get(a, 1.0)); g = 9.81 * cfg["gravity"]
        sc.gravity = (0.0, g * np.sin(th), -g * np.cos(th))                       # +y is the back of the character
        nfr = int(act["uo_frames"]); loop = a in LOOP
        period = nfr * STEP if loop else (nfr - 1) * STEP + 1
        for fc in action_fcurves(act):
            for m in list(fc.modifiers):
                fc.modifiers.remove(m)
            m = fc.modifiers.new("CYCLES"); m.mode_before = "REPEAT" if loop else "NONE"; m.mode_after = "REPEAT" if loop else "NONE"
        sim.hide_viewport = True
        S = []; TP = []; PEL = []
        for i in range(nfr):                                                   # the bound cape of every UO frame; the rigid pose its clasps give is the shape the pin follows
            sc.frame_set(1 + i * STEP); rig.update_tag(); bpy.context.view_layer.update()
            item.hide_viewport = False; bpy.context.view_layer.update()
            s_ = skinned(); S.append(s_)
            PEL.append(np.array(rig.matrix_world) @ np.array(rig.evaluated_get(bpy.context.evaluated_depsgraph_get()).pose.bones["pelvis"].matrix))
            R, t = kabsch(R0[pinned], s_[pinned]); T = R0 @ R.T + t; TP.append(T)                    # the clasps move as the rigid patches of the cape (the skin under them does not: it would stretch the cloth round them)
            item.hide_viewport = True
        sim.hide_viewport = False; bpy.context.view_layer.update()

        # the pose of every UO frame is a shape key of the simulated copy (1 on its own frame, 0 on the others): the pin of Blender's cloth follows what the modifiers BEFORE it make of the
        # mesh, and only an ANIMATED shape key reaches it (uo_cloth_sim.py: measured in Blender 4.2 and 5.2)
        if sim.data.shape_keys:
            if sim.data.shape_keys.animation_data:
                sim.data.shape_keys.animation_data_clear()
            sim.shape_key_clear()
        sim.shape_key_add(name="Basis", from_mix=False)
        sim.data.shape_keys.key_blocks["Basis"].data.foreach_set("co", TP[0].astype(np.float32).ravel())
        riding = 23 <= a <= 29 and cfg["mount_start"] > 0
        st.rest_shape_key = None
        if not riding:                                                          # (Blender starts the cloth from its rest shape key too: riding has none, the rest is the swung-out start)
            rest_kb = sim.shape_key_add(name="rest", from_mix=False); rest_kb.data.foreach_set("co", TP[0].astype(np.float32).ravel()); st.rest_shape_key = rest_kb    # springs and bending rest on the cape as placed
        keys = []
        for j in range(nfr):
            kb = sim.shape_key_add(name="t%d" % j, from_mix=False); kb.data.foreach_set("co", TP[j].astype(np.float32).ravel()); keys.append(kb)
        if riding:                                                             # riding: the cape hanging from the shoulders would start INSIDE the horse (its croup is right behind the rider): it starts swung out
            T0 = TP[0]; cl_ = clasp[pinned]; cL, cR = T0[pinned][cl_ == 1].mean(0), T0[pinned][cl_ == 2].mean(0)       # to the back about the line of the clasps and falls onto the horse
            ax = (cR - cL) / np.linalg.norm(cR - cL); piv = (cL + cR) / 2; ph = np.radians(cfg["mount_start"])
            def rot(P, ang):
                v = P - piv; return piv + v * np.cos(ang) + np.cross(ax, v) * np.sin(ang) + np.outer(v @ ax, ax) * (1 - np.cos(ang))
            Ts = T0.copy(); free = clasp == 0
            for ang in (ph, -ph):                                              # the sign that sends the hem to the back (+y)
                Q = rot(T0, ang)
                if Q[free][:, 1].mean() > T0[free][:, 1].mean():
                    Ts[free] = Q[free]; break
            print("uo_cape_sim: riding start: free vertices mean y %.2f -> %.2f, lowest z %.2f -> %.2f" % (T0[free][:, 1].mean(), Ts[free][:, 1].mean(), T0[:, 2].min(), Ts[:, 2].min()), flush=True)
            keys[0].data.foreach_set("co", Ts.astype(np.float32).ravel()); sim.data.shape_keys.key_blocks["Basis"].data.foreach_set("co", Ts.astype(np.float32).ravel())
        if cfg["noshape"]:
            sim.shape_key_clear(); sim.data.vertices.foreach_set("co", TP[0].astype(np.float32).ravel()); sim.data.update(); keys = []
        pre = int(cfg["preroll"]); cyc = int(cfg["cycles"]) if loop else 1
        f0 = 1 - pre; f1 = 1 + period * cyc if loop else 1 + (nfr - 1) * STEP
        for ui in range(int(np.floor((f0 - 1) / STEP)), int(np.ceil((f1 - 1) / STEP)) + 1):
            idx = ui % nfr if loop else min(max(ui, 0), nfr - 1)
            for j, kb in enumerate(keys):
                kb.value = 1.0 if j == idx else 0.0; kb.keyframe_insert("value", frame=1 + ui * STEP)
        if keys:
            for fc in action_fcurves(sim.data.shape_keys.animation_data.action):
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"
        hf = None
        if 23 <= a <= 29 and cfg["horse"] > 0:                                  # riding: ONE collider, the horse proxy of the first frame, carried by the rider's pelvis (a proxy per UO frame, shown and hidden in turn,
            h0 = bpy.data.objects.get("Horse_a%d_f0" % a)                        # threw the cloth out of the next one and stretched it up to 10 x: the proxies have different meshes, they cannot be blended)
            if h0 is not None:
                hf = bpy.data.objects.new("uo_horse_follow", h0.data); sc.collection.objects.link(hf); hf.rotation_mode = "QUATERNION"
                hf.modifiers.new("Collision", "COLLISION")
                hf.collision.thickness_outer = cfg["thick"]; hf.collision.use_culling = bool(cfg["cull"]); hf.collision.use_normal = bool(cfg["usenormal"]); hf.collision.damping = 0.5; hf.collision.cloth_friction = cfg["friction"]
                H0 = np.array(h0.matrix_world); hf.animation_data_create()
                for ui in range(int(np.floor((f0 - 1) / STEP)), int(np.ceil((f1 - 1) / STEP)) + 1):
                    idx = ui % nfr if loop else min(max(ui, 0), nfr - 1)
                    hf.matrix_world = Matrix((PEL[idx] @ np.linalg.inv(PEL[0]) @ H0).tolist())
                    for path in ("location", "rotation_quaternion", "scale"):
                        hf.keyframe_insert(path, frame=1 + ui * STEP)
                for fc in action_fcurves(hf.animation_data.action):
                    for kp in fc.keyframe_points:
                        kp.interpolation = "LINEAR"
                hf.matrix_world = Matrix(H0.tolist())
                print("uo_cape_sim: action %d: the horse proxy of frame 0 follows the pelvis" % a, flush=True)
        sc.frame_start = f0; sc.frame_end = f1; cm.point_cache.frame_start = f0; cm.point_cache.frame_end = f1
        sc.frame_set(f0)
        base = 1 + (cyc - 1) * period if loop else 1
        want = {base + i * STEP: i for i in range(nfr)}
        for f in range(f0, f1 + 1):
            sc.frame_set(f)
            if cfg["trace"] == 3 and (f % 6 == 0 or f < f0 + 4):
                ev = sim.evaluated_get(bpy.context.evaluated_depsgraph_get()); c = np.empty(nv * 3, np.float32); ev.data.vertices.foreach_get("co", c); c = c.reshape(-1, 3).astype(np.float64)
                r_ = np.linalg.norm(c[EDG[:, 0]] - c[EDG[:, 1]], axis=1) / L0
                print("trace f%d: edge ratio mean %.3f p99 %.3f max %.1f, lowest z %.3f, mean y %.3f" % (f, r_[BIG].mean(), np.percentile(r_[BIG], 99), r_[BIG].max(), c[:, 2].min(), c[:, 1].mean()), flush=True)
            if cfg["trace"] == 2:
                ev = sim.evaluated_get(bpy.context.evaluated_depsgraph_get()); c = np.empty(nv * 3, np.float32); ev.data.vertices.foreach_get("co", c); c = c.reshape(-1, 3)
                print("trace f%d: lowest z %.3f, mean y %.3f, keys %s" % (f, c[:, 2].min(), c[:, 1].mean(), "".join("%.1f" % k.value for k in keys[:4])), flush=True)
            if f in want:
                ev = sim.evaluated_get(bpy.context.evaluated_depsgraph_get())
                c = np.empty(nv * 3, np.float32); ev.data.vertices.foreach_get("co", c)
                i = want[f]; c = c.reshape(-1, 3).astype(np.float64)
                d = c - S[i]
                if cfg["max_move"] > 0:                                          # the cape never wanders further than this from the bound item (a fast fall or blow lets it lag far behind)
                    n = np.maximum(np.linalg.norm(d, axis=1), 1e-9); d = d * (cfg["max_move"] * np.tanh(n / cfg["max_move"]) / n)[:, None]
                res["%d_%d" % (a, i)] = d.astype(np.float32)
                if cfg["trace"]:
                    dv = np.linalg.norm(c - TP[i], axis=1); Ed = np.vstack([f_ for f_ in item.data.edge_keys]) if False else None
                    print("trace a%d f%d: |c - rigid pose| mean %.4f max %.4f m, lowest %.3f, clasp err vs rigid %.4f m" % (a, i, float(dv.mean()), float(dv.max()), c[:, 2].min(), float(np.abs(c[pinned] - TP[i][pinned]).max())), flush=True)
        if hf is not None:
            bpy.data.objects.remove(hf, do_unlink=True)
        d = np.array([np.linalg.norm(res["%d_%d" % (a, i)], axis=1).max() for i in range(nfr)])
        print("action %2d %-26s %d frames, loop %s, %.0f s, largest cape move %.2f m" % (a, act.name, nfr, loop, time.time() - t0, d.max()), flush=True)
    if cfg["smooth"] > 0 and res:
        from scipy.spatial import cKDTree
        from scipy.sparse import coo_matrix
        r = cfg["smooth"]; pr = cKDTree(R0).query_pairs(r, output_type="ndarray")
        dd = np.linalg.norm(R0[pr[:, 0]] - R0[pr[:, 1]], axis=1); wk = np.exp(-(dd / (0.5 * r)) ** 2)
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
