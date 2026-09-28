"""Quad base mesh: Blender Skin modifier on the fitted skeleton, subdivided, then projected onto the body SDF."""
import numpy as np
import bpy
from body import JI, ARM_REST_ANGLE
from sdfmesh import body_parts, body_sdf


def surface_dist(parts, p, d, tmax=0.6, iters=30):
    """Distance from interior point p along unit direction d to the SDF surface (bisection)."""
    if body_sdf(parts, p[None])[0][0] > 0:
        return 0.01
    lo, hi = 0.0, tmax
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        if body_sdf(parts, (p + d * mid)[None])[0][0] < 0:
            lo = mid
        else:
            hi = mid
    return lo


def measured_radius(parts, p, axis_dir):
    """(r_u, r_v) half-extents of the cross-section at p, perpendicular to axis_dir (u ~ sideways, v ~ Y)."""
    a = axis_dir / np.linalg.norm(axis_dir)
    u = np.cross(a, [0.0, 1.0, 0.0])
    if np.linalg.norm(u) < 1e-6:
        u = np.array([1.0, 0, 0])
    u /= np.linalg.norm(u)
    v = np.cross(u, a)
    ru = 0.5 * (surface_dist(parts, p, u) + surface_dist(parts, p, -u))
    rv = 0.5 * (surface_dist(parts, p, v) + surface_dist(parts, p, -v))
    # centre offsets (the skeleton may not be at the middle of the cross-section)
    cu = 0.5 * (surface_dist(parts, p, u) - surface_dist(parts, p, -u))
    cv = 0.5 * (surface_dist(parts, p, v) - surface_dist(parts, p, -v))
    return ru, rv, p + u * cu + v * cv


def skin_graph(S, P, parts=None):
    S = {k: np.asarray(v, np.float64) for k, v in S.items()}
    sa, ca = np.sin(ARM_REST_ANGLE), np.cos(ARM_REST_ANGLE)
    V, E, Rd = [], [], []

    def add(p, r, parent=None):
        V.append(np.asarray(p, float)); Rd.append(r)
        i = len(V) - 1
        if parent is not None:
            E.append((parent, i))
        return i

    pel, sp, ch, nk, hd = (P[JI[n]] for n in ("pelvis", "spine", "chest", "neck", "head"))
    pr, ar, cr, hr = S["pelvis_r"], S["abd_r"], S["chest_r"], S["head_r"]
    root = add(pel + np.array([0, 0, -0.03]), (pr[0] * 0.8, pr[1] * 0.8))
    i_p2 = add((pel + sp) / 2 + np.array([0, 0, 0.02]), (pr[0] * 0.8, pr[1] * 0.8), root)
    i_sp = add(sp + np.array([0, 0, S["abd"] * 0.35]), (ar[0] * 0.85, ar[1] * 0.85), i_p2)
    i_ch = add(ch + np.array([0, 0, 0.03]), (cr[0] * 0.8, cr[1] * 0.8), i_sp)
    i_ct = add(ch + np.array([0, 0, S["chest_len"] * 0.8]), (cr[0] * 0.7, cr[1] * 0.7), i_ch)
    i_nk = add(nk + np.array([0, 0, 0.03]), (S["neck_r"], S["neck_r"]), i_ct)
    i_hd = add(hd + S["head_c"] * np.array([1, 1, 0.3]), (hr[0] * 0.9, hr[1] * 0.9), i_nk)
    i_ht = add(hd + S["head_c"] + np.array([0, 0, hr[2] * 0.85]), (hr[0] * 0.6, hr[1] * 0.6), i_hd)
    for side, sx in (("L", 1), ("R", -1)):
        d = np.array([sx * sa, 0, -ca])
        sh, el, wr = P[JI["shoulder." + side]], P[JI["elbow." + side]], P[JI["wrist." + side]]
        i_s = add(sh, (S["uarm_r"][0], S["uarm_r"][0]), i_ct)
        i_m = add((sh + el) / 2, (S["uarm_r"].mean(), S["uarm_r"].mean()), i_s)
        i_e = add(el, (S["uarm_r"][1], S["uarm_r"][1]), i_m)
        i_f = add((el + wr) / 2, (S["farm_r"].mean(), S["farm_r"].mean()), i_e)
        i_w = add(wr, (S["farm_r"][1], S["farm_r"][1]), i_f)
        i_h = add(wr + d * S["hand"] * 0.9, (S["hand_r"][0] * 0.8, S["hand_r"][1] * 0.8), i_w)
        hp, kn, an = P[JI["hip." + side]], P[JI["knee." + side]], P[JI["ankle." + side]]
        i_hp = add(hp + np.array([0, 0, -0.02]), (S["thigh_r"][0], S["thigh_r"][0]), root)
        i_tm = add((hp + kn) / 2, (S["thigh_r"].mean(), S["thigh_r"].mean()), i_hp)
        i_k = add(kn, (S["thigh_r"][1], S["thigh_r"][1]), i_tm)
        i_sm = add((kn + an) / 2, (S["shin_r"].mean(), S["shin_r"].mean()), i_k)
        i_a = add(an, (S["shin_r"][1], S["shin_r"][1]), i_sm)
        toe = an + np.array([0, -S["foot_len"] + S["heel_y"] + 0.02, -S["ankle_h"] + S["foot_r"][1]])
        add(toe, (S["foot_r"][1], S["foot_r"][1] * 0.8), i_a)
    V = np.array(V)
    if parts is not None:
        # replace guessed radii by cross-sections measured on the fitted body surface
        nb = {i: [] for i in range(len(V))}
        for a_, b_ in E:
            nb[a_].append(b_); nb[b_].append(a_)
        centred = V.copy()
        for i in range(len(V)):
            axis = np.zeros(3)
            for j in nb[i]:
                dvec = V[j] - V[i] if j > i else V[i] - V[j]
                axis += dvec / np.linalg.norm(dvec)
            ru, rv, c = measured_radius(parts, V[i], axis)
            if len(nb[i]) <= 1:   # chain ends sit inside the tip; keep them small
                ru, rv = ru * 0.6, rv * 0.6
            Rd[i] = (max(ru, 0.012), max(rv, 0.012))
            if len(nb[i]) == 2:
                centred[i] = c
        centred[:, 0] = np.where(np.abs(V[:, 0]) < 1e-9, 0.0, centred[:, 0])
        V = centred
    return V, E, Rd, root


def make_skin_mesh(S, P, subdiv=2, parts=None):
    V, E, Rd, root = skin_graph(S, P, parts)
    me = bpy.data.meshes.new("SkinGraph")
    me.from_pydata(V.tolist(), E, [])
    ob = bpy.data.objects.new("SkinGraph", me)
    bpy.context.scene.collection.objects.link(ob)
    sk = ob.modifiers.new("Skin", "SKIN")
    if len(me.skin_vertices) == 0:
        me.skin_vertices.new()
    sv = me.skin_vertices[0].data
    for i, r in enumerate(Rd):
        sv[i].radius = r
        sv[i].use_root = (i == root)
    sk.branch_smoothing = 0.5
    sk.use_x_symmetry = True
    sub = ob.modifiers.new("Sub", "SUBSURF")
    sub.levels = subdiv
    sub.render_levels = subdiv
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    m = ev.to_mesh()
    verts = np.array([v.co[:] for v in m.vertices])
    faces = [list(p.vertices) for p in m.polygons]
    ev.to_mesh_clear()
    bpy.data.objects.remove(ob)
    bpy.data.meshes.remove(me)
    return verts, faces


def sdf_grad(parts, p, h=1e-4):
    g = np.zeros_like(p)
    for i in range(3):
        e = np.zeros(3); e[i] = h
        g[:, i] = (body_sdf(parts, p + e)[0] - body_sdf(parts, p - e)[0]) / (2 * h)
    return g


def project(parts, p, iters=6):
    for _ in range(iters):
        d, _ = body_sdf(parts, p)
        g = sdf_grad(parts, p)
        g /= np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-9)
        p = p - d[:, None] * g
    return p


def adjacency(nv, faces):
    import scipy.sparse as sp
    e = set()
    for f in faces:
        for a, b in zip(f, f[1:] + f[:1]):
            e.add((min(a, b), max(a, b)))
    e = np.array(sorted(e))
    A = sp.coo_matrix((np.ones(len(e) * 2), (np.r_[e[:, 0], e[:, 1]], np.r_[e[:, 1], e[:, 0]])), shape=(nv, nv)).tocsr()
    deg = np.asarray(A.sum(1)).ravel()
    return A, deg


def mesh_normals(v, faces):
    n = np.zeros_like(v)
    for f in faces:
        for k in range(1, len(f) - 1):
            a, b, c = v[f[0]], v[f[k]], v[f[k + 1]]
            fn = np.cross(b - a, c - a)
            for i in (f[0], f[k], f[k + 1]):
                n[i] += fn
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)


def project_along_normals(parts, v, n, reach=0.12, iters=25):
    """Move each vertex along its normal to the SDF zero crossing (bisection); fallback: nearest point."""
    d0, _ = body_sdf(parts, v)
    sgn = np.sign(d0)  # outside -> search inward (-n), inside -> outward (+n)
    dirn = -sgn[:, None] * n
    far = v + dirn * reach
    df, _ = body_sdf(parts, far)
    ok = np.sign(df) != sgn
    lo = np.zeros(len(v)); hi = np.full(len(v), reach)
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        dm, _ = body_sdf(parts, v + dirn * mid[:, None])
        same = np.sign(dm) == sgn
        lo = np.where(same, mid, lo); hi = np.where(same, hi, mid)
    out = v + dirn * (0.5 * (lo + hi))[:, None]
    out[~ok] = project(parts, v[~ok])
    return out


def relax_project(parts, v, faces, rounds=12, lam=0.5):
    A, deg = adjacency(len(v), faces)
    v = project_along_normals(parts, v, mesh_normals(v, faces))
    for _ in range(rounds):
        avg = np.where(deg[:, None] > 0, (A @ v) / np.maximum(deg, 1)[:, None], v)
        g = sdf_grad(parts, v)
        g /= np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-9)
        delta = avg - v
        delta -= np.sum(delta * g, 1, keepdims=True) * g  # tangential only
        v = v + lam * delta
        v = project(parts, v, iters=3)
    return v


def symmetrize(v, tol=1e-3):
    """Snap to exact X symmetry: find mirror partners and average."""
    from scipy.spatial import cKDTree
    t = cKDTree(v)
    m = v * np.array([-1, 1, 1])
    d, idx = t.query(m)
    ok = d < 0.01
    out = v.copy()
    out[ok] = 0.5 * (v[ok] + (v[idx[ok]] * np.array([-1, 1, 1])))
    center = np.abs(out[:, 0]) < tol
    out[center, 0] = 0.0
    return out, idx, ok


def build_base_mesh(S, subdiv=2):
    parts, P = body_parts(S)
    verts, faces = make_skin_mesh(S, P, subdiv)
    v = relax_project(parts, verts, faces)
    v, _, _ = symmetrize(v)
    return v, faces, parts, P
