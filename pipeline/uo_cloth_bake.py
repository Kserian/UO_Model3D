# Cloth simulation for loose items (robe, dress, skirt, cloak): the hanging part falls, swings and collides with the
# body instead of following the bones rigidly. Run it AFTER uo_bind_item.py, with the items selected (Alt+P).
# 1. A simplified copy of the item (about SIM_VERTS vertices) is simulated with Blender's Cloth physics. What the
#    bind put on the cloth chains (PART "skirt" / "robe" / "cloak") hangs free; the rest (shoulders, chest, sleeves)
#    is pinned and follows the skeleton exactly.
# 2. Every UO action is simulated on its own: the item first settles for PREROLL frames in the action's first pose;
#    looping actions (walk, run, stand) run LOOP_CYCLES times and the last cycle is kept, so the loop has no jump.
#    Mounted actions are not simulated (the horse is not a collider) - they keep the bound result.
# 3. The result is saved next to the .blend (OUT_DIR/<item>.npz). render_uo_layer.py uses it automatically; after
#    the bake, playing an action in the viewport shows it too (run the script again with BAKE = False to get that
#    preview back after reopening the file). To go back to the plain bound item, run it with REMOVE = True.
# Bake again after changing the item, its fit or its binding. All actions take about 15-30 minutes; the progress
# is printed in the system console (Window > Toggle System Console), one line per action.
import bpy
import os
import numpy as np
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

MATERIAL = "wool"     # silk, cotton, wool, leather (how light / flowing -> heavy / stiff the cloth is)
SIM_VERTS = 4000      # the simulated copy has about this many vertices (more = finer folds, slower)
ACTIONS = []          # e.g. ["00_walk_unarmed", "04_stand"]; empty = all actions on foot
LOOP_ACTIONS = [0, 1, 2, 3, 4, 7, 8]   # UO actions the game loops (walk, run, stand, combat idle)
LOOP_CYCLES = 3       # looping actions: cycles simulated, the last one is kept
PREROLL = 40          # frames the cloth settles in the first pose of an action (at 24 fps)
QUALITY = 8           # cloth steps per frame (more = fewer tunnelling problems in fast attacks, slower)
GOAL = 0.5            # 0..1: how strongly the hanging part is pulled towards the bound shape (the cloth chains are
                      # fitted to the original UO robe / skirt / cloak frames): 0 = pure cloth, 1 = no cloth at all
TIE = 0.03            # m: separate pieces of the item (layers, a skirt under a belt) closer than this are tied
                      # together, so no piece falls off
DISTANCE = 0.012      # m, the cloth keeps this far from the body
FIX_GAP = 0.004       # m: afterwards every frame is checked against the real posed body; parts of the item inside it
                      # or closer than this are pushed out, smoothly (skin never shows through). 0 = off
OUT_DIR = "//uo_cloth/"
BAKE = True           # False: only (re)enable the viewport preview of an existing bake
REMOVE = False        # True: forget the bake of the selected items (back to the plain bound item)
STEP = 3              # scene frames between two UO frames (as in render_uo_layer.py)

MATERIALS = {         # mass, tension/compression/shear stiffness, bending, damping (Blender's cloth presets)
    "silk":    (0.15, 5, 0.05, 0),
    "cotton":  (0.3, 15, 0.5, 5),
    "wool":    (0.5, 25, 3, 15),
    "leather": (0.4, 80, 150, 25),
}
CHAIN = ("skirt_", "cloak_")                                          # cloth chain bones of the v13 rig

sc = bpy.context.scene
rig = bpy.data.objects["UO_Rig"]
body = bpy.data.objects["UO_Body"]


def cache_path(ob):
    return bpy.path.abspath(OUT_DIR + bpy.path.clean_name(ob.name) + ".npz")


def weights(ob, n):
    names = [g.name for g in ob.vertex_groups]
    W = np.zeros((n, len(names)))
    for v in ob.data.vertices:
        for g in v.groups:
            if g.group < len(names):
                W[v.index, g.group] = g.weight
    return W, names


def signature(ob):
    """vertex count + coordinate sum of the item's rest shape: a bake of a changed item is not used"""
    base = ob.data.shape_keys.key_blocks[0].data if ob.data.shape_keys else ob.data.vertices
    co = np.empty(len(ob.data.vertices) * 3, np.float32); base.foreach_get("co", co)
    return np.array([len(ob.data.vertices), float(np.abs(co.astype(np.float64)).sum())])


def local_co(me):
    co = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", co)
    return co.reshape(-1, 3).astype(np.float64)


def make_proxy(item):
    """simplified, welded copy of the item (same parent / transform / vertex groups), in rest shape"""
    sim = item.copy(); sim.data = item.data.copy(); sim.name = item.name + "_uo_sim"
    if "uo_cloth" in sim:
        del sim["uo_cloth"]
    for c in list(sim.users_collection):
        c.objects.unlink(sim)
    sc.collection.objects.link(sim)
    sim.hide_render = True
    if sim.data.shape_keys:
        sim.shape_key_clear()
    for m in list(sim.modifiers):
        sim.modifiers.remove(m)
    bm = bmesh.new(); bm.from_mesh(sim.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)       # UV-seam splits would tear the cloth apart
    bm.to_mesh(sim.data); bm.free()
    n = len(sim.data.vertices)
    if n > SIM_VERTS * 1.2:
        dec = sim.modifiers.new("dec", "DECIMATE"); dec.ratio = SIM_VERTS / n
        dg = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(sim.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
        sim.modifiers.remove(dec)
        old = sim.data; sim.data = me; bpy.data.meshes.remove(old)
    tie_pieces(sim.data)
    return sim


def tie_pieces(me):
    """loose edges (cloth springs) between vertices of different pieces closer than TIE"""
    n = len(me.vertices)
    E = np.array([e.vertices[:] for e in me.edges]).reshape(-1, 2)
    lab = np.arange(n)
    while True:                                                       # connected pieces
        a = np.minimum(lab[E[:, 0]], lab[E[:, 1]]); nl = lab.copy()
        np.minimum.at(nl, E[:, 0], a); np.minimum.at(nl, E[:, 1], a); nl = nl[nl]
        if (nl == lab).all():
            break
        lab = nl
    if len(np.unique(lab)) < 2:
        return
    from mathutils.kdtree import KDTree
    co = local_co(me); kd = KDTree(n)
    for i, p in enumerate(co):
        kd.insert(p, i)
    kd.balance()
    new = set()
    for i, p in enumerate(co):
        best = None
        for q, j, d in kd.find_range(p, TIE):
            if lab[j] != lab[i] and (best is None or d < best[1]):
                best = (j, d)
        if best:
            new.add((min(i, best[0]), max(i, best[0])))
    if new:
        k = len(me.edges); me.edges.add(len(new))
        for e, (i, j) in zip(list(me.edges)[k:], sorted(new)):
            e.vertices = (i, j)
        me.update()


def pin_weights(sim):
    """1 = follows the skeleton, 0 = free cloth: free where the bind used the cloth chains; without chains (PART
    "all") everything below the hips hangs free, sleeves stay pinned"""
    n = len(sim.data.vertices)
    W, names = weights(sim, n)
    chain = [j for j, nm in enumerate(names) if nm.startswith(CHAIN)]
    if chain:
        free = W[:, chain].sum(1)
    else:
        Mw = np.array(sim.matrix_world); z = local_co(sim.data) @ Mw[2, :3] + Mw[2, 3]
        hip = (rig.matrix_world @ rig.data.bones["pelvis"].head_local).z
        t = np.clip((hip - 0.05 - z) / 0.25, 0, 1); free = t * t * (3 - 2 * t)
        arm = [j for j, nm in enumerate(names) if nm.split(".")[0] in ("upper_arm", "forearm", "hand",
               "upper_arm_twist", "forearm_twist") or nm.startswith("finger")]
        free *= np.clip(1 - 2 * W[:, arm].sum(1), 0, 1)
    pin = GOAL + (1 - GOAL) * np.clip(1 - 1.3 * free, 0, 1)
    g = sim.vertex_groups.get("uo_pin") or sim.vertex_groups.new(name="uo_pin")
    for i in range(n):
        g.add([i], float(pin[i]), "REPLACE")
    return pin


def add_cloth(sim, frames):
    for m in [m for m in sim.modifiers if m.type == "CLOTH"]:
        sim.modifiers.remove(m)
    cm = sim.modifiers.new("UO_Cloth", "CLOTH"); s = cm.settings
    mass, stiff, bend, damp = MATERIALS[MATERIAL]
    s.quality = QUALITY; s.mass = mass
    s.tension_stiffness = s.compression_stiffness = s.shear_stiffness = stiff
    s.bending_stiffness = bend
    s.tension_damping = s.compression_damping = s.shear_damping = damp
    s.air_damping = 1.0
    s.vertex_group_mass = "uo_pin"; s.pin_stiffness = 1.0
    c = cm.collision_settings
    c.use_collision = True; c.distance_min = DISTANCE; c.collision_quality = 4; c.use_self_collision = False
    cm.point_cache.frame_start = 1; cm.point_cache.frame_end = frames
    return cm


def colliders():
    """a simplified copy of the body (and a floor for the falls) pushes the cloth; returns the objects to delete"""
    made = []
    col = body.copy(); col.data = body.data.copy(); col.name = "UO_Body_uo_collider"
    for c in list(col.users_collection):
        c.objects.unlink(col)
    sc.collection.objects.link(col); col.hide_render = True
    if col.data.shape_keys:
        col.shape_key_clear()
    for m in list(col.modifiers):
        col.modifiers.remove(m)
    dec = col.modifiers.new("dec", "DECIMATE"); dec.ratio = min(1.0, 5000 / len(col.data.vertices))
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(col.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    col.modifiers.remove(dec); old = col.data; col.data = me; bpy.data.meshes.remove(old)
    arm = col.modifiers.new("Armature", "ARMATURE"); arm.object = rig
    col.modifiers.new("UO_Collision", "COLLISION")
    col.collision.thickness_outer = DISTANCE; col.collision.cloth_friction = 5.0
    made.append(("obj", col, None))
    me = bpy.data.meshes.new("UO_Floor")
    me.from_pydata([(-3, -3, 0), (3, -3, 0), (3, 3, 0), (-3, 3, 0)], [], [(0, 1, 2, 3)])
    fl = bpy.data.objects.new("UO_Floor", me); sc.collection.objects.link(fl); fl.hide_render = True
    fl.modifiers.new("UO_Collision", "COLLISION"); fl.collision.thickness_outer = DISTANCE
    made.append(("obj", fl, None))
    return made


def poses(act, times):
    """pose (matrix_basis of every bone) of the action at the given scene frames"""
    rig.animation_data.action = act
    out = {}
    for t in sorted(set(times)):
        sc.frame_set(t)
        out[t] = [pb.matrix_basis.copy() for pb in rig.pose.bones]
    return out


def simulate(sim, act):
    """-> {UO frame: proxy vertex positions (object space)}"""
    a = int(act["uo_action"]); nf = int(act["uo_frames"])
    f0, f1 = int(act.frame_range[0]), int(act.frame_range[1])
    L = f1 - f0                                                       # cycle length (the last key = the first)
    if a in LOOP_ACTIONS and L > 0:
        t_of = lambda k: f0 + (k % L)
        run = LOOP_CYCLES * L; keep0 = PREROLL + (LOOP_CYCLES - 1) * L
    else:
        t_of = lambda k: min(f0 + k, f1)
        run = (nf - 1) * STEP + 1 if L > 0 else 1; keep0 = PREROLL
    total = PREROLL + run
    times = [f0] * PREROLL + [t_of(k) for k in range(run)]
    P = poses(act, times)
    rig.animation_data.action = None
    add_cloth(sim, total)
    want = {keep0 + 1 + i * STEP: i for i in range(nf)}
    out = {}
    for s in range(1, total + 1):
        for pb, m in zip(rig.pose.bones, P[times[s - 1]]):
            pb.matrix_basis = m
        sc.frame_set(s)
        if s in want:
            dg = bpy.context.evaluated_depsgraph_get()
            ev = sim.evaluated_get(dg); me = ev.to_mesh()
            out[want[s]] = local_co(me).astype(np.float32); ev.to_mesh_clear()
    return out


def bind_to_proxy(item_co, sim_co, tris):
    """every item vertex rides on the nearest proxy triangle: barycentric point + offset along the normal and in
    the triangle plane"""
    bvh = BVHTree.FromPolygons([Vector(p) for p in sim_co], tris.tolist())
    fi = np.zeros(len(item_co), np.int32); bc = np.zeros((len(item_co), 3)); off = np.zeros((len(item_co), 3))
    fr = frames_of(sim_co, tris)
    for i, p in enumerate(item_co):
        loc, nrm, f, d = bvh.find_nearest(Vector(p))
        a, b, c = sim_co[tris[f]]
        v0, v1, v2 = b - a, c - a, np.array(loc) - a
        d00, d01, d11, d20, d21 = v0 @ v0, v0 @ v1, v1 @ v1, v2 @ v0, v2 @ v1
        den = max(d00 * d11 - d01 * d01, 1e-18)
        v = (d11 * d20 - d01 * d21) / den; w = (d00 * d21 - d01 * d20) / den
        fi[i] = f; bc[i] = (1 - v - w, v, w)
        off[i] = fr[f] @ (p - np.array(loc))
    return fi, bc.astype(np.float32), off.astype(np.float32)


def frames_of(co, tris, vn=None):
    """per triangle orthonormal frame (rows: edge dir, in-plane perpendicular, normal)"""
    a, b, c = co[tris[:, 0]], co[tris[:, 1]], co[tris[:, 2]]
    e1 = b - a; e1 /= np.maximum(np.linalg.norm(e1, axis=1, keepdims=True), 1e-12)
    n = np.cross(b - a, c - a); n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    e2 = np.cross(n, e1)
    return np.stack([e1, e2, n], 1)


def apply_binding(sim_co, tris, fi, bc, off):
    fr = frames_of(sim_co, tris)[fi]
    base = (sim_co[tris[fi]] * bc[..., None]).sum(1)
    return base + np.einsum("nk,nkj->nj", off, fr)


def welded(co):
    """vertices at the same place (UV-seam splits) -> one node, so fixes never tear the item open"""
    key = np.round(co / 1e-5).astype(np.int64)
    _, first, node = np.unique(key, axis=0, return_index=True, return_inverse=True)
    return first, node.ravel()


def push_out(X, bvh, E, deg):
    """displacement that keeps the points X (body space) FIX_GAP outside the body; spread over the item (smooth)"""
    D = np.zeros_like(X); look = np.arange(len(X)); reach = 0.1
    for it in range(12):
        P = X + D; need = np.zeros(len(X)); N = np.zeros_like(X); near = []
        for i in look:
            p = Vector(P[i]); loc, nrm, fi, dist = bvh.find_nearest(p, reach)
            if loc is not None:
                near.append(i); s = (p - loc).dot(nrm)
                if s < FIX_GAP:
                    need[i] = FIX_GAP - s; N[i] = nrm
        if it == 0:
            look = np.array(near, int); reach = FIX_GAP + 0.05
        if not (need > 1e-4).any():
            break
        D += need[:, None] * N
        if it < 11:
            for _ in range(2):
                acc = np.zeros_like(D)
                np.add.at(acc, E[:, 0], D[E[:, 1]]); np.add.at(acc, E[:, 1], D[E[:, 0]])
                D = np.where(deg[:, None] > 0, 0.5 * D + 0.5 * acc / np.maximum(deg, 1)[:, None], D)
            look = np.union1d(look, np.nonzero(np.abs(D).max(1) > 1e-5)[0])
    return D


def fix_pass(item, data, done):
    """push every baked frame of the item out of the real posed body (see FIX_GAP); stored as sparse node offsets"""
    base = item.data.shape_keys.key_blocks[0].data if item.data.shape_keys else item.data.vertices
    ico = np.empty(len(item.data.vertices) * 3, np.float32); base.foreach_get("co", ico)
    first, node = welded(ico.reshape(-1, 3).astype(np.float64))
    E = np.array([e.vertices[:] for e in item.data.edges]).reshape(-1, 2)
    E = np.unique(np.sort(node[E], 1), axis=0); E = E[E[:, 0] != E[:, 1]]
    deg = np.bincount(E.ravel(), minlength=len(first)).astype(float)
    data["fix_node"] = node.astype(np.int32)
    moved = 0
    for act in [a for a in bpy.data.actions if "uo_action" in a and int(a["uo_action"]) in done]:
        a = int(act["uo_action"]); rig.animation_data.action = act
        for i in range(int(data["frames_%d" % a])):
            sc.frame_set(1 + i * STEP)
            dg = bpy.context.evaluated_depsgraph_get()
            ev = body.evaluated_get(dg); me = ev.to_mesh(); bco = local_co(me)
            me.calc_loop_triangles(); btri = [t.vertices[:] for t in me.loop_triangles]; ev.to_mesh_clear()
            bvh = BVHTree.FromPolygons([Vector(p) for p in bco], btri)
            M = np.array(body.matrix_world.inverted() @ item.matrix_world)
            co = apply_binding(data["a%d_f%d" % (a, i)].astype(np.float64), data["tris"], data["fi"], data["bc"],
                               data["off"])[first]
            D = push_out(co @ M[:3, :3].T + M[:3, 3], bvh, E, deg) @ np.linalg.inv(M[:3, :3]).T
            idx = np.nonzero(np.abs(D).max(1) > 2e-4)[0]
            data["d%d_f%d_i" % (a, i)] = idx.astype(np.int32)
            data["d%d_f%d_v" % (a, i)] = D[idx].astype(np.float16)
            moved = max(moved, len(idx))
    print("uo_cloth_bake: %s pushed out of the body (up to %d points per frame)" % (item.name, moved))


def fix_offsets(c, a, i, n):
    """per-vertex fix of frame i of action a (zeros if none)"""
    k = "d%d_f%d_i" % (a, i)
    if "fix_node" not in c or k not in c:
        return 0.0
    Dn = np.zeros((int(c["fix_node"].max()) + 1, 3)); Dn[c[k]] = c["d%d_f%d_v" % (a, i)]
    return Dn[c["fix_node"]]


# ---------------------------------------------------------------- preview / render support (shared with the renderer)
_cache = {}


def load(ob):
    p = ob.get("uo_cloth")
    if not p:
        return None
    p = bpy.path.abspath(p)
    if p not in _cache:
        if not os.path.exists(p):
            return None
        d = np.load(p); _cache[p] = {k: d[k] for k in d.files}
    return _cache[p]


def show(ob, a, t):
    """put the item in the baked shape of UO action a at UO frame t (float: blends two frames); False = no bake"""
    c = load(ob)
    if c is not None and not np.allclose(c["item_sig"], signature(ob), rtol=1e-5):
        c = None                                                      # the item changed since the bake
    arm = [m for m in ob.modifiers if m.type == "ARMATURE"]
    key = ob.data.shape_keys.key_blocks.get("uo_cloth") if ob.data.shape_keys else None
    n = int(c["frames_%d" % a]) if c is not None and ("frames_%d" % a) in c else 0
    if n == 0:
        for m in arm:
            m.show_viewport = m.show_render = True
        if key:
            key.value = 0.0
        return False
    i0 = int(np.floor(t)) % n; i1 = (i0 + 1) % n; w = t - np.floor(t)
    if a not in LOOP_ACTIONS and i0 == n - 1:
        i1, w = i0, 0.0
    sim_co = (1 - w) * c["a%d_f%d" % (a, i0)].astype(np.float64) + w * c["a%d_f%d" % (a, i1)].astype(np.float64)
    co = apply_binding(sim_co, c["tris"], c["fi"], c["bc"], c["off"])
    co = co + (1 - w) * fix_offsets(c, a, i0, len(co)) + w * fix_offsets(c, a, i1, len(co))
    if key is None:
        if ob.data.shape_keys is None:
            ob.shape_key_add(name="Basis", from_mix=False)
        key = ob.shape_key_add(name="uo_cloth", from_mix=False)
    key.data.foreach_set("co", co.astype(np.float32).ravel()); key.value = 1.0
    for m in arm:
        m.show_viewport = m.show_render = False
    ob.data.update()
    return True


def rest(ob):
    for m in ob.modifiers:
        if m.type == "ARMATURE":
            m.show_viewport = m.show_render = True
    if ob.data.shape_keys and "uo_cloth" in ob.data.shape_keys.key_blocks:
        ob.data.shape_keys.key_blocks["uo_cloth"].value = 0.0


def preview(scene, *_):
    act = rig.animation_data.action if rig.animation_data else None
    if act is None or "uo_action" not in act or rig.data.pose_position != "POSE":
        for ob in [o for o in scene.objects if "uo_cloth" in o]:
            rest(ob)
        return
    t = (scene.frame_current - 1) / STEP
    for ob in [o for o in scene.objects if "uo_cloth" in o]:
        show(ob, int(act["uo_action"]), t)


def enable_preview():
    for h in [h for h in bpy.app.handlers.frame_change_post if getattr(h, "__name__", "") == "uo_cloth_preview"]:
        bpy.app.handlers.frame_change_post.remove(h)
    def uo_cloth_preview(scene, *a):
        preview(scene)
    bpy.app.handlers.frame_change_post.append(uo_cloth_preview)


# ---------------------------------------------------------------- main
def bake(item):
    if not any(m.type == "ARMATURE" for m in item.modifiers):
        raise RuntimeError("%s is not bound - run uo_bind_item.py first" % item.name)
    if not bpy.data.filepath:
        raise RuntimeError("save the .blend first (the bake is written next to it)")
    rest(item)
    state = dict(pose=rig.data.pose_position, act=rig.animation_data.action, frame=sc.frame_current,
                 d=rig.get("uo_direction", 0))
    rig.data.pose_position = "REST"; bpy.context.view_layer.update()
    sim = make_proxy(item)
    pin = pin_weights(sim)
    arm = sim.modifiers.new("Armature", "ARMATURE"); arm.object = rig
    sim_rest = local_co(sim.data)
    sim.data.calc_loop_triangles()
    tris = np.array([t.vertices[:] for t in sim.data.loop_triangles], np.int32)
    base = item.data.shape_keys.key_blocks[0].data if item.data.shape_keys else item.data.vertices
    ico = np.empty(len(item.data.vertices) * 3, np.float32); base.foreach_get("co", ico)
    fi, bc, off = bind_to_proxy(ico.reshape(-1, 3).astype(np.float64), sim_rest, tris)
    made = colliders()
    hidden = [o for o in sc.objects if o.type == "MESH" and o is not sim and not o.hide_viewport
              and not o.name.startswith(("UO_Floor", "UO_Body_uo_collider"))]
    for o in hidden:
        o.hide_viewport = True                                       # not evaluated while simulating (faster)
    rig.data.pose_position = "POSE"; rig["uo_direction"] = 0
    data = dict(tris=tris, fi=fi, bc=bc, off=off, sim_rest=sim_rest.astype(np.float32), item_sig=signature(item))
    acts = sorted([a for a in bpy.data.actions if "uo_action" in a], key=lambda a: int(a["uo_action"]))
    done = []
    try:
        try:
            for act in acts:
                a = int(act["uo_action"])
                if (ACTIONS and act.name not in ACTIONS) or 23 <= a <= 29:
                    continue
                res = simulate(sim, act)
                for i, co in res.items():
                    data["a%d_f%d" % (a, i)] = co
                data["frames_%d" % a] = np.array(len(res))
                done.append(a)
                print("uo_cloth_bake: %s %s: %d frames" % (item.name, act.name, len(res)))
        finally:
            for o in hidden:
                o.hide_viewport = False
            for kind, ob, name in made + [("obj", sim, None)]:
                if kind == "mod":
                    ob.modifiers.remove(ob.modifiers[name])
                else:
                    me = ob.data; bpy.data.objects.remove(ob); bpy.data.meshes.remove(me)
        if FIX_GAP > 0 and done:
            fix_pass(item, data, done)
    finally:
        rig.data.pose_position = state["pose"]; rig.animation_data.action = state["act"]
        rig["uo_direction"] = state["d"]; sc.frame_set(state["frame"])
    old = load(item)                                                  # keep other actions baked earlier
    if old is not None and ACTIONS and old["sim_rest"].shape == data["sim_rest"].shape \
            and np.allclose(old["sim_rest"], data["sim_rest"], atol=1e-4) and len(old["fi"]) == len(fi):
        for k, v in old.items():
            if k.startswith("frames_"):
                a = int(k[7:])
            elif k.startswith(("a", "d")) and "_f" in k:
                a = int(k[1:k.index("_f")])
            else:
                continue
            if a not in done:
                data[k] = v
    p = cache_path(item); os.makedirs(os.path.dirname(p), exist_ok=True)
    np.savez_compressed(p, **data)
    _cache.pop(p, None)
    item["uo_cloth"] = bpy.path.relpath(p)
    print("uo_cloth_bake: %s -> %s (%d vertices simulated, %d pinned)" % (item.name, p, len(sim_rest), (pin > 0.99).sum()))


if __name__ == "__main__" and REMOVE:
    for ob in [o for o in bpy.context.selected_objects if "uo_cloth" in o]:
        rest(ob); del ob["uo_cloth"]
        if ob.data.shape_keys and "uo_cloth" in ob.data.shape_keys.key_blocks:
            ob.shape_key_remove(ob.data.shape_keys.key_blocks["uo_cloth"])
        print("uo_cloth_bake: %s back to the bound item" % ob.name)
elif __name__ == "__main__":
    if BAKE:
        for ob in [o for o in bpy.context.selected_objects if o.type == "MESH" and o != body and "_uo_sim" not in o.name]:
            bake(ob)
    enable_preview()
    print("uo_cloth_bake: viewport preview on (play an action of UO_Rig in Pose Position)")
