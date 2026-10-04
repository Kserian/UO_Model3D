"""Silhouette of a rendered item against an ORIGINAL item of the game, frame by frame: does a free model look like the original robe / skirt / ... in motion?

    python item_vs_original.py RENDER_DIR [--sprite pipeline/body13/mul/anim_0469.vd] [--actions 00_walk_unarmed,02_run_unarmed,04_stand,09_attack_1h_slash] [--hip 0.95] [--overlay out.png]

RENDER_DIR/clothing/frames/NN_action/dirK/II.png is what render_uo_layer.py writes with LAYER = "clothing" (canvas 256x256, anchor 128,192, the default of uo_make_item.py). The sprite is placed on the same
canvas by its anchor. Output per action: IoU of the part below `--hip` m (rows under the hips: the legs push the hem there) and the width of the lowest rows, ours minus the original (px, - = narrower).
Different garments of one kind differ in length and cut, so the absolute number is a rough measure; use it to compare settings on the same item. --overlay writes a sheet of the run / walk
(grey = both, red = only ours, green = only the original).
"""
import argparse, glob, os, sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "vdtool"))
import vdtool                                                                   # noqa: E402


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("render"); ap.add_argument("--sprite", default=os.path.join(HERE, "body13", "mul", "anim_0469.vd"))
    ap.add_argument("--actions", default="00_walk_unarmed,02_run_unarmed,04_stand,09_attack_1h_slash"); ap.add_argument("--hip", type=float, default=0.95); ap.add_argument("--overlay")
    a = ap.parse_args()
    _, blocks = vdtool.read_vd(a.sprite)
    spr = {(b["action"], b["dir"]): b for b in blocks}
    hip = int(192 - (a.hip - 0.07) * 36 * np.cos(np.radians(28.4557)))

    def sprite_mask(act, d, i):
        b = spr.get((act, d))
        if b is None or i >= len(b["frames"]):
            return None
        f = b["frames"][i]; rgba = vdtool.frame_rgba(f, b["palette"])
        m = np.zeros((256, 256), bool); h, w = rgba.shape[:2]; x0, y0 = 128 - f["cx"], 192 - f["cy"] - f["h"]
        m[max(y0, 0):y0 + h, max(x0, 0):x0 + w] = rgba[max(-y0, 0):, max(-x0, 0):][..., 3][:256 - max(y0, 0), :256 - max(x0, 0)] > 0
        return m

    tiles = []
    for name in a.actions.split(","):
        act = int(name.split("_")[0]); num = den = 0; wd = []
        for d in range(5):
            for p in sorted(glob.glob(os.path.join(a.render, "clothing", "frames", name, "dir%d" % d, "*.png"))):
                i = int(os.path.basename(p).split(".")[0]); g = sprite_mask(act, d, i)
                if g is None:
                    continue
                m = np.array(Image.open(p).convert("RGBA"))[..., 3] > 0
                r0, g0 = m[hip:], g[hip:]
                num += (r0 & g0).sum(); den += (r0 | g0).sum()
                ys, ym = np.nonzero(g0.any(1))[0], np.nonzero(r0.any(1))[0]
                if len(ys) and len(ym):
                    wd.append(np.ptp(np.nonzero(r0[ym.max() - 6:ym.max()].any(0))[0]) - np.ptp(np.nonzero(g0[ys.max() - 6:ys.max()].any(0))[0]))
                if a.overlay and d in (2, 3) and act in (0, 2) and i in (0, 2, 3, 5, 6, 8):
                    im = np.zeros((256, 256, 3), np.uint8) + 255
                    im[m & g] = (150, 150, 150); im[m & ~g] = (220, 60, 60); im[~m & g] = (60, 170, 60)
                    tiles.append((act, d, i, im[150:200, 90:170].repeat(3, 0).repeat(3, 1)))
        print("%-22s IoU below the hips %.3f | width of the lowest rows %+.1f px (ours - original)" % (name, num / max(den, 1), np.mean(wd) if wd else float("nan")))
    if a.overlay and tiles:
        rows = []
        for key in sorted({(t[0], t[1]) for t in tiles}):
            rows.append(np.concatenate([t[3] for t in sorted(tiles, key=lambda t: t[2]) if (t[0], t[1]) == key], 1))
        w = max(r.shape[1] for r in rows)
        Image.fromarray(np.concatenate([np.pad(r, ((0, 0), (0, w - r.shape[1]), (0, 0)), constant_values=255) for r in rows], 0)).save(a.overlay); print("overlay:", a.overlay)


if __name__ == "__main__":
    main()
