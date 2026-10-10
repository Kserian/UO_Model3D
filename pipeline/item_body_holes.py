"""The ORIGINAL UO body showing through holes of an item's clothing layer: what the client shows when the item (clothing.vd) is drawn over body 400.

    python item_body_holes.py ITEM.blend OUT_DIR [--clothing RENDER_DIR] [--actions 04_stand,...] [--sheet 02_run_unarmed:2 ...] [--json out.json]

item_skin_check.py looks at the 3D preview (body and item rendered together); a user of the client sees something else: the clothing layer (render_uo_layer.py
LAYER "clothing", with EXACT_BODY the body hides the item where the 3D body is in front of it) drawn over the original body frames (client/body_0x190_frames).
A pixel of the original body that is not covered by the item but lies INSIDE the item's outline (the outline closed by 2 px and its holes filled) is a hole the
user sees as the body through the robe. Each hole pixel is labelled by the body part of the 3D model there (hands, head, arms, torso, legs; a render of the body
layer with flat part colours, the nearest labelled pixel): a hand in front of the robe is drawn over it on purpose, a leg or a shoulder is a fault.

RENDER_DIR = a finished render of the item (OUT of run_render_headless.py / uo_make_item.py --vd, holding clothing/frames); without it the clothing layer is rendered
into OUT_DIR. Prints per action the hole pixels by part and the frames with any (hands and head apart), --sheet writes OUT_DIR/holes_<action>_<dir>.png: every frame
of that direction as the client shows it (3x), the hole pixels circled (black = arm, orange = torso, blue = leg, white = hand / head).
"""
import os, sys, glob, json, subprocess
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
BODY = os.path.join(HERE, "..", "client", "body_0x190_frames")
PARTS = {"hand": (255, 0, 0), "head": (0, 255, 0), "arm": (255, 255, 0), "torso": (255, 0, 255), "leg": (0, 255, 255)}
CLOSE = 2                      # px: the outline of the item is closed by this much before its holes are filled (a slit between two folds is not a hole)


def render(blend, out, layer, acts, pre=None, extra=()):
    cmd = [sys.executable, os.path.join(HERE, "run_render_headless.py"), blend, out] + (["--pre", pre] if pre else []) + [
        'LAYER="%s"' % layer, "ONLY=%r" % (list(acts),), "CANVAS=(256,256)", "ANCHOR=(128,192)"] + list(extra)
    subprocess.run(cmd, check=True, capture_output=True)


def body_frame(meta, act, d, f, canvas, anchor):
    """alpha + RGB of the original body frame on our canvas (anchors aligned)"""
    from PIL import Image
    p = os.path.join(BODY, "frames", act, "dir%d" % d, "%02d.png" % f)
    if not os.path.exists(p):
        return None
    a = np.array(Image.open(p).convert("RGBA"))
    ox, oy = anchor[0] - meta["anchor"][0], anchor[1] - meta["anchor"][1]
    out = np.zeros((canvas[1], canvas[0], 4), np.uint8)
    h, w = a.shape[:2]
    out[oy:oy + h, ox:ox + w] = a
    return out


def labels(img):
    """part index per pixel of the flat-coloured body render (-1 = none), nearest of the PARTS colours"""
    cols = np.array(list(PARTS.values()), float)
    rgb = img[..., :3].astype(float); al = img[..., 3] > 0
    d = ((rgb[..., None, :] - cols) ** 2).sum(-1)
    lab = d.argmin(-1); lab[~al] = -1
    return lab


def main():
    from PIL import Image, ImageDraw
    from scipy.ndimage import binary_closing, binary_fill_holes, distance_transform_edt
    args = sys.argv[1:]
    blend, out = os.path.abspath(args.pop(0)), os.path.abspath(args.pop(0))
    acts, sheets, clothing, js = [], [], None, None
    while args:
        f = args.pop(0)
        if f == "--actions":
            acts = args.pop(0).split(",")
        elif f == "--sheet":
            sheets.append(args.pop(0))
        elif f == "--clothing":
            clothing = os.path.abspath(args.pop(0))
        elif f == "--json":
            js = os.path.abspath(args.pop(0))
    os.makedirs(out, exist_ok=True)
    meta = json.load(open(os.path.join(BODY, "meta.json")))
    allacts = sorted({os.path.basename(p) for p in glob.glob(os.path.join(BODY, "frames", "*"))})
    acts = acts or allacts
    cdir = os.path.join(clothing or out, "clothing", "frames")
    if not os.path.isdir(cdir):
        render(blend, out, "clothing", acts)
        cdir = os.path.join(out, "clothing", "frames")
    ldir = os.path.join(out, "body", "frames")
    if not os.path.isdir(ldir):                                  # the body in flat part colours (item_skin_check.py colours it), no outline / UO colours
        render(blend, out, "body", acts, pre=os.path.join(HERE, "item_skin_check.py"), extra=["EXACT_COLORS=False", "EXACT_BODY=False", "OUTLINE=1.0"])
    canvas, anchor = (256, 256), (128, 192)
    pn = list(PARTS)
    rep = {}; tot = np.zeros(len(pn), int); frames_bad = 0; nfr = 0
    for act in acts:
        cnt = np.zeros(len(pn), int); bad = 0; per = {}
        for d in range(5):
            for p in sorted(glob.glob(os.path.join(cdir, act, "dir%d" % d, "*.png"))):
                f = int(os.path.basename(p)[:2]); nfr += 1
                c = np.array(Image.open(p).convert("RGBA")); ca = c[..., 3] > 0
                b = body_frame(meta, act, d, f, canvas, anchor)
                if b is None:
                    continue
                ba = b[..., 3] > 0
                inside = binary_fill_holes(binary_closing(ca, iterations=CLOSE)) if ca.any() else ca
                hole = ba & ~ca & inside
                lp = os.path.join(ldir, act, "dir%d" % d, os.path.basename(p))
                if hole.any() and os.path.exists(lp):
                    lab = labels(np.array(Image.open(lp).convert("RGBA")))
                    have = lab >= 0
                    if have.any():                                       # the part of the nearest labelled pixel (the 3D body is off the original by a pixel or two)
                        _, (iy, ix) = distance_transform_edt(~have, return_indices=True)
                        lab = lab[iy, ix]
                    k = np.bincount(lab[hole], minlength=len(pn))
                else:
                    k = np.zeros(len(pn), int); k[pn.index("torso")] = int(hole.sum())
                cnt += k
                fault = k[pn.index("arm")] + k[pn.index("torso")] + k[pn.index("leg")]
                if fault:
                    bad += 1; per["%d:%d" % (d, f + 1)] = {pn[i]: int(k[i]) for i in range(len(pn)) if k[i]}
        rep[act] = dict(parts={pn[i]: int(cnt[i]) for i in range(len(pn))}, frames_with_fault=bad, frames=per)
        tot += cnt; frames_bad += bad
        print("%-26s arm %4d  torso %4d  leg %4d  | hand %4d  head %3d | frames with arm / torso / leg holes %d" % (
            act, cnt[2], cnt[3], cnt[4], cnt[0], cnt[1], bad), flush=True)
    print("ITEM_BODY_HOLES frames %d, arm %d, torso %d, leg %d px (hand %d, head %d), frames with a fault %d" % (nfr, tot[2], tot[3], tot[4], tot[0], tot[1], frames_bad))
    if js:
        json.dump(rep, open(js, "w"), indent=1)
    for s in sheets:                                                 # the client's view: clothing over the original body, 3x, holes circled
        act, d = s.split(":"); d = int(d); tiles = []
        for p in sorted(glob.glob(os.path.join(cdir, act, "dir%d" % d, "*.png"))):
            f = int(os.path.basename(p)[:2])
            c = np.array(Image.open(p).convert("RGBA")); b = body_frame(meta, act, d, f, canvas, anchor)
            if b is None:
                continue
            bg = Image.new("RGBA", canvas, (30, 34, 30, 255)); bg.alpha_composite(Image.fromarray(b)); bg.alpha_composite(Image.fromarray(c))
            ca = c[..., 3] > 0; inside = binary_fill_holes(binary_closing(ca, iterations=CLOSE)); hole = (b[..., 3] > 0) & ~ca & inside
            box = (70, 90, 186, 200); im = bg.crop(box).resize(((box[2] - box[0]) * 3, (box[3] - box[1]) * 3), Image.NEAREST); dr = ImageDraw.Draw(im)
            lp = os.path.join(ldir, act, "dir%d" % d, os.path.basename(p))
            lab = labels(np.array(Image.open(lp).convert("RGBA"))) if os.path.exists(lp) else None
            if lab is not None and (lab >= 0).any():
                _, (iy, ix) = distance_transform_edt(~(lab >= 0), return_indices=True); lab = lab[iy, ix]
            for y, x in zip(*np.nonzero(hole)):
                part = pn[lab[y, x]] if lab is not None else "torso"
                col = {"arm": (0, 0, 0), "torso": (255, 120, 0), "leg": (0, 160, 255)}.get(part, (255, 255, 255))
                X, Y = (x - box[0]) * 3 + 1, (y - box[1]) * 3 + 1
                dr.ellipse((X - 4, Y - 4, X + 4, Y + 4), outline=col, width=2)
            dr.text((4, 4), "%s d%d f%d" % (act, d, f + 1), fill=(255, 255, 255))
            tiles.append(im)
        if tiles:
            W = Image.new("RGB", (sum(t.width for t in tiles[:5]), tiles[0].height * ((len(tiles) + 4) // 5)), (0, 0, 0))
            for i, t in enumerate(tiles):
                W.paste(t.convert("RGB"), ((i % 5) * t.width, (i // 5) * t.height))
            W.save(os.path.join(out, "holes_%s_%d.png" % (act, d)))


if __name__ == "__main__":
    main()
