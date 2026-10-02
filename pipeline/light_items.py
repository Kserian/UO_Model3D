"""Light / shadow statistics of every wearable animation of the client against the lighting of the 3D body.

    python light_items.py <client dir> <light_table.npz> <out.json> [--stride 2] [--procs 4]

light_table.npz: the output of `light_data.load` saved with np.savez (pixels of the 3D body that the ORIGINAL body frames also cover: normal, self-shadow flag...).
For every people / equipment animation of client/extract/item_animations.json (layers < 25, in anim..anim5) and every frame of the body table (every `stride`-th
frame; mounted actions are not in the table) the item's pixels that lie on a body-model pixel are taken. The item hugs the body (shirt, armour, trousers...), so the
normal of the BODY at that pixel stands for the normal of the item; loose items (robe, cloak, hair, wings) are poorer proxies - the result is a statistic over
hundreds of animations, not a measurement of one. Per animation (linear light = sRGB decoded, mean of R, G, B):
  n          pixels used
  r2_lam     share of the variance of the item's light explained by  A * (0.0798 + 0.9202 * max(n.L, 0))   (A fitted; the item's albedo is taken as uniform)
  A          that albedo
  ks, r2_spec  the same with  + ks * max(n.L, 0)^16   (a metal highlight): ks (in linear light) and the new share explained
  hi99, med  99th percentile and median of the item's light;   top_c: mean n.L of the brightest 1 % of the pixels
  curve      median light in the bins of n.L  [0, .3, .5, .6, .7, .8, .9, .95, 1]  (Lambert: rises about 1.9x from n.L 0.4 to 1)
  shadow     median of  light / (A * S)  for pixels the body shadows itself (ray to the UO light blocked) and for the others (lit), with the counts
"""
import json, mmap, os, struct, sys
from multiprocessing import Pool

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CW, CH, ANCH = 145, 133, (75, 92)
END = 0x7FFF7FFF
dec = lambda v: np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)
_G = {}


def init(src, table, stride):
    _G["src"], _G["stride"] = src, stride
    z = np.load(table)
    keep = ("action", "dir", "frame", "y", "x", "N", "lit", "ao", "part")
    D = {k: z[k] for k in keep}
    order = np.lexsort((D["frame"], D["dir"], D["action"]))
    D = {k: v[order] for k, v in D.items()}
    code = D["action"].astype(np.int64) * 100000 + D["dir"].astype(np.int64) * 1000 + D["frame"]
    u, st = np.unique(code, return_index=True)
    en = np.r_[st[1:], len(code)]
    _G["D"], _G["frames"] = D, [(int(c // 100000), int(c // 1000 % 100), int(c % 1000), s, e) for c, s, e in zip(u, st, en)]
    _G["L"] = np.array([0.00124641, -0.75721306, 0.65316677])
    _G["files"] = {}


def open_files(tag):
    if tag not in _G["files"]:
        ip, mp = os.path.join(_G["src"], tag + ".idx"), os.path.join(_G["src"], tag + ".mul")
        if os.path.exists(ip) and os.path.exists(mp):
            fh = open(mp, "rb")                              # kept open for the life of the mmap
            _G["files"][tag] = (open(ip, "rb").read(), mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ), fh)
        else:
            _G["files"][tag] = None
    return _G["files"][tag]


def decode(idx, mm, body, action, d, i):
    """RGB (CH, CW, 3) uint8 and mask of frame i of (action, dir d) of people / equipment id `body` on the canvas of the original body frames, or None"""
    e = 35000 + (body - 400) * 175 + action * 5 + d
    if 12 * (e + 1) > len(idx):
        return None
    look, length, _ = struct.unpack_from("<iii", idx, 12 * e)
    if look <= 0 or length <= 0 or look + length > len(mm):
        return None
    cnt, = struct.unpack_from("<i", mm, look + 512)
    if i >= cnt:
        return None
    pal = np.frombuffer(mm, "<u2", 256, look).astype(np.int32)
    lut = np.stack([((pal >> 10) & 31) * 255 // 31, ((pal >> 5) & 31) * 255 // 31, (pal & 31) * 255 // 31], 1).astype(np.uint8)
    off, = struct.unpack_from("<i", mm, look + 516 + 4 * i)
    p = look + 512 + off
    cx, cy, w, h = struct.unpack_from("<hhHH", mm, p)
    p += 8
    img = np.zeros((CH, CW, 3), np.uint8); m = np.zeros((CH, CW), bool)
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
        x, y = ANCH[0] + dx, ANCH[1] + dy
        if 0 <= y < CH and n > 0:
            x0, x1 = max(x, 0), min(x + n, CW)
            if x1 > x0:
                idxs = np.frombuffer(mm, np.uint8, n, p)[x0 - x:x1 - x]
                img[y, x0:x1] = lut[idxs]; m[y, x0:x1] = True
        p += n
    return img, m


def analyse(job):
    key, src, name, layers = job
    tag, _, lid = src.partition(":")
    f = open_files(tag)
    if f is None:
        return key, None
    D, L = _G["D"], _G["L"]
    lum, cc, lit, ao = [], [], [], []
    for k, (a, d, i, s, e) in enumerate(_G["frames"]):
        if k % _G["stride"]:
            continue
        r = decode(f[0], f[1], int(lid), a, d, i)
        if r is None:
            continue
        img, m = r
        y, x = D["y"][s:e], D["x"][s:e]
        sel = m[y, x]
        if not sel.any():
            continue
        rgb = img[y[sel], x[sel]].astype(np.float64) / 255
        lum.append(dec(rgb).mean(1)); cc.append(np.maximum(D["N"][s:e][sel] @ L, 0)); lit.append(D["lit"][s:e][sel]); ao.append(D["ao"][s:e][sel])
    if not lum or sum(len(v) for v in lum) < 300:
        return key, None
    y_, c, lit, ao = np.concatenate(lum), np.concatenate(cc), np.concatenate(lit), np.concatenate(ao)
    S = 0.0798 + 0.9202 * c
    A = float((y_ * S).sum() / (S * S).sum()); res = y_ - A * S
    tot = float(((y_ - y_.mean()) ** 2).sum())
    X = np.stack([S, c ** 16], 1); coef, *_ = np.linalg.lstsq(X, y_, rcond=None)
    res2 = y_ - X @ coef
    hi = y_ >= np.percentile(y_, 99)
    sh = lit == 0
    ratio = y_ / np.maximum(A * S, 1e-4)
    edges = np.array([0, 0.3, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.01])
    b = np.digitize(c, edges) - 1
    curve = [float(np.median(y_[b == k])) if (b == k).sum() >= 100 else None for k in range(len(edges) - 1)]      # median light per bin of n.L
    out = dict(name=name, curve=curve, layers=layers, n=int(len(y_)), r2_lam=1 - float((res ** 2).sum()) / tot if tot > 0 else 0.0, A=A,
               ks=float(coef[1]), A2=float(coef[0]), r2_spec=1 - float((res2 ** 2).sum()) / tot if tot > 0 else 0.0,
               med=float(np.median(y_)), hi99=float(np.percentile(y_, 99)), top_c=float(c[hi].mean()),
               shadow=dict(n_shadow=int(sh.sum()), n_lit=int((~sh).sum()),
                           r_shadow=float(np.median(ratio[sh])) if sh.sum() >= 50 else None, r_lit=float(np.median(ratio[~sh])) if (~sh).sum() >= 50 else None))
    return key, out


def main():
    args = sys.argv[1:]
    stride, procs = 2, 4
    for fl, nm in (("--stride", "stride"), ("--procs", "procs")):
        if fl in args:
            i = args.index(fl); v = int(args[i + 1]); del args[i:i + 2]
            if nm == "stride": stride = v
            else: procs = v
    src, table, out = args
    meta = json.load(open(os.path.join(HERE, "..", "client", "extract", "item_animations.json")))
    names = meta["layers"]
    jobs = []
    for key, v in meta["animations"].items():
        lays = [l for l in v["layers"] if l < 25]
        if not lays:
            continue
        nm = "; ".join(it[1] for it in v["items"][:3])
        jobs.append((key, v["src"], nm, [names.get(str(l), str(l)) for l in lays]))
    with Pool(procs, initializer=init, initargs=(src, table, stride)) as pool:
        res = {}
        for n, (k, r) in enumerate(pool.imap_unordered(analyse, jobs, chunksize=4)):
            if r is not None:
                res[k] = r
            if n % 40 == 0:
                print(n, "/", len(jobs), flush=True)
    json.dump(res, open(out, "w"), indent=0)
    print("animations analysed:", len(res))


if __name__ == "__main__":
    main()
