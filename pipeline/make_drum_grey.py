"""The drum in a neutral light grey to be dyed in the client: only the .vd, the gumps (male 50490, female 60490) and the art (0x1541 and the mirror 0x1542), with the body sash and without it.

    python make_drum_grey.py OUT_DIR --vd Drum_meshy_sash.vd --vd-nosash Drum_meshy_nosash.vd --blend ITEM.blend --gumps FOLDER

OUT_DIR/with_bodysash/ and OUT_DIR/no_bodysash/ (the files end with _nosash): Wearable_drum_by_Levy_lightgrey[_nosash].vd, ..._gump_male.png, ..._gump_female.png, ..._art_1541.png, ..._art_1542.png.
Every pixel is r = g = b (the client dyes the grey levels of an item): the .vd palettes are recoloured as in make_drum_colors.py (colour lightgrey of drum_colors.py), then every palette entry is set to its luminance; the
gumps and the arts are rendered again (uo_render_drum_gump.py, PD_COLOR=lightgrey:base, PD_GREY=1).
"""
import argparse, os, shutil, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import drum_colors as dc
import recolor_vd as rv


def build(out, vd_src, blend, gumps, nosash):
    os.makedirs(out, exist_ok=True)
    suffix = "_nosash" if nosash else ""
    prefix = "Wearable_drum_by_Levy_lightgrey" + suffix
    hue, sm, lm = dc.params("lightgrey", "base")
    f0 = rv.make_map(hue, 0.0, 28.0, 0.30, 18.0, 0.08, 0.5, sm, lm)

    def f(rgb):
        r, g, b = f0(rgb)
        v = int(round(0.299 * r + 0.587 * g + 0.114 * b))
        return (v, v, v)
    rv.recolor_vd(vd_src, os.path.join(out, prefix + ".vd"), f)
    tmp = os.path.join(out, "_pd"); os.makedirs(tmp, exist_ok=True)
    env = dict(os.environ, PD_OUT=tmp, PD_GUMPS=gumps, PD_SCRIPTS=HERE, PD_COLOR="lightgrey:base", PD_GREY="1", PD_NOSASH="1" if nosash else "")
    r = subprocess.run([sys.executable, "-I", os.path.join(HERE, "run_script_in_blend.py"), blend, os.path.join(HERE, "uo_render_drum_gump.py")], env=env, capture_output=True, text=True)
    if "PD art done" not in r.stdout:
        raise SystemExit("the paperdoll failed:\n%s\n%s" % (r.stdout[-1500:], r.stderr[-800:]))
    for fn, name in (("gump_male.png", "_gump_male.png"), ("gump_female.png", "_gump_female.png"), ("art.png", "_art_1541.png"), ("art_mirror.png", "_art_1542.png")):
        shutil.move(os.path.join(tmp, fn), os.path.join(out, prefix + name))
    shutil.rmtree(tmp)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("out"); ap.add_argument("--vd", required=True); ap.add_argument("--vd-nosash", required=True); ap.add_argument("--blend", required=True); ap.add_argument("--gumps", required=True)
    a = ap.parse_args()
    build(os.path.join(a.out, "with_bodysash"), a.vd, a.blend, a.gumps, False)
    build(os.path.join(a.out, "no_bodysash"), a.vd_nosash, a.blend, a.gumps, True)
    print("done", a.out)
