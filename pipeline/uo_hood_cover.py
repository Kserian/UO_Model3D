"""Put a hood on the head: brought down onto the skull, out of the shoulders, pushed out of the head skin it does not cover (the ears), radially from the head centre, symmetrically, smoothly.

    python uo_hood_cover.py ITEM.blend [OUT.blend] [--set NAME=VALUE ...]      # e.g. --set GAP=0.015 --set SIGMA=18

ITEM.blend is the output of uo_make_item.py with "kind": "hood" (uo_make_item.py runs this script for a hood, recipe "hood_cover": false = off, {"GAP": 0.015} = settings).
Why: the hood of a free model sits right after uo_autofit_item.py, but the ears of the UO head stand out of its sides (Meshy hood: 52 head skin vertices outside
the hood, both ears; docs/qa/autofit.md "Kaptur"). The push of uo_fit_item.py (out along the skin normal, vertex by vertex) bent the sides of the hood unevenly
(mirror p90 2.6 -> 19 mm) and is off for a hood (uo_prepare_item.py FIT None). Here the hood is seen from the head centre C (head bone + 8 cm up):
  1. the head skin behind the face (y > C - FACE_Y; the face opening stays as the model made it) and its mirror image (so both sides get the same push);
  2. each hood vertex whose direction from C is within CONE of a skin point needs to be at least GAP farther from C than that skin point;
  3. the need spreads to the neighbouring directions (gaussian, SIGMA) and over the mesh (SMOOTH passes, never below the vertex's own need): the whole wall of the
     hood in that direction moves out together (no lumps, the layers of a thick model stay in order);
  4. each vertex takes the larger push of itself and its mirror twin; shape keys move with the mesh, the weights stay.
Before that (TOP_GAP > 0) the whole hood comes down until the inside of its top, straight above C, is TOP_GAP over the skull (Meshy hood after the autofit:
118 mm, it looked too high and its cowl did not lie on the shoulders; user, 2026-10-12), rigidly; the drop is corrected until the top lands at TOP_GAP after the
pushes below (they lift the top a little). After the ears, the hood (the cowl now in the shoulders and chest) is pushed out of the whole body to BODY_GAP along
the skin normal (BODY_ROUNDS rounds; the moves form a smooth field in space, FIELD_SIGMA, mirrored): the cowl lies on the shoulders. Rejected: a per-vertex
vertical drop stopping on the body and a per-vertex push smoothed over the mesh (both crumpled the cloth: the inner and outer layer moved apart). Then the hood is bound again (uo_bind_item.py, PART hood): its weights were taken where it stood before.
Check: the closeups of the head and item_body_holes.py (the layer on the original body).
"""
import sys
import numpy as np
import bpy
from scipy.spatial import cKDTree

GAP = 0.012           # m: the hood at least this far out of the head skin (radially from C)
CONE = 4.0            # deg: a hood vertex and a skin point in the same direction from C
SIGMA = 14.0          # deg: spread of the push over directions (7 left lumps on the side of the hood)
SMOOTH = 30           # passes of smoothing of the push over the mesh
FACE_Y = 0.02         # m: skin in front of C - FACE_Y is the face (left open)
CENTRE_UP = 0.08      # m: C above the head bone head
GROUP_MIN = 0.3       # head skin: the weight of the head bone at least this
TOP_GAP = 0.012       # m: the whole hood moved down until the inside of its top is this far above the skull (0 = leave it where the autofit put it)
BODY_GAP = 0.008      # m: the hood at least this far out of the body skin (cowl on the shoulders), along the skin normal; 0 = off
FIELD_SIGMA = 0.03    # m: the push out of the body is a smooth field in space (gaussian): the inner and outer layer of the cloth move together, nothing crumples
BODY_ROUNDS = 8       # rounds of that push
REBIND = True         # bind again after the moves (uo_bind_item.py)


def ray_up(V, F, c):
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    h = BVHTree.FromPolygons([tuple(v) for v in V], F).ray_cast(Vector(c), Vector((0, 0, 1)), 2.0)
    return h[3] if h[0] is not None else None


def body_push(VI, it, bvh):
    """the hood out of the whole body to BODY_GAP along the skin normal; the moves of the vertices that are too close make a smooth field in space (FIELD_SIGMA),
    mirrored (symmetric), applied to every vertex: both layers of the cloth move together. A per-vertex push smoothed over the mesh crumpled the cowl."""
    from mathutils import Vector
    n = len(VI)
    for rnd in range(BODY_ROUNDS):
        need = np.zeros(n); N = np.zeros((n, 3))
        for i, p in enumerate(VI):
            loc, nor, _, d = bvh.find_nearest(Vector(p), 0.2)
            if loc is None:
                continue
            s = float(np.dot(p - np.array(loc), np.array(nor)))
            if s < BODY_GAP:
                need[i] = BODY_GAP - s; N[i] = nor
        k = np.nonzero(need > 1e-4)[0]
        if not len(k):
            break
        P = np.vstack([VI[k], VI[k] * [-1, 1, 1]]); Dk = need[k, None] * N[k]; Dk = np.vstack([Dk, Dk * [-1, 1, 1]])
        tp = cKDTree(P); D = np.zeros((n, 3)); W = np.zeros(n)
        for i, nb in enumerate(tp.query_ball_point(VI, 3 * FIELD_SIGMA)):
            if nb:
                wgt = np.exp(-0.5 * (np.linalg.norm(P[nb] - VI[i], axis=1) / FIELD_SIGMA) ** 2)
                W[i] = wgt.sum(); D[i] = (wgt[:, None] * Dk[nb]).sum(0)
        D = D / np.maximum(W, 1.0)[:, None] * 1.2                       # far from the push it fades (weight < 1); a little over, the rounds converge faster
        VI = VI + D
        print("uo_hood_cover: %s: body push round %d: %d vertices closer than %.0f mm to the body (at most %.1f mm in), moved at most %.1f mm"
              % (it.name, rnd + 1, len(k), BODY_GAP * 1e3, need.max() * 1e3, np.linalg.norm(D, axis=1).max() * 1e3))
    return VI


def cover(VI, it, c, ts, rs, cone, sig, bvh, F):
    """the hood out of the head skin behind the face (radially from c, symmetric, smooth), then out of the whole body (body_push)"""
    di = VI - c; ri = np.linalg.norm(di, axis=1); ui = di / np.maximum(ri, 1e-9)[:, None]
    need = np.zeros(len(VI))
    for i, nb in enumerate(ts.query_ball_point(ui, 2 * np.sin(cone / 2))):
        if nb:
            need[i] = max(0.0, rs[nb].max() + GAP - ri[i])
    src_i = np.nonzero(need > 0)[0]
    push = np.zeros(len(VI))
    if len(src_i):
        tn = cKDTree(ui[src_i])
        for i, nb in enumerate(tn.query_ball_point(ui, 2 * np.sin(2.5 * sig / 2))):
            if nb:
                ang = 2 * np.arcsin(np.clip(np.linalg.norm(ui[src_i[nb]] - ui[i], axis=1) / 2, 0, 1))
                push[i] = (need[src_i[nb]] * np.exp(-0.5 * (ang / sig) ** 2)).max()
        E = np.array([e.vertices[:] for e in it.data.edges])
        cnt = np.bincount(E.ravel(), minlength=len(VI)).astype(float)
        for _ in range(SMOOTH):
            acc = np.bincount(E[:, 0], push[E[:, 1]], len(VI)) + np.bincount(E[:, 1], push[E[:, 0]], len(VI))
            push = np.maximum(0.5 * push + 0.5 * acc / np.maximum(cnt, 1), need)
        _, j = cKDTree(VI * [-1, 1, 1]).query(VI)
        push = np.maximum(push, push[j])
    VI = VI + ui * push[:, None]
    print("uo_hood_cover: %s: %d vertices closer than %.0f mm to the head skin (at most %.1f mm in), %d moved (at most %.1f mm)"
          % (it.name, len(src_i), GAP * 1e3, need.max() * 1e3, int((push > 1e-4).sum()), push.max() * 1e3))
    if BODY_GAP > 0:
        VI = body_push(VI, it, bvh)
    return VI


def main(src, dst, sets):
    g = globals()
    for k, v in sets:
        g[k] = type(g[k])(v)
    bpy.ops.wm.open_mainfile(filepath=src)
    rig = bpy.data.objects["UO_Rig"]; rig.data.pose_position = "REST"
    body = bpy.data.objects["UO_Body"]
    items = [o for o in bpy.data.collections["Clothing"].all_objects if o.type == "MESH"]
    dg = bpy.context.evaluated_depsgraph_get()
    m = body.evaluated_get(dg).to_mesh(); M = np.array(body.matrix_world)
    VB = np.array([v.co for v in m.vertices]) @ M[:3, :3].T + M[:3, 3]
    hg = body.vertex_groups["head"].index
    w = np.zeros(len(VB))
    for v in body.data.vertices:
        for gr in v.groups:
            if gr.group == hg:
                w[v.index] = gr.weight
    c = np.array(rig.matrix_world @ rig.data.bones["head"].head_local) + np.array([0, 0, CENTRE_UP])
    S = VB[(w > GROUP_MIN) & (VB[:, 1] > c[1] - FACE_Y)]          # the front of the body is -y
    S = np.vstack([S, S * [-1, 1, 1]])
    from mathutils.bvhtree import BVHTree
    bvh_body = BVHTree.FromPolygons([tuple(v) for v in VB], [tuple(p.vertices) for p in m.polygons])
    skin_top = ray_up(VB, [tuple(p.vertices) for p in m.polygons], c)
    ds = S - c; rs = np.linalg.norm(ds, axis=1); ts = cKDTree(ds / rs[:, None])
    cone, sig = np.radians(CONE), np.radians(SIGMA)
    for it in items:
        Mi = np.array(it.matrix_world); Vl = np.array([v.co for v in it.data.vertices]); VI = Vl @ Mi[:3, :3].T + Mi[:3, 3]
        F = [tuple(p.vertices) for p in it.data.polygons]
        top0 = ray_up(VI, F, c)
        V0 = VI; _, twin = cKDTree(V0 * [-1, 1, 1]).query(V0)
        dz = top0 - (skin_top + TOP_GAP) if (TOP_GAP > 0 and top0 is not None and skin_top is not None) else 0.0
        for attempt in range(3 if dz > 0 else 1):
            VI = V0 - [0, 0, dz]
            VI = cover(VI, it, c, ts, rs, cone, sig, bvh_body, F)
            top = ray_up(VI, F, c)
            print("uo_hood_cover: %s: inside of the top %.0f mm above the skull (was %.0f)" % (it.name, (top - skin_top) * 1e3, (top0 - skin_top) * 1e3))
            if dz <= 0 or abs(top - skin_top - TOP_GAP) < 0.003:
                break
            dz += top - skin_top - TOP_GAP
        loc = (VI - Mi[:3, 3]) @ np.linalg.inv(Mi[:3, :3]).T
        delta = loc - Vl
        it.data.vertices.foreach_set("co", loc.astype(np.float32).ravel())
        if it.data.shape_keys:
            for k in it.data.shape_keys.key_blocks:
                co = np.zeros(len(Vl) * 3, np.float32); k.data.foreach_get("co", co)
                k.data.foreach_set("co", (co.reshape(-1, 3) + delta).astype(np.float32).ravel())
        it.data.update()
    if REBIND:
        import os, re
        here = os.path.dirname(os.path.abspath(__file__))
        os.environ.setdefault("UO_SCRIPTS", here)
        text = open(os.path.join(here, "uo_bind_item.py"), encoding="utf-8").read()
        text = re.sub(r"^PART\s*=.*$", "PART = 'hood'", text, count=1, flags=re.M)
        for o in bpy.context.view_layer.objects:
            o.select_set(o in items)
        bpy.context.view_layer.objects.active = items[0]
        exec(compile(text, "uo_bind_item.py", "exec"), {"__name__": "__main__"})
    bpy.ops.wm.save_as_mainfile(filepath=dst)
    print("uo_hood_cover: saved", dst)


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
