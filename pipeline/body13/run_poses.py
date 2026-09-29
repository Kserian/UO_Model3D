"""refit the pose of every non-mounted frame (multiprocessing). usage: run_poses.py shape.json out.json [--init poses.json] [--girth]"""
import sys, json, time, numpy as np
from multiprocessing import Pool
SHAPE, OUT = sys.argv[1], sys.argv[2]
INIT = sys.argv[sys.argv.index("--init") + 1] if "--init" in sys.argv else None
GIRTH = "--girth" in sys.argv
G = {}

def setup():
    from shape13 import Shape, PARTS, unflat, load_params
    import fastr
    r = np.load("rig_poses.npz"); v = np.load("views_all.npz"); bones = list(r["bones"])
    S = Shape(v["U"], v["BV"], v["BDOM"], bones)
    V = np.load(SHAPE)["V"] if SHAPE.endswith(".npz") else S.build(load_params(SHAPE))
    W13 = np.zeros((len(V), len(bones)))
    for j, q in enumerate(PARTS): W13[:, bones.index(q)] = S.PW[S.used][:, j]
    idx, w = fastr.sparse_weights(W13); T = fastr.tris_of(S.faces)
    G.update(r=r, v=v, V=V, idx=idx, w=w, T=T, vk={tuple(k): n for n, k in enumerate(v["keys"])},
             init=json.load(open(INIT)) if INIT else {})

def work(key):
    from posefit import Frame
    a, i = key; r, v = G["r"], G["v"]
    f = [n for n, k in enumerate(r["keys"]) if tuple(k) == (a, i)][0]
    vi = [G["vk"][(a, i, d)] for d in range(5)]
    fr = Frame(G["V"], G["idx"], G["w"], G["T"], r["R"], r["parent"], r["Brel"], v["C"][vi], v["masks"][vi], list(range(5)),
               r["loc"][f], r["quat"][f], movable=[True] * len(r["bones"]))
    x0 = np.array(G["init"]["%d,%d" % (a, i)]["x"]) if "%d,%d" % (a, i) in G["init"] else None
    t = time.time(); x, i0, i1, res = fr.fit(girth=GIRTH, x0=x0)
    return "%d,%d" % (a, i), {"x": list(map(float, x)), "iou0": float(i0), "iou": float(i1), "res": res.tolist()}

if __name__ == "__main__":
    v = np.load("views_all.npz")
    keys = sorted({(int(a), int(i)) for a, i, d in v["keys"]})
    out = {}; t = time.time()
    with Pool(4, initializer=setup) as pool:
        for n, (k, rr) in enumerate(pool.imap_unordered(work, keys)):
            out[k] = rr
            if n % 20 == 0:
                print("%d/%d  mean IoU %.4f -> %.4f  %.0fs" % (n + 1, len(keys), np.mean([o["iou0"] for o in out.values()]),
                      np.mean([o["iou"] for o in out.values()]), time.time() - t), flush=True)
    json.dump(out, open(OUT, "w"))
    print("done %d frames  mean IoU %.4f -> %.4f  %.0fs" % (len(out), np.mean([o["iou0"] for o in out.values()]), np.mean([o["iou"] for o in out.values()]), time.time() - t))
