"""Replace single frames of a .vd with the same frames of another .vd (the rest stays byte for byte), e.g. frames of an item re-rendered after a fix.

    python vd_patch.py OLD.vd NEW.vd OUT.vd 18:*:* 6:1:2 16:*:3 ...        # action:dir:frame, * = all, 0-based as in the .vd

For every block (action, dir) that gets a frame from NEW the palette is rebuilt from all of its frames, starting from the old palette (build_palette keeps the old colours),
the frames of the block are re-encoded; untouched blocks keep their bytes. Frame centres (cx, cy) come with the frames.
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "vdtool"))
import vdtool


def patch(old, new, out, specs):
    at, bo = vdtool.read_vd(old); at2, bn = vdtool.read_vd(new)
    assert at == at2
    want = {}
    for sp in specs:
        a, d, f = sp.split(":")
        for blk in bn:
            if a not in ("*", str(blk["action"])) or d not in ("*", str(blk["dir"])):
                continue
            for i in range(len(blk["frames"])):
                if f in ("*", str(i)):
                    want.setdefault((blk["action"], blk["dir"]), set()).add(i)
    tab = {(b["action"], b["dir"]): b for b in bn}
    blocks = []
    for b in bo:
        key = (b["action"], b["dir"])
        if key not in want or not b["frames"]:
            blocks.append(None if not b["frames"] else dict(palette=b["palette"], frames=[dict(cx=f["cx"], cy=f["cy"], idx=f["idx"]) for f in b["frames"]], raw=True))
            continue
        nb = tab[key]; imgs, cent = [], []
        for i, f in enumerate(b["frames"]):
            src, pal = (nb["frames"][i], nb["palette"]) if i in want[key] else (f, b["palette"])
            imgs.append(vdtool.frame_rgba(src, pal)); cent.append((src["cx"], src["cy"]))
        palette, maps = vdtool.build_palette(imgs, b["palette"])
        blocks.append(dict(palette=palette, frames=[dict(cx=c[0], cy=c[1], idx=m) for c, m in zip(cent, maps)]))
        print("block action %d dir %d: frames %s replaced" % (key[0], key[1], sorted(want[key])))
    vdtool.write_vd(out, at, blocks)


if __name__ == "__main__":
    patch(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:])
