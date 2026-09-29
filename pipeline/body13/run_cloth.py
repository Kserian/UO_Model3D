"""fit a cloth chain rig to an item animation for every non-mounted frame (actions in parallel, frames in order,
each frame starts from the previous one). usage: run_cloth.py shape.json poses.json ANIM out.json"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
import sys, json, time, numpy as np
from multiprocessing import Pool
sys.path.insert(0, HERE)
SHAPE, POSES, ANIM, OUT = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
G = {}
from cloth13 import make_cloth, KINDS


def setup():
    from shape13 import Shape, load_params
    from skel13 import Skel13
    import fastr
    from itemframes import load
    r = np.load("rig_poses.npz"); v = np.load("views_all.npz"); bones = list(r["bones"])
    S = Shape(v["U"], v["BV"], v["BDOM"], bones); Vf = S.build(load_params(SHAPE), full=True); V = Vf[S.used]
    K = Skel13(S, r["R"], r["parent"], bones, Vf)
    kind, zt, zh = KINDS[ANIM]
    rig, CV, CF, CW, top, par = make_cloth(K, V, kind, zt, zh, faces=S.faces)
    G.update(r=r, v=v, V=V, K=K, T=fastr.tris_of(S.faces), rig=rig, CV=CV, CF=CF, CW=CW, par=par, it=load(ANIM),
             P=json.load(open(POSES)), vk={tuple(k): n for n, k in enumerate(v["keys"])}, fk={tuple(k): n for n, k in enumerate(r["keys"])})


def work(a):
    from posefit13 import Frame13
    from clothfit import ClothFrame
    from itemframes import canvas
    r, v = G["r"], G["v"]; out = {}; x = np.zeros(len(G["rig"].names) * 2)
    i = 0
    while "%d,%d" % (a, i) in G["P"]:
        f = G["fk"][(a, i)]
        fr = Frame13(G["K"], None, None, None, None, r["Brel"], None, None, [], r["loc"][f], r["quat"][f])
        Sb = fr.skin(np.array(G["P"]["%d,%d" % (a, i)]["x"]))
        vi = [G["vk"][(a, i, d)] for d in range(5)]
        masks = np.array([canvas(G["it"].get((a, d)), i)[..., 3] > 0 for d in range(5)])
        cf = ClothFrame(G["rig"], G["CV"], G["CF"], G["CW"], Sb, G["K"], G["V"], G["T"], v["C"][vi], list(range(5)), masks, G["par"],
                        prev=x.copy() if i > 0 else None)
        x = cf.fit(x)
        out["%d,%d" % (a, i)] = {"x": list(map(float, x)), "iou": float(cf.last["iou"]), "pen": float(cf.last["pen"])}
        i += 1
    return out


if __name__ == "__main__":
    P = json.load(open(POSES)); acts = sorted({int(k.split(",")[0]) for k in P})
    res = {}; t = time.time()
    with Pool(4, initializer=setup) as pool:
        for o in pool.imap_unordered(work, acts):
            res.update(o)
            print("%d frames  mean IoU %.4f  pen %.3f  %.0fs" % (len(res), np.mean([q["iou"] for q in res.values()]), np.mean([q["pen"] for q in res.values()]), time.time() - t), flush=True)
    json.dump(res, open(OUT, "w"))
    print("done", ANIM, len(res), "frames mean IoU %.4f" % np.mean([q["iou"] for q in res.values()]))
