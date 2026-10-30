"""All the colours of the drum: 20 hues x 2 shades (light, dark), each with the animation (.vd), the paperdoll gumps (male 50490, female 60490), the art (0x1541 and its mirror 0x1542), and a preview sheet.

    python make_drum_colors.py OUT_DIR --vd Drum_meshy_sash.vd --blend ITEM.blend --gumps FOLDER [--only teal,red] [--shades light,dark] [--zip]

--vd: the animation of the red drum (recolor_vd.py rewrites the palettes of every block: no render). --blend: the item of the drum (uo_make_item.py); --gumps: the folder with gump12.png, gump13.png,
gump50490.png, gump60490.png (uo_gump_art.py). The paperdoll and the art are RENDERED again for every colour (uo_render_drum_gump.py, PD_COLOR): the texture's red is not enough to tell the shell from the hoops, and a
recolour of the finished pixels left the brass hoops red on a blue drum. The sheet previews: the gump, the art and a frame of the animation of each variant. Colours: drum_colors.py.
OUT_DIR/NN_name/light|dark/{Drum_meshy_sash_name_shade.vd, gump_male.png, gump_female.png, art.png, art_mirror.png}, OUT_DIR/preview_all.png, OUT_DIR/README_COLORS.md.
"""
import argparse, os, shutil, subprocess, sys, zipfile
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import drum_colors as dc
import recolor_vd as rv
import vd as vdread
import compose_layers as cl


def make_one(out, name, shade, vd_src, blend, gumps, idx):
    d = os.path.join(out, "%02d_%s" % (idx, name), shade); os.makedirs(d, exist_ok=True)
    hue, sm, lm = dc.params(name, shade)
    f = rv.make_map(hue, 0.0, 28.0, 0.30, 18.0, 0.08, 0.5, sm, lm)
    vd_out = os.path.join(d, "Drum_meshy_sash_%s_%s.vd" % (name, shade))
    rv.recolor_vd(vd_src, vd_out, f)
    tmp = os.path.join(d, "_pd"); os.makedirs(tmp, exist_ok=True)
    env = dict(os.environ, PD_OUT=tmp, PD_GUMPS=gumps, PD_SCRIPTS=HERE, PD_COLOR="%s:%s" % (name, shade))
    r = subprocess.run([sys.executable, "-I", os.path.join(HERE, "run_script_in_blend.py"), blend, os.path.join(HERE, "uo_render_drum_gump.py")], env=env, capture_output=True, text=True)
    if "PD art done" not in r.stdout:
        raise SystemExit("the paperdoll of %s %s failed:\n%s\n%s" % (name, shade, r.stdout[-1500:], r.stderr[-800:]))
    for fn in ("gump_male.png", "gump_female.png", "art.png", "art_mirror.png"):
        shutil.move(os.path.join(tmp, fn), os.path.join(d, fn))
    shutil.rmtree(tmp)
    return d, vd_out


def arts(out, cells, ncol=8):
    """OUT/arts/art_1541_name_shade.png (+ art_1542_ the mirror) and OUT/preview_arts.png (the art 3x on grey, the mirror beside it)"""
    ad = os.path.join(out, "arts"); os.makedirs(ad, exist_ok=True)
    cw, ch = 300, 120
    nrow = (len(cells) + ncol - 1) // ncol
    sh = Image.new("RGB", (ncol * cw, nrow * ch), (28, 30, 32)); dr = ImageDraw.Draw(sh)
    for n, (label, d, vdp) in enumerate(cells):
        tag = os.path.basename(os.path.dirname(d))[3:] + "_" + os.path.basename(d)
        shutil.copy(os.path.join(d, "art.png"), os.path.join(ad, "art_1541_%s.png" % tag))
        shutil.copy(os.path.join(d, "art_mirror.png"), os.path.join(ad, "art_1542_%s.png" % tag))
        x0, y0 = (n % ncol) * cw, (n // ncol) * ch
        for k, fn in enumerate(("art.png", "art_mirror.png")):
            a = Image.open(os.path.join(d, fn)).convert("RGBA"); bg = Image.new("RGBA", a.size, (70, 70, 70, 255)); bg.alpha_composite(a)
            sh.paste(bg.convert("RGB").resize((45 * 3, 32 * 3), Image.NEAREST), (x0 + 6 + k * 145, y0 + 18))
        dr.text((x0 + 6, y0 + 4), label, fill=(240, 240, 120))
    p = os.path.join(out, "preview_arts.png"); sh.save(p)
    return p


def sheet(out, cells, ncol=8):
    """cells: [(label, dir, vd path)]: the gump (male, the drum and the hip), the art and a frame of the stand (direction 2) of each variant"""
    body = vdread.read_vd(os.path.join(HERE, "body400.vd"))[2]
    cw, ch = 230, 350
    nrow = (len(cells) + ncol - 1) // ncol
    sh = Image.new("RGB", (ncol * cw, nrow * ch), (28, 30, 32)); dr = ImageDraw.Draw(sh)
    for n, (label, d, vdp) in enumerate(cells):
        x0, y0 = (n % ncol) * cw, (n // ncol) * ch
        g = Image.open(os.path.join(d, "gump_male.png")).convert("RGBA"); b = Image.open(os.path.join(os.path.dirname(os.path.dirname(d)), "_bodies", "gump12.png")).convert("RGBA")
        bg = Image.new("RGBA", b.size, (22, 22, 22, 255)); bg.alpha_composite(b); bg.alpha_composite(g)
        sh.paste(bg.crop((38, 112, 112, 182)).convert("RGB").resize((74 * 3, 70 * 3), Image.NEAREST), (x0 + 4, y0 + 20))
        a = Image.open(os.path.join(d, "art.png")).convert("RGBA"); abg = Image.new("RGBA", a.size, (60, 60, 60, 255)); abg.alpha_composite(a)
        sh.paste(abg.convert("RGB").resize((45 * 3, 32 * 3), Image.NEAREST), (x0 + 4, y0 + 20 + 216))
        fr = vdread.read_vd(vdp)[2][(4, 2)][0]; bf = body[(4, 2)][0]
        c = cl.over(cl.to_canvas(fr["img"], fr["cx"], fr["cy"]), cl.to_canvas(bf["img"], bf["cx"], bf["cy"]))
        bgc = np.zeros_like(c); bgc[...] = (90, 110, 90, 255)
        sh.paste(Image.fromarray(cl.over(c, bgc)).crop((108, 140, 148, 192)).convert("RGB").resize((40 * 2, 52 * 2), Image.NEAREST), (x0 + 4 + 45 * 3 + 10, y0 + 20 + 216))
        dr.text((x0 + 6, y0 + 4), label, fill=(240, 240, 120))
    p = os.path.join(out, "preview_all.png"); sh.save(p)
    return p


README = """# Drum_meshy: 20 colours x 2 shades

Every variant is in `NN_name/light|dark/`:
- `Drum_meshy_sash_<name>_<shade>.vd`: the animation (the original body sash + the drum), palettes recoloured, frames unchanged;
- `gump_male.png` (gump 50490), `gump_female.png` (gump 60490): paperdoll gumps, 260x237 (UOFiddler: Gumps, replace);
- `art.png` (art 0x1541, 45x32), `art_mirror.png` (art 0x1542).
`arts/`: all arts (`art_1541_name_shade.png`, mirror `art_1542_...`), `preview_arts.png`: them all on one sheet.\n`preview_all.png`: the gump, the art and a frame of the stand animation of each variant.
Light: saturation x0.85, luminance x1.45. Dark: saturation x1.0, luminance x0.62. The heads (cream) and the sash (grey) keep their colour; the shell and the brass hoops follow the hue.
Colours and shades: `pipeline/drum_colors.py`; generator: `pipeline/make_drum_colors.py`.
"""


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("out"); ap.add_argument("--vd", required=True); ap.add_argument("--blend", required=True); ap.add_argument("--gumps", required=True)
    ap.add_argument("--only", default=""); ap.add_argument("--shades", default="light,dark"); ap.add_argument("--zip", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    bodies = os.path.join(a.out, "_bodies"); os.makedirs(bodies, exist_ok=True)
    for g in ("gump12.png", "gump13.png"):
        shutil.copy(os.path.join(a.gumps, g), os.path.join(bodies, g))
    only = [x for x in a.only.split(",") if x]
    cells = []
    for idx, (name, hue, sm, lm) in enumerate(dc.COLORS, 1):
        if only and name not in only:
            continue
        for shade in a.shades.split(","):
            d, vdp = make_one(a.out, name, shade, a.vd, a.blend, a.gumps, idx)
            cells.append(("%02d %s %s  (hue %d)" % (idx, name, shade, hue), d, vdp))
            print("done %02d %s %s" % (idx, name, shade), flush=True)
    open(os.path.join(a.out, "README_COLORS.md"), "w").write(README)
    p = sheet(a.out, cells)
    print("arts:", arts(a.out, cells))
    print("preview:", p)
    shutil.rmtree(bodies, ignore_errors=True)
    if a.zip:
        zp = os.path.join(a.out, "Drum_meshy_colors.zip")
        with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
            for root, _, fs in os.walk(a.out):
                for fn in fs:
                    fp = os.path.join(root, fn)
                    if fp != zp:
                        z.write(fp, os.path.relpath(fp, a.out))
        print("zip:", zp)
