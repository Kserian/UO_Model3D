# Bind the SELECTED item meshes to the UO body in one go: parent + Armature modifier + skin weights + shape corrections.
# 1. Model the item on the body in Rest Position, put it in the "Clothing" collection (keep it under ~10k vertices).
# 2. Set PART to the kind of item (e.g. "chest" for a breastplate, "gloves" for gloves), select it and run (Alt+P).
#    Every item vertex follows the skin right under it (MAP = "under"); weights and shape corrections are taken from
#    that skin point and smoothed over the item (SMOOTH). "chest" moves most of the upper-arm weight to the
#    collarbones, so the shoulders of a breastplate stay on the shoulders while the arms move under it.
# Run it again after you change the item's shape (old weights and "uo_" corrections are replaced). Your own shape
# keys (names not starting with "uo_") are kept. The finger, twist and toe bones of the v13 body count as the hand,
# arm and foot in PARTS (e.g. "gloves" follows the fingers too).
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform

PART = "all"          # kind of item, see PARTS below (e.g. "chest" for a breastplate, "gloves" for gloves)
MAP = "under"         # "under": follow the skin right under each vertex (along its normal); "nearest": nearest skin
SMOOTH = 4            # smoothing passes of weights and corrections over the item (0 = off)
STIFF = 1.0           # > 1 sharpens the weights (w^STIFF, renormalised): the item bends in a narrower band at the joints, its parts stay more rigid
                      # (plates); < 1 spreads the bend wider (soft cloth); 1 = as the skin under it
MAX_DIST = 0.15       # m, farthest skin an item vertex may follow along its normal
CORR_KEEP = 0.0       # 0..1: share of the skin corrections kept where FOLLOW moved weight to a parent bone
# PART: (bones the item may follow - None = all, FOLLOW = share of a limb bone's weight that stays on it; the rest goes
# to its parent bone: hand->forearm->upper_arm->clavicle, foot->shin->thigh->pelvis, head->neck). A FOLLOW of
# (share, t0, t1) grows along the bone: `share` near its joint (up to t0 of the bone length), 1.0 from t1 on - so in
# "chest" the pauldron on the shoulder rides on the collarbone while the sleeve further down follows the arm.
PARTS = {
    "all":       (None, {}),                                                   # robe, cloak, full suit: like the skin
    "chest":     (None, {"upper_arm": (0.2, 0.15, 0.45), "hand": 0.0,           # breastplate / armour with
                         "thigh": (0.3, 0.1, 0.4), "foot": 0.0, "head": 0.0}),    # pauldrons and sleeves
    "torso":     (["pelvis", "spine", "chest", "neck"], {}),                   # torso skin only
    "shoulders": (["chest", "upper_arm.L", "upper_arm.R"], {}),                # pauldrons
    "arms":      (["upper_arm.L", "forearm.L", "upper_arm.R", "forearm.R"], {}),   # sleeves, arm armour
    "gloves":    (["forearm.L", "hand.L", "forearm.R", "hand.R"], {}),         # gloves, gauntlets, bracers
    "legs":      (["pelvis", "thigh.L", "shin.L", "thigh.R", "shin.R"], {}),   # leggings, trousers
    "boots":     (["shin.L", "foot.L", "shin.R", "foot.R"], {}),               # boots, greaves
    "helm":      (["head"], {}),                                               # helmet, hat, mask
    "neck":      (["neck", "chest", "head"], {}),                              # gorget, collar
    # cloth (v13 body): weights from the cloth template (bone chains fitted to the original UO cloak / skirt frames)
    "skirt":     (["pelvis", "spine", "thigh.L", "thigh.R"], {}),              # skirt, kilt: all on the skirt chains
    "cloak":     (["chest", "spine", "neck", "clavicle.L", "clavicle.R"], {}), # cloak, cape: all on the cloak chains
    "robe":      (None, {"hand": 0.0, "foot": 0.0, "head": 0.0}),              # robe, dress: top like the skin,
}                                                                              # below the waist the skirt chains,
                                                                               # sleeves on the arms at any height
# PART -> (cloth template object, height band in m over which the item goes from the body weights to the template
# weights below the template's top; None = template weights only)
CLOTH = {"skirt": ("UO_Template_Skirt", None), "cloak": ("UO_Template_Cloak", None), "robe": ("UO_Template_Skirt", 0.35)}
# rigid items: every vertex 100 % on one bone (they do not bend): hair and beards (UO draws them rigid on the head),
# weapons, shields (left forearm), quivers (back). UO holds 2H weapons, staffs, bows and crossbows in the LEFT hand and 1H weapons in the right,
# and moves them differently from the hand: they ride on the weapon bones polearm.L / axe2h.L / bow.L / weapon1h.R (uo_weapon_bones.py,
# calibrated on the original weapons: model the shaft along the class line, see that script). "weapon" = rigid in hand.R and "weapon.L" = rigid
# in hand.L (no calibration).
RIGID = {"hair": "head", "beard": "head", "hat": "head", "weapon": "hand.R", "weapon.L": "hand.L", "weapon1h": "weapon1h.R", "shield": "shield.L", "quiver": "chest",
         "polearm": "polearm.L", "staff": "polearm.L", "weapon2h": "polearm.L", "axe2h": "axe2h.L", "bow": "bow.L", "crossbow": "bow.L"}
PARENT = {"hand": "forearm", "forearm": "upper_arm", "upper_arm": "clavicle", "foot": "shin", "shin": "thigh",
          "thigh": "pelvis", "head": "neck"}

body = bpy.data.objects["UO_Body"]
rig = bpy.data.objects["UO_Rig"]
SUB = {"upper_arm_twist": "upper_arm", "forearm_twist": "forearm", "toe": "foot"}   # extra bones -> their UO bone


def group_of(name):
    """UO bone a body bone belongs to: finger / twist / toe bones count as hand / arm / foot"""
    side = name[-2:] if name.endswith((".L", ".R")) else ""
    base = name[:-2] if side else name
    base = "hand" if base.startswith("finger") else SUB.get(base, base)
    return base + side


def body_regions(allowed):
    """Body skin triangles whose dominant bone is in `allowed`, plus the body vertex weights of those bones."""
    me = body.data
    names = [g.name for g in body.vertex_groups]
    W = np.zeros((len(me.vertices), len(names)))
    for v in me.vertices:
        for g in v.groups:
            W[v.index, g.group] = g.weight
    keep = [i for i, n in enumerate(names) if allowed is None or group_of(n) in allowed]
    basis = np.empty(len(me.vertices) * 3, np.float32)
    (me.shape_keys.key_blocks[0].data if me.shape_keys else me.vertices).foreach_get("co", basis)
    basis = basis.reshape(-1, 3).astype(np.float64)
    me.calc_loop_triangles()
    tri = np.array([t.vertices[:] for t in me.loop_triangles])
    dom = W[tri].sum(1).argmax(1)                                    # dominant bone of every triangle
    tri = tri[np.isin(dom, keep)]
    if not len(tri):
        raise RuntimeError("no body skin for PART %r" % PART)
    bvh = BVHTree.FromPolygons([Vector(p) for p in basis], tri.tolist())
    return bvh, tri, basis, W[:, keep], [names[i] for i in keep]


def cloth_blend(co, wv, bones, tpl_name, band):
    """blend the body weights with the weights of the nearest point of the cloth template (all in body space); with a
    band (robe) the parts on the arms (sleeves) keep the body weights at any height"""
    tpl = bpy.data.objects.get(tpl_name)
    if tpl is None:
        raise RuntimeError("cloth template %s not found (v13 body file)" % tpl_name)
    me = tpl.data
    M = body.matrix_world.inverted() @ tpl.matrix_world
    tco = np.array([M @ v.co for v in me.vertices])
    tn = [g.name for g in tpl.vertex_groups]
    TW = np.zeros((len(me.vertices), len(tn)))
    for v in me.vertices:
        for g in v.groups:
            TW[v.index, g.group] = g.weight
    me.calc_loop_triangles()
    ttri = np.array([t.vertices[:] for t in me.loop_triangles])
    bvh = BVHTree.FromPolygons([Vector(p) for p in tco], ttri.tolist())
    wt = np.zeros((len(co), len(tn)))
    for i, p in enumerate(co):
        loc, nrm, fi, dist = bvh.find_nearest(Vector(p))
        a, b, c = ttri[fi]
        w = barycentric_transform(loc, Vector(tco[a]), Vector(tco[b]), Vector(tco[c]),
                                  Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)))
        w = np.clip(np.array(w), 0, 1); w /= max(w.sum(), 1e-9)
        wt[i] = w[0] * TW[a] + w[1] * TW[b] + w[2] * TW[c]
    wt /= np.maximum(wt.sum(1, keepdims=True), 1e-9)
    if band is None:
        h = np.ones(len(co))
    else:
        top = tco[:, 2].max()
        arm = wv[:, [j for j, b in enumerate(bones) if group_of(b).split(".")[0] in ("upper_arm", "forearm", "hand")]].sum(1)
        h = np.clip((top - co[:, 2]) / band, 0, 1)
        h = h * h * (3 - 2 * h) * np.clip(1 - 2 * arm, 0, 1)             # smooth; sleeves stay on the arms
    names = list(bones) + [b for b in tn if b not in bones]
    out = np.zeros((len(co), len(names)))
    out[:, :len(bones)] = wv * (1 - h)[:, None]
    for j, b in enumerate(tn):
        out[:, names.index(b)] += wt[:, j] * h
    return out, names


def bind(ob, allowed):
    bvh, tri, basis, W, bones = body_regions(allowed)
    M = body.matrix_world.inverted() @ ob.matrix_world               # item space -> body space
    n = len(ob.data.vertices)
    co = np.empty(n * 3, np.float32)
    if ob.data.shape_keys:
        ob.data.shape_keys.key_blocks[0].data.foreach_get("co", co)
    else:
        ob.data.vertices.foreach_get("co", co)
    co = np.array([M @ Vector(p) for p in co.reshape(-1, 3)])        # body space
    ob.data.calc_loop_triangles()
    itri = np.array([t.vertices[:] for t in ob.data.loop_triangles]).reshape(-1, 3)
    fn = np.cross(co[itri[:, 1]] - co[itri[:, 0]], co[itri[:, 2]] - co[itri[:, 0]])
    vn = np.zeros_like(co)
    for k in range(3):
        np.add.at(vn, itri[:, k], fn)
    vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-12)
    idx = np.zeros((n, 3), int); bary = np.zeros((n, 3))
    for i, p in enumerate(co):
        p = Vector(p)
        loc, nrm, fi, dist = bvh.find_nearest(p)
        if MAP == "under" and (p - loc).dot(nrm) > 0:                # vertex outside the body: skin under it
            best = None
            for d in (-Vector(vn[i]), Vector(vn[i])):                 # normals may point either way
                hit = bvh.ray_cast(p, d, MAX_DIST)
                if hit[0] is not None and (p - hit[0]).dot(hit[1]) > 0 and (best is None or hit[3] < best[3]):
                    best = hit
            if best is not None and best[3] < max(3 * dist, dist + 0.05):
                loc, nrm, fi, dist = best
        a, b, c = tri[fi]
        w = barycentric_transform(loc, Vector(basis[a]), Vector(basis[b]), Vector(basis[c]),
                                  Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)))
        idx[i] = a, b, c; bary[i] = np.clip(w, 0, 1); bary[i] /= max(bary[i].sum(), 1e-9)
    edges = np.array([e.vertices[:] for e in ob.data.edges]).reshape(-1, 2)
    deg = np.bincount(edges.ravel(), minlength=n).astype(float)[:, None]

    def smooth(x):
        for _ in range(SMOOTH):
            acc = np.zeros_like(x)
            np.add.at(acc, edges[:, 0], x[edges[:, 1]]); np.add.at(acc, edges[:, 1], x[edges[:, 0]])
            x = np.where(deg > 0, 0.5 * x + 0.5 * acc / np.maximum(deg, 1), x)
        return x

    # --- skin weights: body weights at the nearest skin point, only the PART bones, normalised
    wv = smooth((W[idx] * bary[..., None]).sum(1))
    s = wv.sum(1, keepdims=True)
    wv = np.where(s > 1e-6, wv / np.maximum(s, 1e-9), 0)
    lost = s[:, 0] <= 1e-6                                           # no weight of the part here: nearest bone of the part
    if lost.any():
        wv[lost, W[idx[lost, 0]].argmax(1)] = 1.0
    if STIFF != 1.0:
        wv = wv ** STIFF; wv /= np.maximum(wv.sum(1, keepdims=True), 1e-9)
    moved = np.zeros(n)
    bones = list(bones)
    for base in ("hand", "forearm", "upper_arm", "foot", "shin", "thigh", "head"):   # distal first, so chains fold
        if base not in FOLLOW:
            continue
        for side in ((".L", ".R") if base != "head" else ("",)):
            b, pb = base + side, PARENT[base] + ("" if PARENT[base] in ("pelvis", "neck") else side)
            if b not in rig.data.bones or pb not in rig.data.bones:
                continue
            f = FOLLOW[base]
            if isinstance(f, tuple):                                 # share grows along the bone (t = 0 joint, 1 end)
                bone = rig.data.bones[b]
                to_body = body.matrix_world.inverted() @ rig.matrix_world
                h, t_ = np.array(to_body @ bone.head_local), np.array(to_body @ bone.tail_local)
                t = ((co - h) @ (t_ - h)) / max(((t_ - h) ** 2).sum(), 1e-12)
                f = f[0] + (1 - f[0]) * np.clip((t - f[1]) / max(f[2] - f[1], 1e-6), 0, 1)
            for j in [j for j, nm in enumerate(bones) if group_of(nm) == b]:   # the bone + its finger / twist / toe bones
                mv = wv[:, j] * (1 - f)
                wv[:, j] -= mv; moved += mv
                if pb in bones:
                    wv[:, bones.index(pb)] += mv
                else:
                    wv = np.c_[wv, mv]; bones.append(pb)
    moved = np.clip(moved, 0, 1)
    if PART in CLOTH:
        wv, bones = cloth_blend(co, wv, bones, *CLOTH[PART])
        moved = np.ones(n)
    body_bones = {g.name for g in body.vertex_groups} | {b.name for b in rig.data.bones}
    for g in [g for g in ob.vertex_groups if g.name in body_bones or g.name.startswith("clavicle")]:
        ob.vertex_groups.remove(g)
    for j, name in enumerate(bones):
        nz = np.nonzero(wv[:, j] > 1e-4)[0]
        if len(nz):
            g = ob.vertex_groups.new(name=name)
            for i in nz:
                g.add([int(i)], float(wv[i, j]), "REPLACE")

    # --- parent + Armature modifier
    if ob.parent != rig:
        mw = ob.matrix_world.copy()
        ob.parent = rig; ob.matrix_parent_inverse = rig.matrix_world.inverted(); ob.matrix_world = mw
    arm = next((m for m in ob.modifiers if m.type == "ARMATURE"), None)
    if arm is None:
        arm = ob.modifiers.new("Armature", "ARMATURE")
        try:
            ob.modifiers.move(len(ob.modifiers) - 1, 0)
        except Exception:
            pass
    arm.object = rig; arm.use_vertex_groups = True; arm.use_bone_envelopes = False

    # --- shape corrections of the same skin points (only a body with corrective shape keys, v12)
    if ob.data.shape_keys:
        for k in [k for k in ob.data.shape_keys.key_blocks if k.name.startswith("uo_")]:
            ob.shape_key_remove(k)
    if body.data.shape_keys is None or not any(k.name.startswith("uo_") for k in body.data.shape_keys.key_blocks):
        print("uo_bind_item: %s -> PART %s, bones %s" % (ob.name, PART, bones))
        return
    kb = body.data.shape_keys.key_blocks
    R = np.array((body.matrix_world.inverted() @ ob.matrix_world).to_3x3().inverted())   # body offsets -> item space
    if ob.data.shape_keys is None:
        ob.shape_key_add(name="Basis", from_mix=False)
    for k in [k for k in ob.data.shape_keys.key_blocks if k.name.startswith("uo_")]:
        ob.shape_key_remove(k)
    obasis = np.empty(n * 3, np.float32); ob.data.shape_keys.key_blocks[0].data.foreach_get("co", obasis)
    obasis = obasis.reshape(-1, 3).astype(np.float64)
    drivers = {d.data_path: d for d in body.data.shape_keys.animation_data.drivers}
    nb = len(body.data.vertices); buf = np.empty(nb * 3, np.float32)
    keys = [k for k in kb if k.name.startswith("uo_")]
    for k in keys:
        k.data.foreach_get("co", buf)
        off = buf.reshape(-1, 3) - basis
        o = smooth((off[idx] * bary[..., None]).sum(1) * (1 - moved * (1 - CORR_KEEP))[:, None]) @ R.T
        sk = ob.shape_key_add(name=k.name, from_mix=False)
        sk.data.foreach_set("co", (obasis + o).ravel().astype(np.float32))
        src = drivers['key_blocks["%s"].value' % k.name].driver
        d = sk.driver_add("value").driver; d.type = "SCRIPTED"
        for sv in src.variables:
            v = d.variables.new(); v.name = sv.name; v.type = sv.type
            v.targets[0].id_type = sv.targets[0].id_type; v.targets[0].id = sv.targets[0].id
            v.targets[0].data_path = sv.targets[0].data_path
        d.expression = src.expression
    print("uo_bind_item: %s -> PART %s, bones %s, %d corrections" % (ob.name, PART, bones, len(keys)))


def bind_rigid(ob, bone):
    body_bones = {g.name for g in body.vertex_groups}
    for g in [g for g in ob.vertex_groups if g.name in body_bones]:
        ob.vertex_groups.remove(g)
    g = ob.vertex_groups.new(name=bone); g.add(list(range(len(ob.data.vertices))), 1.0, "REPLACE")
    if ob.parent != rig:
        mw = ob.matrix_world.copy()
        ob.parent = rig; ob.matrix_parent_inverse = rig.matrix_world.inverted(); ob.matrix_world = mw
    arm = next((m for m in ob.modifiers if m.type == "ARMATURE"), None) or ob.modifiers.new("Armature", "ARMATURE")
    arm.object = rig; arm.use_vertex_groups = True; arm.use_bone_envelopes = False
    if ob.data.shape_keys:
        for k in [k for k in ob.data.shape_keys.key_blocks if k.name.startswith("uo_")]:
            ob.shape_key_remove(k)
    print("uo_bind_item: %s -> rigid on %s" % (ob.name, bone))


if PART not in PARTS and PART not in RIGID:
    raise ValueError("PART must be one of %s" % (list(PARTS) + list(RIGID)))
FOLLOW = PARTS[PART][1] if PART in PARTS else {}
pose = rig.data.pose_position
rig.data.pose_position = "REST"
bpy.context.view_layer.update()
try:
    for ob in [o for o in bpy.context.selected_objects if o.type == "MESH" and o != body]:
        if PART in RIGID:
            bone = RIGID[PART]
            if bone not in rig.data.bones:                           # older file without the shield / weapon bones
                bone = {"shield.L": "forearm.L", "polearm.L": "hand.L", "axe2h.L": "hand.L", "bow.L": "hand.L", "weapon1h.R": "hand.R"}.get(bone, bone)
            bind_rigid(ob, bone)
        else:
            bind(ob, PARTS[PART][0])
finally:
    rig.data.pose_position = pose
