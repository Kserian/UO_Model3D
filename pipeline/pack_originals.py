"""Put the original UO body frames into the .blend (enables EXACT_BODY / EXACT_COLORS).
Needs the client file copied here as body400.vd; run build_originals.py first.
usage: python pack_originals.py --blend UO_Body_0x190.blend"""
import bpy, sys, os, json
blend = sys.argv[sys.argv.index("--blend") + 1]
bpy.ops.wm.open_mainfile(filepath=os.path.abspath(blend))
sc = bpy.context.scene
img = bpy.data.images.get("UO_Original_Atlas")
if img: bpy.data.images.remove(img)
img = bpy.data.images.load(os.path.abspath("UO_Original_Atlas.png")); img.name = "UO_Original_Atlas"
img.colorspace_settings.name = "sRGB"; img.alpha_mode = "STRAIGHT"; img.pack()
mat = bpy.data.objects["UO_Body"].data.materials[0]
mat.node_tree.nodes["UOX_atlas"].image = img
t = bpy.data.texts.get("uo_original_frames.json") or bpy.data.texts.new("uo_original_frames.json")
t.from_string(open("uo_original_frames.json").read())
sc["uo_exact"] = 1.0
bpy.ops.wm.save_mainfile()
print("packed")
