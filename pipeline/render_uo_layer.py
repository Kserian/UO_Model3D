# UO layer renderer: renders the body or the clothing layer through "UO_Camera" for every UO action,
# 5 directions and every frame, post-processes like UO art and writes PNGs (vdtool layout) and a .vd file.
# Run from Blender's Text Editor (Alt+P). Edit the settings below first.
#
#   LAYER = "clothing" : objects in the "Clothing" collection; the body is a HOLDOUT (it hides what is behind it,
#                        but is not drawn itself) - exactly what an equipment layer in UO must contain.
#   LAYER = "body"     : only the body (clothing hidden).
#   LAYER = "all"      : body + clothing together (preview; not a UO layer).
#   EXACT_BODY / EXACT_COLORS: use the original UO frames packed in this file (see README) for a pixel-exact body.
#   In Blender's window the frames are rendered step by step (uo_job.py), so the window stays alive: progress in the status bar,
#   ESC cancels. In background mode (blender -b, the bpy module) it is a plain loop; there create an empty file named STOP in the
#   output folder (e.g. uo_render/clothing/STOP) or press Ctrl+C to cancel. Delete STOP before the next run.
#   Several runs into the same OUT_DIR add up: e.g. render ONLY = [attacks] with one grip, then ONLY = [others] with
#   another; each run writes a .vd with ALL actions rendered so far (delete OUT_DIR to start from scratch).
import bpy, os, json
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

LAYER = "clothing"
ONLY = []                          # e.g. ["04_stand", "00_walk_unarmed"]; empty = all 35 UO actions
OUTLINE = 0.38                     # dark 1-px outline like UO art (measured on the original body); 1.0 = off
OUT_DIR = "//uo_render/"           # PNG output root (vdtool 'canvas' layout + meta.json)
WRITE_VD = True
VD_FILE = "//uo_render/%s.vd"      # %s -> LAYER
STEP = 3                           # scene frames between two UO frames
CANVAS = (256, 256)                # render size in px (width, height); 36 px/m. The .vd stores every frame cropped to its content
ANCHOR = (128, 192)                # UO anchor pixel inside the canvas (world point 0, 0, scene["uo_anchor_height"]).
                                   # 256x256 / (128, 192) holds 444 of the 449 people / equipment animations of the Nelderim client
                                   # (the original body frames are 136x120 with anchor (68, 86); use that pair for the old size)
CLOTHING = "Clothing"              # collection with the clothing / equipment meshes
CLOTH_MOUNTED = 1.0                # loose garments (robe, skirt: custom property uo_cloth) in the mounted actions 23-29: share in which the hanging part follows the legs (thighs above the
                                   # knee, shins below it, like skin) instead of hanging from the pelvis with the hull of the legs. A rider sits with the thighs forward and a robe that hangs from
                                   # the pelvis would leave them bare; the original robes lie along the legs. 0 = hang and push like on foot.
HORSE_HOLDOUT = True               # mounted actions: the horse hides what is behind it, clipped to the exact horse sprite
EXACT_COLORS = True                # body in the UO look: colours projected from the original UO frames packed in the file
EXACT_BODY = True                  # body = original UO frames: the "body" layer reproduces the original exactly, and in
                                   # the "clothing" layer the body hides items exactly along the ORIGINAL outline
                                   # (the 3D model only decides what is in front / behind). Turn off for a modified body.
HOLDOUT_MARGIN = 0.01              # m: in the clothing layer the body hides an item only where it is at least this much in
                                   # front of it, so skin poking a few mm through tight armour does not cut holes
                                   # (1 px = 2.8 cm). 0 = plain Cycles holdout (renders every frame twice).
OCCLUDERS = ["head", "upper_arm", "forearm", "hand", "thigh", "shin", "foot"]   # body parts that may hide items
                                   # (with HOLDOUT_MARGIN > 0); the torso (pelvis, spine, chest, neck) never does, because
                                   # items are worn over it and a torso poking through is a model error, not an occluder
OWN_PARTS_NEVER_HIDE = True        # body parts an item is skinned to (a legs item: thighs, shins, pelvis) never hide it: the item
                                   # wraps them, so their skin in front of the item shell is the item's own edge, not an occluder
                                   # (it cut 1-px strips off the sides of trousers). False = every OCCLUDERS part may hide it
TORSO_HIDE_MARGIN = 0.12           # m: the torso (pelvis, spine, chest, neck, clavicle) hides an item only where the item is at least this much behind it.
                                   # Only when a visible item carries the custom property `uo_behind_torso` (a sword, quiver or cape hanging on the back: from the
                                   # front the chest hides it, from the sides it stays visible). Off otherwise: UO draws other items over the torso even where they
                                   # are behind it (a sleeve of an arm behind the chest) and hiding them cost 0.02-0.07 IoU. 0 = never.
DESPECKLE = 28                    # clothing: single dark pixels inside the item darker than their neighbours by more
                                   # than this (0-255) take the colour around them - deep sculpt details / rivets that
                                   # turn into black dots at UO size. 0 = off
FILL_HOLES = 4                     # px: holes INSIDE an item (fully surrounded by it) up to this size are filled - skin
                                   # poking through or a gap in the item mesh, not a real occluder. 0 = off
BODY_GAP = 0.006                   # m: every frame, parts of the bound items closer than this to the arms, hands, legs or
                                   # head of the posed body are pushed out (smoothly) before rendering - otherwise a forearm
                                   # poking through a sleeve in motion cuts a hole in the item. 0 = off
MIN_PIECE = 8                      # px: detached bits of the item smaller than this are removed (collar or cuff rims cut
                                   # off by the head or a hand read as dirt at UO size); the biggest piece always stays. 0 = off


OW, OH, OANCHOR = 136, 120, (68, 86)       # size and anchor of the ORIGINAL UO body frames (atlas, horse masks)
W, H = CANVAS
DX, DY = ANCHOR[0] - OANCHOR[0], ANCHOR[1] - OANCHOR[1]     # where the original frames sit inside the canvas

sc = bpy.context.scene
rig = bpy.data.objects["UO_Rig"]
body = bpy.data.objects["UO_Body"]
clothes = [o for o in bpy.data.collections[CLOTHING].all_objects if o.type == "MESH"] if CLOTHING in bpy.data.collections else []
HAS_CLOTH = any(o.get("uo_cloth") for o in clothes if not o.hide_render)

# BODY_GAP: bound items pushed out of the posed limbs / head, per UO frame (shape key "uo_fix", Armature off)
FIX_MESH, FIX_CACHE, FIX_ON, FIX_ADDED = {}, {}, {}, set()


def fix_mesh(o):
    """welded nodes (UV-seam splits move together, so a fix never tears the item open), their edges and degrees"""
    if o.name not in FIX_MESH:
        co = np.empty(len(o.data.vertices) * 3, np.float32); o.data.vertices.foreach_get("co", co)
        key = np.round(co.reshape(-1, 3).astype(np.float64) / 1e-5).astype(np.int64)
        _, first, node = np.unique(key, axis=0, return_index=True, return_inverse=True); node = node.ravel()
        E = np.empty(len(o.data.edges) * 2, np.int32); o.data.edges.foreach_get("vertices", E)
        E = np.unique(np.sort(node[E.reshape(-1, 2)], 1), axis=0); E = E[E[:, 0] != E[:, 1]]
        FIX_MESH[o.name] = (first, node, E, np.bincount(E.ravel(), minlength=len(first)).astype(float))
    return FIX_MESH[o.name]


# Loose garments (robe, skirt; uo_bind_item.py PART "robe" sets the custom property `uo_cloth`): the hanging part follows the pelvis only and the legs push it out to where
# they reach (cloth_lib.hull_push, calibrated on the original robes: docs/qa/robe_physics.md). Computed per UO frame together with BODY_GAP, before it.
CLOTH_CTX = {}


def cloth_module():
    if "mod" not in CLOTH_CTX:
        here = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else ""
        if here and os.path.exists(os.path.join(here, "cloth_lib.py")):
            import importlib.util
            spec = importlib.util.spec_from_file_location("cloth_lib", os.path.join(here, "cloth_lib.py"))
            CLOTH_CTX["mod"] = importlib.util.module_from_spec(spec); spec.loader.exec_module(CLOTH_CTX["mod"])
        else:
            CLOTH_CTX["mod"] = bpy.data.texts["cloth_lib.py"].as_module()
    return CLOTH_CTX["mod"]


def cloth_ctx():
    """legs as capsules (rest bones, radius from the body skin) and the rest matrices; built once"""
    if "caps" not in CLOTH_CTX:
        cl = cloth_module()
        Mr0 = np.array(rig.matrix_world)
        names = list(cl.Capsules.NAMES) + ["pelvis"]
        heads = np.array([(Mr0 @ np.append(np.array(rig.data.bones[n].head_local), 1))[:3] for n in names])
        tails = np.array([(Mr0 @ np.append(np.array(rig.data.bones[n].tail_local), 1))[:3] for n in names])
        me = body.data
        co = np.empty(len(me.vertices) * 3, np.float32)
        (me.shape_keys.key_blocks[0].data if me.shape_keys else me.vertices).foreach_get("co", co)
        Mb = np.array(body.matrix_world); V = co.reshape(-1, 3).astype(np.float64) @ Mb[:3, :3].T + Mb[:3, 3]
        gn = {g.index: g.name for g in body.vertex_groups}
        dom = np.array([gn[max(v.groups, key=lambda g: g.weight).group] if v.groups else "" for v in me.vertices])
        CLOTH_CTX["caps"] = cl.Capsules(names, heads, tails, V, dom)
        CLOTH_CTX["names"] = names
        CLOTH_CTX["Mr0"] = Mr0
        CLOTH_CTX["inv_local"] = {n: np.linalg.inv(np.array(rig.data.bones[n].matrix_local)) for n in names}
    return CLOTH_CTX


def cloth_push(o, first, dg, Mw, a=0):
    """displacement (item space, one row per welded node `first`) that the legs give a loose garment in the current pose; None when the item is not one"""
    raw = o.get("uo_cloth")
    if not raw:
        return None
    cl = cloth_module(); ctx = cloth_ctx(); prm = json.loads(raw)
    evr = rig.evaluated_get(dg)
    Mr0 = ctx["Mr0"]; Mre = np.array(evr.matrix_world); Dm = Mre @ np.linalg.inv(Mr0)
    skin = {n: Mr0 @ np.array(evr.pose.bones[n].matrix) @ ctx["inv_local"][n] @ np.linalg.inv(Mr0) for n in ctx["names"]}
    caps = ctx["caps"]
    heads = np.array([(skin[ctx["names"][k]] @ np.append(caps.head[j], 1))[:3] for j, k in enumerate(caps.idx)])
    tails = np.array([(skin[ctx["names"][k]] @ np.append(caps.tail[j], 1))[:3] for j, k in enumerate(caps.idx)])
    sel = np.array(["pelvis" not in ctx["names"][k] for k in caps.idx])
    co = np.empty(len(o.data.vertices) * 3, np.float32); o.data.vertices.foreach_get("co", co)
    Vr = co.reshape(-1, 3).astype(np.float64); Mb_ = np.array(o.matrix_basis); Vr = (Vr @ Mb_[:3, :3].T + Mb_[:3, 3])[first]
    if 23 <= a <= 29 and CLOTH_MOUNTED > 0:                                  # riding: the hanging part lies along the legs, as the skin under it would move it
        Vh = np.c_[Vr, np.ones(len(Vr))]
        nv = len(o.data.vertices); Pp = (Vh @ skin["pelvis"].T)[:, :3]; d0 = np.zeros_like(Vr)
        have = all(("uo_leg_" + nm) in o.data.attributes for nm in cl.Capsules.NAMES)
        if have:                                                              # the weights uo_bind_item.py kept before it sent the legs' share to the pelvis
            for nm in cl.Capsules.NAMES:
                w = np.empty(nv, np.float32); o.data.attributes["uo_leg_" + nm].data.foreach_get("value", w)
                d0 += w[first][:, None] * ((Vh @ skin[nm].T)[:, :3] - Pp)
        else:                                                                 # an item bound before: left / right of the middle, thigh above the knee, shin below
            side = np.clip(Vr[:, 0] / 0.06, -1, 1) * 0.5 + 0.5; ws = np.clip((0.58 - Vr[:, 2]) / 0.15, 0, 1)[:, None]
            leg = lambda sd: (1 - ws) * (Vh @ skin["thigh." + sd].T)[:, :3] + ws * (Vh @ skin["shin." + sd].T)[:, :3]
            d0 = np.clip((prm["z_top"] - Vr[:, 2]) / 0.2, 0, 1)[:, None] * ((1 - side)[:, None] * leg("L") + side[:, None] * leg("R") - Pp)
        d0 = d0 * CLOTH_MOUNTED
        return (d0 @ Dm[:3, :3].T) @ np.linalg.inv(Mw[:3, :3]).T
    d0 = cl.hull_push(Vr, skin["pelvis"], heads[sel], tails[sel], caps.radius[sel], centre_xy=tuple(prm["centre"]), margin=prm["margin"], kappa=prm["kappa"],
                      z_top=prm["z_top"], z_hem=prm["z_hem"], ramp=prm.get("ramp", 0.15), drop=prm.get("drop", 1.0))
    return (d0 @ Dm[:3, :3].T) @ np.linalg.inv(Mw[:3, :3]).T


def push_out(X, bvh, E, deg, gap):
    """displacement that keeps the points X (body space) `gap` outside the body parts in bvh; spread over the item"""
    D = np.zeros_like(X); look = np.arange(len(X)); reach = 0.1
    for it in range(12):
        P = X + D; need = np.zeros(len(X)); N = np.zeros_like(X); near = []
        for i in look:
            p = Vector(P[i]); loc, nrm, fi, dist = bvh.find_nearest(p, reach)
            if loc is not None:
                near.append(i); sd = (p - loc).dot(nrm)
                if sd < gap:
                    need[i] = gap - sd; N[i] = nrm
        if it == 0:
            look = np.array(near, int); reach = gap + 0.05
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


def fix_off(o):
    st = FIX_ON.pop(o.name, None)
    if st is None:
        return
    kb = o.data.shape_keys.key_blocks
    kb["uo_fix"].value = 0.0
    for name, mute in st["mute"].items():
        kb[name].mute = mute
    for m, (v, r) in st["arm"]:
        m.show_viewport, m.show_render = v, r
    o.data.update()


def fix_on(o, pos):
    if o.data.shape_keys is None:
        o.shape_key_add(name="Basis", from_mix=False); FIX_ADDED.add(o.name)
    kb = o.data.shape_keys.key_blocks
    key = kb.get("uo_fix") or o.shape_key_add(name="uo_fix", from_mix=False)
    key.data.foreach_set("co", pos.astype(np.float32).ravel()); key.value = 1.0
    others = [k for k in list(kb)[1:] if k.name != "uo_fix"]
    arm = [m for m in o.modifiers if m.type == "ARMATURE"]
    FIX_ON[o.name] = dict(mute={k.name: k.mute for k in others}, arm=[(m, (m.show_viewport, m.show_render)) for m in arm])
    for k in others:
        k.mute = True                                   # the posed shape already contains them
    for m in arm:
        m.show_viewport = m.show_render = False
    o.data.update()


def evaluated_co(ob, dg):
    ev = ob.evaluated_get(dg); me = ev.to_mesh()
    co = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", co)
    return ev, me, co.reshape(-1, 3).astype(np.float64)


def body_fix(a, i):
    """BODY_GAP for UO frame i of action a: the pose does not depend on the direction, so each frame is solved once"""
    items = [o for o in clothes if not o.hide_render and not o.get("uo_no_body_gap")]   # uo_no_body_gap: a rigid item (sword, shield) is never bent
    for o in items:
        fix_off(o)
    if not items:
        return
    bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get()
    todo = [o for o in items if (o.name, a, i) not in FIX_CACHE]
    if todo:
        eb, me, bco = evaluated_co(body, dg)
        me.calc_loop_triangles()
        tri = np.empty(len(me.loop_triangles) * 3, np.int32); me.loop_triangles.foreach_get("vertices", tri)
        tri = tri.reshape(-1, 3); Bi = np.array(eb.matrix_world.inverted()); eb.to_mesh_clear()
        if len(OCCLUDER_TRIS) == len(tri):
            tri = tri[OCCLUDER_TRIS]                    # arms, hands, legs, head: the parts that cut holes
        bvh = BVHTree.FromPolygons([Vector(p) for p in bco], tri.tolist())
    for o in items:
        first, node, E, deg = fix_mesh(o)
        ev, me, co = evaluated_co(o, dg); Mw = np.array(ev.matrix_world); ev.to_mesh_clear()
        if len(co) != len(node):
            FIX_CACHE[(o.name, a, i)] = None            # a modifier changes the vertex count: left as bound
            continue
        if (o.name, a, i) not in FIX_CACHE:
            M = Bi @ Mw
            X = co[first] @ M[:3, :3].T + M[:3, 3]
            Dc = cloth_push(o, first, dg, Mw, a)                                  # loose garment: the legs push it out first
            if Dc is not None:
                X = X + Dc @ M[:3, :3].T
            D = (push_out(X, bvh, E, deg, BODY_GAP) if BODY_GAP > 0 else np.zeros_like(X)) @ np.linalg.inv(M[:3, :3]).T
            if Dc is not None:
                D = D + Dc
            idx = np.nonzero(np.abs(D).max(1) > 2e-4)[0]
            FIX_CACHE[(o.name, a, i)] = (idx.astype(np.int32), D[idx].astype(np.float32)) if len(idx) else None
        c = FIX_CACHE[(o.name, a, i)]
        if c is not None:
            Dn = np.zeros((len(first), 3)); Dn[c[0]] = c[1]
            fix_on(o, co + Dn[node])


def fix_clear():
    for o in clothes:
        fix_off(o)
        sk = o.data.shape_keys
        if sk and "uo_fix" in sk.key_blocks:
            o.shape_key_remove(sk.key_blocks["uo_fix"])
        if o.name in FIX_ADDED and o.data.shape_keys and len(o.data.shape_keys.key_blocks) == 1:
            o.shape_key_clear()



for o in clothes:                                       # left over from a run that crashed: back to the bound item
    if o.data.shape_keys and "uo_fix" in o.data.shape_keys.key_blocks:
        o.shape_key_remove(o.data.shape_keys.key_blocks["uo_fix"])
        for m in o.modifiers:
            if m.type == "ARMATURE":
                m.show_viewport = m.show_render = True
writer = bpy.data.texts["uo_vd_writer.py"].as_module()

if sc.render.engine != "CYCLES":                     # holdout, exact modes and UO shading are set up for Cycles
    print("render_uo_layer: render engine %s -> CYCLES" % sc.render.engine)
    sc.render.engine = "CYCLES"
if not bpy.context.preferences.filepaths.use_scripts_auto_execute:
    print("render_uo_layer: NOTE - 'Auto Run Python Scripts' is off; if the body looks wrong, enable it "
          "(Preferences > Save & Load) and reopen the file")
sc.camera = bpy.data.objects["UO_Camera"]
sc.render.resolution_x, sc.render.resolution_y = W, H
sc.render.resolution_percentage = 100
sc.cycles.device = "CPU"            # 1 sample on a 256x256 frame: a GPU only adds device start-up / kernel loading to every one of the
                                    # thousands of render calls (slow, and the window looks frozen); the CPU is faster here
sc.render.dither_intensity = 0.0    # Blender's 8-bit dither is +-1 noise that depends on the pixel position: it would change
                                    # with the canvas / anchor and spoil the "exact" colours of EXACT_COLORS


def to_canvas(a, fill=0):
    """array of an original 120x136 frame -> CANVAS size, the anchors aligned (identity for 136x120 / (68, 86))"""
    out = np.full((H, W) + a.shape[2:], fill, a.dtype)
    y0, y1, x0, x1 = max(DY, 0), min(DY + OH, H), max(DX, 0), min(DX + OW, W)
    if y1 > y0 and x1 > x0:
        out[y0:y1, x0:x1] = a[y0 - DY:y1 - DY, x0 - DX:x1 - DX]
    return out


def anchor_px():
    """continuous pixel position of the world anchor point in the CANVAS render (pixel i covers [i, i+1))"""
    bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get(); cam = sc.camera.evaluated_get(dg)
    P = np.array(cam.calc_matrix_camera(dg, x=W, y=H)) @ np.array(cam.matrix_world.inverted()) @ \
        np.array([0.0, 0.0, sc.get("uo_anchor_height", 0.07), 1.0])
    return np.array([(P[0] / P[3] + 1) * 0.5 * W, (1 - P[1] / P[3]) * 0.5 * H])


def place_camera():
    """UO_Camera for CANVAS: 36 px/m and the anchor point on ANCHOR (the original frames put it at scene uo_anchor_px =
    (68.5, 86.0), i.e. in the middle of pixel column 68, on the top edge of row 86). Returns the old settings."""
    cd = sc.camera.data
    old = (cd.sensor_fit, cd.ortho_scale, cd.shift_x, cd.shift_y)
    cd.sensor_fit = "HORIZONTAL"
    cd.ortho_scale = W / sc.get("uo_px_per_m", 36.0)
    cd.shift_x = cd.shift_y = 0.0
    p0 = anchor_px(); cd.shift_x = cd.shift_y = 0.01; p1 = anchor_px()
    k = (p1 - p0) / 0.01                                           # px per unit of shift (x and y are independent)
    off = np.array(sc.get("uo_anchor_px", (OANCHOR[0] + 0.5, OANCHOR[1] + 0.0))) - np.array(OANCHOR)
    want = np.array(ANCHOR, float) + off
    sh = (want - p0) / k
    cd.shift_x, cd.shift_y = [0.0 if abs(s * kk) < 1e-3 else float(s) for s, kk in zip(sh, k)]   # the 136x120 frame: exactly the file's camera
    err = np.abs(anchor_px() - want).max()
    if err > 1e-3:
        raise RuntimeError("render_uo_layer: camera does not put the anchor on %s (off by %.4f px)" % (ANCHOR, err))
    return old


def atlas_map(w, h, dx, dy):
    """The body material (UO_Skin, nodes UOX_*) reads the atlas of original frames with the window coordinates of the 136x120
    frame. Two Math nodes (UOC_x, UOC_y) turn the window coordinates of a w x h canvas into those of the original frame,
    which sits at offset (dx, dy) in it. Identity for 136x120 / (68, 86)."""
    for m in bpy.data.materials:
        nt = m.node_tree
        if not nt or "UOX_sep" not in nt.nodes:
            continue
        for name, src, dst, dst_in, mul, add in (
                ("UOC_x", "X", "UOX_u0", 1, w / OW, -dx / OW),
                ("UOC_y", "Y", "UOX_v0", 0, h / OH, 1 - h / OH + dy / OH)):
            n = nt.nodes.get(name)
            if n is None:
                n = nt.nodes.new("ShaderNodeMath"); n.name = n.label = name; n.operation = "MULTIPLY_ADD"
                n.location = (nt.nodes[dst].location.x - 200, nt.nodes[dst].location.y + 120)
                nt.links.new(nt.nodes["UOX_sep"].outputs[src], n.inputs[0])
                nt.links.new(n.outputs[0], nt.nodes[dst].inputs[dst_in])
            n.inputs[1].default_value, n.inputs[2].default_value = mul, add


cam_state = place_camera()
atlas_map(W, H, DX, DY)
sc.render.film_transparent = True
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGBA"
sc.view_settings.view_transform = "Standard"
sc["uo_look"] = 1.0                 # UO lighting (see node group "UO_Look")
sc["uo_exact"] = 1.0 if (EXACT_COLORS and "UO_Original_Atlas" in bpy.data.images) else 0.0   # no atlas -> model colours
EXACT_ANY = EXACT_COLORS or EXACT_BODY
if EXACT_ANY and sc.render.engine == "CYCLES":
    sc.cycles.pixel_filter_type = "BOX"          # one sample point per pixel centre, like the UO art (no blur)
    sc.cycles.filter_width = 0.01
    sc.cycles.use_denoising = False
    sc.cycles.samples = 1                        # 1 sample = exactly the pixel centre (the UO shading is noise-free)
ORIG = {}
if EXACT_ANY and "uo_original_frames.json" in bpy.data.texts:
    import base64, zlib
    ORIG = json.loads(bpy.data.texts["uo_original_frames.json"].as_string())


def original(a, i, d):
    """original UO body frame (uint8 RGBA, CANVAS size, anchor aligned) or None"""
    v = ORIG.get("frames", {}).get("%d,%d,%d" % (a, i, d)) if ORIG else None
    if v is None:
        return None
    return to_canvas(np.frombuffer(zlib.decompress(base64.b64decode(v)), np.uint8).reshape(OH, OW, 4))


def set_tile(a, i, d):
    t = ORIG.get("tiles", {}).get("%d,%d,%d" % (a, i, d)) if ORIG else None
    sc["uo_tile_col"], sc["uo_tile_row"] = (t if t else (0, 0))

horses = {o.name: o for o in bpy.data.objects if o.name.startswith("Horse_")}
for o in horses.values():
    o.hide_render = True
    o.is_holdout = True


HORSE_MASKS = {}                   # exact horse sprite silhouettes: only there can the horse hide anything
if "uo_horse_masks.json" in bpy.data.texts:
    import base64, zlib
    for k, v in json.loads(bpy.data.texts["uo_horse_masks.json"].as_string())["masks"].items():
        bits = np.unpackbits(np.frombuffer(zlib.decompress(base64.b64decode(v)), np.uint8))[:OH * OW]
        HORSE_MASKS[tuple(int(x) for x in k.split(","))] = to_canvas(bits.reshape(OH, OW).astype(bool), False)


def set_horse(a, i):
    for o in horses.values():
        o.hide_render = True
    o = horses.get("Horse_a%d_f%d" % (a, i)) if HORSE_HOLDOUT else None
    if o is not None:          # the horse proxy made for exactly this mounted frame
        o.hide_render = False


state = dict(holdout=body.is_holdout, body_hide=body.hide_render, cloth={o.name: o.hide_render for o in clothes},
             action=rig.animation_data.action, direction=rig.get("uo_direction", 0), pose=rig.data.pose_position)
rig.data.pose_position = "POSE"                      # the actions only play in Pose Position
body.hide_render = False
body.is_holdout = LAYER == "clothing"
for o in clothes:
    o.hide_render = LAYER == "body"
if LAYER == "clothing" and not any(not o.hide_render for o in clothes):
    raise RuntimeError("No visible meshes in the 'Clothing' collection")


def uo_post(px, keep=None):
    """float RGBA (h,w,4), straight alpha -> UO look: over black, 1-bit alpha, dark outline. Returns uint8 RGBA.
    keep: pixels that already carry original UO colours (no extra outline)."""
    a = px[..., 3:4]
    rgb = px[..., :3] * a
    m = px[..., 3] >= 0.5
    inner = m.copy()
    inner[1:] &= m[:-1]; inner[:-1] &= m[1:]; inner[:, 1:] &= m[:, :-1]; inner[:, :-1] &= m[:, 1:]
    edge = m & ~inner
    if keep is not None:
        edge &= ~keep
        rgb[keep & m] = px[..., :3][keep & m]
    rgb[edge] *= OUTLINE
    out = np.zeros(px.shape, np.uint8)
    out[..., :3] = np.clip(rgb * 255 + 0.5, 0, 255).astype(np.uint8)
    out[..., 3] = m * 255
    out[~m, :3] = 0
    return out


def render_px():
    sc.render.filepath = tmp
    bpy.ops.render.render(write_still=True)
    im = bpy.data.images.load(tmp)
    w, h = im.size
    px = np.empty(w * h * 4, np.float32); im.pixels.foreach_get(px)
    bpy.data.images.remove(im)
    return px.reshape(h, w, 4)[::-1]                        # Blender pixels start at the bottom row


def body_part_mask(parts):
    """body triangles (loop_triangles order) whose dominant bone is one of `parts` (names without .L / .R)"""
    me = body.data
    names = [g.name.split(".")[0] for g in body.vertex_groups]
    names = ["hand" if n.startswith("finger") else n for n in names]
    W = np.zeros((len(me.vertices), len(names)))
    for v in me.vertices:
        for g in v.groups:
            W[v.index, g.group] = g.weight
    me.calc_loop_triangles()
    tri = np.array([t.vertices[:] for t in me.loop_triangles])
    dom = W[tri].sum(1).argmax(1)
    return np.array([names[k] in parts for k in dom])


def worn_parts(share=0.04):
    """body parts (names without .L / .R) the visible items are skinned to: an item wraps them, so they never hide it.
    A part counts when it carries at least `share` of an item's total skin weight. Rigid items (one bone: weapons, shields,
    quivers) wrap nothing, except on the head (hair, hats), which they sit on."""
    out = set()
    for o in clothes:
        if o.hide_render or not o.vertex_groups:
            continue
        names = [g.name.split(".")[0] for g in o.vertex_groups]
        names = ["hand" if n.startswith("finger") else n for n in names]
        tot = {}
        for v in o.data.vertices:
            for g in v.groups:
                tot[names[g.group]] = tot.get(names[g.group], 0.0) + g.weight
        if len(o.vertex_groups) == 1:
            out |= {p for p in tot if p == "head"}
            continue
        s = sum(tot.values())
        out |= {p for p, w in tot.items() if s > 0 and w / s >= share}
    return out


WORN = worn_parts() if (LAYER == "clothing" and OWN_PARTS_NEVER_HIDE) else set()
OCCLUDER_TRIS = body_part_mask(set(OCCLUDERS))                 # parts BODY_GAP keeps the items away from
HIDER_TRIS = body_part_mask(set(OCCLUDERS) - WORN)             # parts that may hide an item in the holdout
BEHIND_TORSO = TORSO_HIDE_MARGIN > 0 and LAYER == "clothing" and any(o.get("uo_behind_torso") for o in clothes if not o.hide_render)
TORSO_TRIS = body_part_mask({"pelvis", "spine", "chest", "neck", "clavicle"}) if BEHIND_TORSO else None
print("render_uo_layer: items wrap %s; body parts that may hide them: %s" % (sorted(WORN), sorted(set(OCCLUDERS) - WORN)))


def raster(objs, tri_mask=None):
    """pixel coverage and camera depth (m) of the deformed meshes through UO_Camera, pixel-centre rule (like the
    EXACT render). Returns (bool H x W, float H x W with inf where nothing is). tri_mask: triangles to use."""
    rig.update_tag(); body.update_tag(); bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    cam = sc.camera.evaluated_get(dg)
    Pm = np.array(cam.calc_matrix_camera(dg, x=W, y=H)); Vm = np.array(cam.matrix_world.inverted())
    img = np.zeros((H, W), bool); depth = np.full((H, W), np.inf)
    for ob in objs:
        ev = ob.evaluated_get(dg); me = ev.to_mesh()
        co = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
        me.calc_loop_triangles()
        tri = np.empty(len(me.loop_triangles) * 3, np.int32); me.loop_triangles.foreach_get("vertices", tri); tri = tri.reshape(-1, 3)
        if tri_mask is not None and len(tri_mask) == len(tri):
            tri = tri[tri_mask]
        Mw = np.array(ev.matrix_world)
        ev.to_mesh_clear()
        hv = np.c_[co, np.ones(len(co))] @ (Vm @ Mw).T                  # camera space
        h = hv @ Pm.T
        ndc = h[:, :2] / h[:, 3:4]
        P = np.stack([(ndc[:, 0] + 1) * 0.5 * W, (1 - ndc[:, 1]) * 0.5 * H], 1)[tri]
        Z = -hv[:, 2][tri]
        mn = np.floor(P.min(1)).astype(int); mx = np.ceil(P.max(1)).astype(int)
        A, B, C = P[:, 0], P[:, 1], P[:, 2]
        den = (B[:, 1] - C[:, 1]) * (A[:, 0] - C[:, 0]) + (C[:, 0] - B[:, 0]) * (A[:, 1] - C[:, 1])
        ok = np.abs(den) > 1e-12; size = np.clip(mx - mn, 0, 16)
        for dy in range(int(size[:, 1].max(initial=0)) + 1):
            for dx in range(int(size[:, 0].max(initial=0)) + 1):
                t = np.nonzero(ok & (dx <= size[:, 0]) & (dy <= size[:, 1]))[0]
                px_ = mn[t, 0] + dx; py_ = mn[t, 1] + dy; cx, cy = px_ + 0.5, py_ + 0.5
                l0 = ((B[t, 1] - C[t, 1]) * (cx - C[t, 0]) + (C[t, 0] - B[t, 0]) * (cy - C[t, 1])) / den[t]
                l1 = ((C[t, 1] - A[t, 1]) * (cx - C[t, 0]) + (A[t, 0] - C[t, 0]) * (cy - C[t, 1])) / den[t]
                k = (l0 >= -1e-4) & (l1 >= -1e-4) & (1 - l0 - l1 >= -1e-4) & (px_ >= 0) & (py_ >= 0) & (px_ < W) & (py_ < H)
                img[py_[k], px_[k]] = True
                z = l0[k] * Z[t[k], 0] + l1[k] * Z[t[k], 1] + (1 - l0[k] - l1[k]) * Z[t[k], 2]
                np.minimum.at(depth, (py_[k], px_[k]), z)
    return img, depth


def body_coverage():
    """pixels covered by the (deformed) body mesh through UO_Camera, pixel-centre rule (like the EXACT render)"""
    return raster([body])[0]


def body_occlusion(free, margin):
    """the clothing render without the body, with the body in front of the item removed. The body hides a pixel only
    where it is more than `margin` in front of the visible item surface. Returns (hold, body coverage)."""
    cov, _ = raster([body])
    occ, zb = raster([body], HIDER_TRIS)               # only the parts that may hide items (not the torso)
    _, zi = raster([o for o in clothes if not o.hide_render])
    seen = free[..., 3] >= 0.5
    for _ in range(2):                                  # item pixels Cycles drew but the raster missed: neighbour depth
        miss = seen & np.isinf(zi)
        if not miss.any():
            break
        pad = np.pad(zi, 1, constant_values=np.inf)
        nb = np.min([pad[y:y + H, x:x + W] for y in range(3) for x in range(3)], axis=0)
        zi = np.where(miss, nb, zi)
    hold = free.copy()
    hold[occ & (zb < zi - margin)] = 0.0
    if TORSO_TRIS is not None:                           # items behind the torso (on the back): clearly behind = hidden
        occt, zt = raster([body], TORSO_TRIS)
        hold[occt & (zt < zi - TORSO_HIDE_MARGIN)] = 0.0
    return hold, cov


def render_frame(a, i, d, body_mode):
    """body_mode: 'visible' | 'holdout' | 'hidden'. Includes the horse holdout of mounted actions."""
    body.hide_render = body_mode == "hidden"
    body.is_holdout = body_mode == "holdout"
    set_horse(a, i)
    px = render_px()
    hm = HORSE_MASKS.get((a, i, d)) if HORSE_HOLDOUT else None
    if hm is not None and horses.get("Horse_a%d_f%d" % (a, i)) is not None:
        set_horse(-1, 0)                                # outside the horse sprite nothing is hidden
        px = np.where(hm[..., None], px, render_px())
    return px


def binary_dilation(m, iterations=1):
    """4-neighbour dilation (same result as scipy.ndimage.binary_dilation), numpy only."""
    for _ in range(iterations):
        d = m.copy()
        d[1:] |= m[:-1]
        d[:-1] |= m[1:]
        d[:, 1:] |= m[:, :-1]
        d[:, :-1] |= m[:, 1:]
        m = d
    return m


def fill_small_holes(px, free, max_px):
    """transparent patches up to max_px fully surrounded by the item are filled: with the item from the render without
    the body (skin poking through) or, where the item mesh itself leaves a gap, with the colour of the item around it"""
    a = px[..., 3] >= 0.5
    H, W = a.shape
    outside = np.zeros_like(a)
    outside[0, :] = outside[-1, :] = outside[:, 0] = outside[:, -1] = True
    outside &= ~a
    while True:                                         # transparent pixels connected to the image border
        g = outside.copy()
        g[1:] |= outside[:-1]; g[:-1] |= outside[1:]; g[:, 1:] |= outside[:, :-1]; g[:, :-1] |= outside[:, 1:]
        g &= ~a
        if (g == outside).all():
            break
        outside = g
    hole = ~a & ~outside
    seen = np.zeros_like(hole)
    for y, x in zip(*np.nonzero(hole)):
        if seen[y, x]:
            continue
        comp, stack = [], [(y, x)]
        seen[y, x] = True
        while stack:
            cy, cx = stack.pop()
            comp.append((cy, cx))
            for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                if 0 <= ny < H and 0 <= nx < W and hole[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        if len(comp) > max_px:
            continue                                    # a real opening (e.g. an arm in front of the chest)
        todo = []
        for cy, cx in comp:
            if free[cy, cx, 3] >= 0.5:
                px[cy, cx] = free[cy, cx]
            else:
                todo.append((cy, cx))
        for _ in range(max_px):                         # mesh gap: colour of the neighbouring item pixels
            left = []
            for cy, cx in todo:
                nb = [px[ny, nx] for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1))
                      if 0 <= ny < H and 0 <= nx < W and px[ny, nx, 3] >= 0.5]
                if nb:
                    px[cy, cx] = np.mean(nb, axis=0); px[cy, cx, 3] = 1.0
                else:
                    left.append((cy, cx))
            todo = left
            if not todo:
                break
    return px


def despeckle(img, thr, passes=2):
    """uint8 RGBA: dark single pixels inside the item (not its outline) -> colour of their non-dark neighbours"""
    out = img.copy(); m = out[..., 3] > 0; H, W = m.shape
    offs = [(y, x) for y in range(3) for x in range(3) if (y, x) != (1, 1)]
    for _ in range(passes):
        rgb = out[..., :3].astype(float)
        lum = rgb.mean(-1)
        pad = np.pad(rgb, ((1, 1), (1, 1), (0, 0)), mode="edge"); pm = np.pad(m, 1)
        stack = np.stack([pad[y:y + H, x:x + W] for y, x in offs], 0)
        valid = np.stack([pm[y:y + H, x:x + W] for y, x in offs], 0)
        sl = stack.mean(-1)
        srt = np.sort(np.where(valid, sl, np.inf), axis=0)
        n = valid.sum(0)
        lo = np.take_along_axis(srt, np.clip((n - 1) // 2, 0, 7)[None], 0)[0]
        hi = np.take_along_axis(srt, np.clip(n // 2, 0, 7)[None], 0)[0]
        med = np.where(np.isfinite(hi), (lo + hi) / 2, lo)
        dark = m & (n >= 7) & (lum < med - thr)
        if not dark.any():
            break
        ok = valid & (sl >= (med - thr / 2)[None])
        w = ok.sum(0)
        fill = (stack * ok[..., None]).sum(0) / np.maximum(w, 1)[..., None]
        sel = dark & (w > 0)
        out[sel, :3] = np.clip(fill[sel] + 0.5, 0, 255).astype(np.uint8)
    return out


def drop_small_pieces(img, min_px):
    """uint8 RGBA: detached pieces of the item (8-connected) smaller than min_px -> transparent, except the biggest"""
    m = img[..., 3] > 0; H, W = m.shape
    seen = np.zeros_like(m); pieces = []
    for y0, x0 in zip(*np.nonzero(m)):
        if seen[y0, x0]:
            continue
        comp = [(y0, x0)]; seen[y0, x0] = True; k = 0
        while k < len(comp):
            cy, cx = comp[k]; k += 1
            for ny in (cy - 1, cy, cy + 1):
                for nx in (cx - 1, cx, cx + 1):
                    if 0 <= ny < H and 0 <= nx < W and m[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        comp.append((ny, nx))
        pieces.append(comp)
    out = img.copy()
    big = max(pieces, key=len) if pieces else None
    for comp in pieces:
        if len(comp) < min_px and comp is not big:
            ys, xs = zip(*comp)
            out[list(ys), list(xs)] = 0
    return out


def exact_clothing(hold, free, orig_body, cov):
    """Hide the item exactly where the ORIGINAL body is in front of it; the 3D model decides front/behind."""
    a_h, a_f = hold[..., 3] >= 0.5, free[..., 3] >= 0.5
    hidden = a_f & ~a_h                                 # the model body hides the item here
    out = free.copy()                                   # outside the original body nothing hides the item
    use_hold = orig_body & cov
    out[use_hold] = hold[use_hold]
    rim = orig_body & ~cov & binary_dilation(hidden, iterations=2)   # thin rim the model body does not reach
    out[rim] = 0.0
    return out


root = bpy.path.abspath(OUT_DIR + LAYER + "/")
tmp = os.path.join(root, "_tmp.png")
os.makedirs(root, exist_ok=True)
if os.path.exists(os.path.join(root, "STOP")):
    os.remove(os.path.join(root, "STOP"))                  # a leftover STOP from a cancelled run
blocks, meta_blocks = {}, []
acts = sorted([a for a in bpy.data.actions if "uo_action" in a], key=lambda a: int(a["uo_action"]))
todo = [a for a in acts if not ONLY or a.name in ONLY]
total_frames = sum(int(a["uo_frames"]) * 5 for a in todo)
view_prefs = bpy.context.preferences.view
render_display = view_prefs.render_display_type


def frame_job():
    """one UO frame per step; uo_job.py hands control back to Blender between two of them (the window stays alive, ESC cancels)"""
    view_prefs.render_display_type = "NONE"             # no Render Result window popping up for every frame
    done_frames = 0
    try:
        for act in acts:
            if ONLY and act.name not in ONLY:
                continue
            a = int(act["uo_action"])
            rig.animation_data.action = act
            for d in range(5):
                rig["uo_direction"] = d
                rig.update_tag()
                fdir = os.path.join(root, "frames", act.name, "dir%d" % d)
                os.makedirs(fdir, exist_ok=True)
                frames, meta_frames = [], []
                for i in range(int(act["uo_frames"])):
                    if os.path.exists(os.path.join(root, "STOP")):      # create an empty file named STOP to cancel
                        raise KeyboardInterrupt("STOP file found in " + root)
                    set_tile(a, i, d)
                    sc.frame_set(1 + i * STEP)
                    if (BODY_GAP > 0 or HAS_CLOTH) and LAYER != "body":
                        body_fix(a, i)
                    orig = original(a, i, d) if EXACT_ANY else None
                    orig_m = orig[..., 3] > 0 if orig is not None else None
                    if LAYER == "body" and EXACT_BODY and orig is not None:
                        rgba = orig                                    # the original UO body frame, pixel for pixel
                    elif LAYER == "clothing" and HOLDOUT_MARGIN > 0:
                        free = render_frame(a, i, d, "hidden")
                        hold, cov = body_occlusion(free, HOLDOUT_MARGIN)
                        px = exact_clothing(hold, free, orig_m, cov) if (EXACT_BODY and orig is not None) else hold
                        if FILL_HOLES > 0:
                            px = fill_small_holes(px, free, FILL_HOLES)
                        rgba = uo_post(px)
                        if DESPECKLE > 0:
                            rgba = despeckle(rgba, DESPECKLE)
                        if MIN_PIECE > 0:
                            rgba = drop_small_pieces(rgba, MIN_PIECE)
                    elif LAYER == "clothing":
                        px = render_frame(a, i, d, "holdout")
                        if EXACT_BODY and orig is not None:
                            px = exact_clothing(px, render_frame(a, i, d, "hidden"), orig_m, body_coverage())
                        rgba = uo_post(px)
                        if MIN_PIECE > 0:
                            rgba = drop_small_pieces(rgba, MIN_PIECE)
                    else:
                        px = render_frame(a, i, d, "visible")
                        rgba = uo_post(px, keep=orig_m if (EXACT_COLORS and orig_m is not None) else None)
                    h, w = rgba.shape[:2]
                    frames.append(rgba)
                    png = bpy.data.images.new("uo_tmp_out", w, h, alpha=True)
                    png.pixels.foreach_set((rgba[::-1].astype(np.float32) / 255.0).ravel())
                    png.filepath_raw = os.path.join(fdir, "%02d.png" % i); png.file_format = "PNG"; png.save()
                    bpy.data.images.remove(png)
                    meta_frames.append(dict(file="%02d.png" % i))
                    done_frames += 1
                    yield "%d / %d frames (%s, direction %d)" % (done_frames, total_frames, act.name, d)
                blocks[(a, d)] = frames
                meta_blocks.append(dict(action=a, dir=d, name=act.name, frames=meta_frames))
    finally:
        fix_clear()                                     # items back to bound, also after STOP / an error / ESC


def restore_all():
    view_prefs.render_display_type = render_display
    set_horse(-1, 0)
    body.is_holdout, body.hide_render = state["holdout"], state["body_hide"]
    for o in clothes:
        o.hide_render = state["cloth"][o.name]
    rig.animation_data.action, rig["uo_direction"] = state["action"], state["direction"]
    rig.data.pose_position = state["pose"]
    cd = sc.camera.data
    cd.sensor_fit, cd.ortho_scale, cd.shift_x, cd.shift_y = cam_state               # camera and atlas mapping of the 136x120 file
    atlas_map(OW, OH, 0, 0)
    sc.render.resolution_x, sc.render.resolution_y = OW, OH


def finish():
    global meta_blocks
    if os.path.exists(tmp):
        os.remove(tmp)
    # actions rendered in EARLIER runs into the same folder are kept: each run can use a different item setup (e.g. another
    # grip for some actions) and the final .vd contains every action whose frames are on disk
    names = {int(a["uo_action"]): a.name for a in acts}
    for act in acts:
        a = int(act["uo_action"])
        for d in range(5):
            if (a, d) in blocks:
                continue
            fdir = os.path.join(root, "frames", act.name, "dir%d" % d)
            files = ["%02d.png" % i for i in range(int(act["uo_frames"]))]
            if not all(os.path.exists(os.path.join(fdir, f)) for f in files):
                continue
            frames = []
            for f in files:
                im = bpy.data.images.load(os.path.join(fdir, f)); w, h = im.size
                px = np.empty(w * h * 4, np.float32); im.pixels.foreach_get(px); bpy.data.images.remove(im)
                frames.append(np.clip(px.reshape(h, w, 4)[::-1] * 255 + 0.5, 0, 255).astype(np.uint8))
            blocks[(a, d)] = frames
            meta_blocks.append(dict(action=a, dir=d, name=act.name, frames=[dict(file=f) for f in files]))
    print("actions in this .vd:", sorted({a for a, _ in blocks}))
    # vdtool-compatible meta.json (canvas mode) so the PNGs can also be packed with: python vdtool.py pack <folder> out.vd
    done_blocks = {(b["action"], b["dir"]): b for b in meta_blocks}
    meta_blocks = [done_blocks.get((a, d), dict(action=a, dir=d, name=names.get(a, "action"), frames=[]))
                   for a in range(35) for d in range(5)]
    with open(os.path.join(root, "meta.json"), "w") as fh:
        json.dump(dict(tool="render_uo_layer", anim_type=2, actions=35, mode="canvas", canvas=[W, H],
                       anchor=list(ANCHOR), blocks=meta_blocks), fh, indent=1)
    if WRITE_VD:
        vd_path = bpy.path.abspath(VD_FILE % LAYER)
        writer.write_vd(vd_path, blocks, anim_type=2, anchor=ANCHOR)
        print("wrote", vd_path)

    restore_all()
    print("done ->", root)


def abort(why):
    restore_all()
    print("render_uo_layer: %s - nothing written to the .vd (the frames already rendered stay in %s)" % (why, root))


# Blender's window: a long loop inside "Run Script" freezes it ("Not Responding"), so in the interface the frames are rendered
# step by step from a modal operator (uo_job.py: progress in the status bar, ESC cancels). Without the text: a plain loop.
if "uo_job.py" in bpy.data.texts:
    bpy.data.texts["uo_job.py"].as_module().run(frame_job(), "render_uo_layer", finish, abort)
else:
    try:
        for _ in frame_job():
            pass
    except BaseException:
        abort("error")
        raise
    finish()
