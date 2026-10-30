"""Warm up the base colour texture of the harp glb: the pale, nearly white wear marks along the ridges of the wood (about 0.6 % of the wood texels, RGB ~ 200 192 180) are painted in the colour of the wood,
keeping their brightness and the grain (the ratio to the typical wood luminance, limited), so that they read as light grain and not as paint. Only the colour texture changes (re-encoded JPEG q95).
    python retexture.py in.glb out.glb"""
import json, struct, io, sys
import numpy as np
from PIL import Image
src, dst = sys.argv[1], sys.argv[2]
d = open(src, "rb").read(); L = struct.unpack_from("<I", d, 12)[0]; j = json.loads(d[20:20+L]); bo = 20 + L
bl = struct.unpack_from("<I", d, bo)[0]; b0 = bo + 8; binc = bytes(d[b0:b0+bl])
def img(i):
    bv = j["bufferViews"][j["images"][i]["bufferView"]]; o = bv.get("byteOffset", 0); return Image.open(io.BytesIO(binc[o:o + bv["byteLength"]])).convert("RGB")
bc = np.array(img(0)).astype(np.float32) / 255
mr = np.array(img(1).resize(bc.shape[1::-1], Image.NEAREST))[..., 2]
mx, mn = bc.max(2), bc.min(2); sat = (mx - mn) / np.maximum(mx, 1e-6)
lum = bc @ np.array([0.299, 0.587, 0.114], np.float32)
wood = (mr < 56)
core = wood & (sat > 0.45)
wood_rgb = np.median(bc[core], 0); wood_lum = float(np.median(lum[core]))
w = np.clip((0.55 - sat) / 0.25, 0, 1) * wood * (mx > 0.5)                    # pale wood texels
ratio = np.clip(lum / wood_lum, 0.5, 1.3)[..., None]
target = np.clip(wood_rgb[None, None, :] * ratio, 0, 1)
out = bc * (1 - w[..., None]) + target * w[..., None]
print("typical wood %s, pale texels recoloured: %.2f %% of the wood" % ((wood_rgb * 255).round(), 100 * (w > 0.5).sum() / max(wood.sum(), 1)))
buf = io.BytesIO(); Image.fromarray((np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8)).save(buf, "JPEG", quality=95, subsampling=0); raw = buf.getvalue()
b = binc + b"\0" * ((-len(binc)) % 4); off = len(b); b += raw
j["bufferViews"].append({"buffer": 0, "byteOffset": off, "byteLength": len(raw)}); j["images"][0]["bufferView"] = len(j["bufferViews"]) - 1
j["buffers"][0]["byteLength"] = len(b)
js = json.dumps(j, separators=(",", ":")).encode(); js += b" " * ((-len(js)) % 4)
open(dst, "wb").write(struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(js) + 8 + len(b)) + struct.pack("<I4s", len(js), b"JSON") + js + struct.pack("<I4s", len(b), b"BIN\0") + b)
print("written", dst, len(raw) // 1024, "KB texture")
