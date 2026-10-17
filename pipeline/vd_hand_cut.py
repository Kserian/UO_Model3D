"""Cut the bow where the hand is in front of it. In the ORIGINAL bow sprite (anim.mul 649) the bow is drawn behind the fist: along the shaft there are rows where it has no pixel at
all. Around those rows (`grow` rows more on each side) our bow pixels that lie ON THE ORIGINAL BODY of the same frame (body400.vd: the fist, the forearm) are removed, so the hand
is drawn in front of the grip. Frames whose original bow has no such gap (the bow is in front of the hand there) and bow pixels in the empty space beside the body are left alone;
other frames / blocks keep their bytes.

    python vd_hand_cut.py NEW.vd ORIG_BOW.vd BODY.vd OUT.vd action:dir:frame ... [--grow 3]        # * = all, 0-based
"""
import os, sys
import numpy as np
from scipy import ndimage
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "vdtool"))
import vdtool

CW, CH, AX, AY = 300, 300, 150, 200


def canvas_alpha(f, pal):
    rgba = vdtool.frame_rgba(f, pal); h, w = rgba.shape[:2]
    a = np.zeros((CH, CW), bool); x0, y0 = AX - f["cx"], AY - (f["cy"] + f["h"])
    a[y0:y0 + h, x0:x0 + w] = rgba[..., 3] > 0
    return a


def cut(new, orig, body, out, specs, grow=3):
    at, bn = vdtool.read_vd(new); _, bo = vdtool.read_vd(orig); _, bb = vdtool.read_vd(body)
    to = {(b["action"], b["dir"]): b for b in bo}; tb = {(b["action"], b["dir"]): b for b in bb}
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
        if key not in want:
            blocks.append(dict(palette=b["palette"], frames=[dict(cx=f["cx"], cy=f["cy"], idx=f["idx"]) for f in b["frames"]])); continue
        imgs, cent = [], []
        for i, f in enumerate(b["frames"]):
            rgba = vdtool.frame_rgba(f, b["palette"]).copy()
            if i in want[key]:
                oa = canvas_alpha(to[key]["frames"][i], to[key]["palette"]); ba = canvas_alpha(tb[key]["frames"][i], tb[key]["palette"]); na = canvas_alpha(f, b["palette"])
                rows = np.nonzero(oa.any(1))[0]
                gap = [r for r in range(rows.min(), rows.max() + 1) if not oa[r].any()] if len(rows) else []
                if gap:
                    zone = np.zeros((CH, CW), bool); zone[max(min(gap) - grow, 0):max(gap) + grow + 1] = True
                    kill = zone & na & ba
                    h, w = rgba.shape[:2]; x0, y0 = AX - f["cx"], AY - (f["cy"] + f["h"])
                    sub = kill[y0:y0 + h, x0:x0 + w]
                    rgba[sub] = 0
                    print("action %d dir %d frame %d: original gap %d rows, %d bow pixels on the body cut" % (key[0], key[1], i, len(gap), int(sub.sum())))
            imgs.append(rgba); cent.append((f["cx"], f["cy"]))
        palette, maps = vdtool.build_palette(imgs, b["palette"])
        blocks.append(dict(palette=palette, frames=[dict(cx=c[0], cy=c[1], idx=m) for c, m in zip(cent, maps)]))
    vdtool.write_vd(out, at, blocks)


if __name__ == "__main__":
    args = sys.argv[1:]; grow = 3
    if "--grow" in args:
        k = args.index("--grow"); grow = int(args[k + 1]); del args[k:k + 2]
    cut(args[0], args[1], args[2], args[3], args[4:], grow)
