"""Free-hanging cloth for loose garments (skirt, girdle, kilt): position based dynamics against the legs, pinned at the waistband ONLY.

    python uo_cloth_pbd.py ITEM.blend [--actions 00_walk_unarmed,...|all] [--out cloth_sim.npz] [--jobs 4] [key=value ...]

Same input and the same output as uo_cloth_sim.py (cloth_sim.npz, keys "<action>_<frame>" = the simulated position minus what render_uo_layer.py draws without a simulation: the item as the
skeleton skins it + the leg push), so the renderer needs no change (CLOTH_SIM = 1). What differs is what holds the cloth:
  - Blender's cloth with a pin goal everywhere is pulled to a kinematic target (the leg hull): the cloth is attracted to the body. With the pin only at the waistband (goal 0 below it) it crumpled
    into ropes in the walk: a leg swings 10 cm per frame through a sheet that is not thick, Blender's collision lets it through and the contact solver throws the sheet around (measured on the
    Radiant Star Girdle, 16k vertices: quality 8-24, collision margin 6-20 mm, mass x1-x3, fit gap 14-20 mm: the cloth bunched above the knees in every variant).
  - Here: the band (vertices above z_top - 2 cm) follows the skeleton exactly, everything below hangs free: gravity, air drag, stretch constraints along every edge (silk hardly stretches), weak
    bending constraints across every pair of neighbouring triangles (silk folds easily), the legs and the pelvis as capsules (collision by projection, in every sub-step of every UO frame, so a
    leg never gets through), the ground as a plane. Nothing pulls the cloth to the legs or to a shape: it drapes over them and falls back by its own weight. Loose pieces that touch no
    pinned vertex (shards of a generated model) follow the skin (island 1), else they fall away for ever.
Every action is simulated on its own: PREROLL frames in its first pose (looping actions: the loop), CYCLES loops of a looping action, the last one is kept (the loop closes without a jump).
Settings (key=value): substeps (8 per UO frame), iters (60 Gauss-Seidel iterations per sub-step: with 10 a 0.8 m skirt of 16k vertices stretches by 0.15 m under its own weight, with 60 by 2 cm, 100 by 1 cm), stretch (1: stiffness of the edges, 0..1), bend (0.15: of the bending constraints; silk 0.05-0.3),
damp (1.5 1/s: air drag + internal damping; a heavier, calmer cloth: 3-5; 0 = a pendulum that never stops), gravity (1: x 9.81), friction (0.3: share of the velocity a vertex loses in a sub-step
in which it touches a leg), margin (0.012 m: the cloth stays this far outside the capsule), rpct (75: percentile of the skin distance that is the radius of a capsule), upper (z_top - 0.02 m: the band is
the vertices above z_top + (upper - 0.02)), ramp (0.04 m: how far below the band the pin fades out to zero), island (1), preroll (20 UO-frame durations... in frames of 1/fps x STEP), cycles (2),
glue (0; 0.025 m = pieces of the mesh that are not connected to the cloth, e.g. the strips of uo_fill_banner_gap.py, are tied to the nearest vertices within this distance), smooth (0.03 m: the move averaged over this distance in space, 2 passes, as in uo_cloth_sim.py; 0 = off), abs (0; 1 = also write <out>.abs.npz with the positions themselves), mounted (not simulated, as there).
"""
import json, os, sys, time
import numpy as np
import bpy

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import cloth_lib as cl                                                      # noqa: E402

STEP = 3
LOOP = {0, 1, 2, 3, 4, 5, 6, 7, 8}
CFG = dict(substeps=8, iters=60, stretch=1.0, bend=0.15, damp=1.5, gravity=1.0, friction=0.3, margin=0.012, rpct=75.0, upper=0.0, ramp=0.04, island=1.0, preroll=20, cycles=2,
           smooth=0.03, abs=0.0, floor=0.012, mounted=0.0, glue=0.0)

try:
    from numba import njit
except ImportError:                                                         # slower, same result
    def njit(*a, **k):
        return (lambda f: f) if not (a and callable(a[0])) else a[0]


@njit(cache=True)
def substep(x, v, tgt, pinw, invm, E, L0, B, LB, ch, ct, cr, dt, g, damp, iters, kst, kbe, fric, floor, nst):
    """one sub-step: predict, project the constraints and the collisions, new velocity"""
    n = x.shape[0]; p = np.empty_like(x); hit = np.zeros(n, np.bool_)
    for i in range(n):
        if pinw[i] >= 0.999:
            for k in range(3):
                p[i, k] = tgt[i, k]
        else:
            v[i, 2] -= g * dt
            for k in range(3):
                p[i, k] = x[i, k] + v[i, k] * dt
    ne = E.shape[0]; nb = B.shape[0]; nc = ch.shape[0]
    for it in range(iters):
        for ee in range(ne):
            e = ee if it % 2 == 0 else ne - 1 - ee
            i = E[e, 0]; j = E[e, 1]; w = invm[i] + invm[j]
            if w <= 0.0:
                continue
            dx = p[j, 0] - p[i, 0]; dy = p[j, 1] - p[i, 1]; dz = p[j, 2] - p[i, 2]
            d = np.sqrt(dx * dx + dy * dy + dz * dz)
            if d < 1e-9:
                continue
            c = kst * (d - L0[e]) / (d * w)
            p[i, 0] += invm[i] * c * dx; p[i, 1] += invm[i] * c * dy; p[i, 2] += invm[i] * c * dz
            p[j, 0] -= invm[j] * c * dx; p[j, 1] -= invm[j] * c * dy; p[j, 2] -= invm[j] * c * dz
        for bb in range(nb):
            e = bb if it % 2 == 0 else nb - 1 - bb
            i = B[e, 0]; j = B[e, 1]; w = invm[i] + invm[j]
            if w <= 0.0:
                continue
            dx = p[j, 0] - p[i, 0]; dy = p[j, 1] - p[i, 1]; dz = p[j, 2] - p[i, 2]
            d = np.sqrt(dx * dx + dy * dy + dz * dz)
            if d < 1e-9:
                continue
            c = kbe * (d - LB[e]) / (d * w)
            p[i, 0] += invm[i] * c * dx; p[i, 1] += invm[i] * c * dy; p[i, 2] += invm[i] * c * dz
            p[j, 0] -= invm[j] * c * dx; p[j, 1] -= invm[j] * c * dy; p[j, 2] -= invm[j] * c * dz
        for i in range(n):
            if pinw[i] > 0.0 and pinw[i] < 0.999:                          # the fade below the band: a spring to the skeleton
                for k in range(3):
                    p[i, k] += 0.5 * pinw[i] * (tgt[i, k] - p[i, k])
            if pinw[i] >= 0.999:
                continue
            for c in range(nc):                                             # the legs / the pelvis: out of the capsule
                ax = ch[c, 0]; ay = ch[c, 1]; az = ch[c, 2]
                bx = ct[c, 0] - ax; by = ct[c, 1] - ay; bz = ct[c, 2] - az
                ll = bx * bx + by * by + bz * bz
                t = ((p[i, 0] - ax) * bx + (p[i, 1] - ay) * by + (p[i, 2] - az) * bz) / max(ll, 1e-12)
                t = min(max(t, 0.0), 1.0)
                qx = p[i, 0] - (ax + t * bx); qy = p[i, 1] - (ay + t * by); qz = p[i, 2] - (az + t * bz)
                d = np.sqrt(qx * qx + qy * qy + qz * qz)
                if d < cr[c]:
                    if d < 1e-9:
                        qx, qy, qz, d = 0.0, 0.0, 1.0, 1.0
                    s = (cr[c] - d) / d
                    p[i, 0] += qx * s; p[i, 1] += qy * s; p[i, 2] += qz * s
                    hit[i] = True
            if p[i, 2] < floor:
                p[i, 2] = floor; hit[i] = True
    for i in range(n):
        f = np.exp(-damp * dt)
        if hit[i]:
            f *= 1.0 - fric
        for k in range(3):
            v[i, k] = (p[i, k] - x[i, k]) / dt * f
            x[i, k] = p[i, k]


def mesh_constraints(item):
    """edges and the bending pairs (the two vertices opposite an edge shared by two triangles), rest lengths from the item as it is bound (the rest shape of the cloth)"""
    me = item.data; nv = len(me.vertices)
    co = np.empty(nv * 3, np.float32); me.vertices.foreach_get("co", co); V = co.reshape(-1, 3).astype(np.float64)
    M = np.array(item.matrix_basis); V = V @ M[:3, :3].T + M[:3, 3]
    me.calc_loop_triangles()
    T = np.empty(len(me.loop_triangles) * 3, np.int32); me.loop_triangles.foreach_get("vertices", T); T = T.reshape(-1, 3)
    a = np.r_[T[:, 0], T[:, 1], T[:, 2]]; b = np.r_[T[:, 1], T[:, 2], T[:, 0]]; o = np.r_[T[:, 2], T[:, 0], T[:, 1]]
    lo = np.minimum(a, b); hi = np.maximum(a, b)
    key = lo.astype(np.int64) * nv + hi
    order = np.argsort(key, kind="stable"); ks = key[order]
    uk, first, cnt = np.unique(ks, return_index=True, return_counts=True)
    E = np.c_[uk // nv, uk % nv].astype(np.int32)
    two = np.nonzero(cnt == 2)[0]
    B = np.c_[o[order[first[two]]], o[order[first[two] + 1]]].astype(np.int32)
    B = B[B[:, 0] != B[:, 1]]
    L0 = np.linalg.norm(V[E[:, 0]] - V[E[:, 1]], axis=1); LB = np.linalg.norm(V[B[:, 0]] - V[B[:, 1]], axis=1)
    return V, E, L0, B, LB


def glue_pairs(V, E, dist, k=4):
    """pieces of the mesh that are not connected to the main cloth (the strips filled in between a banner and its frame by uo_fill_banner_gap.py: a mesh of 3 mm, 230 rows, that the solver cannot hold
    up by its own edges) are tied to the nearest vertices of the other pieces within `dist` m by distance constraints with their rest lengths: they move with the cloth they lie next to"""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    from scipy.spatial import cKDTree
    n = len(V)
    nc, comp = connected_components(coo_matrix((np.ones(len(E)), (E[:, 0], E[:, 1])), shape=(n, n)), directed=False)
    big = np.argmax(np.bincount(comp))
    d, nb = cKDTree(V).query(V, k=k + 1)
    pairs = set()
    for i in np.nonzero(comp != big)[0]:
        for dd, j in zip(d[i, 1:], nb[i, 1:]):
            if dd < dist and comp[j] != comp[i]:
                pairs.add((min(i, j), max(i, j)))
    G = np.array(sorted(pairs), np.int32).reshape(-1, 2)
    return G, np.linalg.norm(V[G[:, 0]] - V[G[:, 1]], axis=1) if len(G) else np.zeros(0)


def run_parallel(blend, out, only, jobs, extra):
    import subprocess, tempfile
    bpy.ops.wm.open_mainfile(filepath=blend)
    names = [a.name for a in sorted([a for a in bpy.data.actions if "uo_action" in a], key=lambda a: int(a["uo_action"])) if not (23 <= int(a["uo_action"]) <= 29) and (only is None or a.name in only)]
    groups = [names[k::jobs] for k in range(jobs)]
    tmp = tempfile.mkdtemp(prefix="uo_cloth_pbd_"); procs = []
    for k, g in enumerate(groups):
        if g:
            procs.append((k, subprocess.Popen([sys.executable, os.path.abspath(__file__), blend, "--actions", ",".join(g), "--out", os.path.join(tmp, "p%d.npz" % k)] + extra,
                                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)))
    merged = {}; merged_abs = {}
    for k, p in procs:
        txt = p.communicate()[0]
        print("".join(l + "\n" for l in txt.splitlines() if l.startswith(("action", "uo_cloth_pbd"))), end="", flush=True)
        f = os.path.join(tmp, "p%d.npz" % k)
        if not os.path.exists(f):
            raise SystemExit("worker %d failed:\n%s" % (k, txt[-1500:]))
        z = np.load(f); merged.update({n: z[n] for n in z.files})
        if os.path.exists(f + ".abs.npz"):
            z = np.load(f + ".abs.npz"); merged_abs.update({n: z[n] for n in z.files})
    np.savez_compressed(out, **merged)
    if merged_abs:
        np.savez_compressed(out + ".abs.npz", **merged_abs)
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
            k, v = a.split("=", 1)
            if k not in cfg:
                raise SystemExit("unknown setting %s (%s)" % (k, ", ".join(cfg)))
            cfg[k] = float(v); extra.append(a)
    out = out or os.path.join(os.path.dirname(blend), "cloth_sim.npz")
    if jobs > 1:
        return run_parallel(blend, out, only, jobs, extra)
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc = bpy.context.scene; rig = bpy.data.objects["UO_Rig"]; body = bpy.data.objects["UO_Body"]
    items = [o for o in bpy.data.collections["Clothing"].all_objects if o.type == "MESH" and o.get("uo_cloth") and json.loads(o["uo_cloth"]).get("type") != "cloak"]
    if not items:
        raise SystemExit("no loose garment (custom property uo_cloth) in the Clothing collection")
    item = items[0]; prm = json.loads(item["uo_cloth"]); nv = len(item.data.vertices)
    for o in bpy.data.objects:
        if o.type == "MESH" and o not in (body, item) and "Clothing" not in [c.name for c in o.users_collection]:
            o.hide_viewport = True
    for o in items[1:]:
        o.hide_viewport = True
    rig.data.pose_position = "POSE"
    fps = sc.render.fps / sc.render.fps_base; dt_frame = STEP / fps; ns = int(cfg["substeps"]); dt = dt_frame / ns

    # --- capsules (legs + pelvis) as uo_cloth_sim.py builds them --------------------------------------------------------------------------------------------------------------
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
    caps = cl.Capsules(names, rest_h, rest_t, Vb, dom, names=tuple(cl.Capsules.NAMES) + ("pelvis",), percentile=cfg["rpct"])
    caps_leg = cl.Capsules(names, rest_h, rest_t, Vb, dom)                                    # the legs only, as the renderer's push (cloth_lib.hull_push) builds them
    inv_local = {n: np.linalg.inv(np.array(rig.data.bones[n].matrix_local)) for n in names}
    sel = np.array(["pelvis" not in names[k] for k in caps_leg.idx])
    Vr, E, L0, B, LB = mesh_constraints(item)
    if cfg["glue"] > 0:
        G, LG = glue_pairs(Vr, E, cfg["glue"])
        print("uo_cloth_pbd: %d glue constraints tie the loose strips (%.0f mm) to the cloth next to them" % (len(G), 1000 * cfg["glue"]), flush=True)
        E = np.r_[E, G].astype(np.int32); L0 = np.r_[L0, LG]
    rig.data.pose_position = "POSE"; bpy.context.view_layer.update()
    print("uo_cloth_pbd: item %s, %d vertices, %d edges, %d bending pairs, %d capsules (radii %s), dt %.1f ms x %d sub-steps, waist %.2f m" % (
        item.name, nv, len(E), len(B), len(caps.idx), ", ".join("%.3f" % r for r in caps.radius), 1000 * dt, ns, prm["z_top"]), flush=True)

    def skin_mats():
        dg = bpy.context.evaluated_depsgraph_get(); evr = rig.evaluated_get(dg)
        return {n: Mr0 @ np.array(evr.pose.bones[n].matrix) @ inv_local[n] @ np.linalg.inv(Mr0) for n in names}

    def leg_state(skin, c):
        heads = np.array([(skin[names[k]] @ np.append(c.head[j], 1))[:3] for j, k in enumerate(c.idx)])
        tails = np.array([(skin[names[k]] @ np.append(c.tail[j], 1))[:3] for j, k in enumerate(c.idx)])
        return heads, tails

    def kinematic(skin):
        """the item as the renderer draws it before the simulation: skinned + the push of the legs (the base of cloth_sim.npz), and the skinned item alone (what the band follows)"""
        dg = bpy.context.evaluated_depsgraph_get(); ev = item.evaluated_get(dg)
        c = np.empty(nv * 3, np.float32); ev.data.vertices.foreach_get("co", c)
        M = np.array(item.matrix_world); sk = c.reshape(-1, 3).astype(np.float64) @ M[:3, :3].T + M[:3, 3]
        h, t = leg_state(skin, caps_leg)
        if prm.get("hull") == "rel":
            push = cl.hull_push_rel(Vr, skin["pelvis"], h[sel], t[sel], caps_leg.radius[sel], caps_leg.head[sel], caps_leg.tail[sel], centre_xy=tuple(prm["centre"]), kappa=prm["kappa"],
                                    z_top=prm["z_top"], z_hem=prm["z_hem"], ramp=prm.get("ramp", 0.15), drop=prm.get("drop", 1.0))
        else:
            push = cl.hull_push(Vr, skin["pelvis"], h[sel], t[sel], caps_leg.radius[sel], centre_xy=tuple(prm["centre"]), margin=prm["margin"], kappa=prm["kappa"],
                                z_top=prm["z_top"], z_hem=prm["z_hem"], ramp=prm.get("ramp", 0.15), drop=prm.get("drop", 1.0))
        return sk + push, sk

    # --- which vertices the skeleton holds ------------------------------------------------------------------------------------------------------------------------------------
    z = Vr[:, 2]; top = prm["z_top"] - 0.02 + cfg["upper"]
    pinw = np.clip(1.0 - (top - z) / max(cfg["ramp"], 1e-6), 0.0, 1.0)
    if cfg["island"] > 0:
        from scipy.sparse import coo_matrix
        from scipy.sparse.csgraph import connected_components
        nc, comp = connected_components(coo_matrix((np.ones(len(E)), (E[:, 0], E[:, 1])), shape=(nv, nv)), directed=False)
        held = np.zeros(nc, bool); held[np.unique(comp[pinw >= 0.5])] = True
        loose = ~held[comp]; pinw = np.where(loose, 1.0, pinw)
        print("uo_cloth_pbd: %d vertices pinned (the band), %d in the fade, %d in %d loose pieces follow the skin" % (int((pinw >= 0.999).sum() - loose.sum()), int(((pinw > 0) & (pinw < 0.999)).sum()), int(loose.sum()), int((~held).sum())), flush=True)
    invm = np.where(pinw >= 0.999, 0.0, 1.0)
    margin = cfg["margin"]
    res = {}; ABS = {}
    acts = sorted([a for a in bpy.data.actions if "uo_action" in a], key=lambda a: int(a["uo_action"]))
    from bpy_compat import action_fcurves
    for act in acts:
        a = int(act["uo_action"])
        if (23 <= a <= 29 and not cfg["mounted"]) or (only is not None and act.name not in only):
            continue
        t0 = time.time(); rig.animation_data.action = act; rig["uo_direction"] = 0
        nfr = int(act["uo_frames"]); loop = a in LOOP
        T = []; S = []; CH = []; CT = []
        for i in range(nfr):
            sc.frame_set(1 + i * STEP); rig.update_tag(); bpy.context.view_layer.update()
            skin = skin_mats(); base, sk = kinematic(skin); h, t = leg_state(skin, caps)
            T.append(base); S.append(sk); CH.append(h); CT.append(t)
        T = np.array(T); S = np.array(S); CH = np.array(CH); CT = np.array(CT); cr = caps.radius + margin
        x = T[0].copy(); v = np.zeros_like(x)
        pre = int(round(cfg["preroll"])); cyc = int(cfg["cycles"]) if loop else 1
        seq = [0] * pre + [i for _ in range(cyc) for i in range(nfr)]                  # frame indices in the order they are played; the preroll holds the first pose
        keep = {}
        for q, i in enumerate(seq):
            j = (i + 1) % nfr if loop else min(i + 1, nfr - 1)
            hold = q < pre
            for s in range(ns):
                al = 0.0 if hold else (s + 1) / ns
                tgt = S[i] + al * (S[j] - S[i]); ch = CH[i] + al * (CH[j] - CH[i]); ct = CT[i] + al * (CT[j] - CT[i])
                substep(x, v, tgt, pinw, invm, E, L0, B, LB, ch, ct, cr, dt, 9.81 * cfg["gravity"], cfg["damp"], int(cfg["iters"]), cfg["stretch"], cfg["bend"], cfg["friction"], cfg["floor"], 0)
            if not loop and q == pre - 1:                                                # the state after the preroll is frame 0 of an action that is played once
                keep[0] = x.copy()
            if q >= pre and q >= len(seq) - nfr:                                         # the last loop: the state at the end of UO frame i is the pose of frame j = i + 1
                keep[j % nfr if loop else j] = x.copy()
        for i in range(nfr):
            c = keep.get(i)
            if c is None:
                c = x.copy() if i == nfr - 1 else T[i]
            res["%d_%d" % (a, i)] = (c - T[i]).astype(np.float32)
            if cfg["abs"]:
                ABS["%d_%d" % (a, i)] = c.astype(np.float16)
        d = np.array([np.linalg.norm(res["%d_%d" % (a, i)], axis=1).max() for i in range(nfr)])
        print("action %2d %-26s %d frames, loop %s, %.0f s, largest cloth move %.2f m" % (a, act.name, nfr, loop, time.time() - t0, d.max()), flush=True)
    if cfg["smooth"] > 0 and res:
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
    if ABS:
        np.savez_compressed(out + ".abs.npz", **ABS)
    print("wrote", out, "(%d frames)" % len(res))


if __name__ == "__main__":
    main()
