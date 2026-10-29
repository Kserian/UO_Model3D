"""The colours of the drum: 20 hues x 2 shades (light, dark), and the one function that turns a red colour into another.

    from drum_colors import COLORS, SHADES, recolor_rgb

COLORS: (name, hue in degrees, saturation factor, luminance factor of that hue: a yellow of the same value is much lighter than a blue); SHADES: (saturation factor, luminance factor).
recolor_rgb(rgb, hue, sat_mult, lum_mult): hue to `hue`, saturation x sat_mult (0 = grey), the colour then scaled to the luminance (0.299 R + 0.587 G + 0.114 B) of the original x lum_mult, so the
light and the dark of the shell survive. Used for the palettes of the .vd (recolor_vd.py) and for the pixels of the shell in the paperdoll (uo_render_drum_gump.py).
"""
import colorsys

COLORS = [
    ("red", 0, 1.00, 1.00), ("crimson", 348, 1.00, 0.95), ("rose", 332, 0.85, 1.10), ("magenta", 308, 0.95, 1.00), ("purple", 285, 0.90, 0.95),
    ("violet", 265, 0.95, 1.00), ("indigo", 245, 1.00, 0.90), ("blue", 225, 1.00, 1.00), ("azure", 205, 0.95, 1.10), ("cyan", 187, 0.90, 1.15),
    ("teal", 170, 0.90, 1.00), ("emerald", 148, 0.90, 1.05), ("green", 125, 0.90, 1.00), ("lime", 88, 0.85, 1.20), ("yellow", 55, 0.85, 1.45),
    ("amber", 42, 1.00, 1.30), ("orange", 24, 1.00, 1.10), ("brown", 22, 0.60, 0.70), ("olive", 68, 0.70, 0.85), ("silver", 0, 0.00, 1.20),
]
SHADES = {"light": (0.85, 1.45), "dark": (1.00, 0.62)}


def recolor_rgb(rgb, hue, sat_mult, lum_mult):
    r, g, b = [c / 255.0 for c in rgb]
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    s2 = 0.0 if sat_mult == 0 else min(1.0, s * sat_mult)
    r2, g2, b2 = colorsys.hsv_to_rgb(hue / 360.0, s2, v)
    l2 = 0.299 * r2 + 0.587 * g2 + 0.114 * b2
    k = lum * lum_mult / max(l2, 1e-6)
    return tuple(int(round(min(1.0, c * k) * 255)) for c in (r2, g2, b2))


def params(name, shade):
    """(hue, sat_mult, lum_mult) of a colour name and a shade"""
    n, hue, sm, lm = next(c for c in COLORS if c[0] == name)
    ss, ls = SHADES[shade]
    return hue, sm * ss, lm * ls
