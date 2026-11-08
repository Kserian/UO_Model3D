"""Replace single blocks (action, direction) of an existing .vd with frames rendered later; every other block is copied byte for byte.

    python vd_merge.py BASE.vd OUT.vd RENDER_DIR ACTION:DIRS [ACTION:DIRS ...]
    e.g.  python vd_merge.py Harp_right_hand.vd Harp_right_hand.vd fix_prod 00_walk_unarmed:0,4 04_stand:0,1,2,3,4

RENDER_DIR holds clothing/frames/<action>/dir<k>/NN.png (render_uo_layer.py, LAYER="clothing", canvas 256 x 256, anchor (128, 192)). ACTION is the folder name (NN_name), DIRS the
directions to take. Nothing else of BASE is touched: the palette of a replaced block is built from its own frames, like uo_vd_writer.write_vd does.
"""
import sys, os, struct, glob
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import uo_vd_writer as W

ANCHOR = (128, 192)


def encode_block(frames, anchor=ANCHOR):
    """the bytes of one block: palette, frame offsets, frames (the same code as write_vd)"""
    crops = [W.crop_frame(f, *anchor) for f in frames]
    palette, maps = W.build_palette([c[0] for c in crops])
    fb = [W.encode_frame(ix, c[1], c[2]) for ix, c in zip(maps, crops)]
    data = bytearray(struct.pack("<256H", *palette))
    data += struct.pack("<i", len(fb))
    off = 4 + 4 * len(fb)
    for b in fb:
        data += struct.pack("<i", off); off += len(b)
    for b in fb:
        data += b
    return bytes(data)


def load_frames(render_dir, action, d):
    files = sorted(glob.glob(os.path.join(render_dir, "clothing", "frames", action, "dir%d" % d, "*.png")))
    if not files:
        raise SystemExit("no frames: %s dir%d in %s" % (action, d, render_dir))
    return [np.array(Image.open(f).convert("RGBA")) for f in files]


def merge(base, out, render_dir, specs):
    raw = open(base, "rb").read()
    magic, atype = struct.unpack_from("<hh", raw, 0)
    n = {0: 22, 1: 13, 2: 35}[atype] * 5
    blocks = []
    for i in range(n):
        off, ln, ex = struct.unpack_from("<iii", raw, 4 + 12 * i)
        blocks.append(None if off <= 0 or ln <= 0 else raw[off:off + ln])
    for action, dirs in specs:
        a = int(action[:2])
        for d in dirs:
            blocks[a * 5 + d] = encode_block(load_frames(render_dir, action, d))
            print("replaced block %d (%s) dir %d" % (a, action, d))
    head = bytearray(struct.pack("<hh", magic, atype)); body = bytearray(); start = 4 + 12 * n
    for b in blocks:
        if b is None:
            head += struct.pack("<iii", -1, -1, -1)
        else:
            head += struct.pack("<iii", start + len(body), len(b), 0); body += b
    open(out, "wb").write(head + body)
    print("wrote", out, len(head) + len(body), "bytes")


if __name__ == "__main__":
    specs = [(s.split(":")[0], [int(x) for x in s.split(":")[1].split(",")]) for s in sys.argv[4:]]
    merge(sys.argv[1], sys.argv[2], sys.argv[3], specs)
