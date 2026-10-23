"""Smooth, deterministic motion of a cape pinned at the shoulders (no cloth solver): the way the original cloak 468 moves.

    python uo_cloak_motion.py ITEM.blend [--actions 00_walk_unarmed,...|all] [--out cloth_sim.npz] [key=value ...]

ITEM.blend = the item prepared, bound and hugged (uo_make_item.py, kind cloak: custom property uo_cloth type cloak). For every action and frame (direction 0, the posed rig):
  1. the angles of the original cloak (cloak_pitch.json, fitted per action and frame on the sprite 468 over all 5 directions: the turn of the cape about the shoulder line, at the shoulders d0
     and at the hem d1, back = +) are smoothed in time (looping actions: circularly, the table is quantised to 2.5 deg) and scaled (LIFT, RUN_LIFT: the run and the fast ride lift a little
     more); cloth_lib.cloak_bend turns the cape by them: the centre line is the integral of the turn, so the cape bends (stand: hangs straight; run: streams back, drooping to the hem;
     riding: leaves the shoulders backwards and falls over the rump), it is never a plank, and its shoulder line does not move (displacement 0 there: pinned at the shoulders in every pose);
  2. a gentle wave of the gait: a swing of the hem and a sideways sway growing with the distance from the shoulders, in step with the cycle of the action (WAVE_*);
  3. the cape is kept behind the posed body (a smooth field along y, only backwards: a thigh that swings back pushes the hem back, the cape never goes round to the chest) and, in the
     riding actions, out of the horse of the frame (the proxy Horse_a<action>_f<frame>: it lies on the rump and the back of the horse instead of being cut by it);
  4. the three results are smoothed over the cloth (gaussian in rest positions), so the folds of the model move together and the hem stays even.
The result is the DIFFERENCE between that cape and the skinned item (cloth_sim.npz next to item.blend, keys "<action>_<frame>"): render_uo_layer.py adds it (cloth_push, type cloak).
Settings (key=value): lift (1: x the angles of the table), run_lift (1.15: the extra of the run and the fast ride), wave (1: x the gait wave), margin (0.012 m: the cape stays this far off the
body and the horse), smooth (0.04 m), pin (0.06: the share of the cape height below the shoulder line over which the motion fades in, 0 at the line).
"""
import json, math, os, sys, time
import numpy as np
import bpy
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import cloth_lib as cl                                                      # noqa: E402
from bpy_compat import action_fcurves                                       # noqa: E402

STEP = 3
LOOP = {0, 1, 2, 3, 4, 5, 6, 7, 8}
RUN = {2, 3, 24}                                                            # run, run armed, mounted run
CFG = dict(lift=1.0, run_lift=1.15, ride_lift=1.0, wave=1.0, settle=1.0, margin=0.012, smooth=0.05, pin=0.06, near=0.02, slope_min=0.35, rounds=8)
WAVE = {                                                                    # per action: (hem swing deg, sideways sway m, ripple deg)
    0: (4.0, 0.012, 2.5), 1: (4.0, 0.012, 2.5), 2: (5.0, 0.015, 3.5), 3: (5.0, 0.015, 3.5), 15: (4.0, 0.012, 2.5),
    23: (3.0, 0.010, 2.0), 24: (4.0, 0.015, 3.0), 26: (2.0, 0.008, 1.5), 27: (2.0, 0.008, 1.5), 28: (2.0, 0.008, 1.5), 29: (2.0, 0.008, 1.5)}


def table_rows(tab, a, nfr, loop):
    """angles (deg) of the original cloak for this action, one row per frame of ours (resampled when the counts differ), smoothed in time"""
    rows = np.array(tab["actions"].get(str(a)) or [tab["stand"][:2]], float)
    rows = rows - 0.0
    if len(rows) != nfr:
        t = (np.arange(nfr) + 0.0) * len(rows) / nfr if loop else np.linspace(0, len(rows) - 1, nfr)
        i0 = np.floor(t).astype(int); f = t - i0
        rows = rows[i0 % len(rows)] * (1 - f)[:, None] + rows[(i0 + 1) % len(rows) if loop else np.minimum(i0 + 1, len(rows) - 1)] * f[:, None]
    if nfr > 2:
        k = np.array([0.25, 0.5, 0.25]); out = rows.copy()
        for c in range(2):
            x = rows[:, c]
            xp = np.r_[x[-1], x, x[0]] if loop else np.r_[x[0], x, x[-1]]
            out[:, c] = k[0] * xp[:-2] + k[1] * xp[1:-1] + k[2] * xp[2:]
        rows = out
    return rows


def main():
    args = sys.argv[1:]
    blend = os.path.abspath(args.pop(0)); out = None; only = None; cfg = dict(CFG)
    while args:
        a = args.pop(0)
        if a == "--out":
            out = os.path.abspath(args.pop(0))
        elif a == "--actions":
            v = args.pop(0); only = None if v == "all" else set(v.split(","))
        elif "=" in a:
            k, v = a.split("=", 1); cfg[k] = float(v)
    out = out or os.path.join(os.path.dirname(blend), "cloth_sim.npz")
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc = bpy.context.scene; rig = bpy.data.objects["UO_Rig"]; body = bpy.data.objects["UO_Body"]
    items = [o for o in bpy.data.collections["Clothing"].all_objects if o.type == "MESH" and o.get("uo_cloth") and json.loads(o["uo_cloth"]).get("type") == "cloak"]
    if not items:
        raise SystemExit("uo_cloak_motion: no cloak (custom property uo_cloth of type cloak) in the Clothing collection")
    item = items[0]; prm = json.loads(item["uo_cloth"]); nv = len(item.data.vertices)
    tab = json.load(open(os.path.join(HERE, "cloak_pitch.json")))
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    for o in bpy.data.objects:
        if o.type == "MESH" and o not in (body, item) and "Clothing" not in [c.name for c in o.users_collection] and not o.name.startswith("Horse_"):
            o.hide_viewport = True
    rig.data.pose_position = "REST"; bpy.context.view_layer.update()
    co = np.empty(nv * 3, np.float32); item.data.vertices.foreach_get("co", co); Mi = np.array(item.matrix_basis)
    Vr = co.reshape(-1, 3).astype(np.float64) @ Mi[:3, :3].T + Mi[:3, 3]
    rig.data.pose_position = "POSE"
    z_top, z_hem, y_top = prm["z_top"], prm["z_hem"], prm["y_top"]; H = max(z_top - z_hem, 1e-3)
    s = np.clip((z_top - Vr[:, 2]) / H, 0.0, 1.0)                                            # 0 at the shoulder line, 1 at the hem
    wpin = np.clip(s / max(cfg["pin"], 1e-6), 0.0, 1.0) if cfg["pin"] > 0 else np.ones(nv)
    wpin = wpin * wpin * (3 - 2 * wpin)                                                       # smoothstep: the motion fades in below the shoulder line, 0 on it
    # a gaussian over the cloth (rest positions): smoothing of the displacement fields
    r = cfg["smooth"]; pr = cKDTree(Vr).query_pairs(3 * r, output_type="ndarray")
    dd = np.linalg.norm(Vr[pr[:, 0]] - Vr[pr[:, 1]], axis=1); wk = np.exp(-0.5 * (dd / r) ** 2)
    K = coo_matrix((np.r_[wk, wk, np.ones(nv)], (np.r_[pr[:, 0], pr[:, 1], np.arange(nv)], np.r_[pr[:, 1], pr[:, 0], np.arange(nv)])), shape=(nv, nv)).tocsr()
    ks = np.asarray(K.sum(1)).ravel()
    smooth = lambda D: (K @ D) / (ks[:, None] if D.ndim > 1 else ks)
    smooth_n = lambda D, n: [D := smooth(D) for _ in range(n)][-1]            # n passes: the effective width grows with sqrt(n)
    # neighbours in (x, z) of the rest cape: the "behind the skin" targets are dilated over them
    kxz = cKDTree(Vr[:, [0, 2]]); nbr = kxz.query_ball_point(Vr[:, [0, 2]], cfg["near"])
    names = ["chest"]; inv_local = {n: np.linalg.inv(np.array(rig.data.bones[n].matrix_local)) for n in names}
    Mr0 = np.array(rig.matrix_world)
    res = {}
    acts = sorted([a for a in bpy.data.actions if "uo_action" in a], key=lambda a: int(a["uo_action"]))
    fwd = Vector((0.0, -1.0, 0.0))
    for act in acts:
        a = int(act["uo_action"])
        if only is not None and act.name not in only:
            continue
        t0 = time.time(); rig.animation_data.action = act; rig["uo_direction"] = 0
        nfr = int(act["uo_frames"]); loop = a in LOOP
        for fc in action_fcurves(act):
            for m in list(fc.modifiers):
                fc.modifiers.remove(m)
        rows = table_rows(tab, a, nfr, loop) * cfg["lift"] * (cfg["run_lift"] if a in RUN else 1.0) * (cfg["ride_lift"] if 23 <= a <= 29 else 1.0)
        wv = WAVE.get(a)
        moved = []
        for i in range(nfr):
            sc.frame_set(1 + i * STEP); rig.update_tag(); bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get()
            ev = item.evaluated_get(dg); c = np.empty(nv * 3, np.float32); ev.data.vertices.foreach_get("co", c)
            M = np.array(item.matrix_world); sk = c.reshape(-1, 3).astype(np.float64) @ M[:3, :3].T + M[:3, 3]
            evr = rig.evaluated_get(dg); Rc = (Mr0 @ np.array(evr.pose.bones["chest"].matrix) @ inv_local["chest"] @ np.linalg.inv(Mr0))[:3, :3]
            d0, d1 = np.radians(rows[i])
            ph = 2 * math.pi * i / nfr if nfr > 1 else 0.0
            if wv and cfg["wave"] > 0 and nfr > 1:                                                  # the gait wave: the hem swings, the cape sways sideways, a ripple runs down it
                d1 = d1 + math.radians(wv[0]) * cfg["wave"] * math.sin(ph)
            D = cl.cloak_bend(Vr, z_top, z_hem, y_top, d0, d1)                                     # rest frame
            if wv and cfg["wave"] > 0 and nfr > 1:
                ripple = math.radians(wv[2]) * cfg["wave"] * s * np.sin(ph - 2.5 * s)             # along the centre line: a small extra turn growing with the distance
                D[:, 1] += H * (s ** 2) * 0.5 * ripple
                D[:, 0] += wv[1] * cfg["wave"] * (s ** 1.5) * math.sin(ph + 0.8)
            D = D * wpin[:, None]
            P = sk + D @ Rc.T                                                                       # world
            # behind the posed body: only backwards (+y), a smooth field
            eb = body.evaluated_get(dg); mb = eb.to_mesh(); Mb = eb.matrix_world
            bvh = BVHTree.FromPolygons([Mb @ v.co for v in mb.vertices], [tuple(p.vertices) for p in mb.polygons]); eb.to_mesh_clear()
            horse = bpy.data.objects.get("Horse_a%d_f%d" % (a, i)) if 23 <= a <= 29 else None
            ty = np.full(nv, -np.inf)
            for k in np.nonzero(wpin > 0)[0]:
                loc, nor, _, dist = bvh.ray_cast(Vector(P[k]), fwd, 0.35)
                if loc is not None and nor.dot(fwd) <= 0:
                    ty[k] = loc.y + cfg["margin"] / max(abs(nor.y), cfg["slope_min"])
            ty0 = ty.copy()
            for k in np.nonzero(np.isfinite(ty0))[0]:
                ty[k] = max(ty0[j] for j in nbr[k] if np.isfinite(ty0[j]))
            need = np.where(np.isfinite(ty), np.maximum(ty - P[:, 1], 0.0), 0.0) * wpin
            P[:, 1] += np.maximum(smooth(need), need)                                               # the correction is spread over the cloth, never less than what a vertex needs
            if horse is not None:                                                                    # riding: out of the horse of this frame (nearest-surface push, smooth)
                dgh = bpy.context.evaluated_depsgraph_get(); eh = horse.evaluated_get(dgh); mh = eh.to_mesh(); Mh = eh.matrix_world
                hb = BVHTree.FromPolygons([Mh @ v.co for v in mh.vertices], [tuple(p.vertices) for p in mh.polygons]); eh.to_mesh_clear()
                if cfg["settle"] > 0:                                                                # gravity: what hangs over the horse falls onto it (down to its surface), smoothly
                    ws = np.clip((s - 0.18) / 0.2, 0.0, 1.0); ws = ws * ws * (3 - 2 * ws) * cfg["settle"]; drop = np.zeros(nv); down = Vector((0.0, 0.0, -1.0))
                    for k in np.nonzero(ws > 0)[0]:
                        loc, nor, _, dist = hb.ray_cast(Vector(P[k]), down, 0.9)
                        if loc is not None and nor.dot(down) < 0:
                            drop[k] = dist - cfg["margin"]                                          # the surface is below it (seen from outside): it falls this far
                    drop = np.maximum(drop, 0.0) * ws
                    P[:, 2] -= smooth_n(drop, 4)
                for _ in range(int(cfg["rounds"])):
                    G = np.zeros((nv, 3)); any_ = False
                    for k in np.nonzero(wpin > 0)[0]:
                        loc, nor, _, dist = hb.find_nearest(Vector(P[k]), 0.4)
                        if loc is None:
                            continue
                        sd = (Vector(P[k]) - loc).dot(nor); want = cfg["margin"] - sd
                        if want > 1e-4:
                            G[k] = np.array(nor) * want; any_ = True
                    if not any_:
                        break
                    P = P + smooth_n(G, 4) * 1.6 * wpin[:, None]
            dlt = P - sk
            res["%d_%d" % (a, i)] = dlt.astype(np.float32); moved.append(float(np.linalg.norm(dlt, axis=1).max()))
        print("action %2d %-26s %d frames, %.0f s, largest move %.2f m (angles d0 %.0f..%.0f d1 %.0f..%.0f deg)" % (a, act.name, nfr, time.time() - t0, max(moved), rows[:, 0].min(), rows[:, 0].max(), rows[:, 1].min(), rows[:, 1].max()), flush=True)
    np.savez_compressed(out, **res)
    print("wrote", out, "(%d frames)" % len(res))


if __name__ == "__main__":
    main()
