"""Readers and writers of UO gump (paperdoll) and static art (item icon) images, mul format.

    python uo_gump_art.py gump DIR ID [OUT.png]      # extract gump ID (Gumpidx.mul / Gumpart.mul in DIR) to PNG
    python uo_gump_art.py art  DIR ID [OUT.png]      # extract static art of item ID (art.mul index 0x4000 + ID)
    python uo_gump_art.py list DIR A B          # sizes of the gumps A..B

Gump: Gumpidx entry = lookup, length, extra (width << 16 | height); data = height dword row offsets, then per row runs of (colour uint16, count uint16).
Static art (item): uint32 header, width, height (uint16), height uint16 row offsets (in uint16 from the end of the table), runs (x offset, count, pixels) ended by (0, 0).
Colours: 15 bit 1555, 0 = transparent (gump: the high bit is not alpha; a colour of 0 is transparent, 0x8000 only is not used).
"""
import os, struct, sys
import numpy as np
from PIL import Image


def c16(v):
    r, g, b = (v >> 10) & 31, (v >> 5) & 31, v & 31
    return (r * 255 // 31, g * 255 // 31, b * 255 // 31)


def to555(r, g, b):
    return ((int(r) >> 3) << 10) | ((int(g) >> 3) << 5) | (int(b) >> 3)


def read_index(path, i):
    with open(path, "rb") as f:
        f.seek(i * 12); d = f.read(12)
    if len(d) < 12:
        return None
    lookup, length, extra = struct.unpack("<iii", d)
    return None if lookup < 0 or length <= 0 else (lookup, length, extra)


def read_gump(root, gid):
    e = read_index(os.path.join(root, "Gumpidx.mul"), gid)
    if e is None:
        return None
    lookup, length, extra = e
    w, h = (extra >> 16) & 0xFFFF, extra & 0xFFFF
    with open(os.path.join(root, "Gumpart.mul"), "rb") as f:
        f.seek(lookup); data = f.read(length)
    im = np.zeros((h, w, 4), np.uint8)
    rows = struct.unpack("<%di" % h, data[:4 * h])
    for y in range(h):
        p = rows[y] * 4; x = 0
        end = (rows[y + 1] * 4) if y + 1 < h else len(data)
        while p < end and x < w:
            col, cnt = struct.unpack("<HH", data[p:p + 4]); p += 4
            if col:
                im[y, x:x + cnt] = (*c16(col), 255)
            x += cnt
    return im


def read_art(root, iid):
    e = read_index(os.path.join(root, "artidx.mul"), 0x4000 + iid)
    if e is None:
        return None
    lookup, length, _ = e
    with open(os.path.join(root, "art.mul"), "rb") as f:
        f.seek(lookup); data = f.read(length)
    w, h = struct.unpack("<HH", data[4:8])
    tab = struct.unpack("<%dH" % h, data[8:8 + 2 * h]); base = 8 + 2 * h
    im = np.zeros((h, w, 4), np.uint8)
    for y in range(h):
        p = base + tab[y] * 2; x = 0
        while True:
            xo, cnt = struct.unpack("<HH", data[p:p + 4]); p += 4
            if xo == 0 and cnt == 0:
                break
            x += xo
            px = struct.unpack("<%dH" % cnt, data[p:p + 2 * cnt]); p += 2 * cnt
            for k, v in enumerate(px):
                im[y, x + k] = (*c16(v), 255)
            x += cnt
    return im


def encode_gump(im):
    """RGBA uint8 (h, w, 4) -> (data bytes, extra) of a gump: per row runs of non-transparent / transparent pixels"""
    h, w = im.shape[:2]
    rows, out = [], bytearray()
    for y in range(h):
        rows.append(len(out) // 4 + h)
        x = 0
        while x < w:
            op = im[y, x, 3] >= 128
            x1 = x
            while x1 < w and (im[y, x1, 3] >= 128) == op:
                x1 += 1
            if op:                                                   # a colour run: one run per colour change (a run has one colour)
                k = x
                while k < x1:
                    k1 = k
                    col = to555(*im[y, k, :3]) or 1
                    while k1 < x1 and (to555(*im[y, k1, :3]) or 1) == col:
                        k1 += 1
                    out += struct.pack("<HH", col, k1 - k); k = k1
            else:
                out += struct.pack("<HH", 0, x1 - x)
            x = x1
    return struct.pack("<%di" % h, *rows) + bytes(out), (w << 16) | h


def encode_art(im):
    """RGBA uint8 (h, w, 4) -> static art bytes (header 0, width, height, row table, runs)"""
    h, w = im.shape[:2]
    tab, out = [], bytearray()
    for y in range(h):
        tab.append(len(out) // 2)
        x, last = 0, 0
        while x < w:
            while x < w and im[y, x, 3] < 128:
                x += 1
            if x >= w:
                break
            x1 = x
            while x1 < w and im[y, x1, 3] >= 128:
                x1 += 1
            out += struct.pack("<HH", x - last, x1 - x)
            out += struct.pack("<%dH" % (x1 - x), *[(to555(*im[y, k, :3]) or 1) for k in range(x, x1)])
            last = x1; x = x1
        out += struct.pack("<HH", 0, 0)
    return struct.pack("<IHH", 0, w, h) + struct.pack("<%dH" % h, *tab) + bytes(out)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "list":
        for g in range(int(a[2]), int(a[3]) + 1):
            e = read_index(os.path.join(a[1], "Gumpidx.mul"), g)
            if e:
                print(g, (e[2] >> 16) & 0xFFFF, e[2] & 0xFFFF)
    else:
        im = (read_gump if a[0] == "gump" else read_art)(a[1], int(a[2]))
        if im is None:
            raise SystemExit("no such image")
        print(a[0], a[2], "size", im.shape[1], "x", im.shape[0])
        if len(a) > 3:
            Image.fromarray(im).save(a[3])
