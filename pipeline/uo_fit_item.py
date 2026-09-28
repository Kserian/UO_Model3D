# Fit the SELECTED item meshes onto the UO body (rest pose) before uo_bind_item.py. Place and size the item yourself;
# this script only fixes how it sits on the skin:
# 1. Push: every part closer to the skin than MIN_GAP (or inside the body) is pushed out. The push spreads smoothly
#    over RADIUS, so plates stay rigid and rivets / reliefs move with their plate (details are kept).
# 2. MAX_GAP > 0 also pulls parts that stand off more than that back towards the skin, only where the whole area
#    around (RADIUS) stands off, so the thickness of the item is kept.
# Run it with the item selected (Alt+P); then run uo_bind_item.py. Existing shape keys get the same change.
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

MIN_GAP = 0.008       # m, no part of the item closer to the skin than this (0 = only out of the body)
MAX_GAP = 0.0         # m, > 0: pull parts standing off more than this towards the skin (0 = off)
RADIUS = 0.04         # m, how far a push / pull spreads over the item

body = bpy.data.objects["UO_Body"]
rig = bpy.data.objects["UO_Rig"]


def body_bvh():
    me = body.data
    kb = me.shape_keys.key_blocks["Basis"] if me.shape_keys else None
    co = np.empty(len(me.vertices) * 3, np.float32)
    (kb.data if kb else me.vertices).foreach_get("co", co)
    me.calc_loop_triangles()
    tri = [t.vertices[:] for t in me.loop_triangles]
    return BVHTree.FromPolygons([Vector(p) for p in co.reshape(-1, 3)], tri)


def skin(bvh, P):
    """nearest skin point, its normal and the signed distance (< 0 inside the body) of every point"""
    L = np.zeros_like(P); N = np.zeros_like(P); S = np.zeros(len(P))
    for i, p in enumerate(P):
        loc, nrm, fi, d = bvh.find_nearest(Vector(p))
        L[i] = loc; N[i] = nrm; S[i] = (Vector(p) - loc).dot(nrm)
    return L, N, S


def spread(P, amount, mode):
    """amount per vertex -> smooth field: 'push' = max of amount * falloff, 'pull' = min of amount over RADIUS"""
    kd = KDTree(len(P))
    for i, p in enumerate(P):
        kd.insert(p, i)
    kd.balance()
    out = np.zeros(len(P))
    if mode == "push":
        for i in np.nonzero(amount > 0)[0]:
            for co, j, d in kd.find_range(P[i], RADIUS):
                out[j] = max(out[j], amount[i] * (1 - d / RADIUS))
    else:
        for j in range(len(P)):
            out[j] = min(amount[i] for co, i, d in kd.find_range(P[j], RADIUS))
    return out


def fit(ob, bvh):
    me = ob.data
    M = np.array(body.matrix_world.inverted() @ ob.matrix_world)       # item -> body space
    Mi = np.linalg.inv(M)
    base = me.shape_keys.key_blocks[0] if me.shape_keys else None
    co = np.empty(len(me.vertices) * 3, np.float32)
    (base.data if base else me.vertices).foreach_get("co", co)
    local = co.reshape(-1, 3).astype(np.float64)
    P0 = local @ M[:3, :3].T + M[:3, 3]
    P = P0.copy()
    S0 = skin(bvh, P)[2]
    for _ in range(3):                                               # push out
        L, N, S = skin(bvh, P)
        need = np.maximum(0, MIN_GAP - S)
        if not (need > 1e-4).any():
            break
        P = P + spread(P, need, "push")[:, None] * N
    if MAX_GAP > 0:                                                  # pull in (thickness kept)
        L, N, S = skin(bvh, P)
        P = P - spread(P, np.maximum(0, S - MAX_GAP), "pull")[:, None] * N
    S1 = skin(bvh, P)[2]
    delta = (P @ Mi[:3, :3].T + Mi[:3, 3]) - local                    # back to item space
    if me.shape_keys:
        for k in me.shape_keys.key_blocks:
            c = np.empty(len(me.vertices) * 3, np.float32); k.data.foreach_get("co", c)
            k.data.foreach_set("co", (c.reshape(-1, 3) + delta).ravel().astype(np.float32))
    me.vertices.foreach_set("co", (local + delta).ravel().astype(np.float32))
    me.update()
    print("uo_fit_item: %s | inside body %d -> %d verts | closest %.1f -> %.1f mm | moved %d verts, max %.1f mm"
          % (ob.name, (S0 < 0).sum(), (S1 < 0).sum(), S0.min() * 1000, S1.min() * 1000,
             (np.linalg.norm(P - P0, axis=1) > 1e-4).sum(), np.linalg.norm(P - P0, axis=1).max() * 1000))


pose = rig.data.pose_position
rig.data.pose_position = "REST"
bpy.context.view_layer.update()
try:
    bvh = body_bvh()
    for ob in [o for o in bpy.context.selected_objects if o.type == "MESH" and o != body]:
        fit(ob, bvh)
finally:
    rig.data.pose_position = pose
