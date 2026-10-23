"""A free cape / cloak model -> a UO cloak that hangs from its two clasps, as a cloth with weight: one command.

    python uo_make_cape.py RECIPE.json [--out DIR] [--base ../model/UO_Body_0x190.blend] [--no-sim] [--jobs 4] [--preview] [--vd] [--actions 04_stand,00_walk_unarmed,...] [--all]

RECIPE.json (only "file" is required):
  {"name": "cape", "file": "models/cape.glb",
   "outer": [0, -1, 0],        # the side of the clasps and the folds that run down from them, in the file's axes: it goes OUT (on the back); the middle of the cape lies on the back
   "up_edge": 0.015,           # m (file units): spacing of the cloth sheet that is rebuilt from the model (uo_cape_sheet.py EDGE; 0.015 -> ~9 mm on the body, ~9.5k vertices)
   "sheet": {...},             # more settings of uo_cape_sheet.py (SMOOTH, MAX_JUMP, BAKE, NORMAL)
   "place": {"SCALE": 0.586, "TILT": 5.0, "CLASP": [0.17, 0.10, 1.53], "CLEAR": 0.008},   # uo_cape_place.py: size (the clasps of the file are 0.58 m apart, on the body 0.34 m), the lean of the
                               # cape (the top towards the front, the hem back: it hangs a little away from the back), where the clasps sit (x, y back = +, z), the clearance of the rest pose
   "materials": {...},         # uo_materials.py settings
   "sim": {"density": 0.7, ...},   # uo_cape_sim.py settings (true / absent = the defaults, false = no simulation: the cape is just bound like a cloak)
   "scene": {"uo_outline": 0.6}}   # per-item settings of render_uo_layer.py (README section 4)

Steps (each one of the scripts that are also in the .blend): uo_import_item.py (the model as it is) -> uo_cape_sheet.py (one regular cloth sheet from it, the folds kept, colour baked)
-> uo_materials.py (UO look) -> uo_cape_place.py (turn, scale, lean, clear of the body, the two clasps marked) -> uo_bind_item.py (PART "cloak": skin weights; the custom property
uo_cloth of type "cape") -> uo_cape_sim.py (cloth_sim.npz) -> render_uo_layer.py (preview / .vd).
Result: DIR/item.blend, DIR/report.txt, DIR/cloth_sim.npz, with --preview DIR/preview.png, with --vd DIR/render/clothing.vd.
"""
import argparse, json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import uo_make_item as mk                                                    # noqa: E402  (run_blend: the stage runs inside the .blend with the bpy module)

PREVIEW_ACTIONS = "04_stand,00_walk_unarmed,02_run_unarmed,24_mounted_run,09_attack_1h_slash"


def stage(recipe, out_blend):
    sheet = dict(recipe.get("sheet", {}))
    if "up_edge" in recipe:
        sheet["EDGE"] = float(recipe["up_edge"])
    sheet["DIR"] = tuple(float(x) for x in recipe.get("outer", (0, -1, 0)))
    place = {k: (tuple(v) if isinstance(v, list) else v) for k, v in recipe.get("place", {}).items()}
    scene = dict(mk.scene_of(recipe))
    return '''
import bpy, os, re, sys, json
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
run("uo_import_item.py", FILE=%(file)r, KIND="", NAME="Cape", DECIMATE_TO=0)
run("uo_cape_sheet.py", **%(sheet)r)
run("uo_materials.py", **%(mat)r)
run("uo_cape_place.py", **%(place)r)
run("uo_bind_item.py", PART="cloak")
ob = bpy.data.objects["Cape"]
ob["uo_cloth"] = json.dumps({"type": "cape"})                                   # render_uo_layer.cloth_push: the displacement comes from cloth_sim.npz (uo_cape_sim.py)
ob["uo_behind_torso"] = 1                                                        # the chest hides what hangs behind it (the part of the cape >= TORSO_HIDE_MARGIN behind the torso, seen from the front)
for k, v in %(scene)r.items():
    bpy.context.scene[k] = v
    print("uo_make_cape: scene property %%s = %%r" %% (k, v))
bpy.ops.wm.save_as_mainfile(filepath=%(out)r)
print("uo_make_item: saved", %(out)r)
''' % dict(here=HERE, file=os.path.abspath(recipe["file"]), sheet=sheet, mat=recipe.get("materials", {}), place=place, scene=scene, out=out_blend)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("recipe"); ap.add_argument("--out"); ap.add_argument("--base", default=os.path.join(HERE, "..", "model", "UO_Body_0x190.blend"))
    ap.add_argument("--no-sim", action="store_true"); ap.add_argument("--jobs", type=int, default=4); ap.add_argument("--preview", action="store_true"); ap.add_argument("--vd", action="store_true")
    ap.add_argument("--actions", default=""); ap.add_argument("--all", action="store_true", help="simulate and render all 35 actions (with --vd: the whole clothing.vd, ~1 h)"); ap.add_argument("--skip-prepare", action="store_true", help="reuse DIR/item.blend (only simulate / render)")
    a = ap.parse_args()
    recipe = json.load(open(a.recipe))
    name = recipe.get("name") or os.path.splitext(os.path.basename(recipe["file"]))[0]
    out = os.path.abspath(a.out or os.path.join(os.path.dirname(os.path.abspath(a.recipe)), name)); os.makedirs(out, exist_ok=True)
    blend = os.path.join(out, "item.blend"); t = time.time()
    if not a.skip_prepare:
        for line in mk.run_blend(os.path.abspath(a.base), stage(recipe, blend), os.path.join(out, "report.txt")):
            if line.startswith(("uo_cape", "uo_import_item", "  WARN")):
                print(line[:260])
        print("prepared in %.0f s -> %s" % (time.time() - t, blend))
    acts = [x for x in (a.actions or PREVIEW_ACTIONS).split(",") if x]
    sim = recipe.get("sim", True) is not False and not a.no_sim
    if sim:
        t = time.time(); cfg = ["%s=%s" % kv for kv in (recipe["sim"].items() if isinstance(recipe.get("sim"), dict) else [])]
        cmd = [sys.executable, os.path.join(HERE, "uo_cape_sim.py"), blend, "--jobs", str(a.jobs), "--out", os.path.join(out, "cloth_sim.npz")] + (["--actions", ",".join(acts)] if not a.all else []) + cfg
        r = subprocess.run(cmd, capture_output=True, text=True)
        open(os.path.join(out, "report.txt"), "a").write(r.stdout)
        line = next((l for l in r.stdout.splitlines() if l.startswith("wrote")), "uo_cape_sim failed: " + (r.stderr or r.stdout)[-1500:])
        for l in r.stdout.splitlines():
            if l.startswith(("action", "uo_cape_sim")):
                print(l[:200])
        print("cape simulation: %s (%.0f s)" % (line, time.time() - t))
        if not line.startswith("wrote"):
            sys.exit(1)
    if a.preview or a.vd:
        render = os.path.join(out, "render"); layer = "clothing" if a.vd else "all"
        cmd = [sys.executable, os.path.join(HERE, "run_render_headless.py"), blend, render, 'LAYER="all"' if a.preview and not a.vd else 'LAYER="clothing"',
               "ONLY=%r" % ([] if a.all else acts,), "CANVAS=(256,256)", "ANCHOR=(128,192)"]
        t = time.time(); r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode:
            sys.exit("render failed:\n%s\n%s" % (r.stdout[-2000:], r.stderr[-2000:]))
        print("rendered in %.0f s -> %s" % (time.time() - t, render))
        if a.preview:
            import item_sheet
            im = item_sheet.sheet(render, "all" if not a.vd else "clothing", acts, [0, 2, 4], [0, 0.33, 0.66], 3)
            im.save(os.path.join(out, "preview.png")); print("preview:", os.path.join(out, "preview.png"))
        if a.vd:
            print("vd:", os.path.join(render, "clothing.vd"))
