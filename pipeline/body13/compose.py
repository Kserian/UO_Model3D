"""original body + rendered item layer, side by side for several renders. compose.py out.png dirA dirB ... -- act:frame:dir ..."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
import sys, os, json, base64, zlib, numpy as np
from PIL import Image
sep = sys.argv.index("--"); out = sys.argv[1]; dirs = sys.argv[2:sep]; views = sys.argv[sep + 1:]
ORIG = json.load(open(os.path.join(HERE, "..", "uo_original_frames.json")))["frames"]
rows = []
for v in views:
    act, i, d = v.split(":"); a = int(act[:2])
    o = np.frombuffer(zlib.decompress(base64.b64decode(ORIG["%d,%d,%d" % (a, int(i), int(d))])), np.uint8).reshape(120, 136, 4)
    tiles = [np.where(o[..., 3:] > 0, o[..., :3], 40).astype(np.uint8)]
    for dd in dirs:
        it = np.array(Image.open("%s/clothing/frames/%s/dir%s/%02d.png" % (dd, act, d, int(i))).convert("RGBA"))
        img = np.where(o[..., 3:] > 0, o[..., :3], 40).astype(np.uint8)
        m = it[..., 3] > 0; img[m] = it[m, :3]
        tiles.append(img)
    rows.append(np.concatenate(tiles, 1))
CROP = [int(c) for c in os.environ.get("CROP", "0,0,136,120").split(",")]
rows = [r_.reshape(120, -1, 136, 3)[:, :, :, :] if False else r_ for r_ in rows]
cr = []
for r_ in rows:
    tiles = [r_[:, k * 136:(k + 1) * 136][CROP[1]:CROP[3], CROP[0]:CROP[2]] for k in range(r_.shape[1] // 136)]
    cr.append(np.concatenate([np.pad(t, ((1, 1), (1, 1), (0, 0)), constant_values=90) for t in tiles], 1))
S_ = int(os.environ.get("SCALE", "3"))
im = Image.fromarray(np.concatenate(cr, 0)); im.resize((im.width * S_, im.height * S_), Image.NEAREST).save(out); print(out)
