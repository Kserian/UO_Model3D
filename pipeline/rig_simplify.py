"""One-off: reduce UO_Rig to the 19 bones that move the character (pelvis, spine, chest, neck, head, clavicle, upper_arm, forearm, hand, thigh, shin, foot).

    python rig_simplify.py ../model/UO_Body_0x190.blend OUT.blend

Removed: 30 finger bones (weights -> hand), 4 twist bones (-> upper_arm / forearm), 2 toe bones (-> foot), 52 cloth chains (skirt_*, cloak_*) with their
templates, 5 bones of item motion (polearm.L, axe2h.L, bow.L, weapon1h.R, shield.L); their keys, bone collections and the embedded texts that only served them.
The clavicles do not deform (Deform off, as before): their weight groups stay on UO_Body (Blender ignores them and renormalises the rest, measured: 0 difference;
part labels and the dominant-bone logic of the tests stay as they were), but they are dropped from items (Example_Shirt). Measured on the body (body_part_qa.py, 1050 frames): IoU 0.8922 -> 0.8882 (fingers), twist / toes / weapon bones no change.
Run with the bpy 4.2 module (a file saved by 5.x does not open in 4.2).
"""
import re, sys
import numpy as np
import bpy

src, dst = sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=src)
rig = bpy.data.objects["UO_Rig"]

MAP = {}                                                   # removed bone -> bone that takes its weights
REMOVE = []
for b in rig.data.bones:
    n = b.name
    if n.startswith("finger"):
        MAP[n] = "hand." + n[-1]
    elif n.endswith(("_twist.L", "_twist.R")):
        MAP[n] = n.split("_twist")[0] + n[-2:]
    elif n.startswith("toe."):
        MAP[n] = "foot." + n[-1]
    elif n.startswith(("skirt_", "cloak_")) or n in ("polearm.L", "axe2h.L", "bow.L", "weapon1h.R", "shield.L"):
        pass
    else:
        continue
    REMOVE.append(n)
DROP = {"clavicle.L", "clavicle.R"}


def reskin(ob):
    drop = DROP if ob.name != "UO_Body" else set()
    names = {g.index: g.name for g in ob.vertex_groups}
    keep = [g.name for g in ob.vertex_groups if g.name not in MAP and g.name not in drop and g.name not in REMOVE]
    W = {n: np.zeros(len(ob.data.vertices)) for n in keep}
    for v in ob.data.vertices:
        for g in v.groups:
            n = names[g.group]
            n = MAP.get(n, n)
            if n in W:
                W[n][v.index] += g.weight
    tot = sum(W.values())
    for g in list(ob.vertex_groups):
        ob.vertex_groups.remove(g)
    for n in keep:
        vg = ob.vertex_groups.new(name=n)
        w = np.where(tot > 0, W[n] / np.maximum(tot, 1e-9), 0)
        for i in np.nonzero(w > 1e-5)[0]:
            vg.add([int(i)], float(w[i]), "REPLACE")


for ob in list(bpy.data.objects):
    if ob.name.startswith("UO_Template_"):
        bpy.data.objects.remove(ob)
    elif ob.type == "MESH" and ob.vertex_groups and ob.name != "UO_Horse":
        if ob.name == "UO_Body" or any(m.type == "ARMATURE" for m in ob.modifiers):
            reskin(ob)
if "Templates" in bpy.data.collections:
    bpy.data.collections.remove(bpy.data.collections["Templates"])

bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode="EDIT")
for n in REMOVE:
    eb = rig.data.edit_bones.get(n)
    if eb:
        rig.data.edit_bones.remove(eb)
bpy.ops.object.mode_set(mode="OBJECT")
for c in [c for c in rig.data.collections_all if len(c.bones) == 0]:
    rig.data.collections.remove(c)

gone = set(REMOVE)
for a in bpy.data.actions:
    for fc in list(a.fcurves):
        m = re.match(r'pose\.bones\["(.+?)"\]', fc.data_path)
        if m and m.group(1) in gone:
            a.fcurves.remove(fc)

for t in ("uo_cloth_bake.py", "uo_weapon_bones.py", "uo_place_weapon.py", "uo_place_shield.py", "weapon_motion.json", "uo_transfer_corrections.py"):
    if t in bpy.data.texts:
        bpy.data.texts.remove(bpy.data.texts[t])

bones = [b.name for b in rig.data.bones]
print("bones left %d: %s" % (len(bones), bones))
bpy.ops.wm.save_as_mainfile(filepath=dst)
