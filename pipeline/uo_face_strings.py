# A stringed instrument (lute, mandolin) stood upright by uo_orient_weapon.py (neck up, +Z): turn it about Z so that the strings face -Y, the bowl bulges to +Y and the headstock bends back to +Y
# (the way uo_place_carry.py and the roll of uo_place_weapon.py expect it). Which side the back is on is read from the headstock: it is bent away from the strings.
# Runs on the SELECTED mesh object(s).
import bpy
import numpy as np
from mathutils import Matrix

obs = [o for o in bpy.context.selected_objects if o.type == "MESH"]
co = np.concatenate([np.array([o.matrix_world @ v.co for v in o.data.vertices]) for o in obs])
z0, L = co[:, 2].min(), np.ptp(co[:, 2])
t = (co[:, 2] - z0) / L
head, neck = co[t > 0.9], co[(t > 0.55) & (t < 0.75)]
back = np.sign(head[:, 1].mean() - neck[:, 1].mean()) or 1.0          # +1: the headstock is bent to +Y (already the way we want it)
if back < 0:
    for o in obs:
        o.data.transform(Matrix.Rotation(np.pi, 4, "Z") @ o.matrix_world); o.matrix_world = Matrix.Identity(4)
    bpy.context.view_layer.update()
print("uo_face_strings: headstock offset %+.3f m -> %s" % (head[:, 1].mean() - neck[:, 1].mean(), "turned 180 deg about Z" if back < 0 else "kept"))
