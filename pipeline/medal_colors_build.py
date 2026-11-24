#!/usr/bin/env python3
"""medal_colors_build - the whole medal package in 8 colours x Light / Dark: animation .vd, paperdoll gumps (male, female) and two item arts.

    python medal_colors_build.py OUT_DIR --vd Medal.vd --art-v1 Medal_Art_Wave_Red.png --art-v2 Medal_Art_Loop_Red.png

Per colour folder  OUT_DIR/<Colour>/<Light|Dark>/ :
    Medal_<Shade><Colour>.vd              the animation, only its red pixels recoloured (vd_recolor.py; Light Red is the input file itself)
    Medal_<Shade><Colour>_male.png        paperdoll gump of the medal on the male body gump 0xC   (medal_gump_2d.py)
    Medal_<Shade><Colour>_female.png      the same on the female body gump 0xD
    art_v1_<Shade><Colour>.png            item art 44 x 32, laying 1 (--art-v1)
    art_v2_<Shade><Colour>.png            item art 44 x 32, laying 2 (--art-v2)
The input art and the input .vd are the red ones; every colour is derived from the same two reds of the animation (the dark and the light red pixels):
the gump and the arts use a 4-stop ramp dark / mid / light / hi built from the two colours of the animation (mid = the colour of its dark pixels, light = of its light pixels).
Requires: numpy, pillow.
"""
import argparse
import colorsys
import os
import shutil
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'vdtool'))
import medal_gump_2d as G  # noqa: E402
import vd_recolor  # noqa: E402

# colour: {variant: (hue deg, saturation of the dark px, saturation of the light px, value of the dark px, value of the light px)}; None = the input file as it is
PALETTE = {
    'Red':    {'Light': None,                              'Dark': (355, .92, .88, .20, .36)},
    'Blue':   {'Light': (222, .88, .80, .50, .78),         'Dark': (225, .92, .88, .20, .38)},
    'Green':  {'Light': (125, .85, .74, .38, .58),         'Dark': (130, .92, .85, .17, .34)},
    'Yellow': {'Light': (52,  .88, .68, .62, .82),         'Dark': (46,  .95, .88, .42, .66)},
    'Orange': {'Light': (26,  .93, .76, .58, .82),         'Dark': (22,  .95, .90, .38, .62)},
    'Brown':  {'Light': (28,  .64, .52, .38, .56),         'Dark': (22,  .72, .60, .17, .31)},
    'Pink':   {'Light': (338, .60, .44, .72, .86),         'Dark': (335, .82, .70, .46, .72)},
    'Purple': {'Light': (275, .64, .52, .48, .70),         'Dark': (272, .86, .72, .22, .42)},
}
OUTLINE_RED = (22, 8, 10)                # the outline of the red art (kept exactly for Light Red)


def hsv(h, s, v):
    return tuple(int(round(x * 255)) for x in colorsys.hsv_to_rgb(h / 360, s, v))


def pair(colour, shade):
    """(colour of the dark pixels, colour of the light pixels) of the animation, or None for the input."""
    p = PALETTE[colour][shade]
    if p is None:
        return None
    h, sd, sl, vd, vl = p
    return hsv(h, sd, vd), hsv(h, sl, vl)


def ramp_from_pair(dk, lt):
    """dark / mid / light / hi of the gump and art ribbon for an animation whose dark pixels are dk and light pixels lt."""
    hd, sd, vd = colorsys.rgb_to_hsv(*[c / 255 for c in dk])
    hl, sl, vl = colorsys.rgb_to_hsv(*[c / 255 for c in lt])
    f = lambda h, s, v: tuple(int(round(x * 255)) for x in colorsys.hsv_to_rgb(h, min(max(s, 0), 1), min(max(v, 0), 1)))
    return dict(dark=f(hd, sd, vd * 0.33), mid=tuple(dk), light=tuple(lt), hi=f(hl, sl * 0.84, vl * 1.47))


def recolor_art(img, colors, outline):
    """recolour the ribbon of an art (RGBA array): the brightness of each red pixel picks its place on the new ramp; steel and the rest are kept."""
    a = np.array(img.convert('RGBA'))
    al = a[..., 3] > 0
    is_out = al & (a[..., 0] == OUTLINE_RED[0]) & (a[..., 1] == OUTLINE_RED[1]) & (a[..., 2] == OUTLINE_RED[2])
    red = al & ~is_out & ((a[..., 0].astype(int) - np.maximum(a[..., 1], a[..., 2]).astype(int)) >= 8)
    lum = lambda c: 0.299 * c[..., 0] + 0.587 * c[..., 1] + 0.114 * c[..., 2]
    grid = np.linspace(0, 1.4, 281)
    y_old = lum(G.ramp(grid, G.RIBBON))
    I = np.interp(lum(a[red][:, :3].astype(float)), y_old, grid)
    new = G.ramp(I, colors)
    a[red, :3] = np.clip(np.round(new), 8, 255).astype(np.uint8)
    a[is_out, :3] = outline
    return Image.fromarray(a)


def outline_for(colors):
    d = np.array(colors['dark'], float)
    return tuple(int(round(x)) for x in np.clip(d * 0.6 + np.array([4.0, 3.2, 3.2]), 8, 255))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out'); ap.add_argument('--vd', required=True)
    ap.add_argument('--art-v1', required=True); ap.add_argument('--art-v2', required=True)
    ap.add_argument('--bodies', default=os.path.join(HERE, '..', 'docs', 'paperdoll'))
    o = ap.parse_args()
    art = {1: Image.open(o.art_v1).convert('RGBA'), 2: Image.open(o.art_v2).convert('RGBA')}
    for colour in PALETTE:
        for shade in PALETTE[colour]:
            tag = f'{shade}{colour}'
            d = os.path.join(o.out, colour, shade)
            os.makedirs(d, exist_ok=True)
            pr = pair(colour, shade)
            # animation
            if pr is None:
                shutil.copy(o.vd, os.path.join(d, f'Medal_{tag}.vd'))
                colors = dict(G.RIBBON)
            else:
                vd_recolor.recolor(o.vd, os.path.join(d, f'Medal_{tag}.vd'), np.array(pr[0], float), np.array(pr[1], float))
                colors = ramp_from_pair(*pr)
            # paperdoll gumps
            for sex in ('Male', 'Female'):
                body, gump = G.make_gump(sex, colors, o.bodies)
                Image.fromarray(gump).save(os.path.join(d, f'Medal_{tag}_{sex.lower()}.png'))
            # arts
            for v in (1, 2):
                if pr is None:
                    art[v].save(os.path.join(d, f'art_v{v}_{tag}.png'))
                else:
                    recolor_art(art[v], colors, outline_for(colors)).save(os.path.join(d, f'art_v{v}_{tag}.png'))
            print(tag, 'ok')


if __name__ == '__main__':
    main()
