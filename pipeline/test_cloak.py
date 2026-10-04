"""Cloak: does a cape bound with PART cloak swing like the original cloak 468 (cloak_pitch.json)?

    python test_cloak.py [--actions ...] [--set CLOAK_SWING=0.0] [--tmp DIR] [--out qa.json] [--img overlay.png]

A replica cape (cloak_fit_frames.bent_cape: a wide partial tube behind the body from the shoulders to the shins, in the stand shape of the original: 20 deg at the shoulders)
is bound with `uo_bind_item.py` PART cloak, rendered with the whole pipeline and compared with the sprite 468 frame by frame (IoU of the whole silhouette per action).
`--set CLOAK_SWING=0.0` renders the cape hanging as bound (no swing) for the comparison.
"""
import argparse, json, os, subprocess, sys, tempfile
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "..", "vdtool"))
import vdtool                                                                # noqa: E402
import test_robe as tr                                                       # noqa: E402

DEFAULT_ACTIONS = "04_stand,00_walk_unarmed,02_run_unarmed,09_attack_1h_slash,16_spell_directed,21_die_forward,24_mounted_run"
PRE = r'''
import bpy, os, json, numpy as np, bmesh
scripts = os.environ["UO_TEST_SCRIPTS"]; env = os.environ
d = np.load(env["CLOAK_NPZ"]); V, T = d["V"], d["T"]
body = bpy.data.objects["UO_Body"]
bm = bmesh.new()
vs = [bm.verts.new(tuple(p)) for p in V]
for t in T:
    bm.faces.new([vs[k] for k in t])
me = bpy.data.meshes.new("cloak_replica"); bm.to_mesh(me); bm.free()
item = bpy.data.objects.new("cloak_replica", me); item.matrix_world = body.matrix_world.copy()
clo = bpy.data.collections["Clothing"]
for o in list(clo.all_objects):
    bpy.data.objects.remove(o, do_unlink=True)
clo.objects.link(item)
shirt = bpy.data.objects.get("Example_Shirt")
if shirt is not None:
    me.materials.append(shirt.active_material)
bpy.context.view_layer.update()
for o in bpy.context.view_layer.objects:
    o.select_set(False)
item.select_set(True); bpy.context.view_layer.objects.active = item
import re
text = open(os.path.join(scripts, "uo_bind_item.py")).read()
text = re.sub(r"^PART = .*$", "PART = 'cloak'", text, count=1, flags=re.M)
exec(compile(text, "uo_bind_item.py", "exec"), {"__name__": "__main__"})
'''


def run(a, tmp):
    import cloak_fit_frames as cf
    os.makedirs(tmp, exist_ok=True)
    p = dict(cf.REST); p["n_around"], p["n_rings"] = 36, 30
    V, T = cf.bent_cape(p, np.radians(20.0), 0.0)
    np.savez(os.path.join(tmp, "cape.npz"), V=V, T=T)
    pre = os.path.join(tmp, "pre.py"); open(pre, "w").write("exec(%r)\n" % PRE)
    blend = os.path.abspath(os.path.join(HERE, "..", "model", "UO_Body_0x190.blend"))
    env = dict(os.environ, UO_TEST_SCRIPTS=HERE, CLOAK_NPZ=os.path.join(tmp, "cape.npz"))
    cmd = [sys.executable, os.path.join(HERE, "run_render_headless.py"), blend, tmp, "--pre", pre, 'LAYER="clothing"', "ONLY=%r" % (a.actions.split(","),),
           "CANVAS=(256, 256)", "ANCHOR=(128, 192)"] + a.set
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if r.returncode:
        sys.exit("render failed:\n%s\n%s" % (r.stdout[-2500:], r.stderr[-2500:]))
    _, blocks = vdtool.read_vd(a.sprite)
    sprites = {(b["action"], b["dir"]): b for b in blocks}
    show = {("04_stand", 2, 0), ("02_run_unarmed", 2, 3), ("02_run_unarmed", 1, 3), ("09_attack_1h_slash", 3, 2), ("16_spell_directed", 2, 3)}
    rows, imgs = tr.measure(os.path.join(tmp, "clothing", "frames"), sprites, (256, 256), (128, 192), 0.0, show)
    s = tr.summarize(rows)
    for k in s["by_action"]:
        s["by_action"][k]["iou_all"] = float(np.mean([r["iou_all"] for r in rows if r["a"] == int(k)]))
    return s, imgs


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sprite", default=os.path.join(HERE, "body13", "mul", "anim_0468.vd")); ap.add_argument("--actions", default=DEFAULT_ACTIONS)
    ap.add_argument("--tmp"); ap.add_argument("--out"); ap.add_argument("--img"); ap.add_argument("--set", action="append", default=[])
    a = ap.parse_args()
    tmp = os.path.abspath(a.tmp) if a.tmp else tempfile.mkdtemp(prefix="test_cloak_")
    s, imgs = run(a, tmp)
    print("frames %d | IoU %.3f | %s" % (s["frames"], s["iou_all"], " ".join("%s:%.2f" % (k, v["iou_all"]) for k, v in s["by_action"].items())))
    if a.out:
        json.dump(dict(args=vars(a), result=s), open(a.out, "w"), indent=1)
    if a.img and imgs:
        im = np.concatenate([np.pad(i[60:200, 60:200], ((1, 1), (1, 1), (0, 0)), constant_values=90) for i in imgs], 1)
        Image.fromarray(im).resize((im.shape[1] * 2, im.shape[0] * 2), Image.NEAREST).save(a.img)
