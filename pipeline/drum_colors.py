"""The colours of the drum: 20 colours x 2 shades (light, dark), and the one function that turns a red colour into another.

    from drum_colors import COLORS, SHADES, recolor_rgb

COLORS: (name, hue in degrees, saturation factor, luminance factor of that hue: a yellow of the same value is much lighter than a blue); SHADES: (saturation factor, luminance factor).
recolor_rgb(rgb, hue, sat_mult, lum_mult): hue to `hue`, saturation x sat_mult (0 = grey), the colour then scaled to the luminance (0.299 R + 0.587 G + 0.114 B) of the original x lum_mult, so the
light and the dark of the shell survive. Used for the palettes of the .vd (recolor_vd.py) and for the pixels of the shell in the paperdoll (uo_render_drum_gump.py).
"""
import colorsys

COLORS = [
    ("yellow", 55, 0.85, 1.45), ("orange", 24, 1.00, 1.10), ("red", 0, 1.00, 1.00), ("green", 125, 0.90, 1.00), ("blue", 225, 1.00, 1.00),
    ("violet", 265, 0.95, 1.00), ("brown", 22, 0.60, 0.70), ("grey", 0, 0.00, 1.10), ("navy", 232, 1.00, 0.50), ("pink", 335, 0.60, 1.25),
    ("turquoise", 178, 0.90, 1.10), ("lime", 88, 0.85, 1.20), ("teal", 168, 0.90, 0.80), ("burgundy", 345, 1.00, 0.60), ("gold", 43, 1.00, 1.15),
    ("olive", 68, 0.70, 0.85), ("magenta", 308, 0.95, 1.00), ("sky", 205, 0.80, 1.25), ("beige", 40, 0.30, 1.30), ("purple", 285, 0.90, 0.85),
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
