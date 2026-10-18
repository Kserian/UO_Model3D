"""Widen the neck and the headstock of the lute poses in Lute_poses.blend by 1 px (0.028 m) in the plane of the strings (the width, the mesh's X), the thickness (Y) unchanged.

    python lute_widen_poses.py Lute_poses.blend OUT.blend [--grow 0.014] [--skip Lute_carry]

The meshes are stored upright (butt z = 0 .. tip z = 1 m, the placement is in the object's matrix), so the position of the lute in every action stays as it is: every vertex above Z0 moves
GROW m along X away from the middle of its slice (the neck, the headstock and its pegs), fading in over RAMP like uo_grow_neck.py (WIDTH_ONLY). Lute_carry already has its neck grown by 1 px in both
directions (neck_grow in its recipe), so it is skipped.
"""
import sys
import bpy
import numpy as np

Z0, RAMP, BIN = 0.5, 0.06, 0.02
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
src, out = args[0], args[1]
grow = float(args[args.index("--grow") + 1]) if "--grow" in args else 0.014
skip = set(args[args.index("--skip") + 1].split(",")) if "--skip" in args else {"Lute_carry"}
bpy.ops.wm.open_mainfile(filepath=src)
for ob in [o for o in bpy.data.objects if o.name.startswith("Lute_") and o.type == "MESH" and o.name not in skip]:
    me = ob.data
    co = np.empty(len(me.vertices) * 3, np.float64); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
    z = co[:, 2]; k = np.floor(z / BIN).astype(int); new = co.copy()
    for b in np.unique(k[z > Z0 - RAMP]):
        m = k == b
        cx = (co[m, 0].min() + co[m, 0].max()) / 2
        dx = co[m, 0] - cx
        w = np.clip((z[m] - Z0) / RAMP, 0.0, 1.0); w = w * w * (3 - 2 * w)
        new[m, 0] = co[m, 0] + np.where(np.abs(dx) > 1e-4, np.sign(dx) * grow * w, 0.0)
    me.vertices.foreach_set("co", new.ravel()); me.update()
    s = co[(z > 0.62) & (z < 0.68)]; t = new[(z > 0.62) & (z < 0.68)]
    print("%s: neck width %.3f -> %.3f m, thickness %.3f -> %.3f" % (ob.name, np.ptp(s[:, 0]), np.ptp(t[:, 0]), np.ptp(s[:, 1]), np.ptp(t[:, 1])))
bpy.ops.wm.save_as_mainfile(filepath=out)
