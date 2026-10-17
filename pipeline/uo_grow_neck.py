# Thicken the neck and the headstock of the SELECTED instrument (upright, butt z = 0 .. tip z = LENGTH, from uo_orient_weapon.py / uo_face_strings.py): every vertex above Z0 is pushed away from the axis of its slice
# by GROW m (1 px of the 36 px/m render = 0.028 m across = GROW 0.014 per side), the push fading in over RAMP so that the bowl does not change. The neck of a lute is 2-3 px wide in the 136x120 frames: the held instrument then reads as held.
#   Z0 m: where the neck starts (the bowl ends); RAMP m; GROW m per side; BIN m: height of a slice
import bpy
import numpy as np

Z0 = 0.5
RAMP = 0.06
GROW = 0.014
BIN = 0.02

for ob in [o for o in bpy.context.selected_objects if o.type == "MESH"]:
    me = ob.data
    co = np.empty(len(me.vertices) * 3, np.float64); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
    z = co[:, 2]
    k = np.floor(z / BIN).astype(int)
    new = co.copy()
    for b in np.unique(k[z > Z0 - RAMP]):
        m = k == b
        c = (co[m, :2].min(0) + co[m, :2].max(0)) / 2                        # middle of the slice's bounding box
        d = co[m, :2] - c
        n = np.linalg.norm(d, axis=1)
        w = np.clip((z[m] - Z0) / RAMP, 0.0, 1.0); w = w * w * (3 - 2 * w)  # smoothstep: 0 at the end of the bowl, 1 on the neck
        push = np.where(n > 1e-4, GROW * w / np.maximum(n, 1e-4), 0.0)
        new[m, :2] = co[m, :2] + d * push[:, None]
    me.vertices.foreach_set("co", new.ravel()); me.update()
    print("uo_grow_neck: %s: %d vertices above z %.2f pushed out by up to %.1f mm" % (ob.name, int((z > Z0).sum()), Z0, 1000 * GROW))
