"""refit every non-mounted frame on the 55-bone rig. usage: run_poses13.py shape.json out.json [--init poses.json] [--fix-extra] [--frames a,i;a,i]"""
import sys, json, time, numpy as np
from multiprocessing import Pool
SHAPE, OUT = sys.argv[1], sys.argv[2]
INIT = sys.argv[sys.argv.index("--init") + 1] if "--init" in sys.argv else None
G = {}

def setup():
    from shape13 import Shape, load_params
    from skel13 import Skel13
    import fastr
    r = np.load("rig_poses.npz"); v = np.load("views_all.npz"); bones = list(r["bones"])
    S = Shape(v["U"], v["BV"], v["BDOM"], bones)
    Vf = S.build(load_params(SHAPE), full=True); V = Vf[S.used]
    K = Skel13(S, r["R"], r["parent"], bones, Vf)
    idx, w = fastr.sparse_weights(K.SW); T = fastr.tris_of(S.faces)
    G.update(r=r, v=v, V=V, K=K, idx=idx, w=w, T=T, vk={tuple(k): n for n, k in enumerate(v["keys"])},
             init=json.load(open(INIT)) if INIT else {})

def convert(x, L, names):
    """old 19-bone layout (rot, loc, girth for all 19) -> 55-bone layout"""
    if len(x) == L.size: return np.array(x)
    y = L.zero(); x = np.array(x); y[:60] = x[:60]
    if len(x) > 60:
        g = x[60:].reshape(19, 2)
        for k, b in enumerate(L.gi): y[L.o_g + 2 * k:L.o_g + 2 * k + 2] = g[b]
    return y

def work(key):
    from posefit13 import Frame13
    a, i = key; r, v = G["r"], G["v"]
    f = [n for n, k in enumerate(r["keys"]) if tuple(k) == (a, i)][0]
    vi = [G["vk"][(a, i, d)] for d in range(5)]
    fr = Frame13(G["K"], G["V"], G["idx"], G["w"], G["T"], r["Brel"], v["C"][vi], v["masks"][vi], list(range(5)), r["loc"][f], r["quat"][f])
    k = "%d,%d" % (a, i)
    x0 = convert(G["init"][k]["x"], fr.L, G["K"].names) if k in G["init"] else None
    x, i0, i1, res = fr.fit(x0=x0, fix_extra="--fix-extra" in sys.argv)
    return k, {"x": list(map(float, x)), "iou0": float(i0), "iou": float(i1), "res": res.tolist()}

if __name__ == "__main__":
    v = np.load("views_all.npz")
    keys = sorted({(int(a), int(i)) for a, i, d in v["keys"]})
    if "--frames" in sys.argv:
        keys = [tuple(map(int, s.split(","))) for s in sys.argv[sys.argv.index("--frames") + 1].split(";")]
    out = {}; t = time.time()
    with Pool(4, initializer=setup) as pool:
        for n, (k, rr) in enumerate(pool.imap_unordered(work, keys)):
            out[k] = rr
            if n % 20 == 0 or len(keys) < 20:
                print("%d/%d  mean IoU %.4f -> %.4f  %.0fs" % (n + 1, len(keys), np.mean([o["iou0"] for o in out.values()]),
                      np.mean([o["iou"] for o in out.values()]), time.time() - t), flush=True)
    json.dump(out, open(OUT, "w"))
    print("done %d frames  mean IoU %.4f -> %.4f  %.0fs" % (len(out), np.mean([o["iou0"] for o in out.values()]), np.mean([o["iou"] for o in out.values()]), time.time() - t))
