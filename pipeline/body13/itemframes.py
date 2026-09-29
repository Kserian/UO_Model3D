"""item / body frames from the extracted .vd files on the 136x120 UO canvas (anchor 68,86) used by the originals"""
import os, sys, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "vdtool"))
import vdtool
VD = os.path.join(HERE, "mul", "anim_%04d.vd")


def load(anim):
    _, blocks = vdtool.read_vd(VD % anim)
    return {(b["action"], b["dir"]): b for b in blocks}


def canvas(blk, i, anchor=(68, 86), size=(136, 120)):
    img = np.zeros((size[1], size[0], 4), np.uint8)
    if blk is None or not blk["frames"] or i >= len(blk["frames"]):
        return img
    f = blk["frames"][i]
    rgba = vdtool.frame_rgba(f, blk["palette"])
    h, w = rgba.shape[:2]
    x0, y0 = anchor[0] - f["cx"], anchor[1] - f["cy"] - f["h"]
    ys, xs = slice(max(y0, 0), min(y0 + h, size[1])), slice(max(x0, 0), min(x0 + w, size[0]))
    if ys.stop > ys.start and xs.stop > xs.start:
        img[ys, xs] = rgba[ys.start - y0:ys.stop - y0, xs.start - x0:xs.stop - x0]
    return img
