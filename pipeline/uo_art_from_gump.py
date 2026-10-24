"""Item icon (art) made from the front view of the item (the picture of its paperdoll gump), turned and reduced.

    python uo_art_from_gump.py RAW_DIR [--rot 45] [--w 44] [--h 44]

RAW_DIR = the output of uo_render_paperdoll.py (item_hi.npy: float RGBA, the item alone seen from the front at 3 x the gump's resolution). The picture is turned in its plane by --rot degrees
(a UO item lies on the ground and is drawn at 45 degrees), cut to its bounding box, reduced to fit the box w x h px with the area mean (premultiplied) and a 1-bit alpha. Writes art_raw.npy and
art_mirror_raw.npy (the same mirrored: the client has a second, mirrored icon of an item) for uo_gump_finish.py, which gives them the levels of the animation and the rim.
"""
import argparse, os
import numpy as np
from PIL import Image
from scipy import ndimage


def make(hi, rot, w, h):
    pm = hi.copy(); pm[..., :3] *= pm[..., 3:]
    pm = np.pad(pm, ((4, 4), (4, 4), (0, 0)))
    r = np.stack([ndimage.rotate(pm[..., c], rot, reshape=True, order=1, mode="constant", cval=0.0) for c in range(4)], -1)
    ys, xs = np.nonzero(r[..., 3] > 0.02)
    r = r[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    k = min((w - 2) / r.shape[1], (h - 2) / r.shape[0])
    nw, nh = max(1, int(round(r.shape[1] * k))), max(1, int(round(r.shape[0] * k)))
    small = np.stack([np.asarray(Image.fromarray(r[..., c].astype(np.float32), "F").resize((nw, nh), Image.BOX)) for c in range(4)], -1)
    out = np.zeros((h, w, 4), np.float32)
    y0, x0 = (h - nh) // 2, (w - nw) // 2
    out[y0:y0 + nh, x0:x0 + nw] = small
    a = out[..., 3:4]
    rgb = out[..., :3] / np.maximum(a, 1e-6)
    res = np.zeros_like(out); res[..., :3] = np.where(a > 0.5, rgb, 0); res[..., 3] = (a[..., 0] >= 0.5)
    return res, k


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("raw"); ap.add_argument("--rot", type=float, default=45.0); ap.add_argument("--w", type=int, default=44); ap.add_argument("--h", type=int, default=44)
    a = ap.parse_args()
    hi = np.load(os.path.join(a.raw, "item_hi.npy")).astype(np.float32)
    art, k = make(hi, a.rot, a.w, a.h)
    np.save(os.path.join(a.raw, "art_raw.npy"), art); np.save(os.path.join(a.raw, "art_mirror_raw.npy"), art[:, ::-1].copy())
    print("art %d x %d from the front view turned by %g degrees, reduced x%.3f (%.1f px per m), %d px" % (a.w, a.h, a.rot, k, k * 90.5 * 3, int(art[..., 3].sum())))


if __name__ == "__main__":
    main()
