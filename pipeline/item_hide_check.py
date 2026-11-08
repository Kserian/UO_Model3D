"""Does the body hide the item the way it should in every direction? Item pixels drawn where the body is in front of them ("bleed"), measured against an exact holdout.

    python item_hide_check.py PROD_DIR REF_DIR

PROD_DIR: the render of the clothing layer that goes into the .vd (run_render_headless.py ITEM.blend PROD LAYER='"clothing"' ...).
REF_DIR : the same render with the exact Cycles holdout, the whole body hiding the item (pass a --pre script that sets bpy.context.scene["uo_holdout_margin"] = 0.0:
          a scene property of the item wins over HOLDOUT_MARGIN=0 on the command line).
Per action and direction: item pixels in PROD that are not within 1 px of an item pixel in REF (bleed), and the opposite (lost). The harp: 0.12 % bleed, at most 9 px in a frame.
Without `uo_behind_torso` (the torso hides an item only then) a harp in front of the belly was drawn on the back of the body: 9 % of its pixels, 26 % in stand and fidget 2.
"""
import sys, os, glob
import numpy as np
from PIL import Image
from scipy.ndimage import binary_dilation

prod, ref = sys.argv[1], sys.argv[2]
rows = []
for ad in sorted(glob.glob(os.path.join(prod, "clothing", "frames", "*"))):
    act = os.path.basename(ad); tot = bleed_tot = lost_tot = 0; worst = (0, None); perdir = []
    for d in range(5):
        b_d = 0
        for f in sorted(glob.glob(os.path.join(ad, "dir%d" % d, "*.png"))):
            rf = os.path.join(ref, "clothing", "frames", act, "dir%d" % d, os.path.basename(f))
            if not os.path.exists(rf):
                continue
            P = np.array(Image.open(f).convert("RGBA"))[..., 3] >= 128; R = np.array(Image.open(rf).convert("RGBA"))[..., 3] >= 128
            bleed = int((P & ~binary_dilation(R, iterations=1)).sum()); lost = int((R & ~binary_dilation(P, iterations=1)).sum())
            tot += int(P.sum()); bleed_tot += bleed; lost_tot += lost; b_d += bleed
            if bleed > worst[0]:
                worst = (bleed, "dir%d frame %s" % (d, os.path.basename(f)))
        perdir.append(b_d)
    rows.append((act, tot, bleed_tot, lost_tot, worst, perdir))
print("%-26s %8s %8s %6s %7s  %s" % ("action", "item px", "bleed px", "bleed%", "lost px", "bleed per direction 0..4 | worst frame"))
for act, tot, b, l, w, pd in rows:
    print("%-26s %8d %8d %5.1f%% %7d  %s | %s" % (act, tot, b, 100.0 * b / max(tot, 1), l, pd, ("%d px at %s" % w) if w[0] else "-"))
print("TOTAL item px %d, bleed px %d (%.2f%%)" % (sum(r[1] for r in rows), sum(r[2] for r in rows), 100.0 * sum(r[2] for r in rows) / max(sum(r[1] for r in rows), 1)))
