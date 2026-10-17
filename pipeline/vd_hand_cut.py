"""Cut the bow where the original bow sprite has a hole (the hand wraps the grip): in a window around the middle of the original sprite, a pixel of the new frame survives only
next to a pixel of the ORIGINAL weapon frame (dilated by `dil` px). Outside the window nothing changes.

    python vd_hand_cut.py NEW.vd ORIG.vd OUT.vd action:dir:frame ... [--win 0.25] [--dil 2]       # * = all, 0-based
"""
import os, sys
import numpy as np
from scipy import ndimage
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "vdtool"))
import vdtool

CW, CH, AX, AY = 300, 300, 150, 200


def canvas(f, pal):
    rgba = vdtool.frame_rgba(f, pal); h, w = rgba.shape[:2]
    im = np.zeros((CH, CW, 4), np.uint8); x0, y0 = AX - f["cx"], AY - (f["cy"] + f["h"])
    im[y0:y0 + h, x0:x0 + w] = rgba
    return im


def cut(new, orig, out, specs, win=0.25, dil=2):
    at, bn = vdtool.read_vd(new); _, bo = vdtool.read_vd(orig)
    tab = {(b["action"], b["dir"]): b for b in bo}
    want = {}
    for sp in specs:
        a, d, f = sp.split(":")
        for b in bn:
            if a in ("*", str(b["action"])) and d in ("*", str(b["dir"])):
                for i in range(len(b["frames"])):
                    if f in ("*", str(i)):
                        want.setdefault((b["action"], b["dir"]), set()).add(i)
    blocks = []
    for b in bn:
        key = (b["action"], b["dir"])
        if not b["frames"]:
            blocks.append(None); continue
        imgs, cent = [], []
        for i, f in enumerate(b["frames"]):
            rgba = vdtool.frame_rgba(f, b["palette"])
            if i in want.get(key, ()):
                o = tab[key]; of = o["frames"][i]; oc = canvas(of, o["palette"]); nc = canvas(f, b["palette"])
                ys, xs = np.nonzero(oc[..., 3] > 0)
                if len(ys):
                    cy = (ys.min() + ys.max()) / 2.0; hh = (ys.max() - ys.min() + 1) * win
                    near = ndimage.binary_dilation(oc[..., 3] > 0, iterations=dil)
                    yy = np.arange(CH)[:, None] * np.ones((1, CW))
                    zone = np.abs(yy - cy) <= hh + 2
                    kill = zone & (nc[..., 3] > 0) & ~near
                    n_kill = int(kill.sum())
                    x0, y0 = AX - f["cx"], AY - (f["cy"] + f["h"])
                    sub = kill[y0:y0 + rgba.shape[0], x0:x0 + rgba.shape[1]]
                    rgba = rgba.copy(); rgba[sub, 3] = 0; rgba[sub, :3] = 0
                    print("action %d dir %d frame %d: %d bow pixels cut around the grip" % (key[0], key[1], i, n_kill))
            imgs.append(rgba); cent.append((f["cx"], f["cy"]))
        palette, maps = vdtool.build_palette(imgs, b["palette"])
        blocks.append(dict(palette=palette, frames=[dict(cx=c[0], cy=c[1], idx=m) for c, m in zip(cent, maps)]))
    vdtool.write_vd(out, at, blocks)


if __name__ == "__main__":
    args = sys.argv[1:]; win, dil = 0.25, 2
    if "--win" in args:
        k = args.index("--win"); win = float(args[k + 1]); del args[k:k + 2]
    if "--dil" in args:
        k = args.index("--dil"); dil = int(args[k + 1]); del args[k:k + 2]
    cut(args[0], args[1], args[2], args[3:], win, dil)
