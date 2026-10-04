"""A free 3D model -> a UO item, in one command (no Blender window).

    python uo_make_item.py RECIPE.json [--out DIR] [--base ../model/UO_Body_0x190.blend] [--preview] [--vd] [--actions 04_stand,...]
    python uo_make_item.py --list MODEL.glb          # what is in the file: meshes, vertices, size (to choose `skip` / `keep`)

RECIPE.json (only "file" and "kind" are required):
  {"name": "gambeson", "file": "models/medieval_shirt.glb", "kind": "shirt",
   "skip": ["guy"],            # meshes of the file to leave out (parts of names)      "keep": ["Blade"]  only these
   "turn": 0,                  # 180 when the model came in back to front (the fit also tries it)
   "decimate": 30000,          # vertices above which the model is reduced
   "materials": {"SATURATION": 1.0, "METAL": null},   # uo_materials.py settings (grey item that takes a dye: SATURATION 0)
   "prepare": {"MAX_GAP": 0.0},                       # settings of any script run by uo_prepare_item.py: {"script.py": {"NAME": value}} or flat for uo_prepare_item.py
   "kind_part": null}          # PART of uo_bind_item.py instead of the one of the kind

Steps (each is one of the scripts that are also in the .blend, see README): uo_import_item.py (clean, join, reduce) -> uo_materials.py (UO look) ->
uo_prepare_item.py (uo_autofit_item.py size / place from the skin, uo_densify_item.py, uo_fit_item.py push out of the skin, uo_bind_item.py skin weights).
Result: DIR/item.blend (the base .blend with the item in the collection Clothing), DIR/report.txt (what each step printed), with --preview DIR/preview.png (a few
actions: stand, walk, run, attack, spell, die; 3 directions, 3 moments), with --vd DIR/clothing.vd (all 35 actions, 15-30 minutes).
"""
import argparse, json, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
PREVIEW_ACTIONS = "04_stand,00_walk_unarmed,02_run_unarmed,09_attack_1h_slash,16_spell_directed,21_die_forward"


def source(name):
    return open(os.path.join(HERE, name), encoding="utf-8").read()


def override(text, **over):
    for k, v in over.items():
        text, n = re.subn(r"^%s\s*=.*$" % re.escape(k), "%s = %r" % (k, v), text, count=1, flags=re.M)
        if n != 1:
            raise SystemExit("setting %s not found" % k)
    return text


def build_stage(recipe, out_blend):
    """python text run inside the .blend: import -> materials -> prepare -> save"""
    kind = recipe["kind"]
    imp = dict(FILE=os.path.abspath(recipe["file"]), KIND=kind, SKIP=list(recipe.get("skip", [])), KEEP=list(recipe.get("keep", [])), TURN=int(recipe.get("turn", 0)),
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
run("uo_prepare_item.py", KIND=%(kind)r, **flat)
bpy.ops.wm.save_as_mainfile(filepath=%(out)r)
print("uo_make_item: saved", %(out)r)
''' % dict(here=HERE, imp=imp, mat=recipe.get("materials", {}), prep=recipe.get("prepare", {}), kind=kind, out=out_blend)


def run_blend(base, stage_text, log):
    stage = log + ".stage.py"
    open(stage, "w").write(stage_text)
    r = subprocess.run([sys.executable, os.path.join(HERE, "run_script_in_blend.py"), base, stage], capture_output=True, text=True)
    keep = [l for l in r.stdout.splitlines() if l.startswith(("uo_", "   ", "  WARN", "  AMB", "Traceback")) or "Error" in l]
    open(log, "w").write("\n".join(keep) + "\n")
    if r.returncode or "uo_make_item: saved" not in r.stdout:
        sys.exit("failed:\n%s\n%s" % (r.stdout[-3000:], r.stderr[-2000:]))
    return keep


def list_file(path):
    import bpy
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ext = os.path.splitext(path)[1].lower()
    (bpy.ops.import_scene.gltf if ext in (".glb", ".gltf") else bpy.ops.import_scene.fbx if ext == ".fbx" else bpy.ops.wm.obj_import)(filepath=path)
    import numpy as np
    print("%-34s %9s  %-22s %s" % ("mesh", "vertices", "size (world, file units)", "world z range"))
    for o in bpy.data.objects:
        if o.type == "MESH":
            v = np.array([(o.matrix_world @ x.co)[:] for x in o.data.vertices]); d = v.max(0) - v.min(0)
            print("%-34s %9d  %6.3f x %6.3f x %6.3f  %.3f .. %.3f" % (o.name, len(v), *d, v[:, 2].min(), v[:, 2].max()))
    os._exit(0)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("recipe", nargs="?"); ap.add_argument("--list"); ap.add_argument("--out"); ap.add_argument("--base", default=os.path.join(HERE, "..", "model", "UO_Body_0x190.blend"))
    ap.add_argument("--preview", action="store_true"); ap.add_argument("--vd", action="store_true"); ap.add_argument("--actions", default=PREVIEW_ACTIONS)
    a = ap.parse_args()
    if a.list:
        list_file(os.path.abspath(a.list))
    recipe = json.load(open(a.recipe))
    name = recipe.get("name") or os.path.splitext(os.path.basename(recipe["file"]))[0]
    out = os.path.abspath(a.out or os.path.join(os.path.dirname(os.path.abspath(a.recipe)), name))
    os.makedirs(out, exist_ok=True)
    t = time.time()
    blend = os.path.join(out, "item.blend")
    for line in run_blend(os.path.abspath(a.base), build_stage(recipe, blend), os.path.join(out, "report.txt")):
        if line.startswith(("uo_autofit", "uo_fit", "uo_import", "  WARN", "  AMB")):
            print(line[:260])
    print("prepared in %.0f s -> %s" % (time.time() - t, blend))
    if a.preview or a.vd:
        render = os.path.join(out, "render")
        layer = "clothing" if a.vd else "all"
        acts = [x for x in a.actions.split(",")] if not a.vd else []
        cmd = [sys.executable, os.path.join(HERE, "run_render_headless.py"), blend, render, 'LAYER="all"' if a.preview else 'LAYER="clothing"',
               "ONLY=%r" % (acts,), "CANVAS=(256,256)", "ANCHOR=(128,192)"]
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        if a.preview:
            import item_sheet
            im = item_sheet.sheet(render, "all", acts, [0, 2, 4], [0, 0.33, 0.66], 3)
            im.save(os.path.join(out, "preview.png")); print("preview:", os.path.join(out, "preview.png"))
        if a.vd:
            print("vd:", os.path.join(render, "clothing.vd"))
