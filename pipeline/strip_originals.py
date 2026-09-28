"""Copy of the .blend WITHOUT the packed original UO frames (for the repository). Exact modes stay off until
pack_originals.py puts the frames back from the user's own client files."""
import bpy, sys, os
src, out = sys.argv[sys.argv.index("--src") + 1], sys.argv[sys.argv.index("--out") + 1]
os.makedirs(out, exist_ok=True)
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.open_mainfile(filepath=os.path.abspath(src))
sc = bpy.context.scene
for name in ("UO_Original_Atlas",):
    if name in bpy.data.images:
        bpy.data.images.remove(bpy.data.images[name])
if "uo_original_frames.json" in bpy.data.texts:
    bpy.data.texts.remove(bpy.data.texts["uo_original_frames.json"])
sc["uo_exact"] = 0.0
bpy.data.texts["render_uo_layer.py"].from_string(open("render_uo_layer.py").read())
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(os.path.join(out, "UO_Body_0x190.blend")))
print("stripped")
