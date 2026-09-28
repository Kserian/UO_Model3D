"""Per-direction albedo textures (same lighting model), blended with the global albedo where a direction sees little."""
import sys, pickle, time
import numpy as np
from PIL import Image
sys.argv = ["delight_bake.py"]
src = open("delight_bake.py").read()
exec(src.split("# ---- 1) subsample for the light fit")[0])
light = pickle.load(open("uo_light.pkl", "rb"))
Lc = np.array(light["L_camera"]); amb, dif = light["ambient"], light["diffuse"]
glob = srgb2lin(np.array(Image.open("UO_Body_Albedo.png").convert("RGB")).astype(np.float64))[ty, tx]
num = np.zeros((5, NT, 3)); den = np.zeros((5, NT))
for s in range(NS):
    X, nrm, Pt, Nt = frame_geom(s)
    zc = {}
    for d in range(5):
        idx, col, ncam, w = visible_samples(s, d, X, nrm, Pt, Nt, zc)
        sh = amb + dif * np.maximum(ncam @ Lc, 0)
        diff = np.linalg.norm(glob[idx] * sh[:, None] - col, axis=1)
        w = w * np.exp(-0.5 * (diff / 0.12) ** 2)
        np.add.at(num[d], idx, w[:, None] * col * sh[:, None]); np.add.at(den[d], idx, w * sh * sh)
from texbake import pull_push_fill
for d in range(5):
    alb = num[d] / np.maximum(den[d], 1e-9)[:, None]
    conf = np.clip(den[d] / 2.0, 0, 1)[:, None]          # little evidence -> fall back to the global albedo
    mixd = alb * conf + glob * (1 - conf)
    tex = np.zeros((TEX, TEX, 3)); wt = np.zeros((TEX, TEX))
    tex[ty, tx] = lin2srgb(mixd); wt[ty, tx] = 1.0
    Image.fromarray(np.clip(pull_push_fill(tex, wt), 0, 255).astype(np.uint8)).save(f"UO_Body_Albedo_dir{d}.png")
    print("dir", d, "texels seen %.1f%%" % (100 * (den[d] > 1e-9).mean()), f"{time.time()-t0:.0f}s", flush=True)
