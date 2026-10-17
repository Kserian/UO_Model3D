"""Paperdoll gumps (male / female) and item art of a weapon from a finished picture of it (260 x 237 like the body gump, black background, held in the right hand = on the left of the picture).

    python uo_gump_from_image.py WEAPON.png OUT_DIR [--male docs/paperdoll/paperdoll_male_0xc.png] [--female docs/paperdoll/paperdoll_female_0xd.png]

Gump: black = transparent (1-bit alpha); the picture is the male gump as it is (its grip sits on the fist of the male body gump 12), the female one is moved up / sideways by the difference of the
two fists (measured on the body gumps), and per gender the weapon is cut out under the body gump's fist except its bottom HOLD_SHOW rows (the fist holds it: uo_render_weapon_gump.py).
Art: the weapon lying on the ground seen from above (UO turns the map 45 deg: along the picture's diagonal, top to the upper right), scaled into 44 x 44 px (rim included), a dark rim
around it (ART_RIM grey, as uo_render_weapon_gump.py), 1-bit alpha; art_mirror.png is the mirrored second icon.
Writes gump_male.png, gump_female.png, preview_male.png, preview_female.png (on the body gump, 3 x), art.png, art_mirror.png (and gump_*.bin / art*.bin: Gumpart.mul / art.mul entries, uo_gump_art.py).
"""
import os, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import uo_gump_art as ga

HERE = os.path.dirname(os.path.abspath(__file__))
GW, GH = 260, 237
HOLD_CUT = (8, 9, 6)                     # window of the fist around the grip (x +-8, y 9 above .. 6 below)
HOLD_SHOW = {"male": 2, "female": 3}     # the weapon shows through the bottom rows of the fist
ART_BOX, ART_RIM = 44, 16
FIST_X = (40, 56)                        # columns of the fist of both body gumps, rows searched around the grip
BODY_DEFAULT = {"male": os.path.join(HERE, "..", "docs", "paperdoll", "paperdoll_male_0xc.png"),
                "female": os.path.join(HERE, "..", "docs", "paperdoll", "paperdoll_female_0xd.png")}


def load_weapon(path):
    a = np.asarray(Image.open(path).convert("RGB"), np.uint8)
    out = np.zeros((GH, GW, 4), np.uint8); h, w = min(GH, a.shape[0]), min(GW, a.shape[1])
    out[:h, :w, :3] = a[:h, :w]; out[:h, :w, 3] = np.where(a[:h, :w].max(-1) > 0, 255, 0)
    return out


def fist_centre(body):
    """centre (x, y) of the fist of a body gump: the body pixels left of FIST_X[1] at the height of the hands"""
    m = body[..., 3] > 0; ys, xs = np.nonzero(m[:, :FIST_X[1]])
    sel = (ys > 95) & (ys < 135); return xs[sel].mean(), ys[sel].mean()


def main(weapon, out, bodies):
    os.makedirs(out, exist_ok=True)
    wp = load_weapon(weapon); res = {}
    fc = {g: fist_centre(np.asarray(Image.open(p).convert("RGBA"))) for g, p in bodies.items()}
    for g, p in bodies.items():
        body = np.asarray(Image.open(p).convert("RGBA"), np.uint8)
        dx, dy = (0, 0) if g == "male" else (int(round(fc[g][0] - fc["male"][0])), int(round(fc[g][1] - fc["male"][1])))
        img = np.zeros_like(wp); ys, xs = np.nonzero(wp[..., 3]); ys2, xs2 = ys + dy, xs + dx
        ok = (ys2 >= 0) & (ys2 < GH) & (xs2 >= 0) & (xs2 < GW); img[ys2[ok], xs2[ok]] = wp[ys[ok], xs[ok]]
        gy = fc[g][1]
        rows = (np.arange(GH) > gy - 6) & (np.arange(GH) < gy + 6)                       # the weapon's x at the height of the fist
        gx = np.nonzero(img[rows][..., 3] > 0)[1]; gx = float(np.median(gx)) if len(gx) else 48.0
        bm = np.zeros((GH, GW), bool); bm[:body.shape[0], :body.shape[1]] = body[:GH, :GW, 3] > 0
        yy, xx = np.mgrid[0:GH, 0:GW]
        win = (np.abs(xx + 0.5 - gx) <= HOLD_CUT[0]) & (yy + 0.5 >= gy - HOLD_CUT[1]) & (yy + 0.5 <= gy + HOLD_CUT[2])
        fist = win & bm
        bottom = np.where(fist.any(0), GH - 1 - np.argmax(fist[::-1], 0), -1)
        cut = fist & (img[..., 3] > 0) & (yy <= bottom[None, :] - HOLD_SHOW[g])
        img[cut] = 0
        print("%s: moved by (%d, %d), fist centre (%.1f, %.1f), weapon x %.1f, %d px cut under the fist" % (g, dx, dy, fc[g][0], fc[g][1], gx, cut.sum()))
        Image.fromarray(img).save(os.path.join(out, "gump_%s.png" % g))
        data, extra = ga.encode_gump(img); open(os.path.join(out, "gump_%s.bin" % g), "wb").write(data)
        bg = Image.new("RGBA", (GW, GH), (30, 30, 30, 255)); bg.alpha_composite(Image.fromarray(body)); bg.alpha_composite(Image.fromarray(img))
        bg.resize((GW * 3, GH * 3), Image.NEAREST).save(os.path.join(out, "preview_%s.png" % g)); res[g] = img
    # art
    ys, xs = np.nonzero(wp[..., 3]); crop = wp[ys.min():ys.max() + 1, xs.min():xs.max() + 1].astype(np.float32)
    k = 6; big = np.kron(crop, np.ones((k, k, 1), np.float32))                         # premultiplied rotation (no black fringes)
    pm = big.copy(); pm[..., :3] *= pm[..., 3:] / 255.0
    layers = [Image.fromarray(np.clip(pm[..., i], 0, 255).astype(np.uint8)) for i in range(4)]
    rot = np.stack([np.asarray(l.rotate(-45, resample=Image.BICUBIC, expand=True), np.float32) for l in layers], -1)
    al = rot[..., 3] / 255.0; rgb = rot[..., :3] / np.maximum(al[..., None], 1e-3)
    rys, rxs = np.nonzero(al > 0.01); rgb, al = rgb[rys.min():rys.max() + 1, rxs.min():rxs.max() + 1], al[rys.min():rys.max() + 1, rxs.min():rxs.max() + 1]
    inner = ART_BOX - 2                                                              # room for the 1 px rim
    f = inner / max(al.shape); nh, nw = max(1, int(round(al.shape[0] * f))), max(1, int(round(al.shape[1] * f)))
    pre = np.dstack([rgb * al[..., None], al])
    chans = [np.asarray(Image.fromarray(pre[..., i].astype(np.float32), mode="F").resize((nw, nh), Image.BOX)) for i in range(4)]
    a_s = chans[3]; rgb_s = np.stack(chans[:3], -1) / np.maximum(a_s[..., None], 1e-3)
    art = np.zeros((nh + 2, nw + 2, 4), np.uint8); m = a_s >= 0.4
    art[1:-1, 1:-1, :3] = np.clip(rgb_s, 0, 255).astype(np.uint8); art[1:-1, 1:-1, 3] = np.where(m, 255, 0)
    full = art[..., 3] > 0
    ringm = ~full & (np.roll(full, 1, 0) | np.roll(full, -1, 0) | np.roll(full, 1, 1) | np.roll(full, -1, 1))
    art[ringm] = (ART_RIM, ART_RIM, ART_RIM, 255)
    box = np.zeros((ART_BOX, ART_BOX, 4), np.uint8); oy, ox = (ART_BOX - art.shape[0]) // 2, (ART_BOX - art.shape[1]) // 2
    box[oy:oy + art.shape[0], ox:ox + art.shape[1]] = art
    for name, im in (("art", box), ("art_mirror", box[:, ::-1].copy())):
        Image.fromarray(im).save(os.path.join(out, name + ".png")); open(os.path.join(out, name + ".bin"), "wb").write(ga.encode_art(im))
    print("art: %d x %d px used of %d x %d" % (art.shape[1], art.shape[0], ART_BOX, ART_BOX))


if __name__ == "__main__":
    args = sys.argv[1:]; bodies = dict(BODY_DEFAULT)
    for flag, g in (("--male", "male"), ("--female", "female")):
        if flag in args:
            i = args.index(flag); bodies[g] = args[i + 1]; del args[i:i + 2]
    main(args[0], args[1], bodies)
