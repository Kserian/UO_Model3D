"""refit every mounted frame (actions 23-29) on the 55-bone rig with horse occlusion + no-penetration.
usage: run_mounted13.py shape.json out.json [--init poses.json]"""
import sys, json, time, numpy as np
from multiprocessing import Pool
SHAPE, OUT = sys.argv[1], sys.argv[2]
INIT = sys.argv[sys.argv.index("--init") + 1] if "--init" in sys.argv else None
G = {}

def setup():
    from shape13 import Shape, load_params
    from skel13 import Skel13
    import fastr
    r = np.load("rig_poses.npz"); v = np.load("views_mounted.npz"); bones = list(r["bones"])
    S = Shape(v["U"], v["BV"], v["BDOM"], bones)
    Vf = S.build(load_params(SHAPE), full=True); V = Vf[S.used]
    K = Skel13(S, r["R"], r["parent"], bones, Vf)
    idx, w = fastr.sparse_weights(K.SW); T = fastr.tris_of(S.faces)
    legs = [K.ix[n] for n in K.names if n.startswith(("thigh", "shin", "foot", "toe", "pelvis"))]
    G.update(r=r, v=v, V=V, K=K, idx=idx, w=w, T=T, vk={tuple(k): n for n, k in enumerate(v["keys"])},
             pen_sel=np.nonzero(K.SW[:, legs].sum(1) > 0.5)[0], hs=np.load("horse_sdf.npz"), hm=np.load("horse.npz"),
             init=json.load(open(INIT)) if INIT else {})

def work(key):
    from mounted import MountedFrame
    a, i = key; r, v = G["r"], G["v"]
    f = [n for n, k in enumerate(r["keys"]) if tuple(k) == (a, i)][0]
    vi = [G["vk"][(a, i, d)] for d in range(5)]; tag = "%d_%d" % (a, i)
    fr = MountedFrame(G["K"], G["V"], G["idx"], G["w"], G["T"], r["Brel"], v["C"][vi], v["masks"][vi], list(range(5)), r["loc"][f], r["quat"][f],
                      HV=G["hm"]["v_" + tag], HT=G["hm"]["t_" + tag], sdf=G["hs"]["g_" + tag], lo=G["hs"]["lo_" + tag], pen_sel=G["pen_sel"])
    k = "%d,%d" % (a, i)
    x0 = np.array(G["init"][k]["x"]) if k in G["init"] else None
    fr.eval(fr.L.zero() if x0 is None else x0); p0 = fr.last_pen
    x, i0, i1, res = fr.fit(x0=x0); fr.eval(x)
    return k, {"x": list(map(float, x)), "iou0": float(i0), "iou": float(i1), "res": res.tolist(), "pen0": float(p0), "pen": float(fr.last_pen)}

if __name__ == "__main__":
    v = np.load("views_mounted.npz")
    keys = sorted({(int(a), int(i)) for a, i, d in v["keys"]})
    out = {}; t = time.time()
    with Pool(4, initializer=setup) as pool:
        for n, (k, rr) in enumerate(pool.imap_unordered(work, keys)):
            out[k] = rr
            if n % 10 == 0:
                print("%d/%d  mean IoU %.4f -> %.4f  pen %.3f -> %.3f  %.0fs" % (n + 1, len(keys), np.mean([o["iou0"] for o in out.values()]),
                      np.mean([o["iou"] for o in out.values()]), np.mean([o["pen0"] for o in out.values()]), np.mean([o["pen"] for o in out.values()]), time.time() - t), flush=True)
    json.dump(out, open(OUT, "w"))
    print("done %d frames  mean IoU %.4f -> %.4f  pen %.3f -> %.3f  %.0fs" % (len(out), np.mean([o["iou0"] for o in out.values()]), np.mean([o["iou"] for o in out.values()]),
          np.mean([o["pen0"] for o in out.values()]), np.mean([o["pen"] for o in out.values()]), time.time() - t))
