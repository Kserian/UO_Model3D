"""Pack the original UO body frames (canvas-aligned 136x120, anchor 68,86) as
   1) an atlas PNG for the shader projection, 2) a JSON (per tile base64(zlib(RGBA))) for the render script."""
import json, zlib, base64, numpy as np
from PIL import Image
from targets import targets
COLS, TW, TH = 35, 136, 120
tiles, k = {}, 0
frames = {}
for a in range(35):
    T = targets(a)
    for d in range(5):
        for i in range(len(T)):
            tiles["%d,%d,%d" % (a, i, d)] = (k % COLS, k // COLS); frames[(a, i, d)] = T[i, d]; k += 1
ROWS = (k + COLS - 1) // COLS
atlas = np.zeros((ROWS * TH, COLS * TW, 4), np.uint8)
enc = {}
for (a, i, d), img in frames.items():
    c, r = tiles["%d,%d,%d" % (a, i, d)]
    rgba = img.copy(); rgba[..., 3] = np.where(img[..., 3] > 127, 255, 0); rgba[rgba[..., 3] == 0] = 0
    atlas[r * TH:(r + 1) * TH, c * TW:(c + 1) * TW] = rgba
    enc["%d,%d,%d" % (a, i, d)] = base64.b64encode(zlib.compress(rgba.tobytes(), 9)).decode()
Image.fromarray(atlas).save("UO_Original_Atlas.png", optimize=True)
json.dump(dict(cols=COLS, rows=ROWS, tile=[TW, TH], anchor=[68, 86], tiles=tiles, frames=enc,
               format="key 'action,frame,dir' -> base64(zlib(uint8 RGBA 120x136)); tiles: key -> [col,row] in the atlas"),
          open("uo_original_frames.json", "w"))
print("tiles", k, "atlas", atlas.shape)
