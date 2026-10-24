"""Narrow the side panels of the Radiant Star Girdle's glb uniformly (the waistband and the central banner stay).

    python uo_narrow_panels.py IN.glb OUT.glb [--k 0.77] [--xa 0.26] [--z0 0.70] [--z1 0.76]

Every vertex with |x| > xa (the outer edge of the banner's outer frame, glTF x = Blender x) moves towards the middle: |x'| = xa + (|x| - xa) * k(z), the panels are widest at the hem
(0.44 model units from xa), so the outer edge goes in by 0.44 (1 - k) there and by less higher up; the same factor at every height, so the panels keep their shape, only narrower. k(z) = 1 below
z0 and fades to 1 at z1 (the waistband ring at the top is not touched: the fit to the body stays as it was). Only the POSITION accessor changes (normals stay: the change is a few degrees at most).
In the game (1 px = 2.8 cm, the item at 0.631 x 0.87 of the file: 0.549 m per model unit = 19.8 px per unit) k 0.77 moves the outer edge of each panel in by 0.10 units = 2.0 px (4 px in all).
"""
import argparse, sys
import numpy as np

sys.path.insert(0, __file__.rsplit("/", 1)[0] if "/" in __file__ else ".")
import uo_fill_banner_gap as g


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("inp"); ap.add_argument("out")
    ap.add_argument("--k", type=float, default=0.77); ap.add_argument("--xa", type=float, default=0.26)
    ap.add_argument("--z0", type=float, default=0.70); ap.add_argument("--z1", type=float, default=0.76)
    a = ap.parse_args()
    j, bin_ = g.read_glb(a.inp)
    prim = j["meshes"][0]["primitives"][0]; k = prim["attributes"]["POSITION"]
    P = g.accessor(j, bin_, k).astype(np.float64)
    z = P[:, 1]                                                                         # glTF y = Blender z (up)
    t = np.clip((a.z1 - z) / max(a.z1 - a.z0, 1e-6), 0.0, 1.0); t = t * t * (3 - 2 * t)
    kz = 1.0 - (1.0 - a.k) * t
    ax = np.abs(P[:, 0]); out = np.where(ax > a.xa, a.xa + (ax - a.xa) * kz, ax)
    P2 = P.copy(); P2[:, 0] = np.sign(P[:, 0]) * out
    moved = np.abs(P2[:, 0] - P[:, 0])
    print("k %.2f about |x| = %.2f: %d vertices move, the largest by %.3f units (= %.1f px at 19.8 px per unit), widest |x| %.3f -> %.3f" % (a.k, a.xa, int((moved > 1e-6).sum()), moved.max(), moved.max() * 19.8, ax.max(), np.abs(P2[:, 0]).max()))
    acc = j["accessors"][k]; acc["min"] = P2.min(0).tolist(); acc["max"] = P2.max(0).tolist()
    bv = j["bufferViews"][acc["bufferView"]]; start = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    nb = bytearray(bin_); data = P2.astype(np.float32).tobytes(); nb[start:start + len(data)] = data
    g.write_glb(a.out, j, bytes(nb))


if __name__ == "__main__":
    main()
