"""Put a cape on the back: the upper part of the cloak lies on the shoulders and the back, the lower part hangs free.

    python uo_cloak_hug.py ITEM.blend [OUT.blend] [--set NAME=VALUE ...]      # e.g. --set GAP=0.015

ITEM.blend is the output of uo_make_item.py with "kind": "cloak" (uo_make_item.py runs this script for a cloak; recipe "hug": false = off, {"GAP": 0.015} = settings).
Why: uo_autofit_item.py wraps a cape on the few skin points it covers and left a Meshy cape 6-10 cm off the back and shoulders in every action (median gap to the skin of the upper
half 9.5 cm in the stand, measured with the body at rest and in the posed frames); the cloth simulation (uo_cloth_sim.py) pins the shoulder line to that shape, so it could only
stay as far off. Here, in the rest pose, every vertex looks along -y (the front) to the skin of the back: if the skin is farther than GAP it is brought to GAP in front of it; vertices past the
edge of the body (the sides of a wide cape) take what the nearest vertices with a skin behind them were given, so the cape curves over the shoulder instead of standing out as a board.
The move is full from the shoulder line down to ZFULL, fades to nothing at ZZERO (the lower cape hangs free of the buttocks / legs: the simulation and the swing lift it), and is a smooth field in
space (SIGMA), x and z do not change. Weights stay as bound.
"""
import json, sys
import numpy as np
import bpy
from scipy.spatial import cKDTree

GAP = 0.012           # m: the upper cape is this far off the skin of the back (in the y direction)
ZFULL = 0.30          # m below the shoulder line (uo_cloth z_top): up to here the cape is brought to the skin in full
ZZERO = 0.65          # m below the shoulder line: from here down the cape is left as fitted
REACH = 0.25          # m: a skin farther than this behind (in -y) the vertex is not the cape's back (a leg in front of a hem, nothing)
SIGMA = 0.05          # m: the move is smoothed in space (gaussian), the ripples of the skin do not become ripples of the cloth
RAISE = 0.03          # m: the whole cape is put this much higher (the collar nearer the neck, the shoulders covered; user 2026-10-22)
HEM_TAPER = 0.85      # the width of the cape at the hem relative to the shoulders' (1 = as the model): a cape of the original (468) is nearly straight, a flared A-line one is narrowed (smoothly, ~s^1.5)
SLOPE_MIN = 0.35      # the gap along y is GAP / max(|n_y|, SLOPE_MIN) (n = normal of the skin where the ray hits it): on the slope of the shoulders a gap measured along y is a few mm
                      # along the normal and the skin came through the cape (28 % of the vertices of the upper cape were inside the body, grey stripes on the back). The move stays along y: the
                      # cape never goes round the shoulder to the front (an earlier push along the skin normal wrapped it over the chest)
NEAR = 0.02           # m: a vertex also stays behind the skin of the vertices round it (a shoulder blade next to it): the target is the largest of the neighbours' (dilation), then smoothed
SIDE_K = 12           # nearest vertices with a skin that give the move to a vertex without one
SIDE_MAX = 0.35       # m: the vertex without a skin takes it from vertices that are at most this far (x, z)


def main(src, dst, sets):
    g = globals()
    for k, v in sets:
        g[k] = type(g[k])(v)
    bpy.ops.wm.open_mainfile(filepath=src)
    rig = bpy.data.objects["UO_Rig"]; rig.data.pose_position = "REST"
    body = bpy.data.objects["UO_Body"]
    items = [o for o in bpy.data.collections["Clothing"].all_objects if o.type == "MESH" and o.get("uo_cloth") and json.loads(o["uo_cloth"]).get("type") == "cloak"]
    if not items:
        raise SystemExit("uo_cloak_hug: no cloak (custom property uo_cloth of type cloak) in the Clothing collection")
    it = items[0]; prm = json.loads(it["uo_cloth"])
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get()
    m = body.evaluated_get(dg).to_mesh(); M = np.array(body.matrix_world)
    VB = np.array([v.co for v in m.vertices]) @ M[:3, :3].T + M[:3, 3]
    bvh = BVHTree.FromPolygons([tuple(v) for v in VB], [tuple(p.vertices) for p in m.polygons])
    Mi = np.array(it.matrix_world); Vl = np.array([v.co for v in it.data.vertices]); V = Vl @ Mi[:3, :3].T + Mi[:3, 3]
    zt = prm["z_top"]
    st = np.clip((zt - V[:, 2]) / max(zt - prm["z_hem"], 1e-3), 0.0, 1.0)
    V[:, 0] *= 1.0 - (1.0 - HEM_TAPER) * st ** 1.5
    V[:, 2] += RAISE; zt += RAISE; prm["z_top"] = round(zt, 4); prm["z_hem"] = round(prm["z_hem"] + RAISE, 4)
    t = np.clip((zt - ZFULL - V[:, 2]) / (ZZERO - ZFULL), 0.0, 1.0)
    wz = 0.5 + 0.5 * np.cos(np.pi * t)                                       # 1 down to ZFULL below the shoulder line, 0 from ZZERO
    hit = np.zeros(len(V), bool); gap0 = np.full(len(V), np.nan); ty = np.full(len(V), -np.inf); fwd = Vector((0.0, -1.0, 0.0))
    for i in np.nonzero(wz > 0)[0]:
        loc, nor, _, dist = bvh.ray_cast(Vector(V[i]), fwd, REACH)
        if loc is not None and nor.dot(fwd) > 0:                                # the first surface is seen from inside: the vertex is in the body, its way out is the back
            loc, nor, _, dist = bvh.ray_cast(Vector(V[i]), -fwd, REACH); dist = -dist if loc is not None else dist
        if loc is not None:
            hit[i] = True; gap0[i] = dist
            ty[i] = loc.y + GAP / max(abs(nor.y), SLOPE_MIN)                  # the cape at least this far behind the skin that is in front of this vertex
    kt = cKDTree(V[:, [0, 2]]); hi = np.nonzero(hit)[0]
    ty0 = ty.copy()
    for i, nb in zip(hi, kt.query_ball_point(V[hi][:, [0, 2]], NEAR)):          # dilation: the skin round the vertex (x, z) counts too
        nb = [k for k in nb if hit[k]]; ty[i] = max(ty0[nb])
    need = np.zeros(len(V)); need[hit] = ty[hit] - V[hit, 1]
    # the sides of a wide cape (no skin behind them): what the nearest vertices that have a skin were given
    side = (wz > 0) & ~hit
    if hit.any() and side.any():
        th = cKDTree(V[hit][:, [0, 2]]); d, ix = th.query(V[side][:, [0, 2]], k=min(SIDE_K, int(hit.sum())))
        ds = np.where(d < SIDE_MAX, d, np.inf); wgt = 1.0 / (ds + 0.02); wgt = np.where(np.isfinite(ds), wgt, 0.0)
        ok = wgt.sum(1) > 0
        val = np.zeros(int(side.sum())); nh = need[hit]
        val[ok] = (wgt[ok] * nh[ix[ok]]).sum(1) / wgt[ok].sum(1)
        need[np.nonzero(side)[0]] = val
    dy = need * wz
    kd = cKDTree(V)                                                           # a smooth field in space
    nb = kd.query_ball_point(V, 3 * SIGMA); ds_ = np.zeros_like(dy)
    for i, ix in enumerate(nb):
        w = np.exp(-0.5 * (np.linalg.norm(V[ix] - V[i], axis=1) / SIGMA) ** 2); ds_[i] = (w * dy[ix]).sum() / w.sum()
    dy = np.maximum(ds_, np.where(hit, need * wz, 0.0))                       # the smoothing never takes a vertex back into the skin: where it has to go out, at least what it needs
    top = (V[:, 2] > zt - 0.06)
    loc = Vl.copy(); Vn = V.copy(); Vn[:, 1] += dy
    loc = (Vn - Mi[:3, 3]) @ np.linalg.inv(Mi[:3, :3]).T
    delta = loc - Vl
    it.data.vertices.foreach_set("co", loc.astype(np.float32).ravel())
    if it.data.shape_keys:
        for k in it.data.shape_keys.key_blocks:
            co = np.zeros(len(Vl) * 3, np.float32); k.data.foreach_get("co", co)
            k.data.foreach_set("co", (co.reshape(-1, 3) + delta).astype(np.float32).ravel())
    it.data.update()
    prm["y_top"] = round(float(Vn[top, 1].mean()), 4); it["uo_cloth"] = json.dumps(prm)
    up = hit & (V[:, 2] > zt - ZFULL)
    print("uo_cloak_hug: %s: %d vertices (%d with a skin behind them): gap to the back in the upper cape median %.1f -> %.1f mm, largest move %.1f mm; shoulder line y %.3f"
          % (it.name, int((wz > 0).sum()), int(hit.sum()), 1e3 * np.median(gap0[up]) if up.any() else 0.0, 1e3 * np.median((gap0 + dy)[up]) if up.any() else 0.0, 1e3 * np.abs(dy).max(), prm["y_top"]))
    bpy.ops.wm.save_as_mainfile(filepath=dst)
    print("uo_cloak_hug: saved", dst)


if __name__ == "__main__":
    args = sys.argv[1:]; sets = []; pos = []
    i = 0
    while i < len(args):
        if args[i] == "--set":
            k, v = args[i + 1].split("=", 1); sets.append((k, v)); i += 2
        else:
            pos.append(args[i]); i += 1
    main(pos[0], pos[1] if len(pos) > 1 else pos[0], sets)
    sys.stdout.flush()
