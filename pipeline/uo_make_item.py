"""A free 3D model -> a UO item, in one command (no Blender window).

    python uo_make_item.py RECIPE.json [--out DIR] [--base ../model/UO_Body_0x190.blend] [--preview] [--vd] [--actions 04_stand,...]
    python uo_make_item.py --list MODEL.glb          # what is in the file: meshes, vertices, size (to choose `skip` / `keep`)

RECIPE.json (only "file" and "kind" are required):
  {"name": "gambeson", "file": "models/medieval_shirt.glb", "kind": "shirt",
   "skip": ["guy"],            # meshes of the file to leave out (parts of names)      "keep": ["Blade"]  only these
   "drop_materials": ["Belt", "Buckle"],   # materials whose faces are cut out (a belt that is one mesh with the robe)
   "arms_down": 0,                  # deg; 80-90 for a model in a T-pose (arms out): the sleeves are turned down about the shoulders ("arm_materials": ["sleeve"] names them, "arm_blend": 0.12 m is the width over which the turn fades into the body)
   "turn": 0,                  # 180 when the model came in back to front (the fit also tries it)
   "decimate": 30000,          # vertices above which the model is reduced
   "materials": {"SATURATION": 1.0, "METAL": null},   # uo_materials.py settings (grey item that takes a dye: SATURATION 0)
   "prepare": {"DENSIFY": false},                      # settings of uo_prepare_item.py itself
   "tune": {"uo_fit_item.py": {"MIN_GAP": 0.02, "LIMIT": 0.05}, "uo_autofit_item.py": {"GAP": 0.02}},   # settings of the steps it runs (autofit, densify, fit, bind)
   "sim": true,                     # loose garments (kind robe / skirt): cloth simulation on top of the leg push (uo_cloth_sim.py; on by default, false = off, {"goal": 0.3, ...} = its settings)
   "weapon": {"class": "sword", "part": "weapon1h", "length": null, "tip": "auto"}}   # a weapon instead of "kind": class (sword, dagger, mace, axe, polearm, staff, spear,
                               # bow, crossbow, gun), part (weapon1h, polearm, axe2h, bow: which hand bone and motion), length m (null = of the class), tip ("auto", "heavy", "+y" ...)

A model of several items (straps + a sword on the back; the file has the model's mannequin): "reference": {"keep": ["mannequin mesh"], "kind": "shirt"} is fitted to the body and its
transform goes to every part of "parts": [{"name": "straps", "keep": [...], "kind": "harness"}, {"name": "sword", "keep": [...], "rigid": "quiver"}] (rigid = stiff on a bone; its
uo_behind_torso / uo_no_body_gap properties are set: the chest hides what hangs behind it, the item is not bent away from limbs; "move": [x, y, z] m nudges a part).

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
from mathutils import Matrix
HERE = %(here)r
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
run("uo_autofit_item.py", KIND=ref["kind"])
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
    run("uo_materials.py", **part.get("materials", {}))
    off = part.get("move", [0, 0, 0])
    if any(off):
        for o in obs:
            o.data.transform(Matrix.Translation(off))
    select(obs)
    if part.get("rigid"):
        run("uo_bind_item.py", PART=part["rigid"])
        for o in obs:
            for k in ("uo_no_body_gap", "uo_behind_torso"):
                if part.get(k, True):
                    o[k] = 1
    else:
        run("uo_prepare_item.py", KIND=part["kind"], AUTOFIT=False, **part.get("prepare", {}))
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
