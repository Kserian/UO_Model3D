"""Compare a rendered flail (clothing layer, render_uo_layer.py canvas) with an original flail animation (frames from vdtool.py extract): per frame the ball (the largest
thick blob: the item opened by one pixel) and the whole item (symmetric mean distance between the two sets of item pixels, px), on the common anchor.

    python flail_fit.py OURS_FRAMES OURS_ANCHOR ORIG_FRAMES ORIG_ANCHOR [--actions 01_walk_armed,...] [--json out.json]

    OURS_ANCHOR / ORIG_ANCHOR: "x,y" of the canvas anchor (render_uo_layer CANVAS anchor 128,192; vdtool extract prints it, e.g. 92,103).
Prints per action: frames, mean ball distance (px), mean item distance (px); and the total. docs/qa/flail.md.
"""
import argparse, glob, json, os
import numpy as np
from PIL import Image
from scipy import ndimage


def load(path, anc):
    a = np.array(Image.open(path).convert("RGBA")); m = a[..., 3] > 0
    ys, xs = np.nonzero(m)
    P = np.c_[xs - anc[0], ys - anc[1]].astype(float)
    op = ndimage.binary_opening(m, iterations=1); lab, k = ndimage.label(op)
    ball = None
    if k:
        sz = ndimage.sum(op, lab, range(1, k + 1)); j = int(np.argmax(sz)) + 1
        yy, xx = np.nonzero(lab == j); ball = np.array([xx.mean() - anc[0], yy.mean() - anc[1]])
    return P, ball


def setdist(A, B):
    from scipy.spatial import cKDTree
    return 0.5 * (cKDTree(B).query(A)[0].mean() + cKDTree(A).query(B)[0].mean())


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("ours"); ap.add_argument("oa"); ap.add_argument("orig"); ap.add_argument("ra")
    ap.add_argument("--actions", default=""); ap.add_argument("--json", default="")
    a = ap.parse_args(); oa = tuple(map(int, a.oa.split(","))); ra = tuple(map(int, a.ra.split(",")))
    acts = a.actions.split(",") if a.actions else sorted(os.listdir(a.ours))
    res = {}; allb = []; alli = []
    for act in acts:
        bs, its = [], []
        for f in sorted(glob.glob(os.path.join(a.ours, act, "dir*", "*.png"))):
            g = os.path.join(a.orig, act, os.path.basename(os.path.dirname(f)), os.path.basename(f))
            if not os.path.exists(g):
                continue
            P, b = load(f, oa); Q, c = load(g, ra)
            if len(P) < 3 or len(Q) < 3:
                continue
            its.append(setdist(P, Q))
            if b is not None and c is not None:
                bs.append(float(np.linalg.norm(b - c)))
        if its:
            res[act] = dict(frames=len(its), ball=float(np.mean(bs)) if bs else None, item=float(np.mean(its)))
            allb += bs; alli += its
            print("%-22s frames %3d  ball %5.1f px  item %5.1f px" % (act, len(its), res[act]["ball"] or -1, res[act]["item"]))
    print("FLAIL_FIT ball %.2f px  item %.2f px  (%d frames)" % (np.mean(allb), np.mean(alli), len(alli)))
    if a.json:
        json.dump(dict(actions=res, ball=float(np.mean(allb)), item=float(np.mean(alli))), open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()
