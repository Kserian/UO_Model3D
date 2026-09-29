import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
import bpy, numpy as np
bpy.ops.wm.open_mainfile(filepath=os.path.join(HERE, "..", "..", "model", "UO_Body_0x190.blend"))
body = bpy.data.objects["UO_Body"]; rig = bpy.data.objects["UO_Rig"]
bones = [b.name for b in rig.data.bones]
names = [g.name for g in body.vertex_groups]
kb = body.data.shape_keys.key_blocks["Basis"]; BV = np.array([k.co[:] for k in kb.data])
BW = np.zeros((len(BV), len(bones)))
for v in body.data.vertices:
    for g in v.groups:
        if names[g.group] in bones: BW[v.index, bones.index(names[g.group])] = g.weight
F = np.array([list(p.vertices) for p in body.data.polygons], dtype=object)
np.savez("v12_mesh.npz", BV=BV, BW=BW, faces=F, bones=np.array(bones), groups=np.array(names))
print(len(BV), len(F), "groups", names)
