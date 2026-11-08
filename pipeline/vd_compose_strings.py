"""A .vd of the harp with strings whose wood is EXACTLY the no-strings render, plus only the strings:

    python vd_compose_strings.py WOOD_RENDER STRINGS_RENDER OUT.vd

WOOD_RENDER: render_uo_layer.py (LAYER "clothing", canvas 256 x 256, anchor (128, 192)) of the item WITHOUT strings; STRINGS_RENDER: the same of the item WITH strings, rendered with a high
`uo_edge_floor` (54): a 1-px string is all edge, with the usual darkened edge it came out nearly black, but the floor also lifts the dark rim of the whole wood to grey. Here every pixel of the
wood render is kept as it is (its dark brown rim) and only the pixels that exist in the strings render alone (the strings floating in the harp, alpha 0 in the wood render) are added.
"""
import sys, os, glob
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import uo_vd_writer as W


STRING_MAX = 80      # no string pixel brighter than this (a few lit pixels of a 2-px diagonal came out at 120): the strings are dark grey, all alike


def load(root, act, d):
    return [np.array(Image.open(f).convert("RGBA")) for f in sorted(glob.glob(os.path.join(root, "clothing", "frames", act, "dir%d" % d, "*.png")))]


def main(wood, strings, out):
    blocks = {}; n_str = 0
    for ad in sorted(glob.glob(os.path.join(wood, "clothing", "frames", "*"))):
        act = os.path.basename(ad); a = int(act[:2])
        for d in range(5):
            A, B = load(wood, act, d), load(strings, act, d)
            assert len(A) == len(B), (act, d, len(A), len(B))
            fr = []
            for x, y in zip(A, B):
                z = x.copy(); add = (y[..., 3] >= 128) & (x[..., 3] < 128)
                z[add] = y[add]; z[..., :3][add] = np.minimum(z[..., :3][add], STRING_MAX); n_str += int(add.sum()); fr.append(z)
            blocks[(a, d)] = fr
    W.write_vd(out, blocks, anim_type=2, anchor=(128, 192))
    print("wrote", out, "|", len(blocks), "blocks,", sum(len(v) for v in blocks.values()), "frames,", n_str, "string pixels added")


if __name__ == "__main__":
    main(*sys.argv[1:4])
