"""Put one pose of the lute into the collection Clothing (what render_uo_layer.py renders) and save.

    python lute_select_pose.py Lute_poses.blend Lute_stand OUT.blend

Lute_poses.blend has the body, the rig and 17 lute objects: one in Clothing (Lute_carry) and the others in the collection Lute_poses (not rendered: the collection has hide_render on). Each object carries the custom
properties `uo_actions` (the actions it is meant for) and `uo_render_flags` (the extra render_uo_layer.py settings used for it, see model/example_clothing/lute/README.md).
Then: python run_render_headless.py OUT.blend DIR "LAYER='clothing'" "ONLY=['04_stand']" ... <flags>
"""
import sys
import bpy

src, name, out = sys.argv[-3:]
bpy.ops.wm.open_mainfile(filepath=src)
clothing, poses = bpy.data.collections["Clothing"], bpy.data.collections["Lute_poses"]
for o in list(clothing.objects):
    if o.name.startswith("Lute_") and o.name != name:
        clothing.objects.unlink(o); poses.objects.link(o)
o = bpy.data.objects[name]
if o.name not in clothing.objects:
    poses.objects.unlink(o); clothing.objects.link(o)
print("pose", name, "actions", o.get("uo_actions"), "flags", o.get("uo_render_flags"))
bpy.ops.wm.save_as_mainfile(filepath=out)
