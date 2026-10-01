"""Extent of every people / equipment animation (body ids >= 400) around the UO anchor point, from anim.idx + anim.mul.

Only the frame headers are read (centerX, centerY, width, height), so it takes seconds. Per frame, in pixels from the anchor:
    left = centerX, right = width - centerX, up = centerY + height, down = -centerY
(the anchor is the pixel (centerX, centerY + height) of the stored frame, see README "Format .vd"; right and down count the anchor
column / row itself, so a canvas W x H with anchor (ax, ay) holds left=ax, right=W-ax, up=ay, down=H-ay).
The client mirrors directions 1..3 into 5..7, so for those left and right are swapped as well.

    python measure_equipment_extent.py <client dir with anim*.idx + anim*.mul> <out.json> [canvas as L,R,U,D, e.g. 128,128,192,64]
Keys of the result are "<file>:<body id>", e.g. "anim:527" or "anim4:521" (anim, anim2 .. anim5 are all measured).
"""
import json, mmap, os, struct, sys

N_ACT, N_DIR = 35, 5
CUR = dict(left=68, right=68, up=86, down=34)         # the 136x120 canvas, anchor (68,86); right / down include the anchor column / row


def measure(idx_path, mul_path, tag):
    idx = open(idx_path, "rb").read()
    n_entries = len(idx) // 12
    res = {}
    with open(mul_path, "rb") as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
    body = 400
    while 35000 + (body - 400) * 175 + 175 <= n_entries:
        base = 35000 + (body - 400) * 175
        ext = dict(left=0, right=0, up=-10**6, down=-10**6)
        frames = blocks = 0
        worst = {}
        for a in range(N_ACT):
            for d in range(N_DIR):
                look, length, _ = struct.unpack_from("<iii", idx, 12 * (base + a * 5 + d))
                if look < 0 or length <= 0 or look + length > len(mm):
                    continue
                blocks += 1
                cnt, = struct.unpack_from("<i", mm, look + 512)
                if not 0 < cnt < 64:
                    continue
                offs = struct.unpack_from("<%di" % cnt, mm, look + 516)
                for o in offs:
                    if o < 0 or o + 8 > length:
                        continue
                    cx, cy, w, h = struct.unpack_from("<hhHH", mm, look + 512 + o)
                    if not (0 < w < 2048 and 0 < h < 2048):
                        continue
                    frames += 1
                    v = dict(left=cx, right=w - cx, up=cy + h, down=-cy)
                    sides = [(v["left"], v["right"])]
                    if 1 <= d <= 3:                                   # mirrored into directions 5..7
                        sides.append((v["right"], v["left"]))
                    for l, r in sides:
                        for k, val in (("left", l), ("right", r), ("up", v["up"]), ("down", v["down"])):
                            if val > ext[k]:
                                ext[k] = val
                                worst[k] = (a, d)
        if frames:
            res["%s:%d" % (tag, body)] = dict(blocks=blocks, frames=frames, **ext, worst={k: list(v) for k, v in worst.items()})
        body += 1
    return res


def need(res, canvas):
    """ids whose frames leave the canvas, with the overflow per side"""
    out = {}
    for b, e in res.items():
        over = {k: e[k] - canvas[k] for k in ("left", "right", "up", "down") if e[k] > canvas[k]}
        if over:
            out[b] = over
    return out


if __name__ == "__main__":
    src, out = sys.argv[1], sys.argv[2]
    res = {}
    for tag in ("anim", "anim2", "anim3", "anim4", "anim5"):
        ip, mp = os.path.join(src, tag + ".idx"), os.path.join(src, tag + ".mul")
        if os.path.exists(ip) and os.path.exists(mp):
            r = measure(ip, mp, tag)
            print("%-6s %4d animations with frames, %4d complete (35x5)" % (tag, len(r), sum(e["blocks"] == N_ACT * N_DIR for e in r.values())))
            res.update(r)
    allmax = {k: max(e[k] for e in res.values()) for k in ("left", "right", "up", "down")}
    print("body 400:", {k: res["anim:400"][k] for k in ("left", "right", "up", "down")})
    print("max over everything:", allmax, "at", {k: max(res, key=lambda b: res[b][k]) for k in allmax})
    cvs = [("current 136x120", CUR)]
    if len(sys.argv) > 3:
        cvs.append(("given", dict(zip(("left", "right", "up", "down"), map(int, sys.argv[3].split(","))))))
    for name, cv in cvs:
        n = need(res, cv)
        print("%-16s %s: %d animations leave the canvas, worst overflow %s" % (name, cv, len(n),
              {k: max(o.get(k, 0) for o in n.values()) if n else 0 for k in ("left", "right", "up", "down")}))
    json.dump(dict(canvas_current=CUR, max_all=allmax, bodies=res), open(out, "w"), indent=1)
