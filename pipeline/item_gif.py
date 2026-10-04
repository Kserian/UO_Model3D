"""An animated GIF of a rendered item on the original UO body (to look at the motion, not at single frames).

    python item_gif.py RENDER_DIR OUT.gif [--actions 00_walk_unarmed,02_run_unarmed,09_attack_1h_slash] [--dirs 0,2,3] [--scale 4] [--fps 10] [--layer clothing]

RENDER_DIR holds RENDER_DIR/<layer>/frames/NN_action/dirK/NN.png (render_uo_layer.py, 256x256, anchor (128, 192)); the body frames are the originals of
client/body_0x190_frames (145x133, anchor (75, 92)): they are exactly what the game draws under the item. Every action is shown in the given directions side by side and
looped `--loops` times, one action after the other.
"""
import argparse, glob, json, os
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
BODY = os.path.join(HERE, "..", "client", "body_0x190_frames")
CROP = (88, 100, 168, 200)


def body_frames(meta, act, d):
    blk = next((b for b in meta["blocks"] if b["action"] == act and b["dir"] == d), None)
    out = []
    for f in (blk["frames"] if blk else []):
        im = Image.open(os.path.join(BODY, "frames", "%02d_%s" % (act, blk["name"]), "dir%d" % d, f["file"])).convert("RGBA")
        big = Image.new("RGBA", (256, 256), (0, 0, 0, 0)); big.paste(im, (128 - 75, 192 - 92))
        out.append(big)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root"); ap.add_argument("out"); ap.add_argument("--layer", default="clothing")
    ap.add_argument("--actions", default="00_walk_unarmed,02_run_unarmed,09_attack_1h_slash"); ap.add_argument("--dirs", default="0,2,3")
    ap.add_argument("--scale", type=int, default=4); ap.add_argument("--fps", type=int, default=10); ap.add_argument("--loops", type=int, default=2)
    a = ap.parse_args()
    meta = json.load(open(os.path.join(BODY, "meta.json")))
    dirs = [int(x) for x in a.dirs.split(",")]
    frames = []
    for act in a.actions.split(","):
        n_act = int(act[:2])
        dd = glob.glob(os.path.join(a.root, a.layer, "frames", act + "*"))
        if not dd:
            continue
        per = []
        for d in dirs:
            item = sorted(glob.glob(os.path.join(dd[0], "dir%d" % d, "*.png")))
            body = body_frames(meta, n_act, d)
            per.append((item, body))
        n = min(len(p[0]) for p in per if p[0]) if any(p[0] for p in per) else 0
        for _ in range(a.loops):
            for i in range(n):
                tiles = []
                for item, body in per:
                    bg = Image.new("RGBA", (256, 256), (84, 104, 84, 255))
                    if i < len(body):
                        bg.alpha_composite(body[i])
                    bg.alpha_composite(Image.open(item[i]).convert("RGBA"))
                    tiles.append(bg.crop(CROP))
                W, H = tiles[0].size
                row = Image.new("RGB", (W * len(tiles), H + 12), (20, 20, 20))
                for k, t in enumerate(tiles):
                    row.paste(t.convert("RGB"), (k * W, 12))
                ImageDraw.Draw(row).text((4, 1), act, fill=(255, 255, 255))
                frames.append(row.resize((row.width * a.scale, row.height * a.scale), Image.NEAREST))
    if not frames:
        raise SystemExit("no frames in %s" % a.root)
    frames[0].save(a.out, save_all=True, append_images=frames[1:], duration=int(1000 / a.fps), loop=0, optimize=False)
    print(a.out, len(frames), "frames", frames[0].size)


if __name__ == "__main__":
    main()
