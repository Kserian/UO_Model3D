"""Body QA: silhouette of the pure 3D body (render with EXACT_BODY=False, EXACT_COLORS=False, 136x120 / (68,86)) against the original UO
body frames (client/body_0x190_frames, canvas 145x133, anchor (75,92)).

    python run_render_headless.py ../model/UO_Body_0x190.blend OUT LAYER='"body"' EXACT_BODY=False EXACT_COLORS=False CANVAS='(136,120)' ANCHOR='(68,86)'
    python body_silhouette_qa.py OUT/body/frames [--out ../docs/qa/body_silhouette.json] [--bias bias.png]

Per action / direction: IoU, area ratio (render / original: > 1 = our body is fatter), `outside` (render only) and `missing` (original only) pixels.
The signed bias map (red = we have extra, blue = we miss) is summed over all frames, in anchor coordinates.
"""
import argparse, json, os, sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ORIG = os.path.join(HERE, "..", "client", "body_0x190_frames")
OANCH, RANCH = (75, 92), (68, 86)


def load(p, size):
    return np.array(Image.open(p).convert("RGBA"))[..., 3] > 0 if os.path.exists(p) else np.zeros(size[::-1], bool)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("frames"); ap.add_argument("--out"); ap.add_argument("--bias")
    a = ap.parse_args()
    meta = json.load(open(os.path.join(ORIG, "meta.json")))
    W, H = meta["canvas"]
    rows, bias = [], np.zeros((H, W, 2))
    for blk in meta["blocks"]:
        act = "%02d_%s" % (blk["action"], blk["name"])
        for i, fr in enumerate(blk["frames"]):
            g = load(os.path.join(ORIG, "frames", act, "dir%d" % blk["dir"], fr["file"]), (W, H))
            r = np.zeros((H, W), bool)
            R = load(os.path.join(a.frames, act, "dir%d" % blk["dir"], "%02d.png" % i), (136, 120))
            dx, dy = OANCH[0] - RANCH[0], OANCH[1] - RANCH[1]
            r[dy:dy + 120, dx:dx + 136] = R[:H - dy, :W - dx] if R.shape == (120, 136) else R[:120, :136]
            if not g.any():
                continue
            rows.append(dict(a=blk["action"], d=blk["dir"], i=i, iou=float((r & g).sum() / max((r | g).sum(), 1)), ratio=float(r.sum() / g.sum()),
                             outside=int((r & ~g).sum()), missing=int((g & ~r).sum())))
            bias[..., 0] += r & ~g; bias[..., 1] += g & ~r
    f = lambda k, rs=rows: float(np.mean([x[k] for x in rs]))
    out = dict(frames=len(rows), iou=f("iou"), ratio=f("ratio"), outside=f("outside"), missing=f("missing"),
               by_action={str(x): float(np.mean([r["iou"] for r in rows if r["a"] == x])) for x in sorted({r["a"] for r in rows})},
               by_dir={str(x): float(np.mean([r["iou"] for r in rows if r["d"] == x])) for x in range(5)})
    print("frames %d  IoU %.3f  area ratio %.3f  outside %.1f  missing %.1f" % (out["frames"], out["iou"], out["ratio"], out["outside"], out["missing"]))
    print("by dir:", {k: round(v, 3) for k, v in out["by_dir"].items()})
    print("worst actions:", sorted(((round(v, 3), k) for k, v in out["by_action"].items()))[:6])
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True); json.dump(out, open(a.out, "w"), indent=1)
    if a.bias:
        m = bias.max() or 1; im = np.zeros((H, W, 3), np.uint8) + 20
        im[..., 0] = np.clip(20 + 235 * bias[..., 0] / m, 0, 255); im[..., 2] = np.clip(20 + 235 * bias[..., 1] / m, 0, 255)
        Image.fromarray(im).resize((W * 4, H * 4), Image.NEAREST).save(a.bias)


if __name__ == "__main__":
    main()
