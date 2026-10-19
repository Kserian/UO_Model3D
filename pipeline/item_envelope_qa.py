"""Phase 3 of docs/plans/original_items_calibration.md: how much of our item lies outside what the ORIGINAL items of its slot ever cover? (measure only, never a correction)

    python item_envelope_qa.py <client dir> <layer> (--render RENDER_DIR | --vd item.vd | --anim 434 [--loo]) [--k 3] [--json out.json] [--worst 5]

Envelope = for (layer, action, direction, frame) the number of originals of that layer (the `layer_priors.py` set: complete, on the canvas, not custom) whose sprite covers each pixel of the
256x256 canvas (anchor 128,192). Item pixels with count 0 are outside the union of the originals; with count < k (default 3) outside what at least k originals cover.
--render  RENDER_DIR/clothing/frames/NN_action/dirK/II.png (render_uo_layer.py with LAYER="clothing", canvas 256x256), --vd a .vd file of the item (all its blocks), --anim an original of the client
(anim.mul id; with --loo it is removed from the envelope first: the control "how far outside the others is a real original"). The frame index of the item is mapped to the body frame
index (i * n_body // n_item). The count arrays are cached in `uo_client/envelope_cache/` (derived from the client data, git-ignored).
Output per action: mean share of the item pixels outside the union / outside k originals, and the worst frames (for the human, not a trigger for a correction).
"""
import argparse, glob, json, os, sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "vdtool"))
import vd_scan as V                                                                  # noqa: E402

ROOT = os.path.join(HERE, "..")


def body_frames(cl):
    out = {}
    for a in range(V.N_ACT):
        for d in range(V.N_DIR):
            blk = cl.block("anim", 400, a, d)
            n = V.frame_count(*blk) if blk else 0
            if n:
                out[(a, d)] = n
    return out


def sprite_masks(cl, src, a, d, nb):
    """masks (nb, 256, 256) of animation src (e.g. 'anim:434') in block (a, d), frames mapped to the body frame count; None when missing"""
    tag, _, sid = src.partition(":")
    blk = cl.block(tag, int(sid), a, d)
    n = V.frame_count(*blk) if blk else 0
    if not n:
        return None
    m = np.zeros((n, V.CH, V.CW), bool)
    for k in range(n):
        V.decode(blk[0], blk[1], blk[2], k, m[k])
    return m[[k * n // nb for k in range(nb)]]


def envelope(cl, layer, cache, exclude=None):
    """{(a, d): uint8 counts (nb, 256, 256)} for the originals of `layer`; `exclude` = src removed from the counts"""
    path = os.path.join(cache, "envelope_%s.npz" % layer)
    pri = json.load(open(os.path.join(ROOT, "client", "extract", "layer_priors.json")))["layers"][layer]["items"]
    if os.path.exists(path):
        z = np.load(path)
        env = {tuple(int(x) for x in k.split("_")): z[k] for k in z.files}
    else:
        bf = body_frames(cl)
        env = {}
        for (a, d), nb in bf.items():
            c = np.zeros((nb, V.CH, V.CW), np.uint8)
            for s in pri:
                m = sprite_masks(cl, s, a, d, nb)
                if m is not None:
                    c += m
            env[(a, d)] = c
        os.makedirs(cache, exist_ok=True)
        np.savez_compressed(path, **{"%d_%d" % k: v for k, v in env.items()})
    if exclude and exclude in pri:
        env = dict(env)
        for (a, d), c in env.items():
            m = sprite_masks(cl, exclude, a, d, len(c))
            if m is not None:
                env[(a, d)] = c - m
    return env, len(pri) - (1 if exclude and exclude in pri else 0)


def item_frames(args, cl):
    """yield (action, dir, frame index, n frames, mask) of the item"""
    if args.render:
        for name in sorted(os.listdir(os.path.join(args.render, "clothing", "frames"))):
            a = int(name[:2])
            for d in range(5):
                fs = sorted(glob.glob(os.path.join(args.render, "clothing", "frames", name, "dir%d" % d, "*.png")))
                for i, p in enumerate(fs):
                    yield a, d, i, len(fs), np.array(Image.open(p).convert("RGBA"))[..., 3] > 0
    elif args.vd:
        import vdtool
        _, blocks = vdtool.read_vd(args.vd)
        for b in blocks:
            for i, f in enumerate(b["frames"]):
                rgba = vdtool.frame_rgba(f, b["palette"])
                m = np.zeros((256, 256), bool)
                h, w = rgba.shape[:2]
                x0, y0 = 128 - f["cx"], 192 - f["cy"] - f["h"]
                ys, xs = slice(max(y0, 0), min(y0 + h, 256)), slice(max(x0, 0), min(x0 + w, 256))
                if ys.stop > ys.start and xs.stop > xs.start:
                    m[ys, xs] = rgba[ys.start - y0:ys.stop - y0, xs.start - x0:xs.stop - x0][..., 3] > 0
                yield b["action"], b["dir"], i, len(b["frames"]), m
    else:
        for a in range(V.N_ACT):
            for d in range(V.N_DIR):
                nb = body_frames(cl).get((a, d))
                ms = sprite_masks(cl, "anim:%d" % args.anim, a, d, nb) if nb else None
                for i in range(len(ms) if ms is not None else 0):
                    yield a, d, i, len(ms), ms[i]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("client"); ap.add_argument("layer")
    ap.add_argument("--render"); ap.add_argument("--vd"); ap.add_argument("--anim", type=int); ap.add_argument("--loo", action="store_true")
    ap.add_argument("--k", type=int, default=3); ap.add_argument("--json"); ap.add_argument("--worst", type=int, default=5)
    ap.add_argument("--cache", default=os.path.join(ROOT, "uo_client", "envelope_cache"))
    args = ap.parse_args()
    cl = V.Client(args.client)
    env, n_env = envelope(cl, args.layer, args.cache, ("anim:%d" % args.anim) if args.loo and args.anim else None)
    rows = []
    for a, d, i, n, m in item_frames(args, cl):
        if (a, d) not in env or not m.any():
            continue
        c = env[(a, d)]
        k = i * len(c) // n
        px = m.sum()
        rows.append(dict(a=a, d=d, i=i, px=int(px), out_union=float((m & (c[k] == 0)).sum() / px), out_k=float((m & (c[k] < args.k)).sum() / px)))
    if not rows:
        sys.exit("no frames measured")
    by = {}
    for r in rows:
        by.setdefault(r["a"], []).append(r)
    print("layer %s, %d originals in the envelope, k = %d" % (args.layer, n_env, args.k))
    print("action  frames  outside union  outside <%d originals" % args.k)
    for a, rs in sorted(by.items()):
        print("%6d  %6d  %12.3f  %12.3f" % (a, len(rs), np.mean([r["out_union"] for r in rs]), np.mean([r["out_k"] for r in rs])))
    tot = dict(out_union=float(np.mean([r["out_union"] for r in rows])), out_k=float(np.mean([r["out_k"] for r in rows])), frames=len(rows))
    print("all     %6d  %12.3f  %12.3f" % (tot["frames"], tot["out_union"], tot["out_k"]))
    worst = sorted(rows, key=lambda r: -r["out_union"])[:args.worst]
    print("worst frames (action, dir, frame: outside union):", ", ".join("%d,%d,%d: %.3f" % (r["a"], r["d"], r["i"], r["out_union"]) for r in worst))
    if args.json:
        json.dump(dict(layer=args.layer, n_env=n_env, k=args.k, total=tot, by_action={str(a): dict(out_union=float(np.mean([r["out_union"] for r in rs])), out_k=float(np.mean([r["out_k"] for r in rs]))) for a, rs in by.items()},
                       worst=worst), open(args.json, "w"), indent=1)


if __name__ == "__main__":
    main()
