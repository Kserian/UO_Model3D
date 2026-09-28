"""Minimal .vd (UOFiddler animation export) writer: numpy only, usable inside Blender.

frames are RGBA uint8 arrays on a canvas where the character's ground point is at pixel (anchor_x, anchor_y).
Same format as vdtool.py (see README.md)."""
import struct
import numpy as np

MAGIC = 6
END = 0x7FFF7FFF
ACTIONS_BY_TYPE = {0: 22, 1: 13, 2: 35}


def rgb_to_c15(rgb):
    rgb = np.asarray(rgb, np.int32)
    r, g, b = [(rgb[..., i] * 31 + 127) // 255 for i in range(3)]
    c = (r << 10) | (g << 5) | b
    return np.where(c == 0, 1, c).astype(np.int64)      # 0x0000 is transparent in the client


def c15_to_rgb(c):
    c = np.asarray(c, np.int64)
    return np.stack([((c >> 10) & 31) * 255 // 31, ((c >> 5) & 31) * 255 // 31, (c & 31) * 255 // 31], -1)


def median_cut(colors, counts, n=256):
    """colors (K,3) int, counts (K,) -> palette (<=n,3) float."""
    boxes = [np.arange(len(colors))]
    while len(boxes) < n:
        spans = [np.ptp(colors[b], axis=0).max() if len(b) > 1 else -1 for b in boxes]
        i = int(np.argmax(spans))
        if spans[i] <= 0:
            break
        b = boxes.pop(i)
        ax = int(np.argmax(np.ptp(colors[b], axis=0)))
        order = b[np.argsort(colors[b, ax])]
        cum = np.cumsum(counts[order])
        k = int(np.searchsorted(cum, cum[-1] / 2)) + 1
        k = min(max(k, 1), len(order) - 1)
        boxes += [order[:k], order[k:]]
    return np.array([np.average(colors[b], axis=0, weights=counts[b]) for b in boxes])


def build_palette(images):
    """images: list of RGBA uint8. Returns (palette[256] 15-bit ints, list of index maps (-1 = transparent))."""
    masks = [im[..., 3] >= 128 for im in images]
    c15 = [rgb_to_c15(im[..., :3]) for im in images]
    allc = np.concatenate([c[m] for c, m in zip(c15, masks)] + [np.zeros(0, np.int64)])
    used, counts = np.unique(allc, return_counts=True)
    if len(used) <= 256:
        palette = used.tolist()
    else:
        pal_rgb = median_cut(c15_to_rgb(used).astype(np.float64), counts.astype(np.float64), 256)
        palette = np.unique(rgb_to_c15(np.round(pal_rgb))).tolist()
    palette = palette + [0] * (256 - len(palette))
    pal_rgb = c15_to_rgb(np.array(palette)).astype(np.int64)
    valid = np.array(palette) > 0
    lut = {c: i for i, c in enumerate(palette) if c}
    maps = []
    for im, c, m in zip(images, c15, masks):
        idx = np.full(m.shape, -1, np.int16)
        cc = c[m]
        direct = np.array([lut.get(int(v), -1) for v in cc], np.int16)
        miss = direct < 0
        if miss.any():
            src = c15_to_rgb(cc[miss]).astype(np.int64)
            dist = ((src[:, None, :] - pal_rgb[None, valid, :]) ** 2).sum(-1)
            direct[miss] = np.nonzero(valid)[0][dist.argmin(1)]
        idx[m] = direct
        maps.append(idx)
    return palette, maps


def crop_frame(rgba, anchor_x, anchor_y):
    """Canvas RGBA -> (cropped RGBA, centerX, centerY). Empty frame -> 1x1 transparent."""
    m = rgba[..., 3] >= 128
    if not m.any():
        return np.zeros((1, 1, 4), np.uint8), 0, -1
    ys, xs = np.nonzero(m)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    crop = rgba[y0:y1, x0:x1]
    return crop, int(anchor_x - x0), int((anchor_y - y0) - (y1 - y0))


def encode_frame(idx, cx, cy):
    h, w = idx.shape
    out = bytearray(struct.pack("<hhHH", cx, cy, w, h))
    for y in range(h):
        row = idx[y]
        x = 0
        while x < w:
            if row[x] < 0:
                x += 1
                continue
            x0 = x
            while x < w and row[x] >= 0 and x - x0 < 0xFFF:
                x += 1
            out += struct.pack("<I", (((x0 - cx) & 0x3FF) << 22) | (((y - cy - h) & 0x3FF) << 12) | (x - x0))
            out += bytes(row[x0:x].astype(np.uint8))
    out += struct.pack("<I", END)
    return bytes(out)


def write_vd(path, frames_by_block, anim_type=2, anchor=(68, 86)):
    """frames_by_block: dict (action, direction) -> list of canvas RGBA frames. Missing blocks are written empty."""
    n = ACTIONS_BY_TYPE[anim_type] * 5
    head = bytearray(struct.pack("<hh", MAGIC, anim_type))
    body = bytearray()
    base = 4 + 12 * n
    for i in range(n):
        a, d = divmod(i, 5)
        fr = frames_by_block.get((a, d))
        if not fr:
            head += struct.pack("<iii", -1, -1, -1)
            continue
        crops = [crop_frame(f, *anchor) for f in fr]
        palette, maps = build_palette([c[0] for c in crops])
        fb = [encode_frame(ix, c[1], c[2]) for ix, c in zip(maps, crops)]
        data = bytearray(struct.pack("<256H", *palette))
        data += struct.pack("<i", len(fb))
        off = 4 + 4 * len(fb)
        for b in fb:
            data += struct.pack("<i", off)
            off += len(b)
        for b in fb:
            data += b
        head += struct.pack("<iii", base + len(body), len(data), 0)
        body += data
    with open(path, "wb") as fh:
        fh.write(head + body)
