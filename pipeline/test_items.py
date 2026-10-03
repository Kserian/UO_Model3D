"""Item-level QA: replicas of real UO items rendered with the whole pipeline (uo_bind_item + render_uo_layer) and compared
with the original sprites from the client.

    python test_items.py [--items shirt,pants,plate,gloves,boots,helm] [--actions 04_stand,09_attack_1h_slash,...|--all]
                         [--fit] [--tmp DIR] [--out qa.json] [--img overlay.png] [--canvas 256,256 --anchor 128,192]

The replica of an item is the skin of the body it covers, moved out by the item's thickness (body-hugging shell), so the numbers
measure the model + the render pipeline (occlusion by the body, EXACT_BODY cut, holes, specks, palette), not the 3D modelling of an
item. Sprites: pipeline/body13/mul/anim_NNNN.vd (the Nelderim client, same bytes as anim.mul). Per item and frame:
  iou      overlap of the rendered item with the sprite
  outside  rendered pixels the sprite does not have          missing  sprite pixels the render does not have
  strip    part of `missing` that touches the render (<= 1 px: the 1-px skin strips along the edges of tight items)
  pieces   detached pieces of the render (specks)            clipped  frames where the render touches the canvas border
  colors   most colours (RGB555) in one action/direction block; > 256 means the palette is reduced
"""
import argparse, json, os, subprocess, sys, tempfile, time

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "body13"))
from itemframes import canvas as sprite_canvas, load as load_sprites       # noqa: E402

ITEMS = {      # name: sprite id, bones covered, thickness m, cut (bone, keep from t0 along it), zrange (rest-pose height m), uo_bind_item PART
    # zrange comes from the sprites: lowest/highest row of the item in 04_stand (mean of 5 directions) -> z = -row / (36 cos 28.4557) + 0.07
    "shirt":  dict(anim=434, parts=["pelvis", "spine", "chest", "clavicle", "upper_arm", "neck"], thickness=0.012, cut=None, cut_far=["upper_arm", 0.4], zrange=[1.03, 9], part="chest"),
    "plate":  dict(anim=527, parts=["pelvis", "spine", "chest", "clavicle", "neck", "thigh"], thickness=0.03, cut=None, zrange=[0.68, 9], part="chest"),
    "arms":   dict(anim=528, parts=["upper_arm", "forearm", "clavicle"], thickness=0.025, cut=None, part="arms"),
    "pants":  dict(anim=431, parts=["pelvis", "thigh", "shin"], thickness=0.012, cut=None, zrange=[-9, 1.17], part="legs"),
    "legs":   dict(anim=529, parts=["pelvis", "thigh", "shin"], thickness=0.03, cut=None, zrange=[-9, 1.14], part="legs"),
    "boots":  dict(anim=477, parts=["shin", "foot"], thickness=0.015, cut=None, zrange=[-9, 0.56], part="boots"),
    "gloves": dict(anim=530, parts=["hand", "forearm"], thickness=0.03, cut=["forearm", 0.4], part="gloves"),
    "helm":   dict(anim=563, parts=["head"], thickness=0.02, cut=None, part="helm"),
}
DEFAULT_ITEMS = "shirt,plate,pants,boots,gloves,helm"
DEFAULT_ACTIONS = "04_stand,00_walk_unarmed,09_attack_1h_slash,16_spell_directed,21_die_forward,25_mounted_stand"


def render(blend, out, item, actions, canvas, anchor, fit, spec_path, extra=()):
    env = dict(os.environ, UO_TEST_SPEC=spec_path, UO_TEST_ITEM=item, UO_TEST_FIT="1" if fit else "0", UO_TEST_SCRIPTS=HERE)
    cmd = [sys.executable, os.path.join(HERE, "run_render_headless.py"), blend, out, "--pre", os.path.join(HERE, "test_items_pre.py"),
           'LAYER="clothing"', "ONLY=%r" % (actions,), "CANVAS=%r" % (canvas,), "ANCHOR=%r" % (anchor,)] + list(extra)
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if r.returncode:
        sys.exit("render of %s failed:\n%s\n%s" % (item, r.stdout[-2000:], r.stderr[-2000:]))
    open(os.path.join(out, "log.txt"), "w").write(r.stdout)
    return os.path.join(out, "clothing", "frames")


def measure(frames_root, item, canvas, anchor, img_frames):
    spr = load_sprites(ITEMS[item]["anim"])
    rows, blocks, imgs = [], {}, []
    st = ndimage.generate_binary_structure(2, 2)
    for act in sorted(os.listdir(frames_root)):
        a = int(act[:2])
        for d in range(5):
            fdir = os.path.join(frames_root, act, "dir%d" % d)
            colors = set()
            for fn in sorted(os.listdir(fdir)):
                i = int(fn[:2])
                R = np.array(Image.open(os.path.join(fdir, fn)).convert("RGBA"))
                G = sprite_canvas(spr.get((a, d)), i, anchor, canvas)
                r, g = R[..., 3] > 0, G[..., 3] > 0
                m = R[..., 3] > 0
                c15 = ((R[..., 0].astype(int) * 31 + 127) // 255 << 10) | ((R[..., 1].astype(int) * 31 + 127) // 255 << 5) | ((R[..., 2].astype(int) * 31 + 127) // 255)
                colors |= set(np.unique(c15[m]).tolist())
                if not g.any():
                    continue
                miss = g & ~r
                near = ndimage.binary_dilation(r, st, iterations=1)
                lab, n = ndimage.label(r, structure=st)
                rows.append(dict(a=a, i=i, d=d, iou=(r & g).sum() / max((r | g).sum(), 1), outside=int((r & ~g).sum()), missing=int(miss.sum()),
                                 strip=int((miss & near).sum()), pieces=int(n), clipped=bool(r[0].any() or r[-1].any() or r[:, 0].any() or r[:, -1].any()),
                                 sprite_px=int(g.sum())))
                if (act, i, d) in img_frames:
                    im = np.zeros(r.shape + (3,), np.uint8) + 25
                    im[r & g] = (190, 190, 190); im[r & ~g] = (230, 60, 60); im[g & ~r] = (60, 120, 255)
                    imgs.append(im)
            blocks[(a, d)] = len(colors)
    return rows, blocks, imgs


def summarize(rows, blocks):
    f = lambda k: float(np.mean([r[k] for r in rows])) if rows else 0.0
    return dict(frames=len(rows), iou=f("iou"), outside=f("outside"), missing=f("missing"), strip=f("strip"),
                pieces=f("pieces"), clipped=int(sum(r["clipped"] for r in rows)),
                colors_max=max(blocks.values()) if blocks else 0, blocks_over_256=int(sum(v > 256 for v in blocks.values())),
                by_action={str(a): float(np.mean([r["iou"] for r in rows if r["a"] == a])) for a in sorted({r["a"] for r in rows})})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", default=os.path.join(HERE, "..", "model", "UO_Body_0x190.blend"))
    ap.add_argument("--items", default=DEFAULT_ITEMS)
    ap.add_argument("--actions", default=DEFAULT_ACTIONS)
    ap.add_argument("--all", action="store_true", help="all 35 actions (about 10x slower)")
    ap.add_argument("--fit", action="store_true", help="also run uo_fit_item.py before uo_bind_item.py")
    ap.add_argument("--canvas", default="256,256"); ap.add_argument("--anchor", default="128,192")
    ap.add_argument("--tmp"); ap.add_argument("--out"); ap.add_argument("--img")
    ap.add_argument("--set", action="append", default=[], metavar="NAME=VALUE", help="extra render_uo_layer.py setting, e.g. --set HOLDOUT_MARGIN=0.05 (repeatable)")
    a = ap.parse_args()
    tmp = os.path.abspath(a.tmp) if a.tmp else tempfile.mkdtemp(prefix="test_items_")
    os.makedirs(tmp, exist_ok=True)
    canvas, anchor = tuple(int(x) for x in a.canvas.split(",")), tuple(int(x) for x in a.anchor.split(","))
    spec_path = os.path.join(tmp, "spec.json"); json.dump(ITEMS, open(spec_path, "w"))
    actions = [] if a.all else a.actions.split(",")
    show = {("04_stand", 0, 0), ("09_attack_1h_slash", 3, 1), ("16_spell_directed", 3, 0), ("21_die_forward", 3, 2), ("00_walk_unarmed", 3, 1)}
    res, panels = {}, []
    print("%-7s %6s %6s %8s %8s %6s %6s %7s %7s | %s" % ("item", "frames", "IoU", "outside", "missing", "strip", "pieces", "clipped", "colors", "IoU per action"))
    for item in a.items.split(","):
        t0 = time.time()
        root = render(os.path.abspath(a.blend), os.path.join(tmp, item), item, actions, canvas, anchor, a.fit, spec_path, a.set)
        rows, blocks, imgs = measure(root, item, canvas, anchor, show)
        res[item] = s = summarize(rows, blocks)
        print("%-7s %6d %6.3f %8.1f %8.1f %6.1f %6.2f %7d %7d | %s   (%.0fs)" % (
            item, s["frames"], s["iou"], s["outside"], s["missing"], s["strip"], s["pieces"], s["clipped"], s["colors_max"],
            " ".join("%s:%.2f" % (k, v) for k, v in s["by_action"].items()), time.time() - t0), flush=True)
        if imgs:
            panels.append(np.concatenate([np.pad(im[max(anchor[1] - 90, 0):anchor[1] + 36, max(anchor[0] - 45, 0):anchor[0] + 45],
                                                 ((1, 1), (1, 1), (0, 0)), constant_values=90) for im in imgs], 1))
    mean_iou = float(np.mean([v["iou"] for v in res.values()])) if res else 0.0
    print("mean IoU over items: %.3f" % mean_iou)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        json.dump(dict(canvas=canvas, anchor=anchor, actions=actions or "all", fit=a.fit, items=res, mean_iou=mean_iou), open(a.out, "w"), indent=1)
    if a.img and panels:
        w = max(p.shape[1] for p in panels)
        big = np.concatenate([np.pad(p, ((0, 0), (0, w - p.shape[1]), (0, 0))) for p in panels], 0)
        Image.fromarray(big).resize((big.shape[1] * 2, big.shape[0] * 2), Image.NEAREST).save(a.img)
    print("output in", tmp)
