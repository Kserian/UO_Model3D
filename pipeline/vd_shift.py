"""Shift single frames of a .vd by whole pixels (the offset a frame needs when the client draws it next to the body).

    python vd_shift.py IN.vd OUT.vd 18:0:0:+4 18:0:1:+3 18:3:0:+3 18:3:1:+3          # action:dir:frame:dx[:dy], 0-based as in the .vd
    python vd_shift.py IN.vd OUT.vd --mirror 18:5:0:-3                               # dir 5-7 of the client are the mirror of the stored dirs 3-1: dx is negated and moved to the stored dir

dx > 0 moves the sprite to the right, dy > 0 down (the viewer's X / Y offset). Only the frame centre (cx, cy) changes, the pixels and palette stay.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "vdtool"))
import vdtool

MIRROR = {5: 3, 6: 2, 7: 1}


def shift(src, dst, items, mirror=False):
    at, blocks = vdtool.read_vd(src)
    for it in items:
        p = it.split(":")
        a, d, f, dx = int(p[0]), int(p[1]), int(p[2]), int(p[3]); dy = int(p[4]) if len(p) > 4 else 0
        if d in MIRROR:                                    # the viewer shows the mirrored sprite of a stored direction: left-right is flipped
            d, dx = MIRROR[d], -dx
        blk = blocks[a * 5 + d]
        fr = blk["frames"][f]
        fr["cx"] -= dx; fr["cy"] -= dy                      # the frame is drawn at anchor - centre
        print("action %d dir %d frame %d: shifted by %+d, %+d px" % (a, d, f, dx, dy))
    out = [b if b["frames"] else None for b in blocks]
    vdtool.write_vd(dst, at, out)


if __name__ == "__main__":
    args = [x for x in sys.argv[1:] if x != "--mirror"]
    shift(args[0], args[1], args[2:])
