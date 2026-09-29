"""visualise fitted cloth (json) vs item sprite for given frames: cloth_view.py anim fits.json out.png a,i a,i ..."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
import sys, json, numpy as np
sys.path.insert(0, HERE)
from PIL import Image
from itemframes import load, canvas
from shape13 import Shape, load_params
from skel13 import Skel13
from posefit13 import Frame13
from cloth13 import make_cloth, KINDS
from clothfit import ClothFrame
import fastr
ANIM, FITS, OUT = int(sys.argv[1]), sys.argv[2], sys.argv[3]
frames = [tuple(map(int, s.split(","))) for s in sys.argv[4:]]
r = np.load("rig_poses.npz"); v = np.load("views_all.npz"); bones = list(r["bones"])
S = Shape(v["U"], v["BV"], v["BDOM"], bones); Vf = S.build(load_params("shape_r2.json"), full=True); V = Vf[S.used]
K = Skel13(S, r["R"], r["parent"], bones, Vf); T = fastr.tris_of(S.faces)
P = json.load(open("poses13_r3.json")); F = json.load(open(FITS)); it = load(ANIM)
kind, zt, zh = KINDS[ANIM]; rig, CV, CF, CW, top, par = make_cloth(K, V, kind, zt, zh, faces=S.faces)
fk = {tuple(int(x) for x in k): n for n, k in enumerate(r["keys"])}; vk = {tuple(int(x) for x in k): n for n, k in enumerate(v["keys"])}
rows = []
for a, i in frames:
    f = fk[(a, i)]; fr = Frame13(K, None, None, None, None, r["Brel"], None, None, [], r["loc"][f], r["quat"][f])
    Sb = fr.skin(np.array(P["%d,%d" % (a, i)]["x"])); vi = [vk[(a, i, d)] for d in range(5)]
    masks = np.array([canvas(it.get((a, d)), i)[..., 3] > 0 for d in range(5)])
    cf = ClothFrame(rig, CV, CF, CW, Sb, K, V, T, v["C"][vi], list(range(5)), masks, par)
    m = cf.masks_of(cf.verts(np.array(F["%d,%d" % (a, i)]["x"])))
    tiles = []
    for d in range(5):
        img = np.zeros((120, 136, 3), np.uint8) + 20; img[np.isfinite(cf.BD[d])] = (70, 70, 70)
        img[m[d] & masks[d]] = (170, 170, 170); img[m[d] & ~masks[d]] = (230, 60, 60); img[~m[d] & masks[d]] = (60, 120, 255)
        tiles.append(np.pad(img[10:110, 23:113], ((1, 1), (1, 1), (0, 0)), constant_values=90))
    rows.append(np.concatenate(tiles, 1))
im = Image.fromarray(np.concatenate(rows, 0)); im.resize((im.width * 2, im.height * 2), Image.NEAREST).save(OUT)
