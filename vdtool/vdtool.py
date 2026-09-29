#!/usr/bin/env python3
"""vdtool - rozpakowywanie i pakowanie plikow animacji Ultima Online w formacie .vd (eksport UOFiddlera).

Uzycie:
    python vdtool.py info    plik.vd
    python vdtool.py extract plik.vd  folder            [--raw]
    python vdtool.py pack    folder   nowy.vd
    python vdtool.py verify  a.vd     b.vd

Wymagania: Python 3.8+, pip install pillow numpy
Pelna instrukcja: ../README.md (PL), ../README_EN.md (EN)
"""
import json
import os
import struct
import sys

import numpy as np
from PIL import Image

MAGIC = 6
ACTIONS_BY_TYPE = {0: 22, 1: 13, 2: 35}          # animType -> liczba akcji (high / low / people)
TYPE_NAMES = {0: "high (potwory)", 1: "low (zwierzeta)", 2: "people (ludzie/ekwipunek)"}
PEOPLE_ACTIONS = [
    "walk_unarmed", "walk_armed", "run_unarmed", "run_armed", "stand", "fidget_1", "fidget_2",
    "combat_idle_1h", "combat_idle_2h", "attack_1h_slash", "attack_1h_pierce", "attack_1h_bash",
    "attack_2h_bash", "attack_2h_slash", "attack_2h_pierce", "combat_advance", "spell_directed",
    "spell_area", "attack_bow", "attack_crossbow", "get_hit", "die_forward", "die_backward",
    "mounted_walk", "mounted_run", "mounted_stand", "mounted_attack_1h", "mounted_attack_bow",
    "mounted_attack_crossbow", "mounted_attack_2h", "block", "punch", "bow", "salute", "eat"]
END = 0x7FFF7FFF
CANVAS_MARGIN = 8


# ----------------------------------------------------------------------------- kolory
def c15_to_rgb(c):
    return (((c >> 10) & 31) * 255 // 31, ((c >> 5) & 31) * 255 // 31, (c & 31) * 255 // 31)


def rgb_to_c15(rgb):
    """rgb: (...,3) uint8 -> (...,) uint16 w formacie 1-5-5-5 (bez bitu alfa)."""
    rgb = np.asarray(rgb, np.int32)
    r, g, b = [(rgb[..., i] * 31 + 127) // 255 for i in range(3)]
    c = (r << 10) | (g << 5) | b
    return np.where(c == 0, 1, c).astype(np.uint16)   # 0x0000 = przezroczystosc w kliencie -> prawie czarny


# ----------------------------------------------------------------------------- odczyt
def action_name(anim_type, a):
    if anim_type == 2 and a < len(PEOPLE_ACTIONS):
        return PEOPLE_ACTIONS[a]
    return "action"


def read_vd(path):
    d = open(path, "rb").read()
    magic, anim_type = struct.unpack_from("<hh", d, 0)
    if magic != MAGIC:
        raise ValueError(f"{path}: to nie jest plik .vd (naglowek {magic}, oczekiwano {MAGIC})")
    if anim_type not in ACTIONS_BY_TYPE:
        raise ValueError(f"{path}: nieznany typ animacji {anim_type}")
    n_act = ACTIONS_BY_TYPE[anim_type]
    blocks = []
    for i in range(n_act * 5):
        lookup, length, extra = struct.unpack_from("<iii", d, 4 + 12 * i)
        a, dr = divmod(i, 5)
        blk = dict(action=a, dir=dr, raw_index=(lookup, length, extra), palette=None, frames=[])
        if lookup > 0 and length > 0:
            pal = list(struct.unpack_from("<256H", d, lookup))
            start = lookup + 512
            (fc,) = struct.unpack_from("<i", d, start)
            offs = struct.unpack_from(f"<{fc}i", d, start + 4)
            frames = []
            for fo in offs:
                p = start + fo
                cx, cy, w, h = struct.unpack_from("<hhHH", d, p)
                p += 8
                idx = np.full((max(h, 1), max(w, 1)), -1, np.int16)   # -1 = przezroczysty
                while True:
                    (hdr,) = struct.unpack_from("<I", d, p)
                    p += 4
                    if hdr == END:
                        break
                    n = hdr & 0xFFF
                    dx = (hdr >> 22) & 0x3FF
                    dy = (hdr >> 12) & 0x3FF
                    dx = dx - 0x400 if dx & 0x200 else dx
                    dy = dy - 0x400 if dy & 0x200 else dy
                    x, y = cx + dx, cy + h + dy
                    run = np.frombuffer(d, np.uint8, n, p)
                    if 0 <= y < idx.shape[0]:                           # a few client frames have runs past
                        x0, x1 = max(x, 0), min(x + n, idx.shape[1])    # their declared size: clip them
                        if x1 > x0:
                            idx[y, x0:x1] = run[x0 - x:x1 - x]
                    p += n
                frames.append(dict(cx=cx, cy=cy, w=w, h=h, idx=idx))
            blk["palette"] = [v & 0x7FFF for v in pal]
            blk["frames"] = frames
        blocks.append(blk)
    return anim_type, blocks


def frame_rgba(frame, palette):
    idx = frame["idx"]
    rgba = np.zeros(idx.shape + (4,), np.uint8)
    lut = np.array([c15_to_rgb(c) for c in palette], np.uint8)
    m = idx >= 0
    rgba[m, :3] = lut[idx[m]]
    rgba[m, 3] = 255
    return rgba[: frame["h"], : frame["w"]]


# ----------------------------------------------------------------------------- zapis
def encode_frame(idx, cx, cy):
    """idx: (h,w) int16, -1 = przezroczysty. Zwraca bajty ramki (naglowek + RLE + terminator)."""
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
            dx = (x0 - cx) & 0x3FF
            dy = (y - cy - h) & 0x3FF
            out += struct.pack("<I", (dx << 22) | (dy << 12) | (x - x0))
            out += bytes(row[x0:x].astype(np.uint8))
    out += struct.pack("<I", END)
    return bytes(out)


def build_palette(images, original=None):
    """images: lista RGBA uint8. Zwraca (paleta[256] w 15-bit, lista map indeksow z -1 dla przezroczystosci)."""
    masks = [im[..., 3] >= 128 for im in images]
    c15 = [rgb_to_c15(im[..., :3]) for im in images]
    used = np.unique(np.concatenate([c[m] for c, m in zip(c15, masks)] + [np.zeros(0, np.uint16)]))
    if original is not None and set(used.tolist()) <= set(original):
        palette = list(original)                       # niezmienione kolory -> ta sama paleta co w oryginale
    elif len(used) <= 256:
        palette = used.tolist() + [0] * (256 - len(used))
    else:                                               # >256 kolorow: kwantyzacja wspolna dla calego bloku
        opaque = np.concatenate([im[m][:, :3] for im, m in zip(images, masks)])
        side = int(np.ceil(np.sqrt(len(opaque))))
        tile = np.zeros((side * side, 3), np.uint8)
        tile[: len(opaque)] = opaque
        q = Image.fromarray(tile.reshape(side, side, 3)).quantize(256, method=Image.Quantize.MEDIANCUT,
                                                                  dither=Image.Dither.NONE)
        pal_rgb = np.array(q.getpalette()[: 256 * 3], np.uint8).reshape(-1, 3)
        palette = np.unique(rgb_to_c15(pal_rgb)).tolist()
        palette += [0] * (256 - len(palette))
        print(f"    uwaga: {len(used)} kolorow w bloku -> zredukowano do {len([c for c in palette if c])}")
    pal_arr = np.array(palette, np.int64)
    pal_rgb = np.array([c15_to_rgb(c) for c in palette], np.int64)
    lookup = {c: i for i, c in reversed(list(enumerate(palette))) if c}
    idx_maps = []
    for im, c, m in zip(images, c15, masks):
        idx = np.full(m.shape, -1, np.int16)
        cc = c[m]
        direct = np.array([lookup.get(int(v), -1) for v in cc], np.int16)
        miss = direct < 0
        if miss.any():                                  # najblizszy kolor palety
            src = im[m][miss][:, :3].astype(np.int64)
            valid = pal_arr > 0
            dist = ((src[:, None, :] - pal_rgb[None, valid, :]) ** 2).sum(-1)
            direct[miss] = np.nonzero(valid)[0][dist.argmin(1)]
        idx[m] = direct
        idx_maps.append(idx)
    return palette, idx_maps


def write_vd(path, anim_type, blocks):
    """blocks: lista (w kolejnosci akcja*5+kierunek) dict(palette, frames=[dict(cx,cy,idx)]) lub None."""
    n = len(blocks)
    head = bytearray(struct.pack("<hh", MAGIC, anim_type))
    body = bytearray()
    base = 4 + 12 * n
    for blk in blocks:
        if blk is None or not blk["frames"]:
            head += struct.pack("<iii", -1, -1, -1)
            continue
        fr_bytes = [encode_frame(f["idx"], f["cx"], f["cy"]) for f in blk["frames"]]
        data = bytearray(struct.pack("<256H", *blk["palette"]))
        data += struct.pack("<i", len(fr_bytes))
        off = 4 + 4 * len(fr_bytes)
        for fb in fr_bytes:
            data += struct.pack("<i", off)
            off += len(fb)
        for fb in fr_bytes:
            data += fb
        head += struct.pack("<iii", base + len(body), len(data), 0)
        body += data
    with open(path, "wb") as fh:
        fh.write(head + body)


# ----------------------------------------------------------------------------- komendy
def block_dir(root, anim_type, a, d):
    return os.path.join(root, "frames", f"{a:02d}_{action_name(anim_type, a)}", f"dir{d}")


def cmd_info(path):
    anim_type, blocks = read_vd(path)
    n_act = ACTIONS_BY_TYPE[anim_type]
    print(f"{path}: typ {anim_type} = {TYPE_NAMES[anim_type]}, {n_act} akcji x 5 kierunkow")
    tot = 0
    for a in range(n_act):
        counts = [len(blocks[a * 5 + d]["frames"]) for d in range(5)]
        tot += sum(counts)
        print(f"  {a:2d} {action_name(anim_type, a):24s} klatki na kierunek: {counts}")
    print(f"razem klatek: {tot}")


def cmd_extract(path, out, raw=False):
    anim_type, blocks = read_vd(path)
    n_act = ACTIONS_BY_TYPE[anim_type]
    # wspolne plotno: wszystkie klatki wyrownane do tego samego punktu zaczepienia (ANCHOR)
    ext = [0, 0, 0, 0]  # max w lewo, w prawo, w gore, w dol od punktu zaczepienia
    for b in blocks:
        for f in b["frames"]:
            ext[0] = max(ext[0], f["cx"]); ext[1] = max(ext[1], f["w"] - f["cx"])
            ext[2] = max(ext[2], f["cy"] + f["h"]); ext[3] = max(ext[3], -f["cy"])
    ax, ay = ext[0] + CANVAS_MARGIN, ext[2] + CANVAS_MARGIN
    cw, ch = ax + ext[1] + CANVAS_MARGIN, ay + ext[3] + CANVAS_MARGIN
    meta = dict(tool="vdtool", source=os.path.basename(path), anim_type=anim_type, actions=n_act,
                mode="raw" if raw else "canvas", canvas=[cw, ch], anchor=[ax, ay], blocks=[])
    for b in blocks:
        a, d = b["action"], b["dir"]
        bd = block_dir(out, anim_type, a, d)
        os.makedirs(bd, exist_ok=True)
        entry = dict(action=a, dir=d, name=action_name(anim_type, a), frames=[], palette=b["palette"],
                     raw_index=list(b["raw_index"]))
        for i, f in enumerate(b["frames"]):
            rgba = frame_rgba(f, b["palette"])
            fn = f"{i:02d}.png"
            if raw:
                Image.fromarray(rgba).save(os.path.join(bd, fn))
            else:
                canvas = np.zeros((ch, cw, 4), np.uint8)
                x0, y0 = ax - f["cx"], ay - (f["cy"] + f["h"])
                canvas[y0:y0 + f["h"], x0:x0 + f["w"]] = rgba
                Image.fromarray(canvas).save(os.path.join(bd, fn))
            entry["frames"].append(dict(file=fn, cx=f["cx"], cy=f["cy"], w=f["w"], h=f["h"]))
        meta["blocks"].append(entry)
    with open(os.path.join(out, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=1)
    n = sum(len(b["frames"]) for b in blocks)
    print(f"rozpakowano {n} klatek do {out}/frames  (tryb {meta['mode']}"
          + ("" if raw else f", plotno {cw}x{ch}, punkt zaczepienia {ax},{ay}") + ")")


def cmd_pack(folder, out):
    meta = json.load(open(os.path.join(folder, "meta.json"), encoding="utf-8"))
    anim_type, raw = meta["anim_type"], meta["mode"] == "raw"
    ax, ay = meta["anchor"]
    blocks = []
    warn = 0
    for e in meta["blocks"]:
        a, d = e["action"], e["dir"]
        bd = block_dir(folder, anim_type, a, d)
        files = sorted(f for f in os.listdir(bd) if f.lower().endswith(".png")) if os.path.isdir(bd) else []
        imgs, centers = [], []
        known = {fr["file"]: fr for fr in e["frames"]}
        for fn in files:
            im = np.array(Image.open(os.path.join(bd, fn)).convert("RGBA"))
            if raw:
                fr = known.get(fn)
                if fr is None:
                    raise SystemExit(f"{bd}/{fn}: w trybie --raw nie mozna dodawac klatek (brak srodka w meta.json)")
                if im.shape[1] != fr["w"] or im.shape[0] != fr["h"]:
                    raise SystemExit(f"{bd}/{fn}: w trybie --raw nie wolno zmieniac rozmiaru klatki")
                imgs.append(im); centers.append((fr["cx"], fr["cy"]))
            else:
                m = im[..., 3] >= 128
                if not m.any():
                    imgs.append(np.zeros((1, 1, 4), np.uint8)); centers.append((0, -1))   # pusta klatka 1x1
                    continue
                ys, xs = np.nonzero(m)
                y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
                crop = im[y0:y1, x0:x1]
                h = y1 - y0
                imgs.append(crop); centers.append((int(ax - x0), int((ay - y0) - h)))
        if not imgs:
            blocks.append(None)
            continue
        palette, idx_maps = build_palette(imgs, e.get("palette"))
        blocks.append(dict(palette=palette,
                           frames=[dict(cx=c[0], cy=c[1], idx=ix) for c, ix in zip(centers, idx_maps)]))
    n_act = meta["actions"]
    for a in range(n_act):
        counts = [len(blocks[a * 5 + d]["frames"]) if blocks[a * 5 + d] else 0 for d in range(5)]
        if len(set(counts)) > 1:
            warn += 1
            print(f"  uwaga: akcja {a} ma rozna liczbe klatek w kierunkach: {counts}")
    write_vd(out, anim_type, blocks)
    print(f"zapisano {out}" + (f"  ({warn} ostrzezen)" if warn else ""))


def cmd_verify(p1, p2):
    t1, b1 = read_vd(p1)
    t2, b2 = read_vd(p2)
    if t1 != t2 or len(b1) != len(b2):
        print("ROZNE: typ lub liczba blokow"); return 1
    diff = 0
    for x, y in zip(b1, b2):
        if len(x["frames"]) != len(y["frames"]):
            print(f"  akcja {x['action']} kier. {x['dir']}: liczba klatek {len(x['frames'])} vs {len(y['frames'])}")
            diff += 1; continue
        for i, (f, g) in enumerate(zip(x["frames"], y["frames"])):
            A, B = frame_rgba(f, x["palette"]), frame_rgba(g, y["palette"])
            ax_, ay_ = f["cx"], f["cy"] + f["h"]
            bx_, by_ = g["cx"], g["cy"] + g["h"]
            # porownanie po wyrownaniu do punktu zaczepienia
            W = max(ax_, bx_) + max(f["w"] - ax_, g["w"] - bx_)
            H = max(ay_, by_) + max(f["h"] - ay_, g["h"] - by_)
            ca = np.zeros((H, W, 4), np.uint8); cb = ca.copy()
            ox, oy = max(ax_, bx_), max(ay_, by_)
            ca[oy - ay_:oy - ay_ + f["h"], ox - ax_:ox - ax_ + f["w"]] = A
            cb[oy - by_:oy - by_ + g["h"], ox - bx_:ox - bx_ + g["w"]] = B
            if not np.array_equal(ca, cb):
                diff += 1
                print(f"  akcja {x['action']} kier. {x['dir']} klatka {i}: piksele sie roznia")
    same_bytes = open(p1, "rb").read() == open(p2, "rb").read()
    print("IDENTYCZNE BAJT W BAJT" if same_bytes else ("OBRAZ IDENTYCZNY (inne kodowanie)" if not diff else f"ROZNIC: {diff}"))
    return 0 if not diff else 1


def main(argv):
    if len(argv) < 3 or argv[1] not in ("info", "extract", "pack", "verify"):
        print(__doc__); return 2
    cmd = argv[1]
    if cmd == "info":
        cmd_info(argv[2])
    elif cmd == "extract":
        cmd_extract(argv[2], argv[3], raw="--raw" in argv)
    elif cmd == "pack":
        cmd_pack(argv[2], argv[3])
    elif cmd == "verify":
        return cmd_verify(argv[2], argv[3])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
