"""Blender's cloth simulation against the leg hull, on the replica of the original robe 469 (EXPERIMENT: nothing in the render uses it; result in docs/qa/robe_physics.md, "Sesja 16, symulacja").

    python robe_cloth_sim_test.py sim   POSES.npz OUT.npz ACTIONS [key=value ...]     # bpy: simulate the replica tube (robe_calib.tube, rest shape fitted on the stand frames)
    python robe_cloth_sim_test.py score POSES.npz OUT.npz [OUT2.npz ...]               # numpy: lower-body IoU of the simulated frames, of the hull and of the rigid pelvis hang

The replica is pinned at the waist (2 rings) to the pelvis (Armature modifier), the cloth (quality 8, mass 0.3, tension / compression 15, shear 5, bending 0.5; keys: quality mass tension compression
shear bending damp_air tdamp dist preroll cycles pin_rings gravity pin_stiff collide friction wx wy hybrid goal goal_rings margin kappa) collides with the posed UO_Body (Collision modifier). Every action is simulated on its own: PREROLL frames
in the first pose, looping actions (walk, run, stand...) CYCLES cycles (the actions get a Cycles modifier), the last cycle is kept. Frames as in render_uo_layer.py (scene frame 1 + i * 3).
"""
import json, os, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
BLEND = os.path.join(HERE, "..", "model", "UO_Body_0x190.blend")
SPRITE = os.path.join(HERE, "body13", "mul", "anim_0469.vd")
LOOP = {0, 1, 2, 3, 4, 5, 6, 7, 8}
STEP = 3


def replica(poses):
    import robe_calib as rc
    cal = rc.Calib(poses, SPRITE)
    p = dict(rc.DEFAULT); p.update(drop=1.0, solve=0, margin=0.05, kappa=0.8)
    p = rc.fit_rest(cal, p)
    return cal, p


def simulate(poses, out, acts, cfg):
    import bpy, robe_calib as rc
    cal, p = replica(poses)
    p = dict(p); p["rx1"] *= cfg["wx"]; p["ry"] *= cfg["wy"]                    # more cloth below the hips: wx / wy widen the hem (rx1, ry) of the replica
    V0, T, E = rc.tube(p); N = int(p["n_around"])
    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(BLEND))
    sc = bpy.context.scene; rig = bpy.data.objects["UO_Rig"]; body = bpy.data.objects["UO_Body"]
    for o in bpy.data.objects:
        if o.type == "MESH" and o != body:
            o.hide_render = o.hide_viewport = True
    rig.data.pose_position = "POSE"
    me = bpy.data.meshes.new("replica"); me.from_pydata(V0.tolist(), [], T.tolist()); me.update()
    ob = bpy.data.objects.new("replica", me); sc.collection.objects.link(ob)
    hybrid = bool(cfg.get("hybrid", 0))
    ob.vertex_groups.new(name="pelvis").add(list(range(len(V0))), 1.0, "REPLACE")
    pin = ob.vertex_groups.new(name="pin")
    K = int(p["n_rings"])
    for r in range(K + 1):
        if hybrid:                                              # goal strength: 1 at the waist, falling to `goal` at the hem (the hanging part is free to swing and to collide)
            wgt = max(cfg["goal"], 1.0 - (1.0 - cfg["goal"]) * min(1.0, r / max(cfg["goal_rings"], 1.0)))
            pin.add(list(range(r * N, (r + 1) * N)), wgt, "REPLACE")
        elif r < int(cfg["pin_rings"]):
            pin.add(list(range(r * N, (r + 1) * N)), (1.0, 0.5, 0.25)[min(r, 2)], "REPLACE")
    if not hybrid:
        am = ob.modifiers.new("Armature", "ARMATURE"); am.object = rig; am.use_vertex_groups = True
    cm = ob.modifiers.new("Cloth", "CLOTH"); st = cm.settings
    st.quality = int(cfg["quality"]); st.mass = cfg["mass"]; st.tension_stiffness = cfg["tension"]; st.compression_stiffness = cfg["compression"]; st.shear_stiffness = cfg["shear"]
    st.bending_stiffness = cfg["bending"]; st.air_damping = cfg["damp_air"]; st.tension_damping = st.compression_damping = st.shear_damping = cfg["tdamp"]
    st.vertex_group_mass = "pin"; st.pin_stiffness = cfg["pin_stiff"]
    cs = cm.collision_settings; cs.use_collision = bool(cfg["collide"]); cs.distance_min = cfg["dist"]; cs.collision_quality = 4; cs.use_self_collision = False
    sc.gravity = (0, 0, -9.81 * cfg["gravity"])
    body.modifiers.new("Collision", "COLLISION"); body.collision.thickness_outer = 0.005; body.collision.use_culling = False; body.collision.damping = 0.5; body.collision.cloth_friction = cfg["friction"]
    res = {}
    import cloth_lib as cl
    ip = cal.bones.index("pelvis")

    def targets(a, nfr):
        out = []
        for i in range(nfr):
            Sk = cal.skin[cal.index[(a, 0, i)]]
            X = (np.c_[V0, np.ones(len(V0))] @ Sk[ip].T)[:, :3]
            h, t = cal.caps.posed(Sk)
            out.append(X + cl.hull_push(V0, Sk[ip], h, t, cal.caps.radius, margin=cfg["margin"], kappa=cfg["kappa"], z_top=p["z_top"], z_hem=p["z_hem"], use_tent=True, drop=1.0))
        return out

    for act in sorted([a for a in bpy.data.actions if "uo_action" in a], key=lambda a: int(a["uo_action"])):
        a = int(act["uo_action"])
        if a not in acts:
            continue
        t0 = time.time(); rig.animation_data.action = act; rig["uo_direction"] = 0
        nfr = int(act["uo_frames"]); loop = a in LOOP; period = nfr * STEP if loop else (nfr - 1) * STEP + 1
        for fc in act.fcurves:
            for m in list(fc.modifiers):
                fc.modifiers.remove(m)
            m = fc.modifiers.new("CYCLES"); m.mode_before = "REPEAT" if loop else "NONE"; m.mode_after = "REPEAT" if loop else "NONE"
        pre = int(cfg["preroll"]); cyc = int(cfg["cycles"]) if loop else 1
        f0 = 1 - pre; f1 = 1 + period * cyc if loop else 1 + (nfr - 1) * STEP
        sc.frame_start = f0; sc.frame_end = f1; cm.point_cache.frame_start = f0; cm.point_cache.frame_end = f1
        if hybrid:
            tg = targets(a, nfr)

            def setpos(scene, dg=None, tg=tg, nfr=nfr, loop=loop):
                u = (scene.frame_current - 1) / STEP
                u = u % nfr if loop else min(max(u, 0.0), nfr - 1)
                i0 = int(np.floor(u)); fr = u - i0; i1 = (i0 + 1) % nfr if loop else min(i0 + 1, nfr - 1)
                X = tg[i0 % nfr] * (1 - fr) + tg[i1] * fr
                ob.data.vertices.foreach_set("co", X.astype(np.float32).ravel()); ob.data.update()
            bpy.app.handlers.frame_change_pre[:] = [setpos]
            setpos(sc)
        sc.frame_set(f0)
        base = 1 + (cyc - 1) * period if loop else 1
        want = {base + i * STEP: i for i in range(nfr)}
        for f in range(f0, f1 + 1):
            sc.frame_set(f)
            if f in want:
                ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
                co = np.empty(len(V0) * 3, np.float32); ev.data.vertices.foreach_get("co", co)
                res["%d_%d" % (a, want[f])] = co.reshape(-1, 3).astype(np.float64)
        print("action", a, "frames", nfr, "loop", loop, "%.1f s" % (time.time() - t0), flush=True)
    np.savez_compressed(out, **res)


def score(poses, files):
    import robe_calib as rc, cloth_lib as cl
    cal, p = replica(poses)
    V0, T, E = rc.tube(p); ip = cal.bones.index("pelvis")
    row_hip = rc.CANCH[1] - (p["hip"] - 0.07) * 36 * np.cos(np.radians(28.4557))
    from robe_hull_eval import abs_params
    mg, kp = abs_params(p["z_hem"])

    def iou(a, i, X):
        num = den = 0
        for d in range(5):
            g = cal.spr.get((a, d))
            if g is None or i >= len(g) or not g[i].any():
                continue
            D = cal.dirm[cal.index[(a, d, i)]]
            m = rc.raster_mask(cal.project(X @ D[:3, :3].T + D[:3, 3]), T)
            r0, g0 = m[int(row_hip):], g[i][int(row_hip):]
            num += (r0 & g0).sum(); den += (r0 | g0).sum()
        return num / max(den, 1)

    for f in files:
        r = np.load(f); by = {}
        for k in r.files:
            a, i = map(int, k.split("_")); Sk = cal.skin[cal.index[(a, 0, i)]]
            Xp = (np.c_[V0, np.ones(len(V0))] @ Sk[ip].T)[:, :3]
            h, t = cal.caps.posed(Sk)
            Xh = Xp + cl.hull_push(V0, Sk[ip], h, t, cal.caps.radius, margin=mg, kappa=kp, z_top=p["z_top"], z_hem=p["z_hem"], use_tent=True, drop=1.0)
            by.setdefault(a, []).append((iou(a, i, r[k]), iou(a, i, Xh), iou(a, i, Xp)))
        for a, v in sorted(by.items()):
            v = np.array(v).mean(0); print("%s action %d: cloth sim %.3f | leg hull %.3f | rigid on the pelvis %.3f" % (os.path.basename(f), a, *v))


if __name__ == "__main__":
    mode, poses, out = sys.argv[1], sys.argv[2], sys.argv[3]
    if mode == "sim":
        cfg = dict(quality=8, mass=0.3, tension=15.0, compression=15.0, shear=5.0, bending=0.5, damp_air=1.0, tdamp=5.0, dist=0.005, preroll=40, cycles=3, pin_rings=2, gravity=1.0, pin_stiff=1.0, collide=1, friction=0.0, wx=1.0, wy=1.0, hybrid=0, goal=0.3, goal_rings=26, margin=0.05, kappa=0.8)
        cfg.update({k: float(v) for k, v in (kv.split("=") for kv in sys.argv[5:])})
        simulate(poses, out, [int(x) for x in sys.argv[4].split(",")], cfg)
    else:
        score(poses, [out] + sys.argv[4:])
