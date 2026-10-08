"""A free 3D model -> a UO item, in one command (no Blender window).

    python uo_make_item.py RECIPE.json [--out DIR] [--base ../model/UO_Body_0x190.blend] [--preview] [--vd] [--actions 04_stand,...]
    python uo_make_item.py --list MODEL.glb          # what is in the file: meshes, vertices, size (to choose `skip` / `keep`)

RECIPE.json (only "file" and "kind" are required):
  {"name": "gambeson", "file": "models/medieval_shirt.glb", "kind": "shirt",
   "skip": ["guy"],            # meshes of the file to leave out (parts of names)      "keep": ["Blade"]  only these
   "drop_materials": ["Belt", "Buckle"],   # materials whose faces are cut out (a belt that is one mesh with the robe)
   "arms_down": 0,                  # deg; 80-90 for a model in a T-pose (arms out): the sleeves are turned down about the shoulders ("arm_materials": ["sleeve"] names them, "arm_blend": 0.12 m is the width over which the turn fades into the body)
   "turn": 0,                  # 180 when the model came in back to front (the fit also tries it)
   "stretch": [0.8, 1.25, 1.0],  # width, depth, height factors about the centre (a model made on a mannequin with other proportions than the UO body); "tune": {"uo_autofit_item.py": {"UNIT": 0.3}} = the file is not in metres
   "decimate": 30000,          # vertices above which the model is reduced
   "materials": {"SATURATION": 1.0, "METAL": null},   # uo_materials.py settings (grey item that takes a dye: SATURATION 0)
   "prepare": {"DENSIFY": false},                      # settings of uo_prepare_item.py itself
   "tune": {"uo_fit_item.py": {"MIN_GAP": 0.02, "LIMIT": 0.05}, "uo_autofit_item.py": {"GAP": 0.02}},   # settings of the steps it runs (autofit, densify, fit, bind)
   "sim": true,                     # loose garments (kind robe / skirt): cloth simulation on top of the leg push (uo_cloth_sim.py; on by default, false = off, {"goal": 0.3, ...} = its settings)
   "weapon": {"class": "sword", "part": "weapon1h", "length": null, "tip": "auto"}}   # a weapon instead of "kind": class (sword, dagger, mace, axe, polearm, staff, spear,
                               # bow, crossbow, gun), part (weapon1h, polearm, axe2h, bow: which hand bone and motion), length m (null = of the class), tip ("auto", "heavy", "+y" ...)

A model of several items (straps + a sword on the back; the file has the model's mannequin): "reference": {"keep": ["mannequin mesh"], "kind": "shirt", "turn_back": false} (false = do not try the half turn: for a model whose front is known, e.g. a belt with a sword) is fitted to the body and its
transform goes to every part of "parts": [{"name": "straps", "keep": [...], "kind": "harness"}, {"name": "sword", "keep": [...], "rigid": "quiver"}] (rigid = stiff on a bone; its
uo_behind_torso / uo_no_body_gap properties are set: the chest hides what hangs behind it, the item is not bent away from limbs; "move": [x, y, z] m nudges a part; "skin_shell": {"GAP": 0.03, "VNECK": [1.3, 1.56, 0.1], "ZMAX": 1.56} = rebuild a vest as a shell of the body skin (uo_skin_shell.py); "smooth_mesh": {"iterations": 3, "factor": 0.5} = smooth the finished shape (borders stay); "min_piece": 24 = the renderer drops detached bits smaller than 24 px (default 8); "no_body_gap": true = not bent around the limbs by the renderer; "behind_torso": true = the torso hides what is behind it (garments that wrap the trunk); "cut_above" / "cut_below": z (m) at which a part is cut (a collar above the shoulders, a hem over the thighs); "thicken": {"width": 0.05} = widen a thin long part so that every cross-section direction is at least that wide (a sword: 0.05 m = 2 px), {"factor": 1.3, "own_axis": false} for its hilt on the same axis; "pelvis_share": 0.4 = that share of the weight on the pelvis, the rest on the bone: a sword that follows the leg only partly).

Steps (each is one of the scripts that are also in the .blend, see README): uo_import_item.py (clean, join, reduce) -> uo_materials.py (UO look) ->
uo_prepare_item.py (uo_autofit_item.py size / place from the skin, uo_densify_item.py, uo_fit_item.py push out of the skin, uo_bind_item.py skin weights).
Result: DIR/item.blend (the base .blend with the item in the collection Clothing), DIR/report.txt (what each step printed), DIR/qa.json (item_qa.py: how much of the item is inside the posed body, how far it stands off), with --preview DIR/preview.png (a few
actions: stand, walk, run, attack, spell, die; 3 directions, 3 moments), with --vd DIR/clothing.vd (all 35 actions, 15-30 minutes).
"""
import argparse, json, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
PREVIEW_ACTIONS = "04_stand,00_walk_unarmed,02_run_unarmed,09_attack_1h_slash,16_spell_directed,21_die_forward"
WEAPON_ACTIONS = {"weapon1h": "07_combat_idle_1h,09_attack_1h_slash,10_attack_1h_pierce,11_attack_1h_bash,03_run_armed,21_die_forward",
                  "polearm": "08_combat_idle_2h,13_attack_2h_slash,14_attack_2h_pierce,12_attack_2h_bash,03_run_armed,21_die_forward",
                  "axe2h": "08_combat_idle_2h,13_attack_2h_slash,12_attack_2h_bash,03_run_armed,21_die_forward,20_get_hit",
                  "bow": "04_stand,19_attack_crossbow,18_attack_bow,03_run_armed,20_get_hit,21_die_forward"}


def source(name):
    return open(os.path.join(HERE, name), encoding="utf-8").read()


def override(text, **over):
    for k, v in over.items():
        text, n = re.subn(r"^%s\s*=.*$" % re.escape(k), "%s = %r" % (k, v), text, count=1, flags=re.M)
        if n != 1:
            raise SystemExit("setting %s not found" % k)
    return text


def build_parts_stage(recipe, out_blend):
    """a model made of several items (straps + a sword on the back...): the reference part (e.g. the model's mannequin torso) is fitted to the body, its transform is applied to every
    other part, which then goes its own way (kind: a worn item; rigid: stiff on a bone, e.g. "quiver" = on the chest, a sword on the back)"""
    ref = recipe["reference"]
    parts = recipe["parts"]
    base = dict(file=os.path.abspath(recipe["file"]), decimate=int(recipe.get("decimate", 30000)))
    return '''
import bpy, os, re, sys, json
import numpy as np
from mathutils import Matrix, Vector
HERE = %(here)r
AXIS = []                                   # (centre, direction) of the first thickened part: the long axis of a sword, shared by its hilt parts


def thicken(obs, th):
    """widen a long thin part about its own long axis: "width": m (the widest cross-section of the part becomes this wide, e.g. 0.05 m = 2 px at 36 px/m) or "factor": scale of the cross-section;
    a part with "own_axis" false uses the axis of the first one (a hilt on the sword's axis)"""
    Ms = [np.array(o.matrix_world) for o in obs]
    Vs = [np.array([(Mw @ np.append(np.array(v.co), 1.0))[:3] for v in o.data.vertices]) for o, Mw in zip(obs, Ms)]
    V = np.concatenate(Vs)
    if not AXIS or th.get("own_axis", True):
        c = V.mean(0); u = np.linalg.svd(V - c, full_matrices=False)[2][0]
        AXIS[:] = [(c, u)]
    c, u = AXIS[0]
    d = V - c; t = d @ u; perp = d - np.outer(t, u)
    if "width" in th:                                                    # each cross-section direction at least `width` wide (a flat scabbard seen edge-on is a 1-px line)
        mid = (t > np.percentile(t, 20)) & (t < np.percentile(t, 80))
        pc = np.linalg.svd(perp[mid] - perp[mid].mean(0), full_matrices=False)[2]
        pc1 = pc[0]; pc2 = np.cross(u, pc1)
        e1 = perp[mid] @ pc1; e2 = perp[mid] @ pc2
        w1, w2 = float(np.percentile(e1, 98) - np.percentile(e1, 2)), float(np.percentile(e2, 98) - np.percentile(e2, 2))
        f1, f2 = max(1.0, float(th["width"]) / max(w1, 1e-6)), max(1.0, float(th["width"]) / max(w2, 1e-6))
        perp = np.outer(perp @ pc1, pc1) * f1 + np.outer(perp @ pc2, pc2) * f2
        cur, f = max(w1, w2), 1.0
        msg = "x%%.2f / x%%.2f (cross-section %%.1f x %%.1f cm)" %% (f1, f2, 100 * w1, 100 * w2)
    else:
        cur, f = 0.0, float(th["factor"]); msg = "x%%.2f" %% f
    print("uo_make_item: thicken %%s %%s" %% (obs[0].name, msg))
    k = 0
    for o, Mw, Vo in zip(obs, Ms, Vs):
        n = len(Vo); new = c + np.outer(t[k:k + n], u) + f * perp[k:k + n]; k += n
        loc = (np.linalg.inv(Mw) @ np.c_[new, np.ones(n)].T).T[:, :3]
        o.data.vertices.foreach_set("co", loc.astype(np.float32).ravel()); o.data.update()
rig = bpy.data.objects["UO_Rig"]; rig.data.pose_position = "REST"
for o in list(bpy.data.collections["Clothing"].all_objects):
    bpy.data.objects.remove(o, do_unlink=True)
os.environ["UO_SCRIPTS"] = HERE
def run(script, **over):
    text = open(os.path.join(HERE, script), encoding="utf-8").read()
    for k, v in over.items():
        text, n = re.subn(r"^%%s\\s*=.*$" %% re.escape(k), "%%s = %%r" %% (k, v), text, count=1, flags=re.M)
        assert n == 1, (script, k)
    exec(compile(text, script, "exec"), {"__name__": "__main__"})
def select(obs):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in obs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
base = %(base)r
ref = %(ref)r
run("uo_import_item.py", FILE=base["file"], KIND="", KEEP=ref["keep"], DECIMATE_TO=0, NAME="reference")
run("uo_autofit_item.py", KIND=ref["kind"], TURN_BACK=bool(ref.get("turn_back", True)))
M = Matrix([bpy.context.scene["uo_last_fit"][i * 4:i * 4 + 4] for i in range(4)])
print("uo_make_item: reference %%s fitted; the same transform goes to every part" %% ref["keep"])
for o in [o for o in bpy.data.collections["Clothing"].all_objects]:
    bpy.data.objects.remove(o, do_unlink=True)
for part in %(parts)r:
    run("uo_import_item.py", FILE=base["file"], KIND="", KEEP=part["keep"], SKIP=part.get("skip", []), DECIMATE_TO=base["decimate"], NAME=part["name"])
    obs = [o for o in bpy.context.selected_objects if o.type == "MESH"]
    for o in obs:
        o.data.transform(M)
    bpy.context.view_layer.update()
    if part.get("thicken"):
        thicken(obs, part["thicken"])
    run("uo_materials.py", **part.get("materials", {}))
    if part.get("scale") or part.get("on_bone"):         # a part that is the wrong size / place for the body (a pauldron of a stylised armour): scaled about its own centre, then its centre put on a bone (+ offset, m)
        import numpy as np
        for o in obs:
            vs = np.array([(o.matrix_world @ v.co)[:] for v in o.data.vertices]); c = (vs.min(0) + vs.max(0)) / 2
            k = float(part.get("scale", 1.0))
            o.data.transform(o.matrix_world.inverted() @ Matrix.Translation(c) @ Matrix.Scale(k, 4) @ Matrix.Translation(-c) @ o.matrix_world)
            if part.get("on_bone"):
                bn, d = part["on_bone"]
                bl = (rig.matrix_world @ rig.data.bones[bn + ".L"].head_local)
                side = "L" if abs(bl.x - c[0]) < abs(-bl.x - c[0]) else "R"
                tgt = rig.matrix_world @ rig.data.bones[bn + "." + side].head_local
                o.data.transform(o.matrix_world.inverted() @ Matrix.Translation(Vector(tgt) + Vector(d) - Vector(c)) @ o.matrix_world)
        gap = part.get("clear_skin")
        if gap:                                          # grow the part about its place until it clears the skin of the rest pose (at most 2 %% of its vertices closer than `gap` m): a cup that must not sit inside the shoulder
            from mathutils.bvhtree import BVHTree
            bpy.context.view_layer.update(); body = bpy.data.objects["UO_Body"]; dg = bpy.context.evaluated_depsgraph_get(); eb = body.evaluated_get(dg); mb = eb.to_mesh(); mb.calc_loop_triangles()
            bv = BVHTree.FromPolygons([eb.matrix_world @ v.co for v in mb.vertices], [t.vertices[:] for t in mb.loop_triangles]); eb.to_mesh_clear()
            for o in obs:
                vs = np.array([(o.matrix_world @ v.co)[:] for v in o.data.vertices]); c = (vs.min(0) + vs.max(0)) / 2; k0 = 1.0
                def inside(k):
                    n = 0
                    for q in vs:
                        p = Vector(c + (q - c) * k); loc, nrm, fi, d = bv.find_nearest(p, 0.5)
                        n += loc is not None and ((p - loc).dot(nrm) < gap)
                    return n / len(vs)
                while inside(k0) > 0.02 and k0 < 2.5:
                    k0 *= 1.04
                o.data.transform(o.matrix_world.inverted() @ Matrix.Translation(c) @ Matrix.Scale(k0, 4) @ Matrix.Translation(-c) @ o.matrix_world)
                print("uo_make_item: %%s grown x%%.2f to clear the skin by %%.0f mm" %% (o.name, k0, 1000 * gap))
        bpy.context.view_layer.update()
    cup = part.get("cup")
    if cup:                                              # a shoulder cup (dome): its sphere is fitted, scaled to the shoulder (radius of the skin round the bone head + gap) and centred on the bone head (+ offset)
        import numpy as np
        from mathutils.bvhtree import BVHTree
        bpy.context.view_layer.update(); body = bpy.data.objects["UO_Body"]; dg = bpy.context.evaluated_depsgraph_get(); eb = body.evaluated_get(dg); mb = eb.to_mesh(); mb.calc_loop_triangles()
        bv = BVHTree.FromPolygons([eb.matrix_world @ v.co for v in mb.vertices], [t.vertices[:] for t in mb.loop_triangles]); eb.to_mesh_clear()
        for o in obs:
            vs = np.array([(o.matrix_world @ v.co)[:] for v in o.data.vertices]); keep = np.ones(len(vs), bool)
            for _ in range(4):                           # sphere least squares on the vertices that lie on the dome (the fin and the rim do not)
                A = np.c_[2 * vs[keep], np.ones(keep.sum())]; b = (vs[keep] ** 2).sum(1)
                x = np.linalg.lstsq(A, b, rcond=None)[0]; ctr = x[:3]; r = np.sqrt(x[3] + ctr @ ctr)
                keep = np.abs(np.linalg.norm(vs - ctr, axis=1) - r) < 0.2 * r
            bn = cup.get("bone", "upper_arm")
            bl = rig.matrix_world @ rig.data.bones[bn + ".L"].head_local
            side = "L" if abs(bl.x - ctr[0]) < abs(-bl.x - ctr[0]) else "R"
            head = rig.matrix_world @ rig.data.bones[bn + "." + side].head_local
            loc, nrm, fi, dsk = bv.find_nearest(Vector(head), 0.5)
            k = (dsk + float(cup.get("gap", 0.025))) / r
            tgt = Vector(head) + Vector(cup.get("offset", [0, 0, 0]))
            mx = Matrix.Translation(tgt) @ Matrix.Scale(k, 4) @ Matrix.Translation(-Vector(ctr))
            o.data.transform(o.matrix_world.inverted() @ mx @ o.matrix_world)
            print("uo_make_item: %%s: dome r %%.3f m (%%d of %%d vertices) -> shoulder %%s, skin %%.3f m from the bone head, scaled x%%.2f" %% (o.name, r, keep.sum(), len(vs), side, dsk, k))
        bpy.context.view_layer.update()
    if part.get("cut_below") is not None:                # the hem of a cuirass that reaches over the thighs (they poke through it when the legs move): the part is cut at this height (m, body rest pose)
        import bmesh
        for o in obs:
            bm = bmesh.new(); bm.from_mesh(o.data); bm.transform(o.matrix_world)
            g = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, float(part["cut_below"])), plane_no=(0, 0, 1), clear_inner=True)
            bm.transform(o.matrix_world.inverted()); bm.to_mesh(o.data); bm.free()
        print("uo_make_item: cut below z = %%.3f m" %% float(part["cut_below"]))
    if part.get("cut_above") is not None:                # collar peaks and straps that stand above the shoulder line: the part is cut at this height (m, body rest pose, after "move")
        import bmesh
        off0 = part.get("move", [0, 0, 0])
        for o in obs:
            bm = bmesh.new(); bm.from_mesh(o.data); bm.transform(o.matrix_world)
            bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, float(part["cut_above"]) - off0[2]), plane_no=(0, 0, 1), clear_outer=True)
            bm.transform(o.matrix_world.inverted()); bm.to_mesh(o.data); bm.free()
        print("uo_make_item: cut above z = %%.3f m" %% float(part["cut_above"]))
    off = part.get("move", [0, 0, 0])
    if any(off):
        for o in obs:
            o.data.transform(Matrix.Translation(off))
    select(obs)
    if part.get("rigid"):
        run("uo_bind_item.py", PART=part["rigid"])
        sh = float(part.get("pelvis_share", 0.0))
        if sh > 0:                                       # hangs from the belt: part of the leg's swing only (rigid on the thigh alone drives the hilt into the hip when the leg swings)
            for o in obs:
                bone = [g.name for g in o.vertex_groups][0]
                idx = list(range(len(o.data.vertices)))
                o.vertex_groups[bone].add(idx, 1.0 - sh, "REPLACE")
                (o.vertex_groups.get("pelvis") or o.vertex_groups.new(name="pelvis")).add(idx, sh, "REPLACE")
        arm = part.get("arm_share")
        if arm:                                          # a pauldron: stiff on the chest, part of the weight on the upper arm of its side (turns with the arm only partly, does not stretch)
            for o in obs:
                wx = sum((o.matrix_world @ v.co).x for v in o.data.vertices) / len(o.data.vertices)
                bl = (rig.matrix_world @ rig.data.bones["upper_arm.L"].head_local).x
                side = "L" if abs(bl - wx) < abs(-bl - wx) else "R"
                idx = list(range(len(o.data.vertices)))
                bone = [g.name for g in o.vertex_groups][0]
                o.vertex_groups[bone].add(idx, 1.0 - float(arm), "REPLACE")
                o.vertex_groups.new(name="upper_arm." + side).add(idx, float(arm), "REPLACE")
        for o in obs:
            for k in ("uo_no_body_gap", "uo_behind_torso"):
                if part.get(k, True):
                    o[k] = 1
    else:
        os.environ["UO_PREPARE_EXTRA"] = json.dumps(part.get("tune", {}))
        run("uo_prepare_item.py", KIND=part["kind"], AUTOFIT=False, **part.get("prepare", {}))
        if part.get("pose_clear") is not None:                       # the arms swept through the poses of the animations: the rest shape is pushed out of them (uo_pose_clear.py), then bound again for the new shape
            pc = dict(part["pose_clear"]) if isinstance(part["pose_clear"], dict) else {}
            bind_part = pc.pop("bind", None)
            select(obs)
            run("uo_pose_clear.py", **pc)
            run("uo_bind_item.py", PART=part.get("prepare", {}).get("PART") or bind_part or "chest")
        if part.get("skin_shell") is not None:             # a vest / waistcoat as a shell of the body skin (uo_skin_shell.py): clean, can not poke through the body; the fitted item gives the outline, then it is bound again
            ss = dict(part["skin_shell"]) if isinstance(part["skin_shell"], dict) else {}
            bind_over = ss.pop("bind", {})                    # settings of uo_bind_item.py for the shell (SMOOTH 0: the weights of the skin under each vertex, not smoothed over the mesh)
            select(obs)
            run("uo_skin_shell.py", **ss)
            run("uo_bind_item.py", PART=part.get("prepare", {}).get("PART") or "torso", **bind_over)
        if part.get("smooth_mesh"):                      # Laplacian smoothing of the finished rest shape (bumps and waves left by the push-out of the fit); border vertices (armholes, neckline, hem) stay, the skin weights stay
            sm = part["smooth_mesh"] if isinstance(part["smooth_mesh"], dict) else {}
            import bmesh
            for o in obs:
                bm = bmesh.new(); bm.from_mesh(o.data)
                inner = [v for v in bm.verts if not v.is_boundary]
                for _ in range(int(sm.get("iterations", 3))):
                    bmesh.ops.smooth_vert(bm, verts=inner, factor=float(sm.get("factor", 0.5)), use_axis_x=True, use_axis_y=True, use_axis_z=True)
                bm.to_mesh(o.data); bm.free(); o.data.update()
            print("uo_make_item: smoothed the shape: %%d iterations, factor %%.2f" %% (int(sm.get("iterations", 3)), float(sm.get("factor", 0.5))))
        if part.get("min_piece"):                        # detached bits of the item smaller than this (px) are removed by the renderer (scene property uo_min_piece; default 8): the straps of a vest cut by an arm leave specks
            bpy.context.scene["uo_min_piece"] = max(int(part["min_piece"]), int(bpy.context.scene.get("uo_min_piece", 0)))
        if part.get("no_body_gap"):                      # the renderer does not bend this item around the limbs frame by frame (BODY_GAP: edges jump and tear into spikes where the arm sweeps through a vest); the arm hides what is behind it
            for o in obs:
                o["uo_no_body_gap"] = 1
        if part.get("behind_torso"):                     # a garment that wraps the trunk (vest, belt): the torso hides the half that is behind it in the clothing layer (TORSO_HIDE_MARGIN of render_uo_layer.py), else the client draws the back panel over the chest (through the V of a vest)
            for o in obs:
                o["uo_behind_torso"] = 1
        if part.get("smooth_shade"):                     # smooth normals: a low-poly model shaded flat shows its facets (they stay visible after densifying)
            for o in obs:
                o.data.polygons.foreach_set("use_smooth", [True] * len(o.data.polygons)); o.data.update()
        if part.get("to_bone"):                          # fitted to the skin in the rest pose (pushed out of it), then stiff on one bone of its side: a shoulder cup turns with the upper arm, a sphere round the joint stays round it
            for o in obs:
                wx = sum((o.matrix_world @ v.co).x for v in o.data.vertices) / len(o.data.vertices)
                bl = (rig.matrix_world @ rig.data.bones[part["to_bone"] + ".L"].head_local).x
                bone = part["to_bone"] + ("." + ("L" if abs(bl - wx) < abs(-bl - wx) else "R"))
                for g in list(o.vertex_groups):
                    o.vertex_groups.remove(g)
                o.vertex_groups.new(name=bone).add(list(range(len(o.data.vertices))), 1.0, "REPLACE")
                if o.data.shape_keys:
                    for k in [k for k in o.data.shape_keys.key_blocks if k.name.startswith("uo_")]:
                        o.shape_key_remove(k)
                print("uo_make_item: %%s -> rigid on %%s" %% (o.name, bone))
bpy.ops.wm.save_as_mainfile(filepath=%(out)r)
print("uo_make_item: saved", %(out)r)
''' % dict(here=HERE, base=base, ref=ref, parts=parts, out=out_blend)


def build_stage(recipe, out_blend):
    """python text run inside the .blend: import -> materials -> prepare -> save"""
    if "parts" in recipe:
        return build_parts_stage(recipe, out_blend)
    kind = recipe.get("kind", "")
    imp = dict(FILE=os.path.abspath(recipe["file"]), KIND="" if recipe.get("weapon") else kind, SKIP=list(recipe.get("skip", [])), KEEP=list(recipe.get("keep", [])), DROP_MATERIALS=list(recipe.get("drop_materials", [])), ARMS_DOWN=float(recipe.get("arms_down", 0.0)), ARM_BLEND=float(recipe.get("arm_blend", 0.12)), TURN=int(recipe.get("turn", 0)),
               DECIMATE_TO=int(recipe.get("decimate", 30000)), NAME=recipe.get("name", ""))
    if "scale" in recipe:
        imp["SCALE"] = float(recipe["scale"])
    if "stretch" in recipe:
        imp["STRETCH"] = tuple(float(k) for k in recipe["stretch"])
    return '''
import bpy, os, re, sys
HERE = %(here)r
rig = bpy.data.objects["UO_Rig"]; rig.data.pose_position = "REST"
for o in list(bpy.data.collections["Clothing"].all_objects):
    bpy.data.objects.remove(o, do_unlink=True)
os.environ["UO_SCRIPTS"] = HERE
os.environ["UO_PREPARE_EXTRA"] = %(tune)r
def run(script, **over):
    text = open(os.path.join(HERE, script), encoding="utf-8").read()
    for k, v in over.items():
        text, n = re.subn(r"^%%s\\s*=.*$" %% re.escape(k), "%%s = %%r" %% (k, v), text, count=1, flags=re.M)
        assert n == 1, (script, k)
    exec(compile(text, script, "exec"), {"__name__": "__main__"})
run("uo_import_item.py", **%(imp)r)
run("uo_materials.py", **%(mat)r)
prep = %(prep)r
flat = {k: v for k, v in prep.items() if not isinstance(v, dict)}
wp = %(weapon)r
if wp:                                                           # a weapon: upright, class length, onto the line of its hand bone, rigid on the weapon bone
    run("uo_orient_weapon.py", CLASS=wp["class"], LENGTH=float(wp.get("length") or 0.0), TIP=wp.get("tip", "auto"), FLAT=bool(wp.get("flat", True)))
    run("uo_place_weapon.py", PART=wp["part"], **({"ROLL_DEG": float(wp["roll"])} if "roll" in wp else {}))
    run("uo_bind_item.py", PART=wp["part"])
else:
    run("uo_prepare_item.py", KIND=%(kind)r, **flat)
bpy.ops.wm.save_as_mainfile(filepath=%(out)r)
print("uo_make_item: saved", %(out)r)
''' % dict(here=HERE, imp=imp, mat=recipe.get("materials", {}), prep=recipe.get("prepare", {}), kind=kind, out=out_blend, weapon=recipe.get("weapon"), tune=json.dumps(recipe.get("tune", {})))


def run_blend(base, stage_text, log):
    stage = log + ".stage.py"
    open(stage, "w").write(stage_text)
    r = subprocess.run([sys.executable, os.path.join(HERE, "run_script_in_blend.py"), base, stage], capture_output=True, text=True)
    keep = [l for l in r.stdout.splitlines() if l.startswith(("uo_", "   ", "  WARN", "  AMB", "Traceback")) or "Error" in l]
    open(log, "w").write("\n".join(keep) + "\n")
    if r.returncode or "uo_make_item: saved" not in r.stdout:
        sys.exit("failed:\n%s\n%s" % (r.stdout[-3000:], r.stderr[-2000:]))
    return keep


HINTS = ("mannequin", "dummy", "guy", "human", "body", "skin", "head", "eye", "teeth", "tongue", "base_mesh", "collision", "shadow", "ground", "floor", "stand", "plane")


def list_file(path):
    """meshes of a model file with their size, and which of them look like something other than the item (a mannequin, eyes, a ground plane): candidates for `skip`"""
    import bpy
    import numpy as np
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ext = os.path.splitext(path)[1].lower()
    (bpy.ops.import_scene.gltf if ext in (".glb", ".gltf") else bpy.ops.import_scene.fbx if ext == ".fbx" else bpy.ops.wm.obj_import)(filepath=path)
    rows = []
    for o in bpy.data.objects:
        if o.type == "MESH":
            v = np.array([(o.matrix_world @ x.co)[:] for x in o.data.vertices]); rows.append((o.name, len(v), v.max(0) - v.min(0), v[:, 2].min(), v[:, 2].max()))
    allv = np.array([(max(r[3] for r in rows)), (min(r[4] for r in rows))]) if rows else None
    big = max((r[2].max() for r in rows), default=0)
    print("%-34s %9s  %-24s %-18s %s" % ("mesh", "vertices", "size (file units)", "z range", "hint"))
    for name, n, d, z0, z1 in rows:
        hint = []
        if any(h in name.lower() for h in HINTS):
            hint.append("name looks like a mannequin / helper: skip?")
        if n < 40:
            hint.append("tiny (%d vertices): a detail" % n)
        if n >= 3000 and d[2] > 0.8 * big and d[2] > 1.5 * max(d[0], d[1]) * 0.9 and len(rows) > 1:
            hint.append("whole figure? (as tall as the model): skip?")
        print("%-34s %9d  %6.3f x %6.3f x %6.3f  %.3f .. %.3f  %s" % (name, n, *d, z0, z1, "; ".join(hint)))
    print("total %d meshes, %d vertices. Use  \"skip\": [parts of names]  or  \"keep\": [parts of names]  (\"=name\" = the exact name) in the recipe." % (len(rows), sum(r[1] for r in rows)))
    os._exit(0)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("recipe", nargs="?"); ap.add_argument("--list"); ap.add_argument("--out"); ap.add_argument("--base", default=os.path.join(HERE, "..", "model", "UO_Body_0x190.blend"))
    ap.add_argument("--preview", action="store_true"); ap.add_argument("--vd", action="store_true"); ap.add_argument("--actions", default=""); ap.add_argument("--no-qa", action="store_true", help="skip item_qa.py (penetration / thickness)"); ap.add_argument("--no-sim", action="store_true", help="no cloth simulation of a loose garment (uo_cloth_sim.py)")
    a = ap.parse_args()
    if a.list:
        list_file(os.path.abspath(a.list))
    recipe = json.load(open(a.recipe))
    name = recipe.get("name") or os.path.splitext(os.path.basename(recipe["file"]))[0]
    if "parts" in recipe:
        recipe.setdefault("kind", "")
    out = os.path.abspath(a.out or os.path.join(os.path.dirname(os.path.abspath(a.recipe)), name))
    os.makedirs(out, exist_ok=True)
    t = time.time()
    blend = os.path.join(out, "item.blend")
    for line in run_blend(os.path.abspath(a.base), build_stage(recipe, blend), os.path.join(out, "report.txt")):
        if line.startswith(("uo_autofit", "uo_fit", "uo_import", "  WARN", "  AMB")):
            print(line[:260])
    print("prepared in %.0f s -> %s" % (time.time() - t, blend))
    sim = recipe.get("sim", recipe.get("kind") in ("robe", "skirt")) and not recipe.get("weapon")      # loose garments: cloth simulation on top of the leg push (uo_cloth_sim.py), on by default
    if sim and a.no_sim is False:
        t = time.time(); cfg = ["%s=%s" % kv for kv in (recipe["sim"].items() if isinstance(recipe.get("sim"), dict) else [])]
        acts = [x for x in (a.actions or PREVIEW_ACTIONS).split(",")] if a.preview and not a.vd else None
        cmd = [sys.executable, os.path.join(HERE, "uo_cloth_sim.py"), blend, "--jobs", "4", "--out", os.path.join(out, "cloth_sim.npz")] + (["--actions", ",".join(acts)] if acts else []) + cfg
        r = subprocess.run(cmd, capture_output=True, text=True)
        line = next((l for l in r.stdout.splitlines() if l.startswith("wrote")), "uo_cloth_sim failed: " + (r.stderr or r.stdout)[-400:])
        print("cloth simulation: %s (%.0f s)" % (line, time.time() - t)); open(os.path.join(out, "report.txt"), "a").write(line + "\n")
    if not a.no_qa:                                          # penetration and thickness of the posed item in the main actions (a few seconds, item_qa.py)
        q = subprocess.run([sys.executable, os.path.join(HERE, "item_qa.py"), blend, "--step", "3", "--json", os.path.join(out, "qa.json")], capture_output=True, text=True)
        line = next((l for l in q.stdout.splitlines() if l.startswith("ITEM_QA")), "item_qa failed: " + (q.stderr or q.stdout)[-300:])
        print(line); open(os.path.join(out, "report.txt"), "a").write(line + "\n")
    if a.preview or a.vd:
        render = os.path.join(out, "render")
        layer = "clothing" if a.vd else "all"
        wpart = (recipe.get("weapon") or {}).get("part")
        acts = [x for x in (a.actions or WEAPON_ACTIONS.get(wpart, PREVIEW_ACTIONS)).split(",")] if not a.vd else []
        cmd = [sys.executable, os.path.join(HERE, "run_render_headless.py"), blend, render, 'LAYER="all"' if a.preview else 'LAYER="clothing"',
               "ONLY=%r" % (acts,), "CANVAS=(256,256)", "ANCHOR=(128,192)"]
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        if a.preview:
            import item_sheet
            im = item_sheet.sheet(render, "all", acts, [0, 2, 4], [0, 0.33, 0.66], 3)
            im.save(os.path.join(out, "preview.png")); print("preview:", os.path.join(out, "preview.png"))
        if a.vd:
            print("vd:", os.path.join(render, "clothing.vd"))
