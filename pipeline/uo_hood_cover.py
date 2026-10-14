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
vertical drop stopping on the body and a per-vertex push smoothed over the mesh (both crumpled the cloth: the inner and outer layer moved apart). Then the hood is bound again (uo_bind_item.py, PART hood): its weights were taken where it stood before; and from the chin up (HEAD_RIGID above the head bone)
it follows the head only, blended into the skin weights over HEAD_BLEND below: with skin weights the rim round the chin and cheeks (head weight 0.64 on average at
z 1.52-1.58 m, some 0) stayed with the neck when the head tilted, the opening slid over the face (user, 2026-10-12).
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
BROW_Z = 0.06         # m above C: front skin higher than this (the forehead) that the hood covers (a ray from C through it hits the hood) is pushed out too: the pointed brow
                      # of an Assassin-style hood went into the forehead and the skin showed through it as a strip (2026-10-12); 0 = off (the whole front is the face)
CENTRE_UP = 0.08      # m: C above the head bone head
GROUP_MIN = 0.3       # head skin: the weight of the head bone at least this
TOP_GAP = 0.012       # m: the whole hood moved down until the inside of its top is this far above the skull (0 = leave it where the autofit put it)
BODY_GAP = 0.008      # m: the hood at least this far out of the body skin (cowl on the shoulders), along the skin normal; 0 = off
FIELD_SIGMA = 0.03    # m: the push out of the body is a smooth field in space (gaussian): the inner and outer layer of the cloth move together, nothing crumples
BODY_ROUNDS = 20      # rounds of that push
REBIND = True         # bind again after the moves (uo_bind_item.py)
BIND_SMOOTH = 12      # uo_bind_item.py SMOOTH (passes of smoothing of the weights over the hood)
BIND_ARM = -1.0       # share of the shoulder (upper arm) motion the cowl takes (uo_bind_item.py PARTS "hood" FOLLOW upper_arm); -1 = as in uo_bind_item.py, 0 = the cowl on the chest only
TILT_BACK = 0.0       # deg: the hood is first turned back about the x axis through C (the brim goes up and back, the face is framed, not shaded)
SYMMETRIZE = 4        # passes: the hood is first turned and shifted onto its own best mirror plane (yaw, roll, x), which is put on the body's midplane, then each vertex goes
                      # half way to the nearest point of the mirrored surface (same side of the cloth, at most SYM_MAX away). A free AI model is not symmetric: the Assassin-style
                      # hood was turned 3 deg and its mirror p90 was 21.6 mm, it looked crooked (user, 2026-10-12). 0 = off
SYM_MAX = 0.03        # m
SYM_SIGMA = 0.02      # m: the symmetrizing moves form a smooth field in space (gaussian); a per-vertex snap tore the thin brim (layers matched across)
TILT_FADE = 0.0       # m: > 0 = the turn is full above the head bone head and fades to none over this height below it (smoothstep): the hood turns, the cowl stays on the
                      # shoulders as the model made it (a whole-hood turn of 25 deg lifted the front flaps of the cowl off the chest, Assassin-style hood, 2026-10-12)
SHORTEN = 1.0         # < 1: a shorter cowl: what hangs below SHORTEN_Z (the top of the shoulders) is squeezed up towards it, heights below it x SHORTEN, so the hem keeps its shape
                      # and only just reaches over the shoulders (user, 2026-10-12: the Assassin hood's cowl reached mid-chest, z 1.22 m); then the push out of the body puts it back on the
                      # skin. Drawing it in towards the neck instead left the front long and wrapped the cowl tight round the chest like a vest. 1 = off
SHORTEN_Z = 1.55
FILL_NECK = 0.006     # m: the V of the cowl under the chin (neck, upper chest seen through it: a second opening under the face) is closed by an inner panel of the hood's
                      # cloth this far off the skin: a copy of the skin seen through it (from the front and from above), widened by FILL_RINGS rings so its edges tuck under the cowl; 0 = off
FILL_RINGS = 4
FILL_ZMIN = 1.25      # m: the panel does not go below this
INNER_SHADE = 0.0     # 0..1: > 0 = the inside of the hood (cloth facing the head centre) and the neck panel get this share of their colour (attribute uo_shade x albedo):
                      # the UO light comes almost from the camera and has no occlusion, so the inside of a hood was as light as its outside, a flat grey blob round the face
                      # (user: "no depth", 2026-10-12). 0 = off
INNER_DIST = 0.10     # m: cloth whose normal hits the body within this distance is the inside (the hood round the head, the cowl lining over the neck)
INNER_SMOOTH = 3      # passes of smoothing of the darkening over the mesh
OCCLUSION = 0.0       # 0..1: > 0 = also darker where the hood's own folds and layers (and the body) close the view around a point: under the pointed brow, between the layers of the
                      # cowl, in the folds (OCC_RAYS rays over the half sphere of the normal, hits within OCC_DIST); colour x (1 - OCCLUSION x share of rays hit). Asked for by the user
                      # for this item ("give the hood shading, depth", 2026-10-12); the UO light itself stays as measured (no AO in the renderer). 0 = off
SHADE_MIN = 0.35      # the darkening (inside x occlusion) never takes the colour below this share: deep shade, never black (user, 2026-10-12: "no true black")
OCC_RAYS = 24
OCC_DIST = 0.06       # m
HEAD_RIGID = 0.0      # m above the head bone head: from here up the hood follows the head only (the face opening, chin to crown, keeps to the face)
HEAD_BLEND = 0.07     # m: below that, over this height, the head weight fades into the skin weights (neck, chest) of the cowl
HEAD_NEAR = 0.03      # m: > 0 = the head weight also fades where the hood is nearer the skin of the shoulders / chest than that of the head (over this difference of distance):
                      # the lower rim of a cowl round the neck and shoulders (z 1.48-1.55 m, 40-70 % on the head by height alone) went into the shoulders when the head moved
                      # (attack, spell, run: 1300-3800 hood vertices > 5 mm in the body, Assassin-style hood, 2026-10-12); the rim round the chin stays on the head. 0 = by height only


def symmetrize(VI, F, c, name):
    """onto the best mirror plane, then symmetric (see SYMMETRIZE)"""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    sub = VI[::max(1, len(VI) // 6000)]

    def tr(V, yaw, roll, dx):
        a, b = np.radians(yaw), np.radians(roll)
        Rz = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
        Ry = np.array([[np.cos(b), 0, np.sin(b)], [0, 1, 0], [-np.sin(b), 0, np.cos(b)]])
        return (V - c) @ (Ry @ Rz).T + c + [dx, 0, 0]

    def score(p):
        U = tr(sub, *p); return np.percentile(cKDTree(U * [-1, 1, 1]).query(U)[0], 90)
    s0 = score((0.0, 0.0, 0.0)); best = ((0.0, 0.0, 0.0), s0)
    for step in (2.0, 1.0, 0.5, 0.25):                            # coordinate search (deg, deg, m)
        moved = True
        while moved:
            moved = False
            for k, dlt in ((0, step), (1, step), (2, step / 200)):
                for sg in (-1, 1):
                    q = list(best[0]); q[k] += sg * dlt; s = score(tuple(q))
                    if s < best[1] - 1e-5:
                        best = (tuple(q), s); moved = True
    VI = tr(VI, *best[0])
    print("uo_hood_cover: %s: onto its mirror plane: yaw %.2f deg, roll %.2f deg, x %+.1f mm (mirror p90 %.1f -> %.1f mm)"
          % (name, best[0][0], best[0][1], best[0][2] * 1e3, s0 * 1e3, best[1] * 1e3))
    tri = np.array([(f[0], f[k], f[k + 1]) for f in F for k in range(1, len(f) - 1)])
    for _ in range(SYMMETRIZE):
        Mv = VI * [-1, 1, 1]
        bh = BVHTree.FromPolygons([tuple(v) for v in Mv], [tuple(f[::-1]) for f in tri])     # mirrored: reversed winding keeps the normals outward
        fn = np.cross(VI[tri[:, 1]] - VI[tri[:, 0]], VI[tri[:, 2]] - VI[tri[:, 0]])
        vn = np.zeros_like(VI)
        for k in range(3):
            np.add.at(vn, tri[:, k], fn)
        vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-12)
        D = np.zeros_like(VI); ok = np.zeros(len(VI), bool)
        for i, p in enumerate(VI):
            loc, nor, _, d = bh.find_nearest(Vector(p), SYM_MAX)
            if loc is not None and np.dot(np.array(nor), vn[i]) > 0.5:
                D[i] = 0.5 * (np.array(loc) - p); ok[i] = True
        n_ok = int(ok.sum())
        P = VI[ok]; Dk = D[ok]; tp = cKDTree(P); Ds = np.zeros_like(VI)          # a smooth field in space: both layers of the cloth and the thin brim move together
        for i, nb in enumerate(tp.query_ball_point(VI, 3 * SYM_SIGMA)):
            if nb:
                wgt = np.exp(-0.5 * (np.linalg.norm(P[nb] - VI[i], axis=1) / SYM_SIGMA) ** 2)
                Ds[i] = (wgt[:, None] * Dk[nb]).sum(0) / wgt.sum()
        VI = VI + Ds
    d = cKDTree(VI * [-1, 1, 1]).query(VI)[0]
    print("uo_hood_cover: %s: symmetrized (%d passes, %d of %d vertices), mirror p90 %.1f mm" % (name, SYMMETRIZE, n_ok, len(VI), np.percentile(d, 90) * 1e3))
    return VI


BVHTree_body = []
BVH_BODY_V, BVH_BODY_F = [], []


def occlusion_share(P, Nn, faces, E, body_V, body_F, rays=24, dist=0.06):
    """per vertex the share of `rays` cosine-weighted rays over the half sphere of its normal Nn that hit the item (faces over P) or the body (body_F over body_V)
    within `dist` m: high in folds, between layers, under a sleeve; smoothed twice over the edges E"""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree as _B
    P = np.asarray(P, float); Nn = np.asarray(Nn, float)
    both = _B.FromPolygons([tuple(p) for p in P] + [tuple(v) for v in body_V], [tuple(f) for f in faces] + [tuple(i + len(P) for i in f_) for f_ in body_F])
    rng = np.random.default_rng(0); u = rng.random((rays, 2))
    loc = np.c_[np.sqrt(u[:, 0]) * np.cos(2 * np.pi * u[:, 1]), np.sqrt(u[:, 0]) * np.sin(2 * np.pi * u[:, 1]), np.sqrt(1 - u[:, 0])]   # cosine-weighted
    occ = np.zeros(len(P))
    for i, (p, n) in enumerate(zip(P, Nn)):
        a = np.array([1.0, 0, 0]) if abs(n[0]) < 0.9 else np.array([0, 1.0, 0])
        t1 = np.cross(n, a); t1 /= np.linalg.norm(t1); t2 = np.cross(n, t1)
        D = loc[:, :1] * t1 + loc[:, 1:2] * t2 + loc[:, 2:] * n
        o = Vector(p + 0.002 * n)
        occ[i] = sum(both.ray_cast(o, Vector(d), dist)[0] is not None for d in D) / rays
    E = np.asarray(E); cnt = np.maximum(np.bincount(E.ravel(), minlength=len(P)), 1)
    for _ in range(2):
        occ = 0.5 * occ + 0.5 * (np.bincount(E[:, 0], occ[E[:, 1]], len(P)) + np.bincount(E[:, 1], occ[E[:, 0]], len(P))) / cnt
    return occ


def apply_shade(me, f):
    """attribute uo_shade (per vertex, 0..1) on the mesh `me` and the albedo of its UO_Look materials multiplied by it"""
    a = me.attributes.get("uo_shade") or me.attributes.new("uo_shade", "FLOAT", "POINT")
    a.data.foreach_set("value", np.asarray(f, np.float32))
    for m in me.materials:
        nt = m.node_tree if m else None
        grp = next((n for n in nt.nodes if n.type == "GROUP" and n.node_tree and n.node_tree.name.startswith("UO_Look")), None) if nt else None
        if grp is None or any(n.name == "uo_shade" for n in nt.nodes):
            continue
        at = nt.nodes.new("ShaderNodeAttribute"); at.name = "uo_shade"; at.attribute_type = "GEOMETRY"; at.attribute_name = "uo_shade"
        sc_ = nt.nodes.new("ShaderNodeVectorMath"); sc_.operation = "MULTIPLY"
        at.location = (grp.location.x - 420, grp.location.y - 300); sc_.location = (grp.location.x - 200, grp.location.y - 300)
        if grp.inputs["Albedo"].links:
            nt.links.new(grp.inputs["Albedo"].links[0].from_socket, sc_.inputs[0])
        else:
            sc_.inputs[0].default_value = grp.inputs["Albedo"].default_value[:3]
        nt.links.new(at.outputs["Fac"], sc_.inputs[1]); nt.links.new(sc_.outputs[0], grp.inputs["Albedo"])


def inner_shade(it, c, n_panel):
    """uo_shade per vertex (1 outside, INNER_SHADE inside the hood and on the neck panel) and the albedo of the hood's materials scaled by it"""
    me = it.data; Mw = it.matrix_world; R = Mw.to_3x3()
    P = np.array([Mw @ v.co for v in me.vertices]); Nn = np.array([(R @ v.normal).normalized() for v in me.vertices])
    from mathutils import Vector
    bh = BVHTree_body[0]
    hit = np.array([bh.ray_cast(Vector(p + 0.002 * n), Vector(n), INNER_DIST)[0] is not None for p, n in zip(P, Nn)], float)   # cloth that faces the head / neck (the inside)
    E = np.array([e.vertices[:] for e in me.edges]); cnt = np.maximum(np.bincount(E.ravel(), minlength=len(P)), 1)
    x = hit
    for _ in range(INNER_SMOOTH):                                        # a soft edge round the opening
        x = 0.5 * x + 0.5 * (np.bincount(E[:, 0], x[E[:, 1]], len(P)) + np.bincount(E[:, 1], x[E[:, 0]], len(P))) / cnt
    f = 1 - (1 - INNER_SHADE) * x
    if OCCLUSION > 0:
        occ = occlusion_share(P, Nn, [tuple(p.vertices) for p in me.polygons], E, BVH_BODY_V[0], BVH_BODY_F[0], OCC_RAYS, OCC_DIST)
        f = f * (1 - OCCLUSION * occ)
        print("uo_hood_cover: %s: occlusion x%.2f: share of rays hit p50 %.2f p90 %.2f" % (it.name, OCCLUSION, np.percentile(occ, 50), np.percentile(occ, 90)))
    f[n_panel:] = np.minimum(f[n_panel:], INNER_SHADE)
    f = np.maximum(f, SHADE_MIN)
    apply_shade(me, f)
    print("uo_hood_cover: %s: inside shaded x%.2f (%d of %d vertices darker than 0.9, %d panel vertices)" % (it.name, INNER_SHADE, int((f < 0.9).sum()), len(f), len(f) - n_panel))


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


def fill_neck(it, body, m, VB, whead, c):
    """an inner panel over the skin of the neck / upper chest that is seen through the front of the hood (the V of the cowl)"""
    import bmesh
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get()
    mi = it.evaluated_get(dg).to_mesh(); Mi = it.matrix_world
    bh = BVHTree.FromPolygons([Mi @ v.co for v in mi.vertices], [tuple(p.vertices) for p in mi.polygons])
    NB = np.array([(body.matrix_world.to_3x3() @ v.normal).normalized() for v in m.vertices])
    VH = np.array([Mi @ v.co for v in mi.vertices])
    front = VH[(np.abs(VH[:, 0]) < 0.03) & (VH[:, 1] < c[1] - 0.05) & (VH[:, 2] < c[2])]
    zmin = max(FILL_ZMIN, float(front[:, 2].min())) if len(front) else FILL_ZMIN     # no lower than where the cowl's fronts meet (a short cowl: the bare chest below is not a hole)
    cand = (whead < 0.5) & (VB[:, 1] < c[1] + 0.02) & (VB[:, 2] > zmin) & (VB[:, 2] < c[2]) & (np.abs(VB[:, 0]) < 0.15) & (NB[:, 1] < -0.2)
    seen = np.zeros(len(VB), bool)
    for i in np.nonzero(cand)[0]:
        for d in ((0, -1, 0), (0, -0.866, 0.5)):
            if bh.ray_cast(Vector(VB[i] + NB[i] * 0.004), Vector(d), 1.0)[0] is None:
                seen[i] = True; break
    if not seen.any():
        print("uo_hood_cover: %s: no skin seen through the front of the hood" % it.name); return
    m.calc_loop_triangles()
    tri = np.array([t.vertices[:] for t in m.loop_triangles])
    E = np.vstack([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]])
    sel = seen.copy()
    for _ in range(FILL_RINGS):                                 # widen over the skin (not onto the head)
        grow = np.zeros(len(VB), bool); grow[E[sel[E[:, 0]], 1]] = True; grow[E[sel[E[:, 1]], 0]] = True
        sel |= grow & (whead < 0.5) & (VB[:, 2] > zmin - 0.03)
    T = tri[sel[tri].all(1)]
    used = np.unique(T); idx = {int(v): k for k, v in enumerate(used)}
    P = VB[used] + NB[used] * FILL_NECK
    bm = bmesh.new(); bm.from_mesh(it.data)
    Minv = np.array(Mi.inverted())
    nv = [bm.verts.new(tuple((Minv @ np.append(p, 1.0))[:3])) for p in P]
    bm.verts.ensure_lookup_table()
    for a, b, cc in T:
        try:
            f = bm.faces.new((nv[idx[int(a)]], nv[idx[int(b)]], nv[idx[int(cc)]])); f.material_index = 0; f.smooth = True
        except ValueError:
            pass
    bm.to_mesh(it.data); bm.free(); it.data.update()
    print("uo_hood_cover: %s: neck panel from z %.3f m, %d skin vertices seen through the hood, %d faces, %.0f mm off the skin" % (it.name, zmin, int(seen.sum()), len(T), FILL_NECK * 1e3))


def forehead(VI, F, c, SF):
    """the front skin over the brows that the hood covers: a ray from C through it hits the hood (inside or outside the skin)"""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    if BROW_Z <= 0 or not len(SF):
        return SF[:0]
    bh = BVHTree.FromPolygons([tuple(v) for v in VI], F)
    hit = np.array([bh.ray_cast(Vector(c), Vector(p - c), 0.4)[0] is not None for p in SF])
    out = SF[hit]
    return np.vstack([out, out * [-1, 1, 1]])


def cover(VI, it, c, ts, rs, cone, sig, bvh, F):
    """the hood out of the head skin behind the face (radially from c, symmetric, smooth), then out of the whole body (body_push)"""
    if len(SF := forehead(VI, F, c, SFRONT)):
        S2 = np.vstack([SBACK, SF]); ds = S2 - c; rs = np.linalg.norm(ds, axis=1); ts = cKDTree(ds / rs[:, None])
        print("uo_hood_cover: %s: %d forehead skin points under the hood pushed out too" % (it.name, len(SF) // 2))
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
    global SBACK, SFRONT
    SBACK = S; SFRONT = VB[(w > GROUP_MIN) & (VB[:, 1] <= c[1] - FACE_Y) & (VB[:, 2] > c[2] + BROW_Z)]
    from mathutils.bvhtree import BVHTree
    bvh_body = BVHTree.FromPolygons([tuple(v) for v in VB], [tuple(p.vertices) for p in m.polygons]); BVHTree_body[:] = [bvh_body]; BVH_BODY_V[:] = [VB]; BVH_BODY_F[:] = [[tuple(p.vertices) for p in m.polygons]]
    skin_top = ray_up(VB, [tuple(p.vertices) for p in m.polygons], c)
    ds = S - c; rs = np.linalg.norm(ds, axis=1); ts = cKDTree(ds / rs[:, None])
    cone, sig = np.radians(CONE), np.radians(SIGMA)
    for it in items:
        Mi = np.array(it.matrix_world); Vl = np.array([v.co for v in it.data.vertices]); VI = Vl @ Mi[:3, :3].T + Mi[:3, 3]
        F = [tuple(p.vertices) for p in it.data.polygons]
        if SYMMETRIZE:
            VI = symmetrize(VI, F, c, it.name)
        top0 = ray_up(VI, F, c)
        if TILT_BACK:
            zh = (rig.matrix_world @ rig.data.bones["head"].head_local).z
            x = np.clip((VI[:, 2] - (zh - TILT_FADE)) / TILT_FADE, 0, 1) if TILT_FADE > 0 else np.ones(len(VI))
            a = np.radians(TILT_BACK) * x * x * (3 - 2 * x)
            d = VI - c; ca, sa = np.cos(a), np.sin(a)
            VI = c + np.c_[d[:, 0], ca * d[:, 1] + sa * d[:, 2], -sa * d[:, 1] + ca * d[:, 2]]
            print("uo_hood_cover: %s: turned back %.0f deg about C" % (it.name, TILT_BACK))
        V0 = VI; _, twin = cKDTree(V0 * [-1, 1, 1]).query(V0)
        dz = top0 - (skin_top + TOP_GAP) if (TOP_GAP > 0 and top0 is not None and skin_top is not None) else 0.0
        for attempt in range(3 if dz > 0 else 1):
            VI = V0 - [0, 0, dz]
            if SHORTEN < 1:                                         # shorter cowl: what hangs below SHORTEN_Z is squeezed up towards it (heights x SHORTEN), the hem keeps its shape
                zmin0 = VI[:, 2].min(); below = VI[:, 2] < SHORTEN_Z
                VI = VI.copy(); VI[below, 2] = SHORTEN_Z - (SHORTEN_Z - VI[below, 2]) * SHORTEN
                print("uo_hood_cover: %s: cowl shortened x%.2f below z %.2f m: lowest point z %.3f -> %.3f m" % (it.name, SHORTEN, SHORTEN_Z, zmin0, VI[:, 2].min()))
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
    n_before = len(items[0].data.vertices)
    if FILL_NECK > 0:
        fill_neck(items[0], body, m, VB, w, c)
    if REBIND:
        import os, re
        here = os.path.dirname(os.path.abspath(__file__))
        os.environ.setdefault("UO_SCRIPTS", here)
        text = open(os.path.join(here, "uo_bind_item.py"), encoding="utf-8").read()
        text = re.sub(r"^PART\s*=.*$", "PART = 'hood'", text, count=1, flags=re.M)
        text = re.sub(r"^SMOOTH\s*=.*$", "SMOOTH = %d" % BIND_SMOOTH, text, count=1, flags=re.M)
        if BIND_ARM >= 0:
            text = text.replace('{"upper_arm": 0.5}),   # hood', '{"upper_arm": %r}),   # hood' % BIND_ARM)
        for o in bpy.context.view_layer.objects:
            o.select_set(o in items)
        bpy.context.view_layer.objects.active = items[0]
        exec(compile(text, "uo_bind_item.py", "exec"), {"__name__": "__main__"})
    if HEAD_BLEND >= 0:
        zh = (rig.matrix_world @ rig.data.bones["head"].head_local).z + HEAD_RIGID
        for it in items:
            hg = it.vertex_groups.get("head") or it.vertex_groups.new(name="head")
            others = [g for g in it.vertex_groups if g.name != "head"]
            n = len(it.data.vertices); W = np.zeros((n, len(it.vertex_groups)))
            for v in it.data.vertices:
                for gr in v.groups:
                    W[v.index, gr.group] = gr.weight
            s = W.sum(1, keepdims=True); W = np.where(s > 0, W / np.maximum(s, 1e-9), 0)
            z = np.array([(it.matrix_world @ v.co).z for v in it.data.vertices])
            x = np.clip((z - (zh - HEAD_BLEND)) / max(HEAD_BLEND, 1e-6), 0, 1); tt = x * x * (3 - 2 * x)
            if HEAD_NEAR > 0:
                from mathutils import Vector as _V
                Wb = {g.name: np.zeros(len(VB)) for g in body.vertex_groups}
                for v in body.data.vertices:
                    for gr in v.groups:
                        Wb[body.vertex_groups[gr.group].name][v.index] = gr.weight
                torso = sum(Wb[k] for k in Wb if k.split(".")[0] in ("chest", "spine", "clavicle", "upper_arm"))
                th = cKDTree(VB[Wb["head"] > 0.5]); tt_ = cKDTree(VB[torso > 0.5])
                P = np.array([it.matrix_world @ v.co for v in it.data.vertices])
                dh, dt = th.query(P)[0], tt_.query(P)[0]
                y = np.clip((dt - dh) / HEAD_NEAR + 0.5, 0, 1); tt = tt * y * y * (3 - 2 * y)
            W = W * (1 - tt)[:, None]; W[:, hg.index] += tt
            for g in it.vertex_groups:
                col = W[:, g.index]
                for val in np.unique(np.round(col, 4)):
                    idx = np.nonzero(np.round(col, 4) == val)[0].tolist()
                    if val > 0:
                        g.add(idx, float(val), "REPLACE")
                    else:
                        g.remove(idx)
            print("uo_hood_cover: %s: rigid on the head above z %.3f m (%d vertices), blended over %.0f mm below" % (it.name, zh, int((tt >= 1).sum()), HEAD_BLEND * 1e3))
    if INNER_SHADE > 0:
        inner_shade(items[0], c, n_before)
    bpy.context.scene["uo_head_hides"] = 1                       # the face hides the inside of the hood (render_uo_layer.py HEAD_HIDES)
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
