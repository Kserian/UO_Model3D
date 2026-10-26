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
import bpy, os, json, math
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

LAYER = "clothing"
ONLY = []                          # e.g. ["04_stand", "00_walk_unarmed"]; empty = all 35 UO actions
OUTLINE = 0.38                     # dark 1-px outline like UO art (measured on the original body); 1.0 = off. Items: see OUTLINE_TARGET
OUTLINE_TARGET = 0.38              # items without their own scene "uo_outline": the rim is darkened by one factor for the whole render so that the mean brightness
                                   # of the rim pixels / the pixels one in = this (the client's items 0.33-0.43, mean 0.38, body 0.40; with a fixed 0.38 a small
                                   # textured mask came out 0.24 and lost its texture, our 3D body 0.48). Measured over every frame of the run, applied before
                                   # the .vd is written (a factor per frame jumped up to 0.17 between frames). 0 = the fixed OUTLINE
SAMPLES = 512                      # Cycles samples per pixel for items (adaptive sampling; the pixel filter stays a 0.01 px box = the pixel centre, no blur): the
                                   # gloss of metal in UO_Look (Principled) is sampled at random, so at 1 sample a flail had 61 % of its pixels off the converged
                                   # render (64 samples: 2 %, 512: reference; time 11 -> 22 s for 2 actions). The body layer keeps 1 (its colours are the originals)
SHADE_BODY = 0.0                   # per item (scene "uo_shade_body", 0..1): contact shadow of the body parts in front of the item (hands, arms, head: what hides the item): the item pixels near them are darkened by up to this
                                   # share, smoothly over SHADE_WIDTH px (no line): the sides of a robe next to the hands. Per frame, in the posed picture
SHADE_SLEEVE = 0.0                 # per item (scene "uo_shade_sleeve", 0..1): the same where a sleeve and the torso part of the item meet (needs uo_conform_item.py: attribute uo_region): the torso next to the arm
                                   # (the armpit, the side) and the inside of the sleeve next to the torso
SHADE_WIDTH = 3.0                  # px (1 px = 2.8 cm): width of those gradients (scene "uo_shade_width")
CONTRAST = 1.0                     # per item (scene "uo_contrast", e.g. 1.6): a contrast curve on the item's own pixels, rgb = pivot + k x (rgb - pivot), after the outline: the UO robes are painted with dark creases and bright
                                   # lights (luminance spread in the sleeves 54, ours 31: the sleeves and hands of a smooth shell read thicker than the original's); 1.8 = 52, 1.5 = 45. 1 = off. Not the light: the body and
                                   # the other items are untouched
CONTRAST_PIVOT = 0.49              # 0..1: the grey that stays (scene "uo_contrast_pivot"; 0.49 = 125/255, about the median of a grey robe)
EDGE_FLOOR = 0                     # 0-255: the 1-px outline of an item is never darker than this per channel (0 = off); a black item (leather, a black hilt) got a pure black rim,
                                   # which the client draws as a hard hole-like line; scene property uo_edge_floor (24 = a soft dark grey)
OUT_DIR = "//uo_render/"           # PNG output root (vdtool 'canvas' layout + meta.json)
WRITE_VD = True
VD_FILE = "//uo_render/%s.vd"      # %s -> LAYER
STEP = 3                           # scene frames between two UO frames
CANVAS = (256, 256)                # render size in px (width, height); 36 px/m. The .vd stores every frame cropped to its content
ANCHOR = (128, 192)                # UO anchor pixel inside the canvas (world point 0, 0, scene["uo_anchor_height"]).
                                   # 256x256 / (128, 192) holds 444 of the 449 people / equipment animations of the Nelderim client
                                   # (the original body frames are 136x120 with anchor (68, 86); use that pair for the old size)
CLOTHING = "Clothing"              # collection with the clothing / equipment meshes
SHADOW_SUN_K = 1.0                 # calibration of the Sun of the own shadow (uo_materials.py SHADOW): 1 = a lit surface has (1 - s) of the UO diffuse light (checked with test_shadow.py)
CLOAK_SWING = 1.0                  # cloaks (uo_cloth type cloak): scale of the swing taken from the original cloak (0 = hangs as bound)
CLOTH_SIM = 1                      # 1 = add the cloth simulation of uo_cloth_sim.py (cloth_sim.npz next to the .blend, if there is one) to the push of the legs
CLOTH_MOUNTED = 1.0                # loose garments (robe, skirt: custom property uo_cloth) in the mounted actions 23-29: share in which the hanging part follows the legs (thighs above the
                                   # knee, shins below it, like skin) instead of hanging from the pelvis with the hull of the legs. A rider sits with the thighs forward and a robe that hangs from
                                   # the pelvis would leave them bare; the original robes lie along the legs. 0 = hang and push like on foot.
CLOTH_LIE = 0.0                    # loose garments in the falls 21, 22: share in which the hanging part follows the legs as in riding (CLOTH_MOUNTED) instead of hanging from the pelvis
                                   # pushed out by the legs: a robe lying on the ground lies along the legs (the original robe 469 is a narrow shape with a notch between them, the hull and
                                   # the simulation made one wide lump). 0 = off; scene property uo_cloth_lie (uo_cloth_sim.py does not simulate these actions then)
CLOTH_LIE_DROP = 1.0               # with CLOTH_LIE: below the waist the lying garment falls by gravity onto what is under it (the posed legs / body, else the ground): its height above
                                   # that support is cut to this share (smoothed over the cloth; full 0.3 m under the waist, as far as the body lies). The front between the legs is
                                   # weighted to both of them and stood up over the raised knees as a sail. 1 = off; scene property uo_cloth_lie_drop
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
HIDE_ERODE = 0                     # px: the area where a HAND or the HEAD hides an item is shrunk by this much. The 3D hand / head stand 1-2 px off the
                                   # original sprite, and where they cut the item the ORIGINAL body shows through (EXACT_BODY): a wrist or a shoulder of the
                                   # original in a hole of a sleeve or a collar. 0 = off; scene property uo_hide_erode
LEGS_UNDER = False                 # the legs (thighs, shins, feet) never hide the item: a long robe covers them in the client, and a leg that comes out in front of it in 3D (a foot
                                   # lifted in a fall, a knee through the front slit) cut a hole that showed the ORIGINAL legs. Scene property uo_legs_under
HEAD_HIDES = False                 # the head hides the item even when the item is skinned to it: a hood stands off the head, and through its face opening the inside of its back
                                   # wall is behind the face (with the head "worn" it was drawn over the face). Scene property uo_head_hides
OWN_PARTS_NEVER_HIDE = True        # body parts an item is skinned to (a legs item: thighs, shins, pelvis) never hide it: the item
                                   # wraps them, so their skin in front of the item shell is the item's own edge, not an occluder
                                   # (it cut 1-px strips off the sides of trousers). False = every OCCLUDERS part may hide it
TORSO_HIDE_MARGIN = 0.12           # m: the torso (pelvis, spine, chest, neck, clavicle) hides an item only where the item is at least this much behind it.
                                   # Only when a visible item carries the custom property `uo_behind_torso` (a sword, quiver or cape hanging on the back: from the
                                   # front the chest hides it, from the sides it stays visible). Off otherwise: UO draws other items over the torso even where they
                                   # are behind it (a sleeve of an arm behind the chest) and hiding them cost 0.02-0.07 IoU. 0 = never.
DESPECKLE = 0                      # clothing: single dark pixels inside the item darker than their neighbours by more
                                   # than this (0-255) take the colour around them - deep sculpt details / rivets that
                                   # turn into black dots at UO size. 0 = off. Was 28 while items were rendered at 1 sample (it cleaned that noise);
                                   # at SAMPLES it only erased dark texture detail (17 % of the pixels of a textured mask); per item: scene "uo_despeckle"
FILL_HOLES = 4                     # px: holes INSIDE an item (fully surrounded by it) up to this size are filled - skin
                                   # poking through or a gap in the item mesh, not a real occluder. 0 = off; scene property uo_fill_holes (a torn robe whose
                                   # rips should show the body: 0)
INNER_LINE = 0.0                   # clothing: > 0 = the torso pixels of an item that touch its sleeve (point attribute uo_region of uo_conform_item.py) are darkened to this share: a 1-px
                                   # line that sets the sleeves off the torso like the original robes (an extra label render per frame). 0 = off; scene property uo_inner_line
GRIP_CUT = 0.0                     # px: an item with the property uo_grips (uo_twohand.py: where the hands hold the shaft, per UO frame, armature space) is cut by the hand: item pixels within this radius of a
                                   # projected grip that lie on our hand (fingers included, no depth test) and on the original body sprite are removed, whichever of the two is nearer to the camera in 3D
                                   # (a hand that holds a shaft is in front of it; the 3D depth of a hand pressed to the floor or a fist 2 px off the original sprite did not hide it). 0 = off; scene property uo_grip_cut
OUTLINE_BLEND = 0.0                # clothing: share of the colour of the item pixels next to the rim (inside it) mixed into the rim before it is darkened: the outline is then a darker shade
                                   # of the colours around it, not of the (often much darker) edge pixel itself, and it follows the shading smoothly. 0 = off; scene property uo_outline_blend
EDGE_SMOOTH = 0                    # clothing: passes of outline smoothing (a pixel with at most 1 of its 4 neighbours in the item is dropped, an empty one with 3-4 is filled with the colour
                                   # around): the 1-px spikes and notches of a ragged hem. 0 = off; scene property uo_edge_smooth
BODY_GAP = 0.006                   # m: every frame, parts of the bound items closer than this to the arms, hands, legs or
                                   # head of the posed body are pushed out (smoothly) before rendering - otherwise a forearm
                                   # poking through a sleeve in motion cuts a hole in the item. 0 = off
MIN_PIECE = 8                      # px: detached bits of the item smaller than this are removed (collar or cuff rims cut
                                   # off by the head or a hand read as dirt at UO size); the biggest piece always stays. 0 = off


OW, OH, OANCHOR = 136, 120, (68, 86)       # size and anchor of the ORIGINAL UO body frames (atlas, horse masks)
W, H = CANVAS
DX, DY = ANCHOR[0] - OANCHOR[0], ANCHOR[1] - OANCHOR[1]     # where the original frames sit inside the canvas

sc = bpy.context.scene
MIN_PIECE = int(sc.get("uo_min_piece", MIN_PIECE))       # uo_make_item.py "min_piece" of a part: an item of thin straps (a vest) needs a bigger limit than 8 px for the bits an arm cuts off
HIDE_ERODE = int(sc.get("uo_hide_erode", HIDE_ERODE))
LEGS_UNDER = bool(sc.get("uo_legs_under", LEGS_UNDER))
OCCLUDERS = [x for x in sc["uo_occluders"].split(",") if x] if sc.get("uo_occluders") is not None else OCCLUDERS   # per item ("scene": {"uo_occluders": "head,thigh,shin,foot"}):
                                   # a flail held in the hand: arms and hands cut it far more than the original
HEAD_HIDES = bool(sc.get("uo_head_hides", HEAD_HIDES))     # uo_hood_cover.py sets it for a hood
CLOTH_LIE_DROP = float(sc.get("uo_cloth_lie_drop", CLOTH_LIE_DROP))
LIE_W = {}
FILL_HOLES = int(sc.get("uo_fill_holes", FILL_HOLES))
INNER_LINE = float(sc.get("uo_inner_line", INNER_LINE))
EDGE_SMOOTH = int(sc.get("uo_edge_smooth", EDGE_SMOOTH))
CLOTH_LIE = float(sc.get("uo_cloth_lie", CLOTH_LIE))   # uo_make_item.py "tune": {"scene": {"uo_hide_erode": 1}}
SAMPLES = int(sc.get("uo_samples", SAMPLES))            # an item that wants a cleaner render than the default (1024: gloss of metal, dark leather)
EDGE_FLOOR = int(sc.get("uo_edge_floor", EDGE_FLOOR))
OUTLINE_BLEND = float(sc.get("uo_outline_blend", OUTLINE_BLEND))
GRIP_CUT = float(sc.get("uo_grip_cut", GRIP_CUT))
TORSO_HIDE_MARGIN = float(sc.get("uo_torso_margin", TORSO_HIDE_MARGIN))     # per item: how far behind the chest an item must be for the torso to hide it (uo_behind_torso items; a weapon held in front: 0.03)
SHADE_BODY = float(sc.get("uo_shade_body", SHADE_BODY)); SHADE_SLEEVE = float(sc.get("uo_shade_sleeve", SHADE_SLEEVE)); SHADE_WIDTH = float(sc.get("uo_shade_width", SHADE_WIDTH))
CONTRAST = float(sc.get("uo_contrast", CONTRAST)); CONTRAST_PIVOT = float(sc.get("uo_contrast_pivot", CONTRAST_PIVOT))
OUTLINE_AUTO = LAYER == "clothing" and OUTLINE_TARGET > 0 and sc.get("uo_outline") is None
OUTLINE = float(sc.get("uo_outline", OUTLINE))          # an item whose 1-px outline should be softer than the body's (a light grey robe: 0.6)
RIM = dict(edge=0.0, inner=0.0, ne=0, ni=0, paths={})   # OUTLINE_AUTO: brightness sums of the rim / one pixel in, and the frames of this run
DESPECKLE = int(sc.get("uo_despeckle", DESPECKLE))     # uo_prepare_item.py sets 0 for cloth and leather: the despeckle erased the straps, buttons and stitches of a texture (gambeson front closure)
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
# they reach (cloth_lib.hull_push, calibrated on the original robes). Computed per UO frame together with BODY_GAP, before it.
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
        names = list(cl.Capsules.NAMES) + ["pelvis", "chest"]
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


def cloth_sim_table():
    """the difference the cloth simulation (uo_cloth_sim.py) makes to the kinematic cloth, per action and frame: {"a_i": (n, 3)} in the rest frame; {} when there is none"""
    if "sim" not in CLOTH_CTX:
        CLOTH_CTX["sim"] = {}
        path = os.path.join(os.path.dirname(bpy.data.filepath), "cloth_sim.npz") if bpy.data.filepath else ""
        if CLOTH_SIM and path and os.path.exists(path):
            z = np.load(path); CLOTH_CTX["sim"] = {k: z[k] for k in z.files}
            print("render_uo_layer: cloth simulation %s (%d frames)" % (path, len(CLOTH_CTX["sim"])))
    return CLOTH_CTX["sim"]


def cloak_table():
    if "pitch" not in CLOTH_CTX:
        here = globals().get("__file__") and os.path.dirname(os.path.abspath(__file__))
        if here and os.path.exists(os.path.join(here, "cloak_pitch.json")):
            CLOTH_CTX["pitch"] = json.load(open(os.path.join(here, "cloak_pitch.json")))
        else:
            CLOTH_CTX["pitch"] = json.loads(bpy.data.texts["cloak_pitch.json"].as_string())
    return CLOTH_CTX["pitch"]


def cloth_push(o, first, dg, Mw, a=0, i=0):
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
    if prm.get("type") == "cloak":                                            # a cape: swings back about the shoulders with the action (cloak_pitch.json from the original 468)
        rows = cloak_table()["actions"].get(str(a))
        if not rows:
            return np.zeros((len(first), 3))
        d0, d1 = (np.radians(x) * CLOAK_SWING for x in rows[min(i, len(rows) - 1)])
        d = cl.cloak_bend(Vr, prm["z_top"], prm["z_hem"], prm["y_top"], d0, d1)
        return ((d @ skin["chest"][:3, :3].T) @ Dm[:3, :3].T) @ np.linalg.inv(Mw[:3, :3]).T
    share = CLOTH_MOUNTED if 23 <= a <= 29 else CLOTH_LIE if a in (21, 22) else 0.0
    if share > 0:                                                             # riding (and lying, CLOTH_LIE): the hanging part lies along the legs, as the skin under it would move it
        up = skin["pelvis"][:3, :3].T @ np.array([0.0, 0.0, 1.0])            # how far the body lies (0 upright, 1 lying): CLOTH_LIE_DROP in body_fix
        LIE_W[o.name] = float(np.clip((np.linalg.norm(up[:2]) - 0.3) / 0.5, 0, 1)) if a in (21, 22) else 0.0
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
        d0 = d0 * share
        sim = cloth_sim_table().get("%d_%d" % (a, i))
        if sim is not None and len(sim) == len(o.data.vertices):               # the simulated riding cloth (uo_cloth_sim.py mounted=1): what it did on top of the legs' lie
            d0 = d0 + sim[first].astype(np.float64)
        return (d0 @ Dm[:3, :3].T) @ np.linalg.inv(Mw[:3, :3]).T
    d0 = cl.hull_push(Vr, skin["pelvis"], heads[sel], tails[sel], caps.radius[sel], centre_xy=tuple(prm["centre"]), margin=prm["margin"], kappa=prm["kappa"],
                      z_top=prm["z_top"], z_hem=prm["z_hem"], ramp=prm.get("ramp", 0.15), drop=prm.get("drop", 1.0))
    sim = cloth_sim_table().get("%d_%d" % (a, i))
    if sim is not None and len(sim) == len(o.data.vertices):                   # the simulated cloth: what the simulation did on top of the push of the legs
        d0 = d0 + sim[first].astype(np.float64)
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


FLAIL = {}


def flail_fix(a, i):
    """flails (custom property uo_flail, uo_flail.py): the chain and the ball moved to the simulated nodes of this frame (flail_sim.npz next to the .blend), the haft as bound"""
    obs = [o for o in clothes if not o.hide_render and o.get("uo_flail")]
    if not obs:
        return
    if "sim" not in FLAIL:
        path = os.path.join(os.path.dirname(bpy.data.filepath), "flail_sim.npz") if bpy.data.filepath else ""
        FLAIL["sim"] = dict(np.load(path)) if path and os.path.exists(path) else {}
        print("render_uo_layer: flail simulation %s (%d frames)" % (path, len(FLAIL["sim"])))
    X = FLAIL["sim"].get("%d_%d" % (a, i))
    for o in obs:
        fix_off(o)
    if X is None:
        return
    bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get()
    Mrig = np.array(rig.matrix_world)
    for o in obs:
        prm = json.loads(o["uo_flail"]); R = np.array(prm["nodes"]); n = len(R)
        if (o.name, a, i) not in FIX_CACHE:
            nv = len(o.data.vertices)
            s = np.empty(nv, np.float32); o.data.attributes["uo_flail_s"].data.foreach_get("value", s)
            part = np.empty(nv, np.int32); o.data.attributes["uo_flail_part"].data.foreach_get("value", part)
            co = np.empty(nv * 3, np.float32); o.data.vertices.foreach_get("co", co); co = co.reshape(-1, 3).astype(np.float64)
            Mo = np.linalg.inv(Mrig) @ np.array(o.matrix_world)                      # object -> armature (does not change with the direction)
            Vr = co @ Mo[:3, :3].T + Mo[:3, 3]
            Ms = FLAIL["sim"].get("%d_%d_M" % (a, i))                              # the hand's turn smoothed over the action (uo_flail.py HAND_SMOOTH): the haft drawn with it too
            pb = rig.pose.bones[prm["bone"]]; F = (np.array(pb.matrix) @ np.linalg.inv(np.array(pb.bone.matrix_local)))[:3, :3] if Ms is None else Ms[:3, :3]
            seg = (prm["ball_start"] - prm["haft_end"]) / (n - 2)
            piece = np.where(part == 2, n - 2, np.clip(((s - prm["haft_end"]) / seg).astype(int), 0, n - 3))
            ev, me, cur = evaluated_co(o, dg); Mw = np.array(ev.matrix_world); ev.to_mesh_clear()
            pos = cur.copy(); Mi = np.linalg.inv(Mw) @ Mrig
            if Ms is not None:
                m0 = part == 0; pos[m0] = (Vr[m0] @ Ms[:3, :3].T + Ms[:3, 3]) @ Mi[:3, :3].T + Mi[:3, 3]
            for k in range(n - 1):                                                    # each piece turned like its segment, the turn carried down from the haft (no twist jumps)
                c = F @ (R[k + 1] - R[k]); x = X[k + 1] - X[k]
                F = np.array(Vector(c.tolist()).rotation_difference(Vector(x.tolist())).to_matrix()) @ F
                m = (piece == k) & (part > 0)
                if m.any():
                    P = X[k] + (Vr[m] - R[k]) @ F.T
                    pos[m] = P @ Mi[:3, :3].T + Mi[:3, 3]
            FIX_CACHE[(o.name, a, i)] = pos.astype(np.float32)
        fix_on(o, FIX_CACHE[(o.name, a, i)].astype(np.float64))


def lie_drop(o, first, X, bvh, bco, E, deg):
    """CLOTH_LIE_DROP: the lying skirt (body space X) falls onto the posed body under it (ray straight down) or the ground; displacement in body space"""
    prm = json.loads(o["uo_cloth"]); n = len(o.data.vertices)
    co = np.empty(n * 3, np.float32); o.data.vertices.foreach_get("co", co); Mb_ = np.array(o.matrix_basis)
    zr = ((co.reshape(-1, 3) @ Mb_[:3, :3].T + Mb_[:3, 3])[first])[:, 2]
    k = (1.0 - CLOTH_LIE_DROP) * LIE_W[o.name] * np.clip((prm["z_top"] - zr) / 0.3, 0, 1)
    ground = float(bco[:, 2].min()); top = float(X[:, 2].max()) + 0.1
    sup = np.full(len(X), ground)
    for j in np.nonzero(k > 0)[0]:
        loc = bvh.ray_cast(Vector((X[j, 0], X[j, 1], top)), Vector((0, 0, -1)), top - X[j, 2] + 0.5)[0]
        if loc is not None and loc.z < X[j, 2]:                     # the highest body surface under the cloth (the cloth itself above it)
            sup[j] = max(ground, loc.z)
    dz = -k * np.maximum(X[:, 2] - sup, 0.0)
    for _ in range(6):                                            # smoothed over the cloth: no tearing between a fallen and a held vertex
        acc = np.zeros_like(dz); np.add.at(acc, E[:, 0], dz[E[:, 1]]); np.add.at(acc, E[:, 1], dz[E[:, 0]])
        dz = np.where(deg > 0, 0.5 * dz + 0.5 * acc / np.maximum(deg, 1), dz)
    return np.c_[np.zeros((len(X), 2)), dz]


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
        cbvh = None
        if any(o.get("uo_conform") for o in todo):      # conformed garments: kept out of the skin of their own region (cloth_lib.conform_push)
            cm = CONFORM_TRIS()
            cbvh = [BVHTree.FromPolygons([Vector(p) for p in bco], tri[m].tolist()) for m in cm]
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
            Dc = cloth_push(o, first, dg, Mw, a, i)                                 # loose garment: the legs push it out first
            if Dc is not None:
                X = X + Dc @ M[:3, :3].T
                if CLOTH_LIE_DROP < 1.0 and LIE_W.get(o.name, 0.0) > 0:
                    G = lie_drop(o, first, X, bvh, bco, E, deg)
                    X = X + G; Dc = Dc + G @ np.linalg.inv(M[:3, :3]).T
            if o.get("uo_conform") and cbvh is not None and "uo_region" in o.data.attributes:
                lab = np.empty(len(o.data.vertices), np.int32); o.data.attributes["uo_region"].data.foreach_get("value", lab)
                gap = max(float(json.loads(o["uo_conform"]).get("gap", BODY_GAP)), BODY_GAP)
                D = cloth_module().conform_push(X, cbvh, np.clip(lab[first], 0, len(cbvh) - 1), E, deg, gap, limbs=posed_limbs(dg, Bi)) @ np.linalg.inv(M[:3, :3]).T
            else:
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


SUN_STATE = {}


def shadow_sun(on):
    """own shadow of items whose materials use the node group UO_Look_NS (uo_materials.py SHADOW): a Sun with the UO light direction, in the camera frame like the UO light, that casts shadows;
    its strength is pi * (1 - ambient) * (1 - s) so that a lit surface gets (1 - s) of the UO diffuse light from it (the rest, s, is emission in the group)"""
    ob = bpy.data.objects.get("UO_Sun")
    if not on:
        if ob is not None:
            ld = ob.data; bpy.data.objects.remove(ob, do_unlink=True); bpy.data.lights.remove(ld)
        for m, v in SUN_STATE.pop("emission", {}).items():
            m.cycles.emission_sampling = v
        if "bounces" in SUN_STATE:
            sc.cycles.diffuse_bounces = SUN_STATE.pop("bounces")
        return
    g = bpy.data.node_groups.get("UO_Look_NS")
    if g is None or sc.render.engine != "CYCLES":
        return
    used = any(n.type == "GROUP" and n.node_tree == g for o in clothes if not o.hide_render for m in o.data.materials if m and m.node_tree for n in m.node_tree.nodes)
    if not used:
        return
    from mathutils import Vector
    Lv = Vector(next(n for n in g.nodes if n.type == "COMBXYZ").inputs[i].default_value for i in range(3))
    if ob is None:
        ld = bpy.data.lights.new("UO_Sun", "SUN"); ob = bpy.data.objects.new("UO_Sun", ld); sc.collection.objects.link(ob)
    ob.data.angle = 0.0
    ob.data.energy = SHADOW_SUN_K * 3.14159265 * (1.0 - g["uo_ambient"]) * (1.0 - g["uo_shadow"])
    ob.rotation_euler = Vector((0, 0, 1)).rotation_difference(Lv.normalized()).to_euler()      # a Sun shines along its -Z: +Z points to the light
    ob.hide_render = False
    # the diffuse part must see the Sun only: emissive surfaces (the body, the items: UO_Look is emission) must not light it (that would be noise at 1 sample) and no bounces
    if "bounces" not in SUN_STATE:
        SUN_STATE["bounces"] = sc.cycles.diffuse_bounces; sc.cycles.diffuse_bounces = 0
        SUN_STATE["emission"] = {m: m.cycles.emission_sampling for m in bpy.data.materials}
        for m in bpy.data.materials:
            m.cycles.emission_sampling = "NONE"
if EXACT_ANY and sc.render.engine == "CYCLES":
    sc.cycles.pixel_filter_type = "BOX"          # one sample point per pixel centre, like the UO art (no blur)
    sc.cycles.filter_width = 0.01
    sc.cycles.use_denoising = False
    sc.cycles.samples = 1 if LAYER == "body" else SAMPLES     # every sample at the pixel centre (filter 0.01 px): more samples only average the
    sc.cycles.use_adaptive_sampling = LAYER != "body" and SAMPLES > 1     # random parts of the shading (the gloss of metal); adaptive with a strict
    sc.cycles.adaptive_threshold = 0.002; sc.cycles.adaptive_min_samples = 64  # noise threshold: = fixed 512 samples (0.03 % of the pixels > 2 levels off) in a quarter
                                                                               # of the time; the default threshold (0.01) left 3.9 % of the pixels noisy (> 2 levels)
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
shadow_sun(LAYER != "body")
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
    if OUTLINE_BLEND > 0 and edge.any():               # the rim takes the colour of the item pixels next to it (inside): the outline is a darker shade of its surroundings
        acc = np.zeros_like(rgb); cnt = np.zeros(m.shape)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            sh = np.roll(np.roll(rgb, dy, 0), dx, 1); ok = np.roll(np.roll(inner, dy, 0), dx, 1)
            acc += sh * ok[..., None]; cnt += ok
        nb = acc / np.maximum(cnt, 1)[..., None]
        use = edge & (cnt > 0)
        rgb[use] = (1 - OUTLINE_BLEND) * rgb[use] + OUTLINE_BLEND * nb[use]
    if OUTLINE_AUTO:                                   # the rim is darkened in finish(), by one factor for the whole render
        ring = inner & ~(np.pad(~edge, 1, constant_values=True)[1:-1, 2:] & np.pad(~edge, 1, constant_values=True)[1:-1, :-2]
                         & np.pad(~edge, 1, constant_values=True)[2:, 1:-1] & np.pad(~edge, 1, constant_values=True)[:-2, 1:-1])
        y = rgb.mean(-1)
        RIM["edge"] += float(y[edge].sum()); RIM["ne"] += int(edge.sum()); RIM["inner"] += float(y[ring].sum()); RIM["ni"] += int(ring.sum())
    else:
        rgb[edge] *= OUTLINE
        if EDGE_FLOOR:
            rgb[edge] = np.maximum(rgb[edge], EDGE_FLOOR / 255.0)
    if CONTRAST != 1.0:                                # contrast curve on the item's own pixels (not those that carry original UO colours)
        sel = m if keep is None else (m & ~keep)
        rgb[sel] = np.clip(CONTRAST_PIVOT + CONTRAST * (rgb[sel] - CONTRAST_PIVOT), 0.0, 1.0)
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


LIMB_BONES = ("upper_arm.L", "forearm.L", "upper_arm.R", "forearm.R", "thigh.L", "shin.L", "thigh.R", "shin.R")
LIMB_R = 0.07                      # m: conformed garments: a vertex inside a limb this close to its bone is pushed straight away from the bone (cloth_lib.conform_push)


def posed_limbs(dg, Bi):
    """(head, tail, radius) of the posed limb bones in body space"""
    evr = rig.evaluated_get(dg); Mr = Bi @ np.array(evr.matrix_world)
    out = []
    for n in LIMB_BONES:
        pb = evr.pose.bones.get(n)
        if pb is not None:
            out.append(((Mr @ np.append(np.array(pb.head), 1))[:3], (Mr @ np.append(np.array(pb.tail), 1))[:3], LIMB_R))
    return out


def CONFORM_TRIS():
    """triangle masks of the regions of conformed garments (cloth_lib.CONFORM_BONES), computed once"""
    if "conform" not in CLOTH_CTX:
        me = body.data
        names = [g.name for g in body.vertex_groups]
        W = np.zeros((len(me.vertices), len(names)))
        for v in me.vertices:
            for g in v.groups:
                W[v.index, g.group] = g.weight
        me.calc_loop_triangles()
        tri = np.array([t.vertices[:] for t in me.loop_triangles])
        CLOTH_CTX["conform"] = cloth_module().conform_masks([names[k] for k in W[tri].sum(1).argmax(1)])
    return CLOTH_CTX["conform"]


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
if LAYER == "clothing" and LEGS_UNDER:
    WORN |= {"thigh", "shin", "foot"}
if HEAD_HIDES:
    WORN.discard("head")
OCCLUDER_TRIS = body_part_mask(set(OCCLUDERS))                 # parts BODY_GAP keeps the items away from
HIDER_TRIS = body_part_mask(set(OCCLUDERS) - WORN)             # parts that may hide an item in the holdout
HANDHEAD_TRIS = body_part_mask({"hand", "head"})
HAND_TRIS = body_part_mask({"hand"})                # HIDE_ERODE shrinks what these hide (a hand only next to its sleeve)
HEAD_TRIS = body_part_mask({"head"})
BEHIND_TORSO = TORSO_HIDE_MARGIN > 0 and LAYER == "clothing" and any(o.get("uo_behind_torso") for o in clothes if not o.hide_render)
TORSO_TRIS = body_part_mask({"pelvis", "spine", "chest", "neck", "clavicle"}) if BEHIND_TORSO else None
ACTION_HIDE = json.loads(sc["uo_action_hide"]) if sc.get("uo_action_hide") else {}   # per action: {"29": {"legs_under": 1, "torso": 0}} = in that action the legs never hide the item / the torso does not hide it / only the listed parts may hide it ("occluders": "hand")
_BASE_HIDE = (WORN.copy(), HIDER_TRIS, BEHIND_TORSO, TORSO_TRIS)
_BASE_HORSE = HORSE_HOLDOUT


def set_hiders(a):
    """what may hide the item in action a: the scene's own setting, or the per-action override uo_action_hide"""
    global WORN, HIDER_TRIS, BEHIND_TORSO, TORSO_TRIS, HORSE_HOLDOUT
    o = ACTION_HIDE.get(str(a))
    HORSE_HOLDOUT = _BASE_HORSE and not (o and o.get("horse") == 0)       # "horse": 0 = the horse does not hide the item in this action
    if not o or LAYER != "clothing":
        WORN, HIDER_TRIS, BEHIND_TORSO, TORSO_TRIS = _BASE_HIDE[0].copy(), _BASE_HIDE[1], _BASE_HIDE[2], _BASE_HIDE[3]
        return
    WORN = _BASE_HIDE[0].copy()
    if o.get("legs_under"):
        WORN |= {"thigh", "shin", "foot"}
    HIDER_TRIS = body_part_mask((set(o["occluders"].split(",")) if o.get("occluders") else set(OCCLUDERS)) - WORN)
    BEHIND_TORSO = bool(_BASE_HIDE[2]) and bool(o.get("torso", 1))
    TORSO_TRIS = _BASE_HIDE[3] if BEHIND_TORSO else None
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


FIST_SPRITE = {int(x) for x in str(sc.get("uo_fist_sprite", "")).split(",") if x}   # actions whose weapon is moved so that it goes through the hand SHOWN ON THE ORIGINAL SPRITE (our fitted fist is up to 4 px off it)
FIST_R = float(sc.get("uo_fist_radius", 6.0))      # px: the hand is looked for this far from our fist
FIST_EDT = float(sc.get("uo_fist_edt", 3.4))       # px: a fist is not thicker than this (half width); thicker = the torso, no hand found
FIST_MAX = 8.0                                     # px: the largest shift
STAFF_ACT = {int(x) for x in str(sc.get("uo_staff_actions", "")).split(",") if x}   # actions in which the weapon is laid along the line of an ORIGINAL staff (uo_staff_lines: {"action,dir,frame": [cx, cy, ux, uy]} measured on the original black staff's sprites, px of the canvas, u pointing down)
STAFF_LINES = json.loads(sc["uo_staff_lines"]) if sc.get("uo_staff_lines") else {}
FIST_SHIFT = np.zeros(3)                           # armature-space shift applied to the item in the current frame (the grip points of grip_cut move with it)


def project_world(P):
    """pixels of world points (n, 3) through UO_Camera"""
    rig.update_tag(); bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get(); cam = sc.camera.evaluated_get(dg)
    Pm = np.array(cam.calc_matrix_camera(dg, x=W, y=H)); Vm = np.array(cam.matrix_world.inverted())
    h = np.c_[np.asarray(P, float), np.ones(len(P))] @ (Pm @ Vm).T
    return np.stack([(h[:, 0] / h[:, 3] + 1) * 0.5 * W, (1 - h[:, 1] / h[:, 3]) * 0.5 * H], 1)


def detect_fist(mask, g):
    """centre (px) of the hand on an original sprite near g: the thickest blob of the sprite within FIST_R of g (distance to the edge, the torso is thicker than a fist and is refused), or None"""
    Hm, Wm = mask.shape
    pad = np.pad(mask, 6)
    best, bp = -9.0, None
    for y in range(max(int(g[1] - FIST_R) - 1, 0), min(int(g[1] + FIST_R) + 2, Hm)):
        for x in range(max(int(g[0] - FIST_R) - 1, 0), min(int(g[0] + FIST_R) + 2, Wm)):
            dist = np.hypot(x + 0.5 - g[0], y + 0.5 - g[1])
            if not mask[y, x] or dist > FIST_R:
                continue
            win = pad[y + 6 - 5:y + 6 + 6, x + 6 - 5:x + 6 + 6]
            yy, xx = np.nonzero(~win)
            e = np.min(np.hypot(yy - 5, xx - 5)) if len(yy) else 5.0
            if e - 0.15 * dist > best:
                best, bp = e - 0.15 * dist, (x, y, e)
    if bp is None or bp[2] > FIST_EDT:
        return None
    yy, xx = np.mgrid[0:Hm, 0:Wm]
    w = (np.hypot(xx - bp[0], yy - bp[1]) <= 2.6) & mask
    return np.array([xx[w].mean() + 0.5, yy[w].mean() + 0.5])


def fist_offsets(a, n):
    """per direction and frame the shift (px) from the grip of our weapon to the hand on the original sprite. The hand is found on the sprites of the directions where it stands free; its 3D
    offset from our fist (least squares over them) gives the shift in the directions where it merges with the torso. Smoothed over the action. {d: [shift or None] * n}"""
    obs = [o for o in clothes if not o.hide_render and "uo_grips" in o]
    G, J, found, GPX = {}, {}, {}, {}
    for d in range(5):
        rig["uo_direction"] = d; rig.update_tag(); body.update_tag(); bpy.context.view_layer.update()
        for i in range(n):
            pts = [p for o in obs for p in json.loads(o["uo_grips"]).get("%d,%d" % (a, i), [])]
            if not pts:
                continue
            sc.frame_set(1 + i * STEP); bpy.context.view_layer.update()
            Mr = np.array(rig.matrix_world)                      # the rig turns with the direction
            g3 = np.array(pts[0])                                # armature space; the shifts below are armature-space too
            P = project_world(np.array([g3, g3 + [0.1, 0, 0], g3 + [0, 0.1, 0], g3 + [0, 0, 0.1]]) @ Mr[:3, :3].T + Mr[:3, 3])
            GPX[d, i] = P[0]; G[d, i] = g3; J[d, i] = np.array([(P[k] - P[0]) / 0.1 for k in (1, 2, 3)]).T
            orig = original(a, i, d)
            h = detect_fist(orig[..., 3] > 0, P[0]) if orig is not None else None
            if h is not None:
                found[d, i] = h - P[0]
    absol = json.loads(sc["uo_fist_abs"]).get(str(a), {}) if sc.get("uo_fist_abs") else {}
    nudge = json.loads(sc["uo_fist_nudge"]).get(str(a), {}) if sc.get("uo_fist_nudge") else {}
    man = json.loads(sc["uo_fist_manual"]).get(str(a), {}) if sc.get("uo_fist_manual") else {}   # {"dir": [dx, dy] | {"frame": [dx, dy]}}: shifts read by eye where the hand merges with the body
    if not found and not man:
        return {d: [None] * n for d in range(5)}
    x = np.arange(n)
    def smooth(arr, ok):                                  # arr (n, k): gaps interpolated, median of 3, gauss sigma 0.8 frames
        k = arr.shape[1]; v = np.stack([np.interp(x, x[ok], arr[ok, c]) for c in range(k)], 1)
        v = np.stack([np.median(np.stack([v[np.clip(x + t, 0, n - 1), c] for t in (-1, 0, 1)]), 0) for c in range(k)], 1)
        ker = np.exp(-0.5 * (np.arange(-2, 3) / 0.8) ** 2); ker /= ker.sum()
        return np.stack([np.convolve(np.pad(v[:, c], 2, mode="edge"), ker, mode="valid") for c in range(k)], 1)
    delta = np.full((n, 3), np.nan)                       # world shift of the fist (m) from the directions that see the hand
    for i in range(n):
        rows = [(J[d, i], found[d, i]) for d in range(5) if (d, i) in found]
        if rows:
            A = np.vstack([r[0] for r in rows] + [10.0 * np.eye(3)]); b = np.concatenate([r[1] for r in rows] + [np.zeros(3)])
            delta[i] = np.linalg.lstsq(A, b, rcond=None)[0]
    dok = ~np.isnan(delta[:, 0])
    dsm = smooth(delta, dok) if dok.any() else np.zeros((n, 3))
    out = {}
    for d in range(5):
        raw = np.full((n, 2), np.nan)
        for i in range(n):
            if (d, i) in found:
                raw[i] = found[d, i]
        ok = ~np.isnan(raw[:, 0])
        ok = ~np.isnan(raw[:, 0])
        m_d = man.get(str(d))
        if m_d is not None:
            for i in range(n):
                v = m_d.get(str(i)) if isinstance(m_d, dict) else m_d
                if v is not None:
                    raw[i] = v
            ok = ~np.isnan(raw[:, 0])
        est = np.array([J[d, i] @ dsm[i] if (d, i) in J else [np.nan, np.nan] for i in range(n)])    # the 3D shift seen from this direction
        base = np.where(ok[:, None], raw, est)
        good = ~np.isnan(base[:, 0])
        if not good.any():
            out[d] = [None] * n; continue
        sm = np.stack([np.interp(x, x[good], base[good, c]) for c in range(2)], 1)           # no smoothing: the hand moves from frame to frame (run), the weapon follows it frame by frame
        m = np.hypot(sm[:, 0], sm[:, 1]); sm = sm * np.minimum(1.0, FIST_MAX / np.maximum(m, 1e-9))[:, None]
        ab = absol.get(str(d))                               # the hand's position on the sprite read by eye: the grip goes exactly there ({"frame": [x, y]}, px of the canvas)
        if ab is not None:
            for i in range(n):
                v = ab.get(str(i))
                if v is not None and (d, i) in GPX:
                    sm[i] = np.asarray(v, float) - GPX[d, i]
        nd = nudge.get(str(d))                               # read off the viewer by eye: extra px on top of the shift ({"frame": [dx, dy]} or [dx, dy] for all frames)
        if nd is not None:
            for i in range(n):
                v = nd.get(str(i)) if isinstance(nd, dict) else nd
                if v is not None:
                    sm[i] = sm[i] + np.asarray(v, float)
        print("render_uo_layer: fist on the sprite, action %d dir %d: hand seen in %d / %d frames, shift px %s" % (a, d, ok.sum(), n, np.round(np.hypot(sm[:, 0], sm[:, 1]), 1).tolist()))
        out[d] = [sm[i] for i in range(n)]
    if sc.get("uo_fist_report"):                          # JSON {"a,d,i": [x, y of the grip after the shift, hand found (x, y) or null, shift dx, dy]} for checking
        rp = json.load(open(sc["uo_fist_report"])) if os.path.exists(sc["uo_fist_report"]) else {}
        for d in range(5):
            for i in range(n):
                if out[d][i] is not None and (d, i) in GPX:
                    rp["%d,%d,%d" % (a, d, i)] = [float(GPX[d, i][0] + out[d][i][0]), float(GPX[d, i][1] + out[d][i][1]), (np.round(GPX[d, i] + found[d, i], 2).tolist() if (d, i) in found else None), float(out[d][i][0]), float(out[d][i][1])]
        json.dump(rp, open(sc["uo_fist_report"], "w"))
    return out


def staff_plan(a, n):
    """per direction and frame (shift px, turn rad): the weapon turned about its grip, in the plane of the camera, until its projected axis lies on the original staff's line of that frame (the ball end follows the same end of the staff all
    through the action: the end is chosen in the first frame by the smaller turn and kept by continuity), and moved across so that the line passes through the grip. {d: [(shift, turn) or None] * n}"""
    obs = [o for o in clothes if not o.hide_render and "uo_grips" in o]
    for o in obs:
        fix_off(o)
    WMd = json.loads(bpy.data.texts["weapon_motion.json"].as_string())["polearm.L"]["dir"]
    out, ball = {}, None
    for d in range(5):
        rig["uo_direction"] = d; rig.update_tag(); body.update_tag(); bpy.context.view_layer.update()
        row, u_prev = [], None
        for i in range(n):
            ln = STAFF_LINES.get("%d,%d,%d" % (a, d, i))
            pts = [p for o in obs for p in json.loads(o["uo_grips"]).get("%d,%d" % (a, i), [])]
            if not ln or not pts:
                row.append(None); continue
            sc.frame_set(1 + i * STEP); bpy.context.view_layer.update()
            Mr = np.array(rig.matrix_world)
            D3 = np.array(rig.pose.bones["polearm.L"].matrix.to_3x3() @ Vector(WMd)); D3 /= np.linalg.norm(D3)
            gw = np.array(pts[0]) @ Mr[:3, :3].T + Mr[:3, 3]; dw = Mr[:3, :3] @ D3
            if ball is None:                                                  # which end of the bone's axis is the ball: the end with more vertices
                dg = bpy.context.evaluated_depsgraph_get(); ev, me, cur = evaluated_co(obs[0], dg); Mo = np.array(ev.matrix_world); ev.to_mesh_clear()
                sv = (cur @ Mo[:3, :3].T + Mo[:3, 3] - gw) @ dw
                ball = 1.0 if (sv > sv.max() - 0.25).sum() > (sv < sv.min() + 0.25).sum() else -1.0
            P = project_world(np.array([gw, gw + 0.2 * ball * dw]))
            w = P[1] - P[0]; w /= np.linalg.norm(w)                          # towards the ball
            c, u = np.array(ln[:2]), np.array(ln[2:])
            if u_prev is None:
                if w @ u < 0:
                    u = -u
            elif u @ u_prev < 0:
                u = -u
            u_prev = u
            phi = math.atan2(w[0] * u[1] - w[1] * u[0], w @ u)              # turn (image plane, y down) that makes w point along u
            fwd = -np.array(sc.camera.matrix_world)[:3, 2]; fwd /= np.linalg.norm(fwd)
            alpha = phi
            tip = rot_axis(gw + 0.2 * ball * dw, gw, fwd, alpha); Pt = project_world(np.array([gw, tip]))
            wt = Pt[1] - Pt[0]; wt /= np.linalg.norm(wt)
            if wt @ u < 0.99 and rot_ok(gw, dw * ball, fwd, -phi, project_world, u):   # the other way round
                alpha = -phi
            r = c - P[0]; shift = r - (r @ u) * u                               # across the line only
            row.append((shift, alpha))
        out[d] = row
    return out


def rot_ok(gw, dw, fwd, alpha, project, u):
    """True when turning by alpha puts the projected axis closer to u than the sign tried before"""
    Pt = project(np.array([gw, rot_axis(gw + 0.2 * dw, gw, fwd, alpha)]))
    wt = Pt[1] - Pt[0]; wt /= np.linalg.norm(wt)
    return wt @ u > 0.99


def rot_axis(p, pivot, axis, ang):
    """point p turned about the axis through pivot by ang (Rodrigues)"""
    v = p - pivot; k = axis / np.linalg.norm(axis)
    return pivot + v * math.cos(ang) + np.cross(k, v) * math.sin(ang) + k * (k @ v) * (1 - math.cos(ang))


def fist_fix(a, i, plan):
    """the item moved by `off` px in the camera plane (to where the hand is on the original sprite); FIST_SHIFT keeps the shift for grip_cut"""
    global FIST_SHIFT
    obs = [o for o in clothes if not o.hide_render and "uo_grips" in o]
    for o in obs:
        fix_off(o)
    FIST_SHIFT = np.zeros(3)
    off, rot = plan if plan is not None else (None, 0.0)
    if off is None or (np.hypot(*off) < 0.05 and abs(rot) < 1e-4):
        return
    pts = [p for o in obs for p in json.loads(o["uo_grips"]).get("%d,%d" % (a, i), [])]
    if not pts:
        return
    Mrig = np.array(rig.matrix_world)
    g = np.array(pts[0]) @ Mrig[:3, :3].T + Mrig[:3, 3]
    P = project_world(np.array([g, g + [0.1, 0, 0], g + [0, 0.1, 0], g + [0, 0, 0.1]]))
    Jm = np.array([(P[k] - P[0]) / 0.1 for k in (1, 2, 3)]).T          # px per m for the world axes (2 x 3)
    delta = np.linalg.lstsq(Jm, np.asarray(off, float), rcond=None)[0]   # minimum-norm world shift giving `off` px (it lies in the camera plane)
    bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get()
    Mc = np.array(sc.camera.matrix_world); fwd = -Mc[:3, 2]
    for o in obs:
        ev, me, cur = evaluated_co(o, dg); Mo = np.array(ev.matrix_world); ev.to_mesh_clear()
        pw = cur @ Mo[:3, :3].T + Mo[:3, 3]
        if abs(rot) > 1e-6:                                    # turned about the grip in the plane of the camera
            v = pw - g; k = fwd / np.linalg.norm(fwd)
            pw = g + v * math.cos(rot) + np.cross(k, v) * math.sin(rot) + k * (v @ k)[:, None] * (1 - math.cos(rot))
        pw = pw + delta
        fix_on(o, (pw - Mo[:3, 3]) @ np.linalg.inv(Mo[:3, :3]).T)
    FIST_SHIFT = np.linalg.inv(Mrig[:3, :3]) @ delta


def grip_cut(px, a, i, orig_m):
    """remove the item pixels the hands that hold it cover (GRIP_CUT)"""
    pts = []
    for o in clothes:
        if not o.hide_render and "uo_grips" in o:
            pts += json.loads(o["uo_grips"]).get("%d,%d" % (a, i), [])
    if not pts:
        return px
    pts = (np.array(pts) + FIST_SHIFT).tolist()
    rig.update_tag(); bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get(); cam = sc.camera.evaluated_get(dg)
    Pm = np.array(cam.calc_matrix_camera(dg, x=W, y=H)); Vm = np.array(cam.matrix_world.inverted()); Mw = np.array(rig.matrix_world)
    hv = np.c_[np.array(pts), np.ones(len(pts))] @ (Vm @ Mw).T
    h = hv @ Pm.T; ndc = h[:, :2] / h[:, 3:4]
    gp = np.stack([(ndc[:, 0] + 1) * 0.5 * W, (1 - ndc[:, 1]) * 0.5 * H], 1)
    if str(a) in str(sc.get("uo_grip_cut_orig", "")).split(","):     # grips taken from the original sprites (the hand of our 3D arm is elsewhere): the original body pixels near the grip, no 3D hand
        hand = np.ones((H, W), bool)
    else:
        hand, _ = raster([body], HAND_TRIS)
        hand = binary_dilation(hand, 1)
    yy, xx = np.mgrid[0:H, 0:W]
    near = np.zeros((H, W), bool)
    for gx, gy in gp:
        near |= (xx + 0.5 - gx) ** 2 + (yy + 0.5 - gy) ** 2 <= GRIP_CUT ** 2
    cut = near & hand & (px[..., 3] >= 0.5)
    if orig_m is not None:
        cut &= orig_m
    px = px.copy(); px[cut] = 0.0
    return px


def body_coverage():
    """pixels covered by the (deformed) body mesh through UO_Camera, pixel-centre rule (like the EXACT render)"""
    return raster([body])[0]


def body_occlusion(free, margin):
    """the clothing render without the body, with the body in front of the item removed. The body hides a pixel only
    where it is more than `margin` in front of the visible item surface. Returns (hold, body coverage)."""
    cov, _ = raster([body])
    occ, zb = raster([body], HIDER_TRIS & ~HANDHEAD_TRIS if HIDE_ERODE > 0 else HIDER_TRIS)   # only the parts that may hide items (not the torso)
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
    if HIDE_ERODE > 0:                                   # hands and head: their hiding area shrunk (they stand off the original sprite by a pixel or two)
        vis = [o for o in clothes if not o.hide_render]
        for part_tris, near_sleeve in ((HIDER_TRIS & HEAD_TRIS, False), (HIDER_TRIS & HANDHEAD_TRIS & ~HEAD_TRIS, True)):
            occh, zh = raster([body], part_tris)
            hh = occh & (zh < zi - margin)
            shrunk = ~binary_dilation(~hh, HIDE_ERODE)
            if near_sleeve and len(vis) == 1 and "uo_region" in vis[0].data.attributes:   # a hand: only next to its sleeve (the wrist at the cuff), a hand in front of the robe keeps its size
                me = vis[0].data; me.calc_loop_triangles()
                rv = np.empty(len(me.vertices), np.int32); me.attributes["uo_region"].data.foreach_get("value", rv)
                tv = np.empty(len(me.loop_triangles) * 3, np.int32); me.loop_triangles.foreach_get("vertices", tv)
                sl, zs = raster(vis, rv[tv.reshape(-1, 3)].max(1) > 0)
                near = binary_dilation(sl & (zs <= zi + 0.005), HIDE_ERODE + 1)
                shrunk = np.where(near, shrunk, hh)
            hold[shrunk] = 0.0
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


def region_labels(a, i, d):
    """INNER_LINE: which pixels of the clothing layer are a sleeve (1) and which the torso part (0) of the items with uo_region; -1 elsewhere"""
    obs = [o for o in clothes if not o.hide_render and "uo_region" in o.data.attributes]
    if not obs:
        return None
    m = bpy.data.materials.get("uo_region_label")
    if m is None:
        m = bpy.data.materials.new("uo_region_label"); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
        at = nt.nodes.new("ShaderNodeAttribute"); at.attribute_type = "GEOMETRY"; at.attribute_name = "uo_region"
        dv = nt.nodes.new("ShaderNodeMath"); dv.operation = "DIVIDE"; dv.inputs[1].default_value = 4.0
        cr = nt.nodes.new("ShaderNodeValToRGB"); cr.color_ramp.interpolation = "CONSTANT"; el = cr.color_ramp.elements
        el[0].position = 0.0; el[0].color = (1, 0, 0, 1); el[1].position = 0.125; el[1].color = (0, 1, 0, 1)
        e = el.new(0.375); e.color = (0, 0, 1, 1); e = el.new(0.625); e.color = (0, 1, 0, 1); e = el.new(0.875); e.color = (0, 0, 1, 1)
        em = nt.nodes.new("ShaderNodeEmission"); out = nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(at.outputs["Fac"], dv.inputs[0]); nt.links.new(dv.outputs[0], cr.inputs["Fac"]); nt.links.new(cr.outputs["Color"], em.inputs["Color"]); nt.links.new(em.outputs[0], out.inputs["Surface"])
    keep = {o.name: [sl.material for sl in o.material_slots] for o in obs}
    for o in obs:
        for sl in o.material_slots:
            sl.material = m
    ns = (sc.cycles.samples, sc.cycles.use_adaptive_sampling); sc.cycles.samples = 1; sc.cycles.use_adaptive_sampling = False   # flat labels: 1 sample is exact
    try:
        px = render_frame(a, i, d, "holdout")
    finally:
        sc.cycles.samples, sc.cycles.use_adaptive_sampling = ns
        for o in obs:
            for sl, mt in zip(o.material_slots, keep[o.name]):
                sl.material = mt
    lab = np.full(px.shape[:2], -1, np.int8); on = px[..., 3] >= 0.5
    c = px[..., :3].argmax(2)
    lab[on & (c == 0)] = 0; lab[on & (c > 0)] = 1
    return lab


def inner_line(px, lab, k):
    """INNER_LINE: torso pixels next to a sleeve pixel darkened to k"""
    on = px[..., 3] >= 0.5
    line = on & (lab == 0) & binary_dilation(on & (lab == 1), 1)
    px = px.copy(); px[line, :3] *= k
    return px


def contact_shade(px, free, lab):
    """SHADE_BODY / SHADE_SLEEVE: smooth contact shadows (1 - s (1 - d / SHADE_WIDTH)^2 within SHADE_WIDTH px of the occluder): near the body parts that hide the item (pixels of the unhidden render
    `free` that the item layer `px` lacks), and where the sleeve and the torso part meet (labels `lab`: sleeve 1, torso 0)"""
    from scipy.ndimage import distance_transform_edt
    on = px[..., 3] >= 0.5
    f = np.ones(on.shape, np.float32)

    def near(src):
        d = distance_transform_edt(~src)
        t = np.clip(1.0 - d / SHADE_WIDTH, 0.0, 1.0)
        return t * t
    if SHADE_BODY > 0:
        hid = (free[..., 3] >= 0.5) & ~on
        if hid.any():
            f *= 1.0 - SHADE_BODY * near(hid)
    if SHADE_SLEEVE > 0 and lab is not None:
        sl = on & (lab == 1); to = on & (lab == 0)
        if sl.any() and to.any():
            f[to] *= 1.0 - SHADE_SLEEVE * near(sl)[to]
            f[sl] *= 1.0 - SHADE_SLEEVE * near(to)[sl]
    px = px.copy(); px[on, :3] *= f[on][:, None]
    return px


def edge_smooth(px, passes):
    """EDGE_SMOOTH: 1-px spikes of the outline dropped, 1-px notches filled with the mean colour of their neighbours"""
    px = px.copy()
    for _ in range(passes):
        on = px[..., 3] >= 0.5
        n = np.zeros(on.shape, np.int8)
        n[1:] += on[:-1]; n[:-1] += on[1:]; n[:, 1:] += on[:, :-1]; n[:, :-1] += on[:, 1:]
        spike = on & (n <= 1); notch = ~on & (n >= 3)
        if notch.any():
            acc = np.zeros(px.shape[:2] + (3,), np.float32); w = on.astype(np.float32)
            for sl_to, sl_from in (((slice(1, None),), (slice(None, -1),)), ((slice(None, -1),), (slice(1, None),)),
                                   ((slice(None), slice(1, None)), (slice(None), slice(None, -1))), ((slice(None), slice(None, -1)), (slice(None), slice(1, None)))):
                acc[sl_to] += px[sl_from][..., :3] * w[sl_from][..., None]
            px[notch, :3] = acc[notch] / np.maximum(n[notch], 1)[:, None]; px[notch, 3] = 1.0
        px[spike, 3] = 0.0
    return px


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
            set_hiders(a)
            if a in STAFF_ACT and STAFF_LINES and LAYER == "clothing":
                fist_all = staff_plan(a, int(act["uo_frames"]))
            else:
                fist_all = fist_offsets(a, int(act["uo_frames"])) if (a in FIST_SPRITE and LAYER == "clothing" and EXACT_ANY) else None
                if fist_all:
                    fist_all = {dd: [(v, 0.0) if v is not None else None for v in row] for dd, row in fist_all.items()}
            for d in range(5):
                rig["uo_direction"] = d
                rig.update_tag()
                fdir = os.path.join(root, "frames", act.name, "dir%d" % d)
                os.makedirs(fdir, exist_ok=True)
                frames, meta_frames = [], []
                offs = fist_all[d] if fist_all else None
                for i in range(int(act["uo_frames"])):
                    if os.path.exists(os.path.join(root, "STOP")):      # create an empty file named STOP to cancel
                        raise KeyboardInterrupt("STOP file found in " + root)
                    set_tile(a, i, d)
                    sc.frame_set(1 + i * STEP)
                    if (BODY_GAP > 0 or HAS_CLOTH) and LAYER != "body":
                        body_fix(a, i)
                    if LAYER != "body":
                        flail_fix(a, i)
                    if (FIST_SPRITE or STAFF_ACT) and LAYER == "clothing":
                        fist_fix(a, i, offs[i] if offs else None)
                    orig = original(a, i, d) if EXACT_ANY else None
                    orig_m = orig[..., 3] > 0 if orig is not None else None
                    if LAYER == "body" and EXACT_BODY and orig is not None:
                        rgba = orig                                    # the original UO body frame, pixel for pixel
                    elif LAYER == "clothing" and HOLDOUT_MARGIN > 0:
                        free = render_frame(a, i, d, "hidden")
                        hold, cov = body_occlusion(free, HOLDOUT_MARGIN)
                        px = exact_clothing(hold, free, orig_m, cov) if (EXACT_BODY and orig is not None) else hold
                        if GRIP_CUT > 0:
                            px = grip_cut(px, a, i, orig_m if EXACT_BODY else None)
                        if FILL_HOLES > 0:
                            px = fill_small_holes(px, free, FILL_HOLES)
                        lab = region_labels(a, i, d) if (INNER_LINE > 0 or SHADE_SLEEVE > 0) else None
                        if INNER_LINE > 0 and lab is not None:
                            px = inner_line(px, lab, INNER_LINE)
                        if SHADE_BODY > 0 or SHADE_SLEEVE > 0:
                            px = contact_shade(px, free, lab)
                        if EDGE_SMOOTH > 0:
                            px = edge_smooth(px, EDGE_SMOOTH)
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
                    RIM["paths"][(a, d, i)] = os.path.join(fdir, "%02d.png" % i)
                    done_frames += 1
                    yield "%d / %d frames (%s, direction %d)" % (done_frames, total_frames, act.name, d)
                blocks[(a, d)] = frames
                meta_blocks.append(dict(action=a, dir=d, name=act.name, frames=meta_frames))
    finally:
        fix_clear()                                     # items back to bound, also after STOP / an error / ESC


def restore_all():
    shadow_sun(False)
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
    if OUTLINE_AUTO and RIM["ne"] and RIM["ni"]:      # one rim factor for the whole render: rim / one pixel in = OUTLINE_TARGET
        r = (RIM["edge"] / RIM["ne"]) / max(RIM["inner"] / RIM["ni"], 1e-6)
        k = float(np.clip(OUTLINE_TARGET / max(r, 1e-6), 0.25, 1.0))
        print("render_uo_layer: rim / one pixel in %.2f before the outline, outline factor %.2f (target %.2f)" % (r, k, OUTLINE_TARGET))
        for (a, d, i), path in RIM["paths"].items():
            fr = blocks[(a, d)][i]; m = fr[..., 3] > 0
            inner = m.copy(); inner[1:] &= m[:-1]; inner[:-1] &= m[1:]; inner[:, 1:] &= m[:, :-1]; inner[:, :-1] &= m[:, 1:]
            edge = m & ~inner
            fr[..., :3][edge] = np.clip(fr[..., :3][edge].astype(np.float32) * k + 0.5, 0, 255).astype(np.uint8)
            if EDGE_FLOOR:
                fr[..., :3][edge] = np.maximum(fr[..., :3][edge], EDGE_FLOOR)
            h, w = fr.shape[:2]; png = bpy.data.images.new("uo_tmp_out", w, h, alpha=True)
            png.pixels.foreach_set((fr[::-1].astype(np.float32) / 255.0).ravel())
            png.filepath_raw = path; png.file_format = "PNG"; png.save(); bpy.data.images.remove(png)
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
