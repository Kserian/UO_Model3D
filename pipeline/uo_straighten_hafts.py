# Crossed axes whose hafts are skewed and offset (a Meshy model: the upper-left half 38 deg and the lower-right half 29 deg from the vertical, the other pair 5 px apart sideways):
# in the FRONT view (x right, z up) each of the four half-hafts (with the head on it) is turned about the hub to a common angle (+-deg from the vertical, a symmetric X) and shifted so that its axis passes through
# the hub centre: the upper and the lower half of a haft lie on one straight line. Depth (y) is not touched; the hub plate (within cut_r of the hub) stays, the halves are blended in over blend_r.
# CFG comes from the recipe ("rigid": {"straighten": {...}}): {"deg": 30, "hub": [0.0, 1.36], "cut_r": 0.10, "blend_r": 0.08, "halves": {"UL": {"deg": 38.36, "off_m": 0.0109}, ...}}
# where the halves are measured on a front render of the item (uo_render_back_gump.py writes them to halves.json: deg = the half-line's angle from the vertical, down-right positive; off_m = signed distance
# of the hub from that line along its normal). Run on the item in the rest pose, before it is bound (the mesh is edited in world space).
import bpy
import numpy as np
from mathutils import Vector

CFG = {}
items = [o for o in bpy.data.collections["Clothing"].all_objects if o.type == "MESH"]
HUB = CFG["hub"]; T = np.radians(CFG["deg"]); CUT_R, BLEND_R = CFG.get("cut_r", 0.10), CFG.get("blend_r", 0.08)
QUAD = {"UL": (-1, 1, T), "UR": (1, 1, -T), "LL": (-1, -1, -T), "LR": (1, -1, T)}
for ob in items:
    M = ob.matrix_world.copy(); Mi = M.inverted()
    co = np.array([(M @ v.co)[:] for v in ob.data.vertices])
    x, z = co[:, 0] - HUB[0], co[:, 2] - HUB[1]; r = np.hypot(x, z)
    w = np.clip((r - CUT_R) / BLEND_R, 0.0, 1.0); w = w * w * (3 - 2 * w)
    new = co.copy()
    for name, (sx, sz, want) in QUAD.items():
        m = (np.sign(x) == sx) & (np.sign(z) == sz)
        ang = np.radians(CFG["halves"][name]["deg"]); off = CFG["halves"][name]["off_m"]
        dth = want - ang
        xr = x * np.cos(dth) - z * np.sin(dth); zr = x * np.sin(dth) + z * np.cos(dth)
        nx, nz = -np.cos(want), -np.sin(want)
        xs_, zs_ = xr + off * nx, zr + off * nz
        tx, tz = x + w * (xs_ - x), z + w * (zs_ - z)
        new[m, 0] = HUB[0] + tx[m]; new[m, 2] = HUB[1] + tz[m]
    for v, p in zip(ob.data.vertices, new):
        v.co = Mi @ Vector(p.tolist())
    ob.data.update()
bpy.context.view_layer.update()
print("uo_straighten_hafts: %d object(s), hafts turned about the hub (%.2f, %.2f) to +-%.0f deg" % (len(items), HUB[0], HUB[1], CFG["deg"]))
