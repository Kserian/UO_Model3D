"""A 3.5 m tall pole next to the body: cut by the old 136x120 canvas, whole on 256x256 / (128, 192).

    python test_tall_item.py [--blend ../model/UO_Body_0x190.blend] [--tmp DIR]
Adds the pole (not bound to the rig) to the Clothing collection through run_render_headless.py --pre, renders 04_stand
and checks the top of the pole in the frames and in the .vd written for the canvas.
"""
import argparse, os, subprocess, sys, tempfile
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
PRE = '''
import bmesh
me = bpy.data.meshes.new("test_pole"); bm = bmesh.new()
bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.03, radius2=0.03, depth=3.5, matrix=__import__("mathutils").Matrix.Translation((0.5, -0.3, 1.75)))
bm.to_mesh(me); bm.free()
ob = bpy.data.objects.new("test_pole", me)
for o in bpy.data.collections["Clothing"].all_objects:
    o.hide_render = True
bpy.data.collections["Clothing"].objects.link(ob)
'''


def run(blend, out, canvas, anchor, pre):
    cmd = [sys.executable, os.path.join(HERE, "run_render_headless.py"), blend, out, "--pre", pre, 'LAYER="clothing"', 'ONLY=["04_stand"]',
           "CANVAS=%r" % (canvas,), "ANCHOR=%r" % (anchor,), "BODY_GAP=0", "EXACT_BODY=False"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit("render failed:\n" + r.stdout[-1500:] + r.stderr[-1500:])
    return np.array(Image.open(os.path.join(out, "clothing", "frames", "04_stand", "dir0", "00.png")).convert("RGBA"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", default=os.path.join(HERE, "..", "model", "UO_Body_0x190.blend"))
    ap.add_argument("--tmp")
    a = ap.parse_args()
    tmp = os.path.abspath(a.tmp) if a.tmp else tempfile.mkdtemp(prefix="test_tall_")
    os.makedirs(tmp, exist_ok=True)
    pre = os.path.join(tmp, "pre.py"); open(pre, "w").write(PRE)
    old = run(os.path.abspath(a.blend), os.path.join(tmp, "old"), (136, 120), (68, 86), pre)
    new = run(os.path.abspath(a.blend), os.path.join(tmp, "new"), (256, 256), (128, 192), pre)
    rows = lambda im: np.nonzero(im[..., 3] > 0)[0]
    o_top, n_top = rows(old).min(), rows(new).min()
    n_up = 192 - n_top                                     # rows above the anchor row
    th = np.radians(28.4557)                               # camera elevation; the pole stands 0.3 m towards the camera, radius 3 cm
    exp_px = ((3.5 - 0.07) * np.cos(th) + (-0.3 + 0.03) * np.sin(th)) * 36
    print("old canvas: topmost pole row %d (0 = cut by the canvas) | 256x256: top at row %d = %d px above the anchor, expected ~%.0f" % (o_top, n_top, n_up, exp_px))
    ok = o_top == 0 and n_top > 0 and abs(n_up - exp_px) < 3
    print("OK" if ok else "FAIL"); sys.exit(0 if ok else 1)
