"""An animated GIF of a rendered item on the original UO body (to look at the motion, not at single frames).

    python item_gif.py RENDER_DIR OUT.gif [--actions 00_walk_unarmed,02_run_unarmed,09_attack_1h_slash] [--dirs 0,2,3] [--scale 4] [--fps 10] [--layer clothing] [--crop auto|X0,Y0,X1,Y1]

RENDER_DIR holds RENDER_DIR/<layer>/frames/NN_action/dirK/NN.png (render_uo_layer.py, 256x256, anchor (128, 192)); the body frames are the originals of
client/body_0x190_frames (145x133, anchor (75, 92)): they are exactly what the game draws under the item. Every action is shown in the given directions side by side and
looped `--loops` times, one action after the other. `--crop auto` (default: the fixed window CROP) = the window that holds every pixel of every shown frame (body and item) + 6 px,
so that nothing is cut off in the falls, the rides and the long swings.
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
    ap.add_argument("--crop", default=""); ap.add_argument("--scale", type=int, default=4); ap.add_argument("--fps", type=int, default=10); ap.add_argument("--loops", type=int, default=2)
    a = ap.parse_args()
    meta = json.load(open(os.path.join(BODY, "meta.json")))
    dirs = [int(x) for x in a.dirs.split(",")]
    crop = CROP
    if a.crop == "auto":
        box = None
        for act in a.actions.split(","):
            dd = glob.glob(os.path.join(a.root, a.layer, "frames", act + "*"))
            if not dd:
                continue
            for d in dirs:
                for f in sorted(glob.glob(os.path.join(dd[0], "dir%d" % d, "*.png"))) + [None] * 0:
                    bb = Image.open(f).convert("RGBA").getchannel("A").point(lambda v: 255 if v >= 128 else 0).getbbox()
                    if bb:
                        box = bb if box is None else (min(box[0], bb[0]), min(box[1], bb[1]), max(box[2], bb[2]), max(box[3], bb[3]))
                for im in body_frames(meta, int(act[:2]), d):
                    bb = im.getchannel("A").point(lambda v: 255 if v >= 128 else 0).getbbox()
                    if bb:
                        box = bb if box is None else (min(box[0], bb[0]), min(box[1], bb[1]), max(box[2], bb[2]), max(box[3], bb[3]))
        if box:
            crop = (max(box[0] - 6, 0), max(box[1] - 6, 0), min(box[2] + 6, 256), min(box[3] + 6, 256)); print("crop", crop)
    elif a.crop:
        crop = tuple(int(x) for x in a.crop.split(","))
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
                    tiles.append(bg.crop(crop))
                W, H = tiles[0].size
                row = Image.new("RGB", (W * len(tiles), H + 12), (20, 20, 20))
                for k, t in enumerate(tiles):
                    row.paste(t.convert("RGB"), (k * W, 12))
                ImageDraw.Draw(row).text((4, 1), act, fill=(255, 255, 255))
                frames.append(row.resize((row.width * a.scale, row.height * a.scale), Image.NEAREST))
    if not frames:
        raise SystemExit("no frames in %s" % a.root)
    ms = 1000.0 / a.fps; dur = [int(round((k + 1) * ms / 10.0)) * 10 - int(round(k * ms / 10.0)) * 10 for k in range(len(frames))]     # GIF delays are whole 1/100 s: the average stays exactly 1 / fps
    frames[0].save(a.out, save_all=True, append_images=frames[1:], duration=dur, loop=0, optimize=False)
    print(a.out, len(frames), "frames", frames[0].size)


if __name__ == "__main__":
    main()
