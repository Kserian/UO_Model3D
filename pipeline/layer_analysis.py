"""Analysis A: what every wearable layer of the original client looks like next to the body, from the `stand` frames (no Cycles).

    python layer_analysis.py <client dir with anim*.idx/.mul + tiledata data> <parts.npz> <out.json> [--files anim,anim2,anim3,anim4,anim5]

parts.npz comes from `body_part_raster.py ../model/UO_Body_0x190.blend parts.npz --actions 4` (part labels of the 3D body in the stand pose,
canvas 145x133, anchor (75,92)). For every animation of `client/extract/item_animations.json` that has a layer < 25 (and frames in the listed files; default: all of anim, anim2, anim3, anim4, anim5 - the wearable animations in them are the game's originals)
the 5 directions of action 4 (stand), frame 0, are put on a 256x256 canvas (anchor 128,192) next to the original body 400 and measured:

 * z range of the item in the rest pose (m, ground = 0): rows -> z = 0.07 - row / (36 cos 28.4557 deg), mean of the 5 directions (the formula of
   `uo_import_item.py` EXTENTS: bottom edge of the lowest and top edge of the highest pixel row);
 * cover[part]: share of the pixels of a body part (3D body, nearest part to every body pixel of the ORIGINAL silhouette) that the item covers;
 * out[part]: distance (px, 1 px = 1/36 m = 2.78 cm) of every item pixel OUTSIDE the original body silhouette to that silhouette, grouped by the body part nearest
   to the pixel: n pixels, p50, p90, max. It is the only place where the thickness of the item can be read from a flat sprite (inside the silhouette the
   body is hidden by the item), so it is a lower bound of the standoff of the item from the skin, mostly at arms, legs, hem and neck.
Left / right parts are merged; clavicle, spine, pelvis, chest are `torso`.
"""
import json, mmap, os, struct, sys
import numpy as np
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
CW, CH, ANCH = 256, 256, (128, 192)
PXM = 36.0
COS = np.cos(np.radians(28.4557))
END = 0x7FFF7FFF
STAND = 4
GROUP = {"chest": "torso", "spine": "torso", "pelvis": "torso", "clavicle": "torso", "upper_arm": "upper_arm", "forearm": "forearm", "hand": "hand",
         "thigh": "thigh", "shin": "shin", "foot": "foot", "head": "head", "neck": "neck"}
ORDER = ["head", "neck", "torso", "upper_arm", "forearm", "hand", "thigh", "shin", "foot"]


class Files:
    def __init__(self, src):
        self.src, self.cache = src, {}

    def get(self, tag):
        if tag not in self.cache:
            ip, mp = os.path.join(self.src, tag + ".idx"), os.path.join(self.src, tag + ".mul")
            if not (os.path.exists(ip) and os.path.exists(mp)):
                self.cache[tag] = None
            else:
                with open(mp, "rb") as f:
                    self.cache[tag] = (open(ip, "rb").read(), mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ))
        return self.cache[tag]


def stand_mask(fl, tag, body, d):
    """opaque mask of frame 0 of (stand, dir d) of people / equipment id `body` on the 256x256 canvas, or None"""
    f = fl.get(tag)
    if f is None:
        return None
    idx, mm = f
    e = 35000 + (body - 400) * 175 + STAND * 5 + d
    if 12 * (e + 1) > len(idx):
        return None
    look, length, _ = struct.unpack_from("<iii", idx, 12 * e)
    if look <= 0 or length <= 0 or look + length > len(mm):
        return None
    cnt, = struct.unpack_from("<i", mm, look + 512)
    if cnt < 1:
        return None
    off, = struct.unpack_from("<i", mm, look + 516)
    p = look + 512 + off
    cx, cy, w, h = struct.unpack_from("<hhHH", mm, p)
    p += 8
    m = np.zeros((CH, CW), bool)
    x_org, y_org = ANCH[0] - cx, ANCH[1] - cy - h
    while True:
        hdr, = struct.unpack_from("<I", mm, p)
        p += 4
        if hdr == END:
            break
        n = hdr & 0xFFF
        dx = (hdr >> 22) & 0x3FF
        dy = (hdr >> 12) & 0x3FF
        dx = dx - 0x400 if dx & 0x200 else dx
        dy = dy - 0x400 if dy & 0x200 else dy
        x, y = ANCH[0] + dx, ANCH[1] + dy                     # (dx, dy) are relative to the anchor
        if 0 <= y < CH:
            m[y, max(x, 0):max(min(x + n, CW), 0)] = True
        p += n
    return m


def main():
    args = sys.argv[1:]
    files = ["anim", "anim2", "anim3", "anim4", "anim5"]
    if "--files" in args:
        i = args.index("--files")
        files = args[i + 1].split(",")
        del args[i:i + 2]
    src, parts_npz, out = args
    z = np.load(parts_npz)
    names = [str(n) for n in z["parts"]]
    gname = [GROUP[n.split(".")[0]] for n in names]
    lab_small = z["lab"]                                            # (5, 133, 145), anchor (75, 92)
    dirs = {int(k[1]): i for i, k in enumerate(z["key"]) if int(k[0]) == STAND and int(k[2]) == 0}
    fl = Files(src)
    meta = json.load(open(os.path.join(HERE, "..", "client", "extract", "item_animations.json")))
    layer_names = meta["layers"]

    body_mask, plab, near_lab, dist_out = {}, {}, {}, {}
    for d in range(5):
        B = stand_mask(fl, "anim", 400, d)
        L = np.full((CH, CW), -1, np.int16)
        s = lab_small[dirs[d]]
        L[ANCH[1] - 92:ANCH[1] - 92 + 133, ANCH[0] - 75:ANCH[0] - 75 + 145] = s
        G = np.full(L.shape, -1, np.int16)
        for pi, g in enumerate(gname):
            G[L == pi] = ORDER.index(g)
        # nearest 3D part label for every pixel of the canvas
        _, (iy, ix) = ndimage.distance_transform_edt(G < 0, return_indices=True)
        body_mask[d], plab[d], near_lab[d] = B, G, G[iy, ix]
        dist_out[d] = ndimage.distance_transform_edt(~B)            # distance to the original silhouette (0 inside)

    res = {}
    for key, v in meta["animations"].items():
        lays = [l for l in v["layers"] if l < 25]
        tag, _, lid = v["src"].partition(":")
        if not lays or not v["frames"] or tag not in files:
            continue
        ms = [stand_mask(fl, tag, int(lid), d) for d in range(5)]
        if any(m is None or not m.any() for m in ms):
            continue
        zlo = zhi = 0.0
        cover = {g: [] for g in ORDER}
        outd = {g: [] for g in ORDER}
        for d, m in enumerate(ms):
            rows = np.nonzero(m.any(1))[0]
            zhi += 0.07 - (rows[0] - ANCH[1]) / (PXM * COS)
            zlo += 0.07 - (rows[-1] + 1 - ANCH[1]) / (PXM * COS)
            for gi, g in enumerate(ORDER):
                sel = (plab[d] == gi) | ((near_lab[d] == gi) & body_mask[d])
                if sel.sum():
                    cover[g].append((m & sel).sum() / sel.sum())
            o = m & ~body_mask[d]
            for gi, g in enumerate(ORDER):
                dd = dist_out[d][o & (near_lab[d] == gi)]
                if dd.size:
                    outd[g].append(dd)
        rec = dict(src=v["src"], items=[n for _, n in v["items"]][:3], layers=[layer_names[str(l)] for l in lays],
                   zlo=round(zlo / 5, 3), zhi=round(zhi / 5, 3),
                   cover={g: round(float(np.mean(c)), 3) for g, c in cover.items() if c},
                   out={})
        for g, ds in outd.items():
            if not ds:
                continue
            dd = np.concatenate(ds)
            rec["out"][g] = dict(n=int(len(dd) / 5), p50=round(float(np.percentile(dd, 50)), 2), p90=round(float(np.percentile(dd, 90)), 2),
                                 max=round(float(dd.max()), 2))
        res[key] = rec
    json.dump(dict(canvas=[CW, CH], anchor=ANCH, files=files, animations=res), open(out, "w"), indent=1)
    print("%d animations measured" % len(res))


if __name__ == "__main__":
    main()
