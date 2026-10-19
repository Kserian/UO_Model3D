"""Scan of ALL wearable animations (`.vd` data) of the UO client against the original body 400: every action x direction x frame (no Blender).

    python vd_scan.py <client dir: anim*.idx/.mul, tiledata.mul, Bodyconv.def, Equipconv.def> <out.json> [--jobs 4] [--files anim,anim2,..] [--actions 0,4] [--parts parts.npz]

--parts: output of `body_part_raster.py ../model/UO_Body_0x190.blend parts.npz` (all actions; part labels of OUR 3D body, canvas 145x133, anchor (75,92)). Every pixel
is then also assigned to the body part nearest to it (as in `layer_analysis.py`) and `cover_part` / `out_part` are written per part.

Which animations: every wearable tile of `tiledata.mul` (flag 0x00400000, animation id != 0) -> `Equipconv.def` (body type 400: equipment id -> convert-to id)
-> the id itself when `AnimationFrame1..4.uop` has it (the client prefers them), else `Bodyconv.def` (file anim2..anim5 and id there; no line = the same id in anim.mul)
-> blocks `35000 + (id - 400) * 175 + action * 5 + dir` (35 actions x 5 directions; directions 5-7 are mirrors). Layer 25 (mounts / creatures) is skipped.
Animations that live in the .uop (see `uop.py`: gargoyle items, horns, wings, new shields, a few new human items) are NOT examined: the gargoyle ones by decision, the human
ones because their frame counts / numbering do not match the body 400 of anim.mul (stand: 6-11 frames vs 1); they are only listed (`in_uop`).
Every frame is put on a 256x256 canvas (anchor 128,192, 36 px/m) next to the SAME frame of the original body 400 (frame k of the item -> frame
k * n_body // n_item of the body when the counts differ) and measured: bbox (px from the anchor), area, share of the body silhouette that the item covers,
pixels outside the silhouette and their distance to it (histogram, 1 px = 2.78 cm), the same in 6 height bands (and, with --parts, in 9 body parts) of the body bbox
(+ above / below), pixels outside the canvas. Per (animation, action) the numbers are pooled over the directions and frames and written as JSON (aggregates only, no pixels).
"""
import json, mmap, os, struct, sys
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from numba import njit
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from extract_tiledata import read_items, read_bodyconv, LAYERS, WEARABLE
import uop

CW, CH, AX, AY = 256, 256, 128, 192
N_ACT, N_DIR = 35, 5
NB, NH = 6, 64                                   # height bands, distance histogram bins (px, the last = 63+)
END = 0x7FFF7FFF
# columns of a per-frame record
C_OK, C_X0, C_X1, C_Y0, C_Y1, C_AREA, C_IN, C_OUT, C_CLIP = range(9)
C_BIN = 9                                        # NB + 2 columns: inside-body pixels per band (band NB = above the body bbox, NB + 1 = below)
C_BOUT = C_BIN + NB + 2                          # NB + 2 columns: outside-body pixels per band
C_HIST = C_BOUT + NB + 2                         # NH columns: distance histogram of the outside pixels
C_PIN = C_HIST + NH                              # NP columns: inside-body pixels per nearest body part
C_POUT = C_PIN + 9                               # NP columns: outside-body pixels per nearest body part
C_PHIST = C_POUT + 9                             # NP x NHP columns: distance histogram of the outside pixels per part
NP, NHP = 9, 24
C_PYMAX = C_PHIST + NP * NHP                     # NP columns: lowest row of the item pixels nearest to a part (y - AY + 512, 0 = none)
C_PYMIN = C_PYMAX + NP                           # NP columns: 512 - (highest row y - AY) (0 = none)
NCOL = C_PYMIN + NP
PARTS = ["head", "neck", "torso", "upper_arm", "forearm", "hand", "thigh", "shin", "foot"]
GROUP = {"chest": "torso", "spine": "torso", "pelvis": "torso", "clavicle": "torso", "upper_arm": "upper_arm", "forearm": "forearm", "hand": "hand",
         "thigh": "thigh", "shin": "shin", "foot": "foot", "head": "head", "neck": "neck"}
PCW, PCH, PANCH = 145, 133, (75, 92)             # canvas / anchor of the part labels


def read_equipconv(path, body=400):
    m = {}
    for line in open(path, encoding="latin-1"):
        t = line.split("#")[0].split()
        if len(t) >= 3 and all(x.lstrip("-").isdigit() for x in t[:3]) and int(t[0]) == body:
            m[int(t[1])] = int(t[2])
    return m


def resolve(client):
    """wearable animations: {src: dict(layers, items, anim_ids)}; src = 'uop:<id>' or '<file>:<id>' (anim.mul .. anim5.mul)"""
    econv = read_equipconv(os.path.join(client, "Equipconv.def"))
    bconv = read_bodyconv(os.path.join(client, "Bodyconv.def"))
    tiles = [(tid, layer, anim, name) for tid, flags, layer, anim, name in read_items(os.path.join(client, "tiledata.mul"))
             if flags & WEARABLE and anim and layer < 25]
    in_uop = {b for b, _ in uop.Frames(client, {econv.get(a, a) for _, _, a, _ in tiles}).index}
    res = {}
    for tid, layer, anim, name in tiles:
        a = econv.get(anim, anim)
        src = "uop:%d" % a if a in in_uop else "%s:%d" % bconv.get(a, ("anim", a))
        r = res.setdefault(src, dict(layers=set(), items=[], anim_ids=set()))
        r["layers"].add(layer)
        r["items"].append((tid, name))
        r["anim_ids"].add(anim)
    return res


class Client:
    def __init__(self, src):
        self.src, self.c = src, {}

    def get(self, tag):
        if tag not in self.c:
            ip, mp = os.path.join(self.src, tag + ".idx"), os.path.join(self.src, tag + ".mul")
            if not (os.path.exists(ip) and os.path.exists(mp)):
                self.c[tag] = None
            else:
                self.c[tag] = (np.frombuffer(open(ip, "rb").read(), np.int32).reshape(-1, 3),
                               np.memmap(mp, np.uint8, "r"))
        return self.c[tag]

    def block(self, tag, body, a, d):
        """(mmap, offset of the block, length) or None"""
        f = self.get(tag)
        if f is None:
            return None
        idx, mm = f
        e = 35000 + (body - 400) * 175 + a * 5 + d
        if a >= N_ACT or e >= len(idx):
            return None
        look, length, _ = idx[e]
        if look < 0 or length <= 0 or look + length > len(mm):
            return None
        return mm, int(look), int(length)


@njit(cache=True)
def rd32(mm, p):
    v = np.int64(mm[p]) | np.int64(mm[p + 1]) << 8 | np.int64(mm[p + 2]) << 16 | np.int64(mm[p + 3]) << 24
    return v - 0x100000000 if v >= 0x80000000 else v


@njit(cache=True)
def rd16(mm, p):
    v = np.int64(mm[p]) | np.int64(mm[p + 1]) << 8
    return v - 0x10000 if v >= 0x8000 else v


@njit(cache=True)
def decode(mm, look, length, k, m):
    """frame k of a block into the canvas mask m (cleared first); returns number of pixels that fall outside the canvas (-1 = broken frame)"""
    m[:, :] = False
    off = rd32(mm, look + 516 + 4 * k)
    p = look + 512 + off
    if off == 0:                                    # placeholder: this frame has no image
        return 0
    if off < 0 or off + 8 > length - 512:
        return -1
    p += 8
    clip = 0
    end = look + length
    while p + 4 <= end:
        hdr = rd32(mm, p) & np.int64(0xFFFFFFFF)
        p += 4
        if hdr == END:
            return clip
        n = hdr & 0xFFF
        dx = (hdr >> 22) & 0x3FF
        dy = (hdr >> 12) & 0x3FF
        if dx & 0x200:
            dx -= 0x400
        if dy & 0x200:
            dy -= 0x400
        x, y = AX + dx, AY + dy
        for i in range(n):
            if 0 <= y < CH and 0 <= x + i < CW:
                m[y, x + i] = True
            else:
                clip += 1
        p += n
    return -1


@njit(cache=True)
def measure(m, B, dist, near, top, bot, rec):
    """fill rec for one frame: m item mask, B body mask, dist uint8 distance to the body silhouette (0 inside), top / bot = rows of the body bbox (-1 = no body)"""
    rec[:] = 0
    x0 = y0 = 10 ** 6
    x1 = y1 = -10 ** 6
    for y in range(CH):
        for x in range(CW):
            if not m[y, x]:
                continue
            rec[C_AREA] += 1
            x0, x1, y0, y1 = min(x0, x), max(x1, x), min(y0, y), max(y1, y)
            if top >= 0:
                if y < top:
                    b = NB
                elif y > bot:
                    b = NB + 1
                else:
                    b = (y - top) * NB // (bot - top + 1)
            else:
                b = NB
            g = near[y, x]
            if g < NP:
                rec[C_PYMAX + g] = max(rec[C_PYMAX + g], y - AY + 512)
                rec[C_PYMIN + g] = max(rec[C_PYMIN + g], 512 - (y - AY))
            if B[y, x]:
                rec[C_IN] += 1
                rec[C_BIN + b] += 1
                if g < NP:
                    rec[C_PIN + g] += 1
            else:
                rec[C_OUT] += 1
                rec[C_BOUT + b] += 1
                rec[C_HIST + min(dist[y, x], NH - 1)] += 1
                if g < NP:
                    rec[C_POUT + g] += 1
                    rec[C_PHIST + g * NHP + min(dist[y, x], NHP - 1)] += 1
    if rec[C_AREA] > 0:
        rec[C_X0], rec[C_X1], rec[C_Y0], rec[C_Y1] = x0 - AX, x1 - AX + 1, y0 - AY, y1 - AY + 1
        rec[C_OK] = 1


@njit(cache=True)
def scan_block(mm, look, length, nf, bmask, bdist, bnear, btop, bbot, bmap, recs):
    m = np.zeros((CH, CW), np.bool_)
    bad = 0
    for k in range(nf):
        clip = decode(mm, look, length, k, m)
        if clip < 0:
            bad += 1
            recs[k, :] = 0
            continue
        j = bmap[k]
        if j >= 0:
            measure(m, bmask[j], bdist[j], bnear[j], btop[j], bbot[j], recs[k])
        else:
            measure(m, bmask[0], bdist[0], bnear[0], -1, -1, recs[k])
        recs[k, C_CLIP] = clip
    return bad


def frame_count(mm, look, length):
    if length < 520:
        return 0
    cnt = struct.unpack_from("<i", mm, look + 512)[0]
    return cnt if 0 < cnt < 128 and 516 + 4 * cnt <= length else 0


def load_parts(path):
    """{(action, dir, frame): group label image (-1 = none) on the 256x256 canvas} from body_part_raster.py output, or {}"""
    if not path:
        return {}
    z = np.load(path)
    gi = np.array([PARTS.index(GROUP[str(n).split(".")[0]]) for n in z["parts"]] + [-1], np.int16)     # label -1 -> -1 (last element)
    out = {}
    for lab, key in zip(z["lab"], z["key"]):
        G = np.full((CH, CW), -1, np.int16)
        G[AY - PANCH[1]:AY - PANCH[1] + PCH, AX - PANCH[0]:AX - PANCH[0] + PCW] = gi[lab]
        out[tuple(int(x) for x in key)] = G
    return out


def body_reference(cl, a, d, parts, tag="anim", body=400):
    """masks, distance maps (uint8), nearest-part maps (uint8, 255 = unknown), body bbox rows of the frames of reference body (tag, body) for block (a, d); None when missing"""
    blk = cl.block(tag, body, a, d)
    if blk is None:
        return None
    mm, look, length = blk
    n = frame_count(mm, look, length)
    if not n:
        return None
    masks = np.zeros((n, CH, CW), bool)
    for k in range(n):
        decode(mm, look, length, k, masks[k])
    dist = np.empty((n, CH, CW), np.uint8)
    near = np.full((n, CH, CW), 255, np.uint8)
    top, bot = np.full(n, -1, np.int32), np.full(n, -1, np.int32)
    for k in range(n):
        dist[k] = np.minimum(ndimage.distance_transform_edt(~masks[k]), 255)
        G = parts.get((a, d, k)) if (tag, body) == ("anim", 400) else None     # part labels are those of OUR (human) body
        if G is not None and (G >= 0).any():
            _, (iy, ix) = ndimage.distance_transform_edt(G < 0, return_indices=True)
            near[k] = G[iy, ix]
        rows = np.nonzero(masks[k].any(1))[0]
        if rows.size:
            top[k], bot[k] = rows[0], rows[-1]
    return masks, dist, near, top, bot


def pct(h, q):
    """percentile (px) of a distance histogram, 0 when empty"""
    c = np.cumsum(h)
    return int(np.searchsorted(c, q / 100 * c[-1])) if c[-1] else 0


def make_ref(cl, a, parts, tag, bid):
    ref = {d: body_reference(cl, a, d, parts, tag, bid) for d in range(N_DIR)}
    body_area = {d: (ref[d][0].sum((1, 2)) if ref[d] else None) for d in range(N_DIR)}
    body_band = {}
    for d in range(N_DIR):
        if ref[d] is None:
            continue
        bb = []
        for k in range(len(ref[d][0])):
            t, b = ref[d][3][k], ref[d][4][k]
            c = np.zeros(NB + 2, int)
            if t >= 0:
                rows = ref[d][0][k].sum(1)
                for y in range(t, b + 1):
                    c[(y - t) * NB // (b - t + 1)] += rows[y]
            bb.append(c)
        body_band[d] = np.array(bb)
    body_part = {d: np.array([[((ref[d][2][k] == g) & ref[d][0][k]).sum() for g in range(NP)] for k in range(len(ref[d][0]))]) for d in range(N_DIR) if ref[d]}
    return ref, body_area, body_band, body_part


def measure_src(cl, src, a, R, parts):
    """record of animation src, action a against reference R = make_ref(...); None when the animation has no frames in this action"""
    ref, body_area, body_band, body_part = R
    tag, _, sid = src.partition(":")
    recs, nfr, bodyfr, bad, mism = [], [], [], 0, 0
    for d in range(N_DIR):
        blk = cl.block(tag, int(sid), a, d)
        n = frame_count(*blk) if blk else 0
        nfr.append(n)
        if not n:
            continue
        mm, look, length = blk
        r = ref[d]
        nb = len(r[0]) if r else 0
        bodyfr.append(nb)
        if nb and nb != n:
            mism += 1
        bmap = np.array([(k * nb // n) if nb else -1 for k in range(n)], np.int32)
        rc = np.zeros((n, NCOL), np.int64)
        if r:
            bad += scan_block(mm, look, length, n, r[0], r[1], r[2], r[3], r[4], bmap, rc)
        else:
            z = np.zeros((1, CH, CW), bool)
            bad += scan_block(mm, look, length, n, z, np.zeros((1, CH, CW), np.uint8), np.full((1, CH, CW), 255, np.uint8), np.full(1, -1, np.int32), np.full(1, -1, np.int32), bmap, rc)
        area_b = np.array([body_area[d][j] if j >= 0 else 0 for j in bmap]) if r else np.zeros(n)
        recs.append((d, rc, bmap, area_b))
    if not recs:
        return None
    R = np.concatenate([x[1] for x in recs])
    ok = R[:, C_OK] == 1
    rec = dict(frames=nfr, body_frames=[len(ref[d][0]) if ref[d] else 0 for d in range(N_DIR)], frame_count_mismatch=mism, broken=int(bad),
               empty=int((~ok).sum()))
    if ok.any():
        Ro = R[ok]
        hist = Ro[:, C_HIST:C_HIST + NH].sum(0)
        ab = np.concatenate([x[3] for x in recs])[ok]
        has_b = ab > 0
        rec.update(
            x0=int(Ro[:, C_X0].min()), x1=int(Ro[:, C_X1].max()), y0=int(Ro[:, C_Y0].min()), y1=int(Ro[:, C_Y1].max()),
            area=round(float(Ro[:, C_AREA].mean()), 1),
            cover=round(float((Ro[has_b, C_IN] / ab[has_b]).mean()), 4) if has_b.any() else None,
            out_frac=round(float((Ro[:, C_OUT] / Ro[:, C_AREA]).mean()), 4),
            out_px=round(float(Ro[:, C_OUT].mean()), 1),
            dist=dict(p50=pct(hist, 50), p90=pct(hist, 90), p99=pct(hist, 99), max=int(np.nonzero(hist)[0].max()) if hist.any() else 0),
            clip=int(R[:, C_CLIP].sum()),
            band_out=[round(float(v), 1) for v in Ro[:, C_BOUT:C_BOUT + NB + 2].mean(0)])
        if has_b.any():
            bcov = []
            for bi in range(NB):
                den = np.concatenate([body_band[x[0]][x[2], bi] for x in recs])[ok]
                s = den > 0
                bcov.append(round(float((Ro[s, C_BIN + bi] / den[s]).mean()), 3) if s.any() else None)
            rec["band_cover"] = bcov
            if parts:
                pc, po, py = {}, {}, {}
                for gi, g in enumerate(PARTS):
                    has = Ro[:, C_PYMAX + gi] > 0
                    if has.any():                                   # mean over the frames of the highest / lowest item row at this part, px from the anchor
                        py[g] = [round(float((512 - Ro[has, C_PYMIN + gi]).mean()), 1), round(float((Ro[has, C_PYMAX + gi] - 512).mean()), 1)]
                    den = np.concatenate([body_part[x[0]][x[2], gi] for x in recs])[ok]
                    sel = den > 0
                    if sel.any():
                        pc[g] = round(float((Ro[sel, C_PIN + gi] / den[sel]).mean()), 3)
                    h = Ro[:, C_PHIST + gi * NHP:C_PHIST + (gi + 1) * NHP].sum(0)
                    if h.any():
                        po[g] = dict(n=round(float(Ro[:, C_POUT + gi].mean()), 1), p50=pct(h, 50), p90=pct(h, 90), max=int(np.nonzero(h)[0].max()))
                rec["cover_part"], rec["out_part"], rec["part_y"] = pc, po, py
    return rec




def do_action(args):
    client, a, srcs, parts_path = args
    cl = Client(client)
    ref = make_ref(cl, a, load_parts(parts_path), "anim", 400)
    parts = parts_path
    out = {}
    for src in srcs:
        rec = measure_src(cl, src, a, ref, parts)
        if rec:
            out[src] = rec
    return a, out


def main():
    args = sys.argv[1:]
    jobs, files, actions, parts = 4, None, list(range(N_ACT)), None
    for opt in ("--jobs", "--files", "--actions", "--parts"):
        if opt in args:
            i = args.index(opt)
            v = args[i + 1]
            del args[i:i + 2]
            if opt == "--jobs":
                jobs = int(v)
            elif opt == "--files":
                files = v.split(",")
            elif opt == "--parts":
                parts = os.path.abspath(v)
            else:
                actions = [int(x) for x in v.split(",")]
    client, out = args
    ani = resolve(client)
    if files:
        ani = {k: v for k, v in ani.items() if k.split(":")[0] in files}
    ub = [int(x.partition(":")[2]) for x in ani if x.startswith("uop:")]
    fr = uop.Frames(client, ub)
    in_uop = {x: dict(layers=sorted(LAYERS.get(l, str(l)) for l in ani[x]["layers"]), items=[n for _, n in ani[x]["items"]][:3], actions=fr.actions(int(x.partition(":")[2])))
              for x in sorted(ani) if x.startswith("uop:")}
    srcs = sorted(x for x in ani if not x.startswith("uop:"))
    print("%d wearable animations in anim*.mul, %d in the .uop (not examined), %d actions" % (len(srcs), len(in_uop), len(actions)), flush=True)
    res = {s: dict(layers=sorted(LAYERS.get(l, str(l)) for l in ani[s]["layers"]), anim_ids=sorted(ani[s]["anim_ids"]),
                   n_items=len(ani[s]["items"]), items=[n for _, n in ani[s]["items"]][:4], actions={}) for s in srcs}
    with ProcessPoolExecutor(jobs) as ex:
        for a, o in ex.map(do_action, [(client, a, srcs, parts) for a in actions]):
            for s, r in o.items():
                res[s]["actions"][str(a)] = r
            print("action %d: %d animations" % (a, len(o)), flush=True)
    missing = {s: dict(layers=r["layers"], anim_ids=r["anim_ids"], n_items=r["n_items"], items=r["items"]) for s, r in res.items() if not r["actions"]}
    res = {s: r for s, r in res.items() if r["actions"]}
    json.dump(dict(canvas=[CW, CH], anchor=[AX, AY], bands=NB, parts=PARTS, actions=actions, animations=res, no_frames=missing, in_uop=in_uop),
              open(out, "w"), separators=(",", ":"))
    print("%d animations with frames -> %s" % (len(res), out))


if __name__ == "__main__":
    main()
