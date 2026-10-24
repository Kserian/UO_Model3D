"""Last step of a paperdoll gump / item icon of a worn item: the look of its animation (brightness, rim) and the files of the client.

    python uo_gump_finish.py RAW_DIR FRAMES_DIR OUT_DIR [--rim 0.45] [--art-h 40]

RAW_DIR = the output of uo_render_paperdoll.py (gump_male_raw.npy, gump_female_raw.npy, art_raw.npy, float RGBA), FRAMES_DIR = the item's animation frames (render_uo_layer.py,
.../clothing/frames/NN_action/dirK/NN.png): the front view of the gump is lit much brighter than the animation (white cloth), so its luminance is mapped to the animation's: the 5th /
50th / 95th percentile of the item's own pixels (without the rim) of the frames of stand, walk and run go to the same percentiles of the gump (piecewise linear on the luminance, the hue
stays). Then 1-px spikes of the outline are dropped (as the renderer's uo_edge_smooth) and the rim pixels (next to transparency) multiplied by --rim (the client's gumps and arts have a dark
rim: 0.45 as in uo_render_weapon_gump.py). Writes gump_male.png / .bin, gump_female.png / .bin (a Gumpart.mul entry; Gumpidx.mul extra = width << 16 | height), art.png / .bin (an art.mul entry)
and levels.json (the percentiles).
"""
import argparse, glob, json, os, sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import uo_gump_art as ga

LUMA = np.array([0.299, 0.587, 0.114], np.float32)


def interior(a8):
    """the item's own pixels without the rim: mask of alpha > 0 whose 4 neighbours are alpha > 0 too"""
    m = a8[..., 3] > 0
    n = m.copy(); n[1:] &= m[:-1]; n[:-1] &= m[1:]; n[:, 1:] &= m[:, :-1]; n[:, :-1] &= m[:, 1:]
    return n


def percentiles(rgb, mask):
    y = (rgb[mask][:, :3].astype(np.float32) * LUMA).sum(1)
    return np.percentile(y, [5, 50, 95])


def remap(a8, src, dst):
    """luminance of every pixel through the piecewise linear map src (3 percentiles) -> dst; the colour keeps its hue (rgb scaled by the new luma / the old)"""
    rgb = a8[..., :3].astype(np.float32); y = (rgb * LUMA).sum(-1)
    xs = np.array([0.0, *src, 255.0]); ys = np.array([0.0, *dst, 255.0])
    ny = np.interp(y, xs, ys)
    k = ny / np.maximum(y, 1e-3)
    out = a8.copy(); out[..., :3] = np.clip(rgb * k[..., None] + 0.5, 0, 255).astype(np.uint8)
    return out


def spikes(a8, passes=3):
    a8 = a8.copy()
    for _ in range(passes):
        on = a8[..., 3] > 0
        n = np.zeros(on.shape, np.int8)
        n[1:] += on[:-1]; n[:-1] += on[1:]; n[:, 1:] += on[:, :-1]; n[:, :-1] += on[:, 1:]
        a8[on & (n <= 1), 3] = 0
    return a8


def rim(a8, k):
    m = a8[..., 3] > 0
    inner = interior(a8)
    edge = m & ~inner
    out = a8.copy(); out[edge, :3] = np.clip(a8[edge, :3].astype(np.float32) * k + 0.5, 0, 255).astype(np.uint8)
    out[~m, :3] = 0
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw"); ap.add_argument("frames"); ap.add_argument("out"); ap.add_argument("--rim", type=float, default=0.45)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    pix = []
    for act in ("04_stand", "00_walk_unarmed", "02_run_unarmed"):
        for f in sorted(glob.glob(os.path.join(a.frames, act + "*", "dir*", "*.png"))):
            im = np.array(Image.open(f).convert("RGBA")); pix.append(im[interior(im)][:, :3])
    ref = np.percentile((np.concatenate(pix).astype(np.float32) * LUMA).sum(1), [5, 50, 95])
    levels = {"animation": ref.tolist()}
    names = [("gump_male", "gump_male_raw.npy"), ("gump_female", "gump_female_raw.npy"), ("art", "art_raw.npy")]
    for name, npy in names:
        raw = np.load(os.path.join(a.raw, npy))
        a8 = np.clip(raw * 255 + 0.5, 0, 255).astype(np.uint8); a8[..., 3] = np.where(raw[..., 3] >= 0.5, 255, 0)
        src = percentiles(a8, interior(a8)); levels[name + "_before"] = src.tolist()
        a8 = remap(a8, src, ref)
        a8 = rim(spikes(a8), a.rim)
        levels[name + "_after"] = percentiles(a8, interior(a8)).tolist()
        Image.fromarray(a8).save(os.path.join(a.out, name + ".png"))
        if name == "art":
            open(os.path.join(a.out, "art.bin"), "wb").write(ga.encode_art(a8))
        else:
            data, extra = ga.encode_gump(a8)
            open(os.path.join(a.out, name + ".bin"), "wb").write(data); levels[name + "_extra"] = extra
    json.dump(levels, open(os.path.join(a.out, "levels.json"), "w"), indent=1)
    print(json.dumps({k: [round(x, 1) for x in v] if isinstance(v, list) else v for k, v in levels.items()}))


if __name__ == "__main__":
    main()
