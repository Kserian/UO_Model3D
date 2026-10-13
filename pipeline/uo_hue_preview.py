"""How images (item art, paperdoll gumps) look dyed with hues of the client's hues.mul, as the client draws them.

    python uo_hue_preview.py HUES.mul OUT.png [--hues 2419,2213,...] [--partial 0|1|both] [--zoom 3] [--crop x0,y0,x1,y1] LABEL=IMG.png ...

hues.mul: blocks of a 4-byte header + 8 hues; a hue = 32 colours (15-bit, dark to light), table start, table end (uint16), name (20 bytes). Hue number N (as on the
server, 1-based) = block (N - 1) // 8, entry (N - 1) % 8.
The client dyes a pixel by its red channel: colour = hue[red >> 3] (5-bit red = index of the hue's 32 colours). Without the tiledata flag PartialHue (0x00040000) every
pixel is dyed (a brown haft takes the hue's light end, its red is high); with it only the grey pixels (R = G = B).
Rows: the images; columns: undyed, then each hue (with --partial both: every hue twice, full / partial).
"""
import struct, sys
import numpy as np
from PIL import Image, ImageDraw

ORE = (2419, 2406, 2413, 2418, 2213, 2425, 2207, 2219)   # RunUO ore hues: dull copper, shadow iron, copper, bronze, gold, agapite, verite, valorite


def read_hues(path):
    d = open(path, "rb").read(); out = []
    for b in range(len(d) // 708):
        for e in range(8):
            o = b * 708 + 4 + e * 88
            cols = struct.unpack_from("<32H", d, o)
            name = d[o + 68:o + 88].split(b"\0")[0].decode("latin-1")
            out.append((np.array(cols, np.int32), name))
    return out


def c555(v):
    v = np.asarray(v, np.int32)
    return np.stack([((v >> 10) & 31) * 255 // 31, ((v >> 5) & 31) * 255 // 31, (v & 31) * 255 // 31], -1).astype(np.uint8)


def dye(im, hue_cols, partial):
    """RGBA uint8 -> dyed RGBA: index = 5-bit red; partial: only R = G = B pixels (compared in 15 bits)"""
    out = im.copy(); m = im[..., 3] > 0
    r5, g5, b5 = (im[..., 0].astype(np.int32) >> 3), (im[..., 1].astype(np.int32) >> 3), (im[..., 2].astype(np.int32) >> 3)
    sel = m & ((r5 == g5) & (g5 == b5) if partial else True)
    out[sel, :3] = c555(hue_cols[r5[sel]])
    return out


def main(a):
    hues_path, out = a[0], a[1]; hues = list(ORE); partial = "0"; zoom = 3; crop = None; imgs = []
    i = 2
    while i < len(a):
        if a[i] == "--hues":
            hues = [int(x) for x in a[i + 1].split(",")]; i += 2
        elif a[i] == "--partial":
            partial = a[i + 1]; i += 2
        elif a[i] == "--zoom":
            zoom = int(a[i + 1]); i += 2
        elif a[i] == "--crop":
            crop = [int(x) for x in a[i + 1].split(",")]; i += 2
        else:
            lab, p = a[i].split("=", 1); imgs.append((lab, np.array(Image.open(p).convert("RGBA")))); i += 1
    table = read_hues(hues_path)
    modes = {"0": [False], "1": [True], "both": [False, True]}[partial]
    cols = [("undyed", None, False)] + [(("%d%s" % (h, " P" if pm else "")), h, pm) for h in hues for pm in modes]
    cells = []
    for lab, im in imgs:
        if crop:
            im = im[crop[1]:crop[3], crop[0]:crop[2]]
        row = []
        for cl, h, pm in cols:
            d = im if h is None else dye(im, table[h - 1][0], pm)
            bg = np.zeros(d.shape[:2] + (3,), np.uint8); bg[:] = (52, 52, 52); m = d[..., 3] > 0; bg[m] = d[m][:, :3]
            row.append(Image.fromarray(bg).resize((d.shape[1] * zoom, d.shape[0] * zoom), Image.NEAREST))
        cells.append((lab, row))
    cw = max(t.size[0] for _, r in cells for t in r) + 4; chh = max(t.size[1] for _, r in cells for t in r) + 4
    S = Image.new("RGB", (90 + len(cols) * cw, 14 + len(cells) * chh), (20, 20, 20)); dr = ImageDraw.Draw(S)
    for j, (cl, h, pm) in enumerate(cols):
        dr.text((90 + j * cw + 2, 2), cl + ("" if h is None else " " + table[h - 1][1][:10]), fill=(230, 230, 230))
    for i_, (lab, row) in enumerate(cells):
        dr.text((2, 14 + i_ * chh + 2), lab, fill=(255, 255, 0))
        for j, t in enumerate(row):
            S.paste(t, (90 + j * cw, 14 + i_ * chh))
    S.save(out); print("uo_hue_preview:", out, S.size)


if __name__ == "__main__":
    main(sys.argv[1:])
