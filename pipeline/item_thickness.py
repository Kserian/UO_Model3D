"""How far does an item stand out of the body silhouette, measured the way the originals can be measured: on frames. "Not too thick" in numbers.

    python item_thickness.py RENDER_DIR [--layer clothing] [--actions 04_stand,00_walk_unarmed,09_attack_1h_slash]      # our render (render_uo_layer.py)
    python item_thickness.py --sprite pipeline/body13/mul/anim_0527.vd [--actions 4,0,9]                                # an original item of the game

For every frame of the given actions (5 directions) the pixels of the item that lie OUTSIDE the silhouette of the original body (client/body_0x190_frames, same frame) are
measured by their distance from that silhouette (1 px = 2.78 cm); prints the mean over frames of the share of the item that is outside, and p50 / p90 / max of the distance (cm).
Compare an item with the original of its slot (e.g. a plate 527, a shirt 434, a helm 563, a skirt 449): that is the thickness the game has.
"""
import argparse, glob, json, os, sys
import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "vdtool"))
import vdtool                                                    # noqa: E402

BODY = os.path.join(HERE, "..", "client", "body_0x190_frames")
PX_CM = 100 / 36.0
_meta = json.load(open(os.path.join(BODY, "meta.json")))


def body_mask(act, d, i):
    blk = next((b for b in _meta["blocks"] if b["action"] == act and b["dir"] == d), None)
    if not blk or i >= len(blk["frames"]):
        return None
    im = np.array(Image.open(os.path.join(BODY, "frames", "%02d_%s" % (act, blk["name"]), "dir%d" % d, blk["frames"][i]["file"])).convert("RGBA"))[..., 3] > 0
    out = np.zeros((256, 256), bool); out[192 - 92:192 - 92 + im.shape[0], 128 - 75:128 - 75 + im.shape[1]] = im      # anchor (75, 92) -> (128, 192)
    return out


def sprite_mask(blk, i):
    f = blk["frames"][i]
    a = vdtool.frame_rgba(f, blk["palette"])[..., 3] > 0
    out = np.zeros((256, 256), bool); x0, y0 = 128 - f["cx"], 192 - f["cy"] - f["h"]
    h, w = a.shape
    out[y0:y0 + h, x0:x0 + w] = a
    return out


def measure(masks):
    shares, dists = [], []
    for item, body in masks:
        if body is None or not item.any():
            continue
        out = item & ~body
        shares.append(out.sum() / max(item.sum(), 1))
        if out.any():
            dist = ndimage.distance_transform_edt(~body)
            dists.append(dist[out] * PX_CM)
    d = np.concatenate(dists) if dists else np.zeros(1)
    return dict(frames=len(shares), outside_share=float(np.mean(shares)) if shares else 0.0, p50=float(np.percentile(d, 50)), p90=float(np.percentile(d, 90)), max=float(d.max()))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?"); ap.add_argument("--layer", default="clothing"); ap.add_argument("--sprite"); ap.add_argument("--actions", default="")
    a = ap.parse_args()
    masks = []
    if a.sprite:
        _, blocks = vdtool.read_vd(a.sprite); by = {(b["action"], b["dir"]): b for b in blocks}
        acts = [int(x) for x in (a.actions or "4,0,2,9,16").split(",")]
        for act in acts:
            for d in range(5):
                b = by.get((act, d))
                for i in range(len(b["frames"]) if b else 0):
                    masks.append((sprite_mask(b, i), body_mask(act, d, i)))
    else:
        acts = (a.actions or "04_stand,00_walk_unarmed,02_run_unarmed,09_attack_1h_slash,16_spell_directed").split(",")
        for act in acts:
            dd = glob.glob(os.path.join(a.root, a.layer, "frames", act + "*"))
            if not dd:
                continue
            for d in range(5):
                for i, fn in enumerate(sorted(glob.glob(os.path.join(dd[0], "dir%d" % d, "*.png")))):
                    masks.append((np.array(Image.open(fn).convert("RGBA"))[..., 3] > 0, body_mask(int(act[:2]), d, i)))
    r = measure(masks)
    print("frames %d | item outside the body silhouette: %.1f%% of its pixels | distance p50 %.1f  p90 %.1f  max %.1f cm" % (r["frames"], 100 * r["outside_share"], r["p50"], r["p90"], r["max"]))
