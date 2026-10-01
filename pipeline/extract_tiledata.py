"""Wearable items of the UO client joined with their animation and with the measured extents.

tiledata.mul (High Seas layout: 0x4000 land tiles of 30 bytes, 0x10000 item tiles of 41 bytes, a 4-byte header before every
32 tiles) gives for every wearable item its animation id and layer. Bodyconv.def says in which file the animation lives
(orig -> anim2 / anim3 / anim4 / anim5 id; no line = same id in anim.mul). equipment_extent.json (measure_equipment_extent.py)
gives the extent of that animation around the anchor.

    python extract_tiledata.py <tiledata.mul> <Bodyconv.def> <equipment_extent.json> <out.json>
"""
import json, struct, sys
from collections import defaultdict

LAYERS = {1: "OneHanded", 2: "TwoHanded", 3: "Shoes", 4: "Pants", 5: "Shirt", 6: "Helm", 7: "Gloves", 8: "Ring", 9: "Talisman",
          10: "Neck", 11: "Hair", 12: "Waist", 13: "InnerTorso", 14: "Bracelet", 16: "FacialHair", 17: "MiddleTorso",
          18: "Earrings", 19: "Arms", 20: "Cloak", 21: "Backpack", 22: "OuterTorso", 23: "OuterLegs", 24: "InnerLegs"}
WEARABLE = 0x00400000
FILES = ("anim2", "anim3", "anim4", "anim5")
CANVASES = {"136x120": dict(left=68, right=68, up=86, down=34), "256x256": dict(left=128, right=128, up=192, down=64)}


def read_items(path):
    d = open(path, "rb").read()
    off = 512 * (4 + 32 * 30)                                  # land tiles
    items = []
    for g in range(0x10000 // 32):
        off += 4
        for i in range(32):
            flags, weight, quality, misc, unk2, qty, anim, unk3, hue, stack, value, height = struct.unpack_from("<QBBHBBHBBBBB", d, off)
            name = d[off + 21:off + 41].split(b"\0")[0].decode("latin-1")
            items.append((g * 32 + i, flags, quality, anim, name))
            off += 41
    assert off == len(d), (off, len(d))
    return items


def read_bodyconv(path):
    m = {}
    for line in open(path, encoding="latin-1"):
        line = line.split("#")[0].strip()
        t = line.split()
        if len(t) >= 5 and all(x.lstrip("-").isdigit() for x in t[:5]):
            o, *a = [int(x) for x in t[:5]]
            for f, v in zip(FILES, a):
                if v >= 0:
                    m[o] = (f, v)
                    break
    return m


if __name__ == "__main__":
    tdata, bconv, ext_path, out = sys.argv[1:5]
    ext = json.load(open(ext_path))["bodies"]
    conv = read_bodyconv(bconv)
    anims = defaultdict(lambda: dict(layers=set(), items=[]))
    for tid, flags, layer, anim, name in read_items(tdata):
        if flags & WEARABLE and anim:
            a = anims[anim]
            a["layers"].add(layer)
            a["items"].append((tid, name))
    res = {}
    for anim, a in sorted(anims.items()):
        src = "%s:%d" % conv.get(anim, ("anim", anim))
        e = ext.get(src)
        res[anim] = dict(src=src, layers=sorted(a["layers"]), n_items=len(a["items"]), items=a["items"][:6],
                         extent={k: e[k] for k in ("left", "right", "up", "down")} if e else None, frames=e["frames"] if e else 0,
                         complete=bool(e and e["blocks"] == 175))
    stats = {}
    print("wearable animation ids: %d, with frames in the client: %d" % (len(res), sum(1 for r in res.values() if r["extent"])))
    for layer in sorted({l for r in res.values() for l in r["layers"]}):
        rows = [r for r in res.values() if layer in r["layers"] and r["extent"]]
        if not rows:
            continue
        s = {"animations": len(rows)}
        for cname, cv in CANVASES.items():
            out_ = [r for r in rows if any(r["extent"][k] > cv[k] for k in cv)]
            s["over_" + cname] = len(out_)
            s["max_over_" + cname] = max((max(r["extent"][k] - cv[k] for k in cv) for r in rows), default=0)
        stats[LAYERS.get(layer, str(layer))] = s
        print("%-12s %3d animations | outside 136x120: %3d (worst +%3d px) | outside 256x256: %2d (worst +%3d px)" % (
            LAYERS.get(layer, layer), s["animations"], s["over_136x120"], s["max_over_136x120"], s["over_256x256"], s["max_over_256x256"]))
    out_rows = [(a, r) for a, r in res.items() if r["extent"] and any(r["extent"][k] > CANVASES["256x256"][k] for k in CANVASES["256x256"])]
    print("outside 256x256:")
    for a, r in out_rows:
        print("  anim id %4d (%s) layers %s extent %s items %s" % (a, r["src"], [LAYERS.get(l, l) for l in r["layers"]], r["extent"], [n for _, n in r["items"][:3]]))
    json.dump(dict(layers=LAYERS, stats_by_layer=stats, animations={str(a): r for a, r in res.items()}), open(out, "w"), indent=1)
