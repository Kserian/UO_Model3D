"""refine the hand rotation per frame from the original weapon / shield frames (the body silhouette cannot tell how
the fist is turned): the calibrated stick (grip json) must follow the weapon sprite (chamfer), the body silhouette
must not get worse. usage: handfit.py poses_in.json grip.json poses_out.json [--w_body 40]"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
import sys, json, numpy as np
from multiprocessing import Pool
POS_IN, GRIP, POS_OUT = sys.argv[1:4]
W_BODY = float(sys.argv[sys.argv.index("--w_body") + 1]) if "--w_body" in sys.argv else 40.0
G = {}


def setup():
    sys.path.insert(0, HERE)
    from itemframes import load
    from shape13 import Shape, load_params
    from skel13 import Skel13
    import fastr
    r = np.load("rig_poses.npz"); v = np.load("views_all.npz"); bones = list(r["bones"])
    S = Shape(v["U"], v["BV"], v["BDOM"], bones); Vf = S.build(load_params("shape_r2.json"), full=True); V = Vf[S.used]
    K = Skel13(S, r["R"], r["parent"], bones, Vf)
    idx, w = fastr.sparse_weights(K.SW)
    g = json.load(open(GRIP))
    G.update(r=r, v=v, K=K, V=V, idx=idx, w=w, T=fastr.tris_of(S.faces), it=load(g["anim"]), g=g, P=json.load(open(POS_IN)),
             vk={tuple(int(x) for x in k): n for n, k in enumerate(v["keys"])}, fk={tuple(int(x) for x in k): n for n, k in enumerate(r["keys"])})


def chamfer(M, dt, pix, p0, u, L, ns=40):
    a = M @ np.r_[p0, 1]; b = M @ np.r_[p0 + u * L, 1]
    A = np.array([(a[0] + 1) * 68, (1 - a[1]) * 60]); B = np.array([(b[0] + 1) * 68, (1 - b[1]) * 60])
    t = np.linspace(0, 1, ns + 1)[:, None]; Q = A + (B - A) * t
    qi = np.clip(Q.astype(int), [0, 0], [135, 119])
    d1 = np.minimum(dt[qi[:, 1], qi[:, 0]], 15).mean()
    e = B - A; ll = e @ e + 1e-9; tt = np.clip(((pix - A) @ e) / ll, 0, 1)
    d2 = np.minimum(np.linalg.norm(A + np.outer(tt, e) - pix, axis=1), 15).mean()
    return 0.5 * (d1 + d2)


def work(key):
    from scipy.ndimage import distance_transform_edt
    from itemframes import canvas
    from posefit13 import Frame13
    from posefit import score_views
    from fk import rig_world
    r, v, K, g = G["r"], G["v"], G["K"], G["g"]
    a, i = map(int, key.split(",")); x0 = np.array(G["P"][key]["x"])
    bh = K.ix[g["bone"]]; p0 = np.array(g["grip"]); u = np.array(g["dir"]); L = g["length"]
    f = G["fk"][(a, i)]; vi = [G["vk"][(a, i, d)] for d in range(5)]
    wm = [canvas(G["it"].get((a, d)), i)[..., 3] > 0 for d in range(5)]
    dirs = [d for d in range(5) if wm[d].any()]
    if not dirs:
        return key, dict(G["P"][key], hand_fit=None)
    DT = {d: distance_transform_edt(~wm[d]) for d in dirs}; PIX = {d: np.argwhere(wm[d])[:, ::-1] + 0.5 for d in dirs}
    fr = Frame13(K, G["V"], G["idx"], G["w"], G["T"], r["Brel"], v["C"][vi], v["masks"][vi], list(range(5)), r["loc"][f], r["quat"][f])
    j0 = 3 * bh                                                            # hand rotation slots in x
    def cost(x):
        Sk = fr.skin(x); Ph = Sk[bh] @ K.R[bh]
        ch = np.mean([chamfer(v["C"][vi[d]] @ rig_world(d) @ Ph, DT[d], PIX[d], p0, u, L) for d in dirs])
        res = score_views(fr.V, np.array([fr.C[k] @ fr.RW[k] @ Sk for k in range(5)]), fr.idx, fr.w, fr.T, fr.masks)
        iou = (res[:, 0] / np.maximum(res[:, 1], 1)).mean()
        return ch - W_BODY * iou, ch, iou
    x = x0.copy(); f0, ch0, iou0 = cost(x); fb = f0
    for st in (0.4, 0.2, 0.1, 0.05, 0.025):
        for _ in range(3):
            imp = False
            for jj in list(range(j0, j0 + 3)) + [3 * K.ix[g["bone"].replace("hand", "forearm")] + k for k in range(3)]:
                for sg in (1, -1):
                    y = x.copy(); y[jj] += sg * st
                    fy, _, _ = cost(y)
                    if fy < fb - 1e-4: x, fb = y, fy; imp = True; break
            if not imp: break
    _, ch1, iou1 = cost(x)
    rec = dict(G["P"][key]); rec["x"] = list(map(float, x)); rec["iou"] = float(iou1)
    rec["hand_fit"] = dict(chamfer0=float(ch0), chamfer=float(ch1), iou0=float(iou0))
    return key, rec


if __name__ == "__main__":
    P = json.load(open(POS_IN)); out = {}
    with Pool(4, initializer=setup) as pool:
        for n, (k, rec) in enumerate(pool.imap_unordered(work, sorted(P))):
            out[k] = rec
            if n % 30 == 0:
                hf = [o["hand_fit"] for o in out.values() if o.get("hand_fit")]
                if hf: print("%d/%d chamfer %.2f -> %.2f px  body IoU %.4f -> %.4f" % (n + 1, len(P), np.mean([h["chamfer0"] for h in hf]), np.mean([h["chamfer"] for h in hf]),
                                np.mean([h["iou0"] for h in hf]), np.mean([o["iou"] for o in out.values() if o.get("hand_fit")])), flush=True)
    json.dump(out, open(POS_OUT, "w"))
    hf = [o["hand_fit"] for o in out.values() if o.get("hand_fit")]
    print("done: chamfer %.2f -> %.2f px, body IoU %.4f -> %.4f" % (np.mean([h["chamfer0"] for h in hf]), np.mean([h["chamfer"] for h in hf]),
          np.mean([h["iou0"] for h in hf]), np.mean([o["iou"] for o in out.values() if o.get("hand_fit")])))
