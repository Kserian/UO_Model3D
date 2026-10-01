"""Body QA per part: the label images of body_part_raster.py against the original UO body frames (client/body_0x190_frames).

    python body_part_raster.py ../model/UO_Body_0x190.blend /tmp/lab.npz
    python body_part_qa.py /tmp/lab.npz [--out ../docs/qa/body_parts_baseline.json]

Per part: `model+` = pixels only the model has (counted for the part that draws them), `sprite+` = pixels only the original has
(counted for the nearest model part). Totals are pixels per frame; IoU is the whole-silhouette IoU (same as body_silhouette_qa.py).
"""
import argparse, json, os
import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt

HERE = os.path.dirname(os.path.abspath(__file__))
ORIG = os.path.join(HERE, "..", "client", "body_0x190_frames")


def originals():
    meta = json.load(open(os.path.join(ORIG, "meta.json")))
    W, H = meta["canvas"]; out = {}
    for blk in meta["blocks"]:
        act = "%02d_%s" % (blk["action"], blk["name"])
        for i, fr in enumerate(blk["frames"]):
            p = os.path.join(ORIG, "frames", act, "dir%d" % blk["dir"], fr["file"])
            out[(blk["action"], blk["dir"], i)] = np.array(Image.open(p).convert("RGBA"))[..., 3] > 0 if os.path.exists(p) else np.zeros((H, W), bool)
    return out


def analyse(lab, key, parts):
    O = originals(); P = len(parts)
    sprite = np.zeros((len(key), P)); model = np.zeros((len(key), P)); iou = np.zeros(len(key)); ok = np.zeros(len(key), bool)
    for n, (a, d, i) in enumerate(key):
        g = O[(a, d, i)]; L = lab[n]; m = L >= 0
        if not g.any():
            continue
        ok[n] = True
        iou[n] = (m & g).sum() / max((m | g).sum(), 1)
        b = m & ~g; np.add.at(model[n], L[b], 1)
        r = g & ~m
        if r.any():
            _, (iy, ix) = distance_transform_edt(~m, return_indices=True)
            np.add.at(sprite[n], L[iy[r], ix[r]], 1)
    return iou, sprite, model, ok


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("lab"); ap.add_argument("--out")
    a = ap.parse_args()
    d = np.load(a.lab); lab, key, parts = d["lab"], d["key"], [str(p) for p in d["parts"]]
    iou, sprite, model, ok = analyse(lab, key, parts)
    k = ok
    print("frames %d  IoU %.4f  model+ %.1f  sprite+ %.1f px/frame" % (k.sum(), iou[k].mean(), model[k].sum(1).mean(), sprite[k].sum(1).mean()))
    print("%-12s %8s %8s %8s" % ("part", "sprite+", "model+", "sum"))
    rows = []
    for j, p in sorted(enumerate(parts), key=lambda t: -(sprite[k][:, t[0]].sum() + model[k][:, t[0]].sum())):
        s, m = sprite[k][:, j].mean(), model[k][:, j].mean(); rows.append((p, s, m))
        print("%-12s %8.2f %8.2f %8.2f" % (p, s, m, s + m))
    if a.out:
        out = dict(frames=int(k.sum()), iou=float(iou[k].mean()), parts={p: dict(sprite=float(s), model=float(m)) for p, s, m in rows},
                   iou_by_action={str(x): float(iou[k & (key[:, 0] == x)].mean()) for x in sorted(set(key[:, 0]))})
        json.dump(out, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
