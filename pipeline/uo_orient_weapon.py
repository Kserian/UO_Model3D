# Stand a free weapon model upright the way uo_place_weapon.py wants it: shaft along +Z, the head / tip UP (+Z), the butt at z = 0 on the Z axis, the flat of the blade (the wide
# side of the head: sword blade, axe bit, the side of a gun) along +X; and give it the length of its class. Models come lying along X or Y, tip left or right, in any size.
# What it does, on the SELECTED mesh object(s) (after uo_import_item.py with KIND = "" - no placement on the body - and uo_materials.py):
# 1. the long axis of the mesh (principal axis of its vertices) becomes Z;
# 2. the TIP is the end where the cross-section is smaller (a blade point, a muzzle, a spear head is narrower than a pommel or a stock) - the model is turned so that it points up
#    (TIP = "auto"; give "+axis" / "-axis" like "-y" when the model has a narrow butt and a wide head, e.g. a mace or a hammer: there the tip is the heavy end, say TIP = "heavy");
# 3. the widest side perpendicular to the shaft goes to +X (the blade's flat, the side of the stock); a round shaft keeps whatever it had;
# 4. scaled so that the length along the shaft is LENGTH m (by CLASS, LENGTHS below: the typical original of the class, measured) unless LENGTH > 0 is given; the butt end at the origin.
# Then: uo_place_weapon.py (PART weapon1h / polearm / axe2h / bow) and uo_bind_item.py with the same PART. See docs/qa/weapons_free_models.md.
import bpy
import numpy as np
from mathutils import Matrix

CLASS = "sword"       # sword, dagger, mace, axe, axe2h, polearm, staff, spear, bow, crossbow, gun
LENGTH = 0.0          # m, total length along the shaft; 0 = from CLASS
TIP = "auto"          # "auto" (narrower end), "heavy" (the end with more vertices / mass is the head: mace, hammer, axe), or "+x", "-x", "+y", "-y", "+z", "-z" (model axis the tip points to)
FLAT = True           # turn the widest side perpendicular to the shaft to +X
LENGTHS = {"sword": 1.1, "dagger": 0.5, "mace": 1.2, "axe": 1.35, "axe2h": 1.4, "polearm": 2.5, "staff": 2.4, "spear": 2.7, "bow": 1.34, "crossbow": 1.1, "gun": 1.2}
# measured on the original weapons of the client (docs/qa/weapons_free_models.md): the longest bounding-box diagonal over all frames of the animation, m. 1H blades 0.83 katana /
# 0.97 cutlass / 1.12 scimitar / 1.21 broadsword / 1.31 viking sword; maces, hammers, clubs 1.06-1.29; 1H axes 1.34-1.39; 2H axes 1.39-1.65; bardiche 2.37, halberd 2.51, long spear
# 2.70; quarter staff 2.27, black staff 2.78; bow 1.34; crossbow 1.09, heavy crossbow 1.44. The dagger (0.5) is not measured.


def principal_axes(P):
    c = P.mean(0)
    u, s, vt = np.linalg.svd(P - c, full_matrices=False)
    return c, vt                                  # rows: long, wide, thin


def width_at(P, a, t, frac=0.04):
    """size of the cross-section (area of the bounding box perpendicular to the axis) in the end 4 % of the length at t (0 = low end, 1 = high end)"""
    lo, hi = a.min(), a.max(); L = hi - lo
    sel = (a >= lo + (1 - frac) * L) if t else (a <= lo + frac * L)
    q = P[sel]
    return float(np.prod(np.ptp(q, axis=0))) if len(q) > 3 else 0.0


def run():
    obs = [o for o in bpy.context.selected_objects if o.type == "MESH"]
    if not obs:
        raise RuntimeError("select the weapon first")
    allv = np.concatenate([np.array([o.matrix_world @ v.co for v in o.data.vertices]) for o in obs])
    c, vt = principal_axes(allv)
    Q = (allv - c) @ vt.T                         # coordinates in (long, wide, thin)
    if TIP in ("auto", "heavy"):
        w_lo, w_hi = width_at(Q[:, 1:], Q[:, 0], 0), width_at(Q[:, 1:], Q[:, 0], 1)
        n_lo, n_hi = (Q[:, 0] < Q[:, 0].min() + 0.15 * np.ptp(Q[:, 0])).sum(), (Q[:, 0] > Q[:, 0].max() - 0.15 * np.ptp(Q[:, 0])).sum()
        tip_high = (w_hi < w_lo) if TIP == "auto" else (n_hi > n_lo)
    else:
        ax = {"x": 0, "y": 1, "z": 2}[TIP[1]]; sign = 1 if TIP[0] == "+" else -1
        tip_high = float(vt[0][ax] * sign) > 0
    long_ax = vt[0] if tip_high else -vt[0]
    wide = vt[1]
    # rotation: long -> +Z, wide -> +X
    z = long_ax / np.linalg.norm(long_ax)
    x = wide - (wide @ z) * z; x /= np.linalg.norm(x)
    if not FLAT:
        x = np.cross([0, 0, 1.0], z) if abs(z[2]) < 0.99 else np.array([1.0, 0, 0]); x /= np.linalg.norm(x)
    y = np.cross(z, x)
    Rm = np.array([x, y, z])                      # model -> upright: rows are the new axes
    U = (allv - c) @ Rm.T
    L = np.ptp(U[:, 2]); target = LENGTH if LENGTH > 0 else LENTH_OF(CLASS)
    s = target / L
    zmin = U[:, 2].min(); mid = [(U[:, 0].min() + U[:, 0].max()) / 2, (U[:, 1].min() + U[:, 1].max()) / 2]
    T = np.eye(4); T[:3, :3] = s * Rm; T[:3, 3] = -s * (Rm @ c) - np.array([s * mid[0], s * mid[1], s * zmin])
    for o in obs:
        o.data.transform(Matrix(T) @ o.matrix_world)
        o.matrix_world = Matrix.Identity(4)
    bpy.context.view_layer.update()
    print("uo_orient_weapon: %s: tip %s (cross-section %.4g / %.4g), length %.3f -> %.2f m (x%.4f), flat side on +X" % (
        ", ".join(o.name for o in obs), "up" if tip_high else "flipped", w_lo if TIP == "auto" else 0, w_hi if TIP == "auto" else 0, L, target, s))


def LENTH_OF(cls):
    if cls not in LENGTHS:
        raise ValueError("CLASS must be one of %s" % list(LENGTHS))
    return LENGTHS[cls]


run()
