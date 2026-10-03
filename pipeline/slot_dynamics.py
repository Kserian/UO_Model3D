"""Dynamics of worn items in the ORIGINAL frames: how much an item stands off the body and how much that changes in motion.

    python slot_dynamics.py [--out ../docs/qa/slot_dynamics.json]

For every item sprite in pipeline/body13/mul (pants 431, shirt 434, skirt 449, cloak 468, boots 477, plate 527, arms 528, legs 529, gloves 530, helm 563,
shield 582, katana 627) and every frame of every action / direction that the body 400 also has: the item mask next to the body mask (same frame,
same anchor). Per item and action group (stand / walk+run / fight / spell / die / mounted / other):
  cover    share of the item that lies INSIDE the body silhouette (tight items ~ 0.8+, loose ones less)
  off      item pixels outside the body silhouette per frame (flare, hem, cloak)
  off_cv   variation of `off` over the frames of one animation (std / mean): ~0 = the item keeps its shape, large = it swings / flares
  swing    std over the frames of an animation of the horizontal offset (px) of the centroid of the item pixels OUTSIDE the body, in the direction the
           body faces mirrored to a common side (dir 1..3 -> x, 0 / 4 mirrored): loose parts lag and swing behind the movement
  area_cv  variation of the item area over the frames (std / mean): the item grows and shrinks with the pose
"""
import argparse, json, os, sys
import numpy as np
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "body13"))
from itemframes import canvas as sprite_canvas, load as load_sprites       # noqa: E402
import body_part_qa as Q                                                   # noqa: E402

ITEMS = {"pants": 431, "shirt": 434, "skirt": 449, "cloak": 468, "boots": 477, "plate": 527, "arms": 528, "legs": 529, "gloves": 530,
         "helm": 563, "shield": 582, "katana": 627}
GROUP = {"stand": "stand", "walk": "walk/run", "run": "walk/run", "fidget": "stand", "combat_idle": "stand", "attack": "fight", "combat_advance": "walk/run",
         "spell": "spell", "get_hit": "fight", "die": "die", "mounted": "mounted", "block": "fight", "punch": "fight", "bow": "other", "salute": "other", "eat": "other"}
BODY_ANCHOR, BIG, BIG_ANCHOR = (75, 92), (256, 256), (128, 192)


def group(name):
    for k, v in GROUP.items():
        if name.startswith(k):
            return v
    return "other"


def render_masks(root):
    """item masks from frames rendered by test_items.py (256x256, anchor (128,192)): {(act, dir): [mask, ...]}"""
    out = {}
    for act in sorted(os.listdir(root)):
        for d in range(5):
            fdir = os.path.join(root, act, "dir%d" % d)
            if os.path.isdir(fdir):
                from PIL import Image
                out[(int(act[:2]), d)] = [np.array(Image.open(os.path.join(fdir, fn)).convert("RGBA"))[..., 3] > 0 for fn in sorted(os.listdir(fdir))]
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out"); ap.add_argument("--render", help="frames dir of test_items.py (.../<item>/clothing/frames): the same metrics for our render")
    ap.add_argument("--item", help="with --render: the item (sprite) to compare with"); a = ap.parse_args()
    O = Q.originals(); meta = json.load(open(os.path.join(Q.ORIG, "meta.json")))
    names = {b["action"]: b["name"] for b in meta["blocks"]}
    sx, sy = BIG_ANCHOR[0] - BODY_ANCHOR[0], BIG_ANCHOR[1] - BODY_ANCHOR[1]
    res = {}
    rmasks = render_masks(a.render) if a.render else None
    for item, anim in ({a.item: ITEMS[a.item]} if a.render else ITEMS).items():
        spr = load_sprites(anim); acc = {}
        for (act, d), blk in sorted(spr.items()):
            if act not in names or not blk["frames"] or (rmasks is not None and (act, d) not in rmasks):
                continue
            offs, areas, cxs, covers = [], [], [], []
            for i in range(len(rmasks[(act, d)]) if rmasks is not None else len(blk["frames"])):
                b = O.get((act, d, i))
                if b is None or not b.any():
                    continue
                body = np.zeros(BIG, bool); body[sy:sy + b.shape[0], sx:sx + b.shape[1]] = b
                it = rmasks[(act, d)][i] if rmasks is not None else sprite_canvas(blk, i, BIG_ANCHOR, BIG)[..., 3] > 0
                if not it.any():
                    continue
                out = it & ~ndimage.binary_dilation(body, iterations=1)
                areas.append(it.sum()); covers.append((it & body).sum() / it.sum()); offs.append(out.sum())
                if out.sum() >= 3:
                    xs = np.nonzero(out)[1].mean() - np.nonzero(body)[1].mean()
                    cxs.append(xs * (-1 if d in (0, 1) else 1))        # dirs 0,1 face left in the sheet: mirror to one side
                else:
                    cxs.append(np.nan)
            if len(areas) < 3:
                continue
            offs, areas, cxs = np.array(offs, float), np.array(areas, float), np.array(cxs, float)
            g = acc.setdefault(group(names[act]), dict(cover=[], off=[], off_cv=[], swing=[], area_cv=[]))
            g["cover"].append(float(np.mean(covers))); g["off"].append(float(offs.mean())); g["off_cv"].append(float(offs.std() / max(offs.mean(), 1.0)))
            g["swing"].append(float(np.nanstd(cxs)) if np.isfinite(cxs).sum() >= 3 else 0.0); g["area_cv"].append(float(areas.std() / areas.mean()))
        res[item] = {k: {m: round(float(np.mean(v)), 3) for m, v in g.items()} | {"n": len(g["off"])} for k, g in acc.items()}
    print("%-7s %-9s %6s %7s %7s %7s %7s" % ("item", "group", "cover", "off", "off_cv", "swing", "area_cv"))
    for item, gs in res.items():
        for k, g in sorted(gs.items()):
            print("%-7s %-9s %6.2f %7.1f %7.2f %7.2f %7.3f" % (item, k, g["cover"], g["off"], g["off_cv"], g["swing"], g["area_cv"]))
    if a.out:
        json.dump(res, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
