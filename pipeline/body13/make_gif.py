"""animated preview: rendered item layers composited over the ORIGINAL UO body frames (and the original horse in the
mounted actions), 5 directions side by side, drawn like the client: horse, body, then the equipment layers.
usage: make_gif.py out.gif action_name layer_dir [layer_dir ...] [--scale 3] [--ms 120]"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
import sys, os, json, base64, zlib, numpy as np
from PIL import Image
args = [a for a in sys.argv[1:] if not a.startswith("--")]
opt = lambda k, d: type(d)(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d
out, act, layers = args[0], args[1], [a for a in args[2:] if not a.replace(".", "").isdigit()]
SC = opt("--scale", 3); MS = opt("--ms", 120)
ORIG = json.load(open(os.path.join(HERE, "..", "uo_original_frames.json")))["frames"]
HORSE = os.path.join(HERE, "..", "..", "client", "horse_0xC8_frames", "frames")
HORSE_OF = {23: 0, 24: 1, 25: 2, 26: 2, 27: 2, 28: 2, 29: 2}
CW, CH, AX, AY = 182, 153, 93, 106                      # horse canvas; the body canvas (136x120, anchor 68,86) sits at +25,+20
OX, OY = AX - 68, AY - 86
a = int(act[:2]); frames = []
i = 0
while "%d,%d,0" % (a, i) in ORIG:
    tiles = []
    for d in range(5):
        img = np.zeros((CH, CW, 3), np.uint8) + 36
        if a in HORSE_OF:
            ha = HORSE_OF[a]; hf = i if ha in (0, 1) else 0
            fn = os.path.join(HORSE, "%02d_action" % ha, "dir%d" % d, "%02d.png" % hf)
            if os.path.exists(fn):
                h = np.array(Image.open(fn).convert("RGBA")); m = h[..., 3] > 0; img[m] = h[m, :3]
        o = np.frombuffer(zlib.decompress(base64.b64decode(ORIG["%d,%d,%d" % (a, i, d)])), np.uint8).reshape(120, 136, 4)
        sub_ = img[OY:OY + 120, OX:OX + 136]
        m = o[..., 3] > 0; sub_[m] = o[m, :3]
        order = [L for L in layers if "Cloak" not in L]
        cloak = [L for L in layers if "Cloak" in L]
        order = (order + cloak) if d >= 3 else (cloak + order)       # the cloak is behind the body facing the camera
        for L in order:
            for sub in ("clothing", "all"):
                fn = os.path.join(L, sub, "frames", act, "dir%d" % d, "%02d.png" % i)
                if os.path.exists(fn):
                    it = np.array(Image.open(fn).convert("RGBA")); m = it[..., 3] > 0; sub_[m] = it[m, :3]; break
        tiles.append(img[8:150, 20:162])
    frames.append(Image.fromarray(np.concatenate(tiles, 1)).resize((142 * 5 * SC, 142 * SC), Image.NEAREST))
    i += 1
frames[0].save(out, save_all=True, append_images=frames[1:], duration=MS, loop=0, optimize=True)
print(out, len(frames), "frames")
