"""Put re-rendered actions into an existing render folder and pack the .vd: patch only the actions that are wrong instead of rendering all 35 again.

    python vd_splice.py BASE_RENDER PATCH_RENDER OUT.vd --actions 08_combat_idle_2h,12_attack_2h_bash [--dirs 3]

BASE_RENDER and PATCH_RENDER are render folders of render_uo_layer.py (LAYER folder with frames/ and meta.json, e.g. OUT/render/clothing); both with the same CANVAS / ANCHOR.
The frames of the listed actions (all directions, or only --dirs) in BASE_RENDER's copy are replaced by those of PATCH_RENDER, then vdtool packs the folder. BASE_RENDER is not changed.
"""
import argparse, os, shutil, subprocess, sys, tempfile, glob

HERE = os.path.dirname(os.path.abspath(__file__))
VDTOOL = os.path.join(HERE, "..", "vdtool", "vdtool.py")

ap = argparse.ArgumentParser()
ap.add_argument("base"); ap.add_argument("patch"); ap.add_argument("out")
ap.add_argument("--actions", required=True); ap.add_argument("--dirs", default="0,1,2,3,4"); ap.add_argument("--keep", help="keep the merged folder here")
a = ap.parse_args()
tmp = os.path.abspath(a.keep) if a.keep else tempfile.mkdtemp(prefix="vd_splice_")
if os.path.exists(tmp):
    shutil.rmtree(tmp)
shutil.copytree(a.base, tmp)
n = 0
for act in a.actions.split(","):
    for d in a.dirs.split(","):
        src = os.path.join(a.patch, "frames", act, "dir%s" % d)
        dst = os.path.join(tmp, "frames", act, "dir%s" % d)
        if not os.path.isdir(src):
            sys.exit("no frames in %s" % src)
        if os.path.isdir(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst); n += len(glob.glob(os.path.join(dst, "*.png")))
print("replaced %d frames of %s (dirs %s)" % (n, a.actions, a.dirs))
subprocess.run([sys.executable, VDTOOL, "pack", tmp, os.path.abspath(a.out)], check=True)
if not a.keep:
    shutil.rmtree(tmp)
