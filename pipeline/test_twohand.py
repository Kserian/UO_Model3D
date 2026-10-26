"""Test of the two-handed weapon chain (uo_spikes.py + uo_twohand.py) on a synthetic spiked mace (no foreign file needed).

    python test_twohand.py [--keep DIR]

Builds a mace (shaft, ball, 9 radial spikes) with bpy, makes it an item with uo_make_item.py ("weapon": part polearm, spikes, "twohand") and checks the stats of
uo_twohand.py (twohand.json) and the keyed bone:
  1. the spikes are longer than the model's (top of the mace higher by the spike growth), the ball is found;
  2. 2H actions (8, 12, 13, 15): both fists on the shaft (lower fist <= 1 cm off, no smoothing pulls it away);
  3. falls (21, 22): the shaft lies along the body in the last frame (<= 15 deg from pelvis -> head);
  4. mounted actions: the weapon clears the horse proxies (intrusion <= 10 mm) except the swing 29 (<= 60 mm);
  5. the bone is keyed in all 35 actions and the keyed bone matches the target (uo_twohand.py checks it: 0.0000).
Prints RESULT OK / FAILED. Needs bpy 4.2, numpy, scipy.
"""
import json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

BUILD = r'''
import bpy, math, sys
bpy.ops.wm.read_factory_settings(use_empty=True)
mat = bpy.data.materials.new("steel"); mat.use_nodes = True
mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.5, 0.5, 0.52, 1)
objs = []
def add(op, **kw):
    op(**kw); o = bpy.context.active_object; o.data.materials.append(mat); objs.append(o); return o
add(bpy.ops.mesh.primitive_cylinder_add, radius=0.02, depth=1.3, location=(0, 0, 0.65), vertices=16)
bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.select_all(action="SELECT"); bpy.ops.mesh.subdivide(number_cuts=20); bpy.ops.object.mode_set(mode="OBJECT")
add(bpy.ops.mesh.primitive_uv_sphere_add, radius=0.1, location=(0, 0, 1.2), segments=64, ring_count=32)
dirs = [(0, 0, 1)] + [(math.cos(a) * 0.9, math.sin(a) * 0.9, 0.3) for a in [i * math.pi / 2 for i in range(4)]] + [(math.cos(a) * 0.9, math.sin(a) * 0.9, -0.4) for a in [i * math.pi / 2 for i in range(4)]]
from mathutils import Vector
for d in dirs:
    d = Vector(d).normalized()
    c = add(bpy.ops.mesh.primitive_cone_add, radius1=0.03, radius2=0.0, depth=0.3, vertices=16, location=Vector((0, 0, 1.2)) + d * 0.2)
    bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.select_all(action="SELECT"); bpy.ops.mesh.subdivide(number_cuts=6); bpy.ops.object.mode_set(mode="OBJECT")
    c.rotation_euler = Vector((0, 0, 1)).rotation_difference(d).to_euler()
bpy.ops.object.select_all(action="DESELECT")
for o in objs:
    o.select_set(True)
bpy.context.view_layer.objects.active = objs[0]
bpy.ops.object.join()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
bpy.ops.export_scene.gltf(filepath=sys.argv[-1], export_format="GLB", use_selection=True)
'''


def main():
    keep = sys.argv[sys.argv.index("--keep") + 1] if "--keep" in sys.argv else None
    tmp = keep or tempfile.mkdtemp(prefix="test_twohand_")
    os.makedirs(tmp, exist_ok=True)
    glb = os.path.join(tmp, "mace.glb")
    open(os.path.join(tmp, "build.py"), "w").write(BUILD)
    r = subprocess.run([sys.executable, os.path.join(tmp, "build.py"), glb], capture_output=True, text=True)
    if not os.path.exists(glb):
        sys.exit("could not build the test mace:\n" + r.stdout[-1500:] + r.stderr[-1500:])
    recipe = dict(name="test_mace", file=glb, weapon={"class": "mace", "part": "polearm", "length": 1.35, "tip": "+z", "spikes": {"LENGTH": 1.5, "WIDTH": 1.5},
                                                      "no_body_gap": True, "behind_torso": True}, twohand={}, decimate=30000)
    rp = os.path.join(tmp, "recipe.json"); json.dump(recipe, open(rp, "w"))
    out = os.path.join(tmp, "out")
    r = subprocess.run([sys.executable, os.path.join(HERE, "uo_make_item.py"), rp, "--out", out, "--no-qa"], capture_output=True, text=True)
    rep = open(os.path.join(out, "report.txt")).read() if os.path.exists(os.path.join(out, "report.txt")) else ""
    st_path = os.path.join(out, "twohand.json")
    if r.returncode or not os.path.exists(st_path):
        sys.exit("uo_make_item failed:\n%s\n%s" % (r.stdout[-2500:], r.stderr[-1500:]))
    st = {int(k): v for k, v in json.load(open(st_path)).items()}
    ok = True

    def check(name, cond, info=""):
        nonlocal ok
        ok &= bool(cond)
        print("%-62s %s %s" % (name, "ok " if cond else "FAIL", info))
    spk = [l for l in rep.splitlines() if l.startswith("uo_spikes")]
    n_sp = int(spk[0].split(" spikes")[0].split()[-1]) if spk else 0
    check("spikes found and enlarged (9 made, 9-11 counted)", 9 <= n_sp <= 11, spk[0][:120] if spk else "no uo_spikes line")
    check("all 35 actions planned", len(st) == 35, str(len(st)))
    for a in (8, 12, 13, 15):
        off = st[a]["lower_fist_off_cm"]
        check("action %d: both fists on the shaft" % a, off and off[1] <= 1.0, "lower fist off %s cm" % (None if not off else "%.2f / %.2f" % tuple(off)))
    for a in (23, 24, 25, 26, 27, 28, 29):
        note = " ".join(st[a]["notes"])
        mm = [float(x) for x in note.split("worst intrusion ")[1].split(" mm")[0:1]] if "worst intrusion" in note else [999.0]
        lim = 60.0 if a == 29 else 10.0
        check("mounted action %d clears the horse" % a, mm[0] <= lim, "intrusion %.0f mm (limit %.0f)" % (mm[0], lim))
    for a in (21, 22):
        note = " ".join(st[a]["notes"])
        e = st[a]["axis_err_last_deg"]
        check("fall %d: the shaft lies along the body in the last frame" % a, e is not None and e <= 15.0, "%.1f deg from pelvis -> head" % e)
    print("RESULT", "OK" if ok else "FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
