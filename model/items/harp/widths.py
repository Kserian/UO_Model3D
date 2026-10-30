"""Width of the arms / neck of the harp frame in game pixels (36 px/m) at the final length, and the thickness: python widths.py harp.glb [LENGTH 0.65] [NSTRING_TRI 240]"""
import json, struct, sys
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
d = open(sys.argv[1], "rb").read(); L = struct.unpack_from("<I", d, 12)[0]; j = json.loads(d[20:20+L]); b0 = 20 + L + 8
LEN = float(sys.argv[2]) if len(sys.argv) > 2 else 0.65; NS = int(sys.argv[3]) if len(sys.argv) > 3 else 240
p = j["meshes"][0]["primitives"][0]
def acc(i):
    a = j["accessors"][i]; bv = j["bufferViews"][a["bufferView"]]; nc = {"VEC2": 2, "VEC3": 3, "SCALAR": 1}[a["type"]]; ct = {5126: "<f4", 5125: "<u4"}[a["componentType"]]
    return np.frombuffer(d, dtype=ct, count=a["count"] * nc, offset=b0 + bv.get("byteOffset", 0) + a.get("byteOffset", 0)).reshape(-1, nc)
pos = acc(p["attributes"]["POSITION"]).astype(np.float64); idx = acc(p["indices"]).ravel().reshape(-1, 3).astype(np.int64)[:-NS] if NS else acc(p["indices"]).ravel().reshape(-1, 3)
H = np.ptp(pos[:, 1]); s = LEN / H                                      # model units -> m
MM = 1.0                                                                # raster: 1 px = 1 mm
x = (pos[:, 0] - pos[:, 0].min()) * s * 1000; z = (pos[:, 1] - pos[:, 1].min()) * s * 1000
W_, H_ = int(x.max()) + 4, int(z.max()) + 4
im = Image.new("L", (W_, H_), 0); dr = ImageDraw.Draw(im)
for t in idx[::1]: dr.polygon([(x[t[0]], H_ - z[t[0]]), (x[t[1]], H_ - z[t[1]]), (x[t[2]], H_ - z[t[2]])], fill=255)
m = ndi.binary_closing(np.array(im) > 0, iterations=3)
dt = ndi.distance_transform_edt(m); ridge = (dt >= ndi.maximum_filter(dt, size=9)) & (dt > 12)
w = 2 * dt[ridge]; PX = 1000 / 36.0
print("final height %.2f m, width %.0f mm; frame arms / neck (ridge of the silhouette): width in game px  p5 %.2f  p25 %.2f  median %.2f  p75 %.2f   (1 px = %.1f mm)" % (LEN, x.max(), *(np.percentile(w, q) / PX for q in (5, 25, 50, 75)), PX))
# thickness: extent along z (glTF) per height band, frame only
zt = pos[:, 2] * s * 1000; hb = ((pos[:, 1] - pos[:, 1].min()) * s * 1000 // 30).astype(int)
th = [np.ptp(zt[(hb == k)]) for k in range(hb.max() + 1) if (hb == k).sum() > 200]
print("thickness per 3 cm band (px): median %.2f  min %.2f  max %.2f" % (np.median(th) / PX, np.min(th) / PX, np.max(th) / PX))
Image.fromarray((m * 255).astype(np.uint8)).resize((W_ // 2, H_ // 2)).save(sys.argv[1] + ".sil.png")
