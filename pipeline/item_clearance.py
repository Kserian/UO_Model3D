"""How close does a worn item come to the body, and how much does it stretch, in every frame of every action (numpy skinning, no render).

    python item_clearance.py ITEM.blend [--actions all|04_stand,00_walk_unarmed,...] [--gap 0.005] [--json out.json] [--npz frames.npz] [--no-push]

Every item vertex belongs to the body region it is skinned to (the biggest share of its weight: torso, left arm, right arm, left leg, right leg). Per frame the signed
distance of every item vertex to the whole (closed) body skin is taken, and the body region of the nearest skin decides whose it is:
  own<gap   share of the item vertices closer than `gap` to the skin of their OWN region (a sleeve to its arm and hand, the body of a shirt to the torso and head), or in it,
  own<0     share inside the skin of their own region, and the deepest (mm). This is the skin poking through the item.
  legs<0    a skirt (loose garment): share inside the legs after the push of the legs (render_uo_layer.py pushes these out by BODY_GAP).
  bare<0    share inside a hand or the head (a hand bent into its cuff, the chin into a collar: bare parts move into the item, as they do in cloth),
  cross<0   share inside the skin of ANOTHER region (a sleeve pressed into the side of the torso: the arm in its sleeve is between them, a body-to-body contact).
  stretch   edge length in the pose / at rest over the welded item edges: p99, and the share of edges stretched by more than 30 % (and the same for the
            body skin under the item, for comparison: a skin-tight item cannot stretch less than the skin).
Items of a loose garment (custom property uo_cloth) get the push of the legs of render_uo_layer.py (cloth_lib.hull_push, no simulation) before they are measured, and
conformed items (custom property uo_conform, uo_conform_item.py) the per-frame push out of the skin of their region (cloth_lib.conform_push) as the render does it
(--no-push: measured as skinned, before it).
"""
import sys, os, json
import numpy as np
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

STEP_SCENE = 3
HERE = os.path.dirname(os.path.abspath(__file__))
REGIONS = ("torso", "arm.L", "arm.R", "leg.L", "leg.R")


def bone_region(name):
    n = name.split(".")[0]
    side = name[-2:] if name[-2:] in (".L", ".R") else ""
    if n in ("upper_arm", "forearm"):
        return "arm" + side
    if n == "hand" or n.startswith("finger"):
        return "hand" + side
    if n in ("thigh", "shin", "foot"):
        return "leg" + side
    if n == "head":
        return "head"
    if n in ("polearm", "axe2h", "bow", "shield", "weapon1h"):
        return "hand" + side
    return "torso"


def weights(ob, bones):
    """dense (n, B) skin weights over the rig bones, normalised like the Armature modifier"""
    W = np.zeros((len(ob.data.vertices), len(bones)))
    gi = {g.index: bones.index(g.name) for g in ob.vertex_groups if g.name in bones}
    for v in ob.data.vertices:
        for g in v.groups:
            if g.group in gi:
                W[v.index, gi[g.group]] += g.weight
    s = W.sum(1, keepdims=True)
    return np.where(s > 0, W / np.maximum(s, 1e-12), 0.0)


def rest_co(ob):
    co = np.empty(len(ob.data.vertices) * 3, np.float32); ob.data.vertices.foreach_get("co", co)
    M = np.array(ob.matrix_world)
    return co.reshape(-1, 3).astype(np.float64) @ M[:3, :3].T + M[:3, 3]


def welded(ob, V):
    key = np.round(V / 1e-5).astype(np.int64)
    _, first, node = np.unique(key, axis=0, return_index=True, return_inverse=True); node = node.ravel()
    E = np.empty(len(ob.data.edges) * 2, np.int32); ob.data.edges.foreach_get("vertices", E)
    E = np.unique(np.sort(node[E.reshape(-1, 2)], 1), axis=0); E = E[E[:, 0] != E[:, 1]]
    return first, node, E


def skin_points(V, W, S):
    """linear blend skinning: V (n, 3) rest, W (n, B), S (B, 4, 4)"""
    out = np.zeros_like(V)
    for b in np.nonzero(W.any(0))[0]:
        m = W[:, b] > 0
        out[m] += W[m, b, None] * (V[m] @ S[b, :3, :3].T + S[b, :3, 3])
    return out


def capture(rig, acts, want, bones):
    sc = bpy.context.scene
    Mw0 = np.array(rig.matrix_world)
    inv_local = {b: np.linalg.inv(np.array(rig.data.bones[b].matrix_local)) for b in bones}
    rig.data.pose_position = "POSE"; rig["uo_direction"] = 0
    out = []
    for a in want:
        act = acts[a]; rig.animation_data.action = act
        for i in range(int(act["uo_frames"])):
            sc.frame_set(1 + i * STEP_SCENE); rig.update_tag(); bpy.context.view_layer.update()
            ev = rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
            out.append((a, i, np.stack([Mw0 @ np.array(ev.pose.bones[b].matrix) @ inv_local[b] @ np.linalg.inv(Mw0) for b in bones])))
    rig.data.pose_position = "REST"
    return out


def signed(bvh, P, reach=0.3):
    S = np.full(len(P), reach); F = np.full(len(P), -1)
    for k, p in enumerate(P):
        loc, nrm, fi, d = bvh.find_nearest(Vector(p), reach)
        if loc is not None:
            S[k] = (Vector(p) - loc).dot(nrm); F[k] = fi
    return S, F


def main():
    args = sys.argv[1:]
    blend = os.path.abspath(args.pop(0))
    actions, gap, out, npz, push = "all", 0.005, None, None, True
    while args:
        f = args.pop(0)
        if f == "--actions":
            actions = args.pop(0)
        elif f == "--gap":
            gap = float(args.pop(0))
        elif f == "--json":
            out = args.pop(0)
        elif f == "--npz":
            npz = args.pop(0)
        elif f == "--no-push":
            push = False
    bpy.ops.wm.open_mainfile(filepath=blend)
    rig, body = bpy.data.objects["UO_Rig"], bpy.data.objects["UO_Body"]
    items = [o for o in bpy.data.collections["Clothing"].all_objects if o.type == "MESH" and not o.hide_render]
    acts = {int(a["uo_action"]): a for a in bpy.data.actions if "uo_action" in a}
    want = sorted(acts) if actions == "all" else [int(x[:2]) for x in actions.split(",")]
    bones = [b.name for b in rig.data.bones]
    breg = np.array([bone_region(b) for b in bones])
    rig.data.pose_position = "REST"; bpy.context.view_layer.update()

    Vb = rest_co(body); Wb = weights(body, bones)
    me = body.data; me.calc_loop_triangles()
    tri = np.array([t.vertices[:] for t in me.loop_triangles])
    vreg = breg[Wb.argmax(1)]
    treg = np.array([max(set(r), key=list(r).count) for r in vreg[tri]])

    import importlib.util
    spec = importlib.util.spec_from_file_location("cloth_lib", os.path.join(HERE, "cloth_lib.py")); cl = importlib.util.module_from_spec(spec); spec.loader.exec_module(cl)
    heads = np.array([np.array(rig.matrix_world @ rig.data.bones[b].head_local) for b in bones])
    tails = np.array([np.array(rig.matrix_world @ rig.data.bones[b].tail_local) for b in bones])
    caps = cl.Capsules(bones, heads, tails, Vb, np.array(bones)[Wb.argmax(1)])

    data = []
    for o in items:
        V = rest_co(o); W = weights(o, bones)
        first, node, E = welded(o, V)
        Vn, Wn = V[first], W[first]
        share = np.stack([Wn[:, breg == r].sum(1) for r in REGIONS], 1)
        reg = np.array(REGIONS)[share.argmax(1)]
        prm = json.loads(o["uo_cloth"]) if o.get("uo_cloth") and "type" not in json.loads(o["uo_cloth"]) else None
        under = np.unique(tri[np.isin(treg, list(set(reg)))].ravel())        # body skin of the regions the item covers (for the stretch comparison)
        Eb = np.unique(np.sort(np.concatenate([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [0, 2]]]), 1), axis=0)
        Eb = Eb[np.isin(Eb, under).all(1)]
        conf = None
        if push and o.get("uo_conform") and "uo_region" in o.data.attributes:
            lab = np.empty(len(o.data.vertices), np.int32); o.data.attributes["uo_region"].data.foreach_get("value", lab)
            conf = (np.clip(lab[first], 0, len(cl.CONFORM_BONES) - 1), float(json.loads(o["uo_conform"]).get("gap", 0.006)), np.bincount(E.ravel(), minlength=len(first)).astype(float))
        data.append(dict(o=o, Vn=Vn, Wn=Wn, E=E, reg=reg, prm=prm, Eb=Eb, conf=conf, L0=np.linalg.norm(Vn[E[:, 0]] - Vn[E[:, 1]], axis=1),
                         Lb0=np.linalg.norm(Vb[Eb[:, 0]] - Vb[Eb[:, 1]], axis=1)))
        print("%s: %d welded vertices, regions %s%s" % (o.name, len(Vn), {r: int((reg == r).sum()) for r in REGIONS if (reg == r).any()}, ", loose garment (legs push)" if prm else ""))

    cmask = cl.conform_masks([bones[k] for k in Wb[tri].sum(1).argmax(1)])
    frames = capture(rig, acts, want, bones)
    rows, keep = [], {}
    for a, i, S in frames:
        Pb = skin_points(Vb, Wb, S)
        bvh = BVHTree.FromPolygons([Vector(p) for p in Pb], tri.tolist())
        for d in data:
            P = skin_points(d["Vn"], d["Wn"], S)
            if d["prm"]:
                h, t = caps.posed(S)
                sel = np.array(["pelvis" not in bones[k] for k in caps.idx])
                prm = d["prm"]
                P = P + cl.hull_push(d["Vn"], S[bones.index("pelvis")], h[sel], t[sel], caps.radius[sel], centre_xy=tuple(prm["centre"]), margin=prm["margin"], kappa=prm["kappa"],
                                     z_top=prm["z_top"], z_hem=prm["z_hem"], ramp=prm.get("ramp", 0.15), drop=prm.get("drop", 1.0))
            if d["conf"] is not None:                                         # what the render does per frame
                cb = [BVHTree.FromPolygons([Vector(p) for p in Pb], tri[m].tolist()) for m in cmask]
                lab, cg, deg = d["conf"]
                P = P + cl.conform_push(P, cb, lab, d["E"], deg, max(cg, 0.006))
            sd, fi = signed(bvh, P)
            near = treg[np.maximum(fi, 0)]
            mine = (near == d["reg"]) | (fi < 0)
            legs = np.char.startswith(near.astype(str), "leg") & ~mine
            bare = np.char.startswith(near.astype(str), "hand") | (near == "head")
            own = np.where(mine, sd, 0.3)
            legd = np.where(legs, sd, 0.3)
            bared = np.where(bare, sd, 0.3)
            anyd = np.where(~mine & ~legs & ~bare, sd, 0.3)
            L = np.linalg.norm(P[d["E"][:, 0]] - P[d["E"][:, 1]], axis=1) / np.maximum(d["L0"], 1e-9)
            Lb = np.linalg.norm(Pb[d["Eb"][:, 0]] - Pb[d["Eb"][:, 1]], axis=1) / np.maximum(d["Lb0"], 1e-9)
            per = {r: float((own[d["reg"] == r] < 0).mean()) for r in REGIONS if (d["reg"] == r).any()}
            rows.append(dict(action=a, name=acts[a].name, frame=i, item=d["o"].name, own_gap=float((own < gap).mean()), own_in=float((own < 0).mean()),
                             depth_mm=float(max(0.0, -own.min()) * 1000), any_in=float((anyd < 0).mean()), any_depth_mm=float(max(0.0, -anyd.min()) * 1000),
                             legs_in=float((legd < 0).mean()), legs_depth_mm=float(max(0.0, -legd.min()) * 1000), bare_in=float((bared < 0).mean()),
                             stretch_p99=float(np.percentile(L, 99)), stretch_30=float((L > 1.3).mean()), squash_30=float((L < 0.7).mean()),
                             skin_p99=float(np.percentile(Lb, 99)), skin_30=float((Lb > 1.3).mean()), own_in_by_region=per))
            if npz:
                keep["%d_%d_%s" % (a, i, d["o"].name)] = own.astype(np.float32)
    by = {}
    for r in rows:
        by.setdefault(r["name"], []).append(r)
    print("%-26s %8s %7s %8s %7s %8s %7s %8s | %7s %7s | %7s %7s" % ("action", "own<gap", "own<0", "deep mm", "legs<0", "deep mm", "cross<0", "deep mm", "str p99", ">1.3", "skin99", "sk>1.3"))
    for name, rs in by.items():
        mx = lambda k: max(r[k] for r in rs)
        print("%-26s %7.2f%% %6.2f%% %8.1f %6.2f%% %8.1f %6.2f%% %8.1f | %7.2f %6.2f%% | %7.2f %6.2f%%" % (name, 100 * mx("own_gap"), 100 * mx("own_in"), mx("depth_mm"), 100 * mx("legs_in"), mx("legs_depth_mm"),
                                                                                       100 * mx("any_in"), mx("any_depth_mm"),
                                                                                       mx("stretch_p99"), 100 * mx("stretch_30"), mx("skin_p99"), 100 * mx("skin_30")), flush=True)
    s = dict(own_gap_mean=float(np.mean([r["own_gap"] for r in rows])), own_in_mean=float(np.mean([r["own_in"] for r in rows])), own_in_max=max(r["own_in"] for r in rows),
             depth_max_mm=max(r["depth_mm"] for r in rows), frames_with_own_in=int(sum(r["own_in"] > 0 for r in rows)), frames=len(rows),
             any_in_mean=float(np.mean([r["any_in"] for r in rows])), legs_in_mean=float(np.mean([r["legs_in"] for r in rows])), legs_depth_max_mm=max(r["legs_depth_mm"] for r in rows), bare_in_mean=float(np.mean([r["bare_in"] for r in rows])), stretch_p99_max=max(r["stretch_p99"] for r in rows),
             stretch_30_mean=float(np.mean([r["stretch_30"] for r in rows])), skin_p99_max=max(r["skin_p99"] for r in rows), skin_30_mean=float(np.mean([r["skin_30"] for r in rows])))
    print("CLEARANCE own<gap %.2f%% | own<0 mean %.3f%%, max %.2f%%, frames with any %d/%d, deepest %.1f mm | legs<0 %.2f%% (%.0f mm) | bare<0 %.2f%% | cross<0 %.2f%% | stretch p99 max %.2f, >1.3 %.2f%% (skin %.2f, %.2f%%)" % (
        100 * s["own_gap_mean"], 100 * s["own_in_mean"], 100 * s["own_in_max"], s["frames_with_own_in"], s["frames"], s["depth_max_mm"], 100 * s["legs_in_mean"], s["legs_depth_max_mm"], 100 * s["bare_in_mean"], 100 * s["any_in_mean"],
        s["stretch_p99_max"], 100 * s["stretch_30_mean"], s["skin_p99_max"], 100 * s["skin_30_mean"]))
    if out:
        json.dump(dict(blend=blend, gap=gap, summary=s, frames=rows), open(out, "w"), indent=1)
    if npz:
        np.savez_compressed(npz, **keep)
    sys.stdout.flush(); os._exit(0)


if __name__ == "__main__":
    main()
