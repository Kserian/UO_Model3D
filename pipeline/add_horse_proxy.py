"""Add horse proxy meshes (visual hulls of the UO horse 0xC8) to the .blend as hidden holdout objects."""
import bpy, sys, os, pickle
import numpy as np

SRC = sys.argv[sys.argv.index("--src") + 1]
OUT = sys.argv[sys.argv.index("--out") + 1]
os.makedirs(OUT, exist_ok=True)
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.open_mainfile(filepath=os.path.abspath(SRC))
sc = bpy.context.scene
rig = bpy.data.objects["UO_Rig"]
hulls = pickle.load(open(os.environ.get("UO_HULL_OUT", "horse_hulls.pkl"), "rb"))
LIFT = float(sc.get("uo_anchor_height", 0.0))      # the fit's coordinates have the UO anchor at z = 0

col = bpy.data.collections.get("Horse_Proxy") or bpy.data.collections.new("Horse_Proxy")
if col.name not in sc.collection.children:
    sc.collection.children.link(col)
mat = bpy.data.materials.new("Horse_Proxy_Mat"); mat.diffuse_color = (0.45, 0.33, 0.22, 1)
for old in [o for o in bpy.data.objects if o.name.startswith("Horse_")]:
    bpy.data.objects.remove(old)
for (ra, i), (v, f) in sorted(hulls.items()):
    name = f"Horse_a{ra}_f{i}"
    me = bpy.data.meshes.new(name)
    me.from_pydata((v + np.array([0.0, 0.0, LIFT])).tolist(), [], f.tolist()); me.update()
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    bpy.context.view_layer.objects.active = ob
    dec = ob.modifiers.new("Decimate", "DECIMATE"); dec.ratio = 0.06
    with bpy.context.temp_override(object=ob, active_object=ob):
        bpy.ops.object.modifier_apply(modifier=dec.name)
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(mat)
    ob.parent = rig                      # turns with uo_direction like the rider
    ob.hide_render = True
    ob.hide_viewport = True
    ob["uo_rider_action"] = ra; ob["uo_rider_frame"] = i

# exact 2D horse silhouettes (from the UO horse sprites) for every mounted frame and direction: the proxy only decides
# WHAT is behind the horse, the sprite mask decides WHERE the horse is (pixel-exact edges)
import json, zlib, base64
sys.path.insert(0, "../vdtool")
import vdtool
_, horse = vdtool.read_vd("horse200.vd")
HORSE_OF = {23: 0, 24: 1, 25: 2, 26: 2, 27: 2, 28: 2, 29: 2}
AX, AY, CW, CH = 68, 86, 136, 120
masks = {}
for act in bpy.data.actions:
    if "uo_action" not in act or int(act["uo_action"]) not in HORSE_OF:
        continue
    a = int(act["uo_action"]); ha = HORSE_OF[a]
    for d in range(5):
        blk = horse[ha * 5 + d]
        for i in range(int(act["uo_frames"])):
            fr = blk["frames"][i % len(blk["frames"])]
            al = vdtool.frame_rgba(fr, blk["palette"])[..., 3] > 0
            m = np.zeros((CH, CW), bool)
            ys, xs = np.nonzero(al)
            ys, xs = ys + AY - (fr["cy"] + fr["h"]), xs + AX - fr["cx"]
            ok = (ys >= 0) & (ys < CH) & (xs >= 0) & (xs < CW)
            m[ys[ok], xs[ok]] = True
            masks["%d,%d,%d" % (a, i, d)] = base64.b64encode(zlib.compress(np.packbits(m.ravel()).tobytes(), 9)).decode()
mt = bpy.data.texts.get("uo_horse_masks.json") or bpy.data.texts.new("uo_horse_masks.json")
mt.from_string(json.dumps(dict(format="rider_action,frame,dir -> base64(zlib(packbits(120x136 bool)))", masks=masks)))
print("horse masks", len(masks))

txt = bpy.data.texts.get("render_uo_layer.py") or bpy.data.texts.new("render_uo_layer.py")
txt.from_string(open("render_uo_layer.py").read())
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(os.path.join(OUT, "UO_Body_0x190.blend")))
print("saved")
