"""Test of uo_import_item.py with a stand-in for a foreign model: a body-hugging replica of a UO item (test_items.py) is made "foreign" (other size,
other place, Y-up glTF with the skeleton and weights of the UO rig still inside), saved as .glb, imported into a fresh UO_Body_0x190.blend by
uo_import_item.py, then fitted, bound and rendered; the result is compared with the sprite of the original item (test_real_item.py).

    python test_import_item.py [--item shirt] [--scale 1.15] [--offset 0.12,0.05,-0.20] [--turn 0] [--tmp DIR]
"""
import argparse, json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
STAGE_A = r'''
import bpy, os, json, numpy as np
exec(open(os.path.join(os.environ["UO_TEST_SCRIPTS"], "test_items_pre.py")).read(), {"__name__": "__pre__", "bpy": bpy})
item = bpy.context.view_layer.objects.active
rig = bpy.data.objects["UO_Rig"]; rig.data.pose_position = "REST"
s, off = float(os.environ["FOREIGN_SCALE"]), [float(x) for x in os.environ["FOREIGN_OFFSET"].split(",")]
bpy.context.view_layer.update()
for o in list(bpy.data.objects):                      # only the item and the rig go into the file
    if o not in (item, rig):
        bpy.data.objects.remove(o, do_unlink=True)
ref = np.array([item.matrix_world @ v.co for v in item.data.vertices])
np.save(os.environ["FOREIGN_REF"], ref)
item.scale = (s, s, s); item.location = (np.array(item.location) * s + off)
bpy.context.view_layer.update()
bpy.ops.object.select_all(action="SELECT")
bpy.ops.export_scene.gltf(filepath=os.environ["FOREIGN_GLB"], use_selection=True, export_apply=False, export_skins=True)
print("stage A: foreign glb written")
'''
STAGE_B = r'''
import bpy, os, sys, re, numpy as np
bpy.context.view_layer.objects.active = None
rig = bpy.data.objects["UO_Rig"]; rig.data.pose_position = "REST"
for o in [o for o in bpy.data.collections["Clothing"].all_objects]:
    bpy.data.objects.remove(o, do_unlink=True)
def run(script, **over):
    text = open(os.path.join(os.environ["UO_TEST_SCRIPTS"], script)).read()
    for k, v in over.items():
        text, n = re.subn(r"^%s\s*=.*$" % k, "%s = %r" % (k, v), text, count=1, flags=re.M)
        assert n == 1, (script, k)
    exec(compile(text, script, "exec"), {"__name__": "__main__"})
MODE = os.environ.get("FOREIGN_MODE", "height")
if MODE == "wrap":                                     # units / place / size from the skin (uo_autofit_item.py), not from one height per KIND
    run("uo_import_item.py", FILE=os.environ["FOREIGN_GLB"], KIND="", TURN=int(os.environ["FOREIGN_TURN"]))
    run("uo_autofit_item.py", KIND=os.environ["FOREIGN_KIND"])
else:
    run("uo_import_item.py", FILE=os.environ["FOREIGN_GLB"], KIND=os.environ["FOREIGN_KIND"], TURN=int(os.environ["FOREIGN_TURN"]), PLACE="height")
item = bpy.context.view_layer.objects.active
got = np.array([item.matrix_world @ v.co for v in item.data.vertices]); ref = np.load(os.environ["FOREIGN_REF"])
print("RESULT bbox ref  min", ref.min(0).round(3), "max", ref.max(0).round(3))
from scipy.spatial import cKDTree
_e = cKDTree(got).query(ref)[0] * 1000
print("RESULT nearest-vertex error mm (ref -> got): mean %.1f  p95 %.1f  max %.1f | height ratio %.3f  width ratio %.3f" % (_e.mean(), np.percentile(_e, 95), _e.max(), np.ptp(got[:, 2]) / max(np.ptp(ref[:, 2]), 1e-9), np.ptp(got[:, 0]) / max(np.ptp(ref[:, 0]), 1e-9)))
if len(ref) == len(got):
    e = np.linalg.norm(got - ref, axis=1) * 1000
    print("RESULT vertex error mm: mean %.1f  p95 %.1f  max %.1f  | scale ratio %.3f" % (e.mean(), np.percentile(e, 95), e.max(), np.ptp(got[:, 2]) / max(np.ptp(ref[:, 2]), 1e-9)))
print("RESULT bbox got  min", got.min(0).round(3), "max", got.max(0).round(3))
run("uo_materials.py")
run("uo_fit_item.py")
run("uo_bind_item.py", PART=os.environ["FOREIGN_PART"])
bpy.ops.wm.save_as_mainfile(filepath=os.environ["FOREIGN_OUT"])
'''
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--item", default="shirt"); ap.add_argument("--scale", default="1.15"); ap.add_argument("--offset", default="0.12,0.05,-0.20")
    ap.add_argument("--turn", default="0"); ap.add_argument("--skip", default="icosphere"); ap.add_argument("--tmp"); ap.add_argument("--render", action="store_true")
    ap.add_argument("--mode", default="height", choices=["height", "wrap"]); ap.add_argument("--zrange", help="lo,hi: cut the replica to this height range (a short item)")
    a = ap.parse_args()
    tmp = os.path.abspath(a.tmp) if a.tmp else tempfile.mkdtemp(prefix="test_import_")
    os.makedirs(tmp, exist_ok=True)
    sys.path.insert(0, HERE)
    import test_items as ti
    if a.zrange:
        ti.ITEMS[a.item] = dict(ti.ITEMS[a.item], zrange=[float(x) for x in a.zrange.split(",")])
    spec = os.path.join(tmp, "spec.json"); json.dump(ti.ITEMS, open(spec, "w"))
    blend = os.path.abspath(os.path.join(HERE, "..", "model", "UO_Body_0x190.blend"))
    sa, sb = os.path.join(tmp, "stage_a.py"), os.path.join(tmp, "stage_b.py")
    open(sa, "w").write(STAGE_A); open(sb, "w").write(STAGE_B)
    kind = a.item
    env = dict(os.environ, UO_TEST_SPEC=spec, UO_TEST_ITEM=a.item, UO_TEST_FIT="0", UO_TEST_SCRIPTS=HERE, FOREIGN_SCALE=a.scale, FOREIGN_OFFSET=a.offset,
               FOREIGN_REF=os.path.join(tmp, "ref.npy"), FOREIGN_GLB=os.path.join(tmp, "foreign.glb"), FOREIGN_KIND=kind, FOREIGN_TURN=a.turn,
               FOREIGN_PART=ti.ITEMS[a.item]["part"], UO_IMPORT_SKIP=a.skip, FOREIGN_OUT=os.path.join(tmp, "imported.blend"), FOREIGN_MODE=a.mode)
    for stage in (sa, sb):
        r = subprocess.run([sys.executable, os.path.join(HERE, "run_script_in_blend.py"), blend, stage], capture_output=True, text=True, env=env)
        print("\n".join(l for l in r.stdout.splitlines() if l.startswith(("RESULT", "  AMBIG", "uo_autofit_item", "uo_import_item", "uo_materials", "uo_fit", "uo_bind", "stage", "   "))))
        if r.returncode:
            sys.exit("%s failed:\n%s\n%s" % (stage, r.stdout[-2500:], r.stderr[-2500:]))
    if a.render:
        r = subprocess.run([sys.executable, os.path.join(HERE, "test_real_item.py"), "--blend", env["FOREIGN_OUT"], "--anim", str(ti.ITEMS[a.item]["anim"]),
                            "--tmp", os.path.join(tmp, "render"), "--img", os.path.join(tmp, "overlay.png")], capture_output=True, text=True)
        print(r.stdout[-800:], r.stderr[-800:] if r.returncode else "")
    print("output in", tmp)
