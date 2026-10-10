"""Skin showing through an item on the frames: the 'all' preview (body and item rendered together in 3D, render_uo_layer.py LAYER "all") with the item flat blue and the
body flat by part (hands red, head green, arms yellow, torso magenta, legs cyan), then the pixels of pure arm / torso colour are counted (blends at the edge of a hand
read as magenta and are left out). The clothing layer cannot show this: there the item is drawn over the body even where the skin is in front of it.

    python item_skin_check.py ITEM.blend OUT_DIR [--actions 04_stand,17_spell_area,...] [--sheet 17_spell_area]

Prints per action the arm / torso pixels and the frames with any; --sheet writes OUT_DIR/marked_<action>.png (5 directions x frames, the counted pixels circled:
black = arm, orange = torso, blue = leg). Torso pixels next to the head (the neck above a collar) do not count; the pelvis under a short hem does (look at the sheet).
Runs the render (about 7 min for all actions); OUT_DIR/all/frames is reused when it is there.
"""
import os, sys, glob, subprocess
import numpy as np

COLS = {"hand": (1, 0, 0), "head": (0, 1, 0), "arm": (1, 1, 0), "torso": (1, 0, 1), "leg": (0, 1, 1)}


def colour_scene():
    """the --pre part (run_render_headless.py): flat emission colours on the items and the body parts"""
    import bpy

    def emit(name, c):
        m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
        e = nt.nodes.new("ShaderNodeEmission"); e.inputs[0].default_value = (*c, 1); o = nt.nodes.new("ShaderNodeOutputMaterial"); nt.links.new(e.outputs[0], o.inputs[0])
        return m
    blue = emit("check_item", (0.0, 0.25, 1.0))
    for ob in bpy.data.collections["Clothing"].all_objects:
        if ob.type == "MESH":
            ob.data.materials.clear(); ob.data.materials.append(blue)
            for p in ob.data.polygons:
                p.material_index = 0
    body = bpy.data.objects["UO_Body"]; me = body.data
    names = [g.name for g in body.vertex_groups]
    W = np.zeros((len(me.vertices), len(names)))
    for v in me.vertices:
        for g in v.groups:
            W[v.index, g.group] = g.weight

    def part(n):
        b = n.split(".")[0]
        return "hand" if (b == "hand" or b.startswith("finger")) else "head" if b == "head" else "arm" if b in ("upper_arm", "forearm") else "leg" if b in ("thigh", "shin", "foot") else "torso"
    order = list(COLS)
    me.materials.clear()
    for k in order:
        me.materials.append(emit("check_" + k, COLS[k]))
    for p in me.polygons:
        p.material_index = order.index(part(names[W[list(p.vertices)].sum(0).argmax()]))


def masks(a):
    from scipy.ndimage import binary_dilation
    r, g, b, al = a[..., 0], a[..., 1], a[..., 2], a[..., 3] > 0
    arm = al & (r > 200) & (g > 200) & (b < 80)
    tor = al & (r > 200) & (b > 200) & (g < 80)
    head = al & (g > 150) & (r < 110) & (b < 110); red = al & (r > 150) & (g < 110) & (b < 110)
    tor &= ~binary_dilation(head, iterations=4) & ~binary_dilation(red, iterations=2)
    arm &= ~binary_dilation(red, iterations=1)
    return arm, tor


def leg_mask(a):
    """legs (cyan): a robe / skirt hem that ends above the feet shows them legitimately below it, so this is reported apart (arm / torso are what must stay covered)"""
    r, g, b, al = a[..., 0], a[..., 1], a[..., 2], a[..., 3] > 0
    return al & (r < 110) & (g > 200) & (b > 200)


def main():
    from PIL import Image, ImageDraw
    args = sys.argv[1:]
    blend, out = os.path.abspath(args.pop(0)), os.path.abspath(args.pop(0))
    acts, sheets = [], []
    while args:
        f = args.pop(0)
        if f == "--actions":
            acts = args.pop(0).split(",")
        elif f == "--sheet":
            sheets.append(args.pop(0))
    here = os.path.dirname(os.path.abspath(__file__))
    if not os.path.isdir(os.path.join(out, "all", "frames")):
        subprocess.run([sys.executable, os.path.join(here, "run_render_headless.py"), blend, out, "--pre", os.path.abspath(__file__), 'LAYER="all"', "EXACT_COLORS=False",
                        "EXACT_BODY=False", "ONLY=%r" % (acts,), "CANVAS=(256,256)", "ANCHOR=(128,192)"], check=True, capture_output=True)
    tot = [0, 0, 0, 0, 0]
    for act in sorted(os.listdir(os.path.join(out, "all", "frames"))):
        if acts and act not in acts:
            continue
        arm = tor = leg = fr = bad = 0
        for f in sorted(glob.glob(os.path.join(out, "all", "frames", act, "dir*", "*.png"))):
            im = np.array(Image.open(f).convert("RGBA")).astype(int); m1, m2 = masks(im)
            leg += int(leg_mask(im).sum()); arm += int(m1.sum()); tor += int(m2.sum()); fr += 1; bad += int((m1.sum() + m2.sum()) > 0)
        tot = [tot[0] + fr, tot[1] + arm, tot[2] + tor, tot[3] + bad, tot[4] + leg]
        print("%-26s frames %4d  arm px %4d  torso px %4d  frames with any %d  (leg px %d)" % (act, fr, arm, tor, bad, leg))
    print("ITEM_SKIN frames %d, arm px %d, torso px %d, frames with any %d, leg px %d" % tuple(tot))
    for act in sheets:
        rows = []
        for d in range(5):
            row = []
            for f in sorted(glob.glob(os.path.join(out, "all", "frames", act, "dir%d" % d, "*.png"))):
                a = np.array(Image.open(f).convert("RGBA")).astype(int); m1, m2 = masks(a)
                crop = (88, 90, 168, 200)
                im = Image.new("RGBA", a.shape[1::-1], (255, 255, 255, 255)); im.alpha_composite(Image.fromarray(a.astype(np.uint8)))
                im = im.crop(crop).resize(((crop[2] - crop[0]) * 4, (crop[3] - crop[1]) * 4), Image.NEAREST); dr = ImageDraw.Draw(im)
                for m, c in ((m1, (0, 0, 0)), (m2, (255, 120, 0)), (leg_mask(a), (0, 160, 255))):
                    for y, x in zip(*np.nonzero(m)):
                        X = (x - crop[0]) * 4 + 2; Y = (y - crop[1]) * 4 + 2; dr.ellipse((X - 5, Y - 5, X + 5, Y + 5), outline=c, width=2)
                row.append(im)
            rows.append(row)
        W = Image.new("RGB", (max(len(r) for r in rows) * 320, 440 * len(rows)), (255, 255, 255))
        for i, r in enumerate(rows):
            for j, t in enumerate(r):
                W.paste(t.convert("RGB"), (j * 320, i * 440))
        W.resize((W.width // 2, W.height // 2)).save(os.path.join(out, "marked_%s.png" % act))


if __name__ == "__pre__":
    colour_scene()
elif __name__ == "__main__":
    main()
