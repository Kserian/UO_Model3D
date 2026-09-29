"""fit the cloth chains in the mounted actions (23-29): horse occlusion + no penetration of the horse proxy.
usage: run_cloth_mounted.py shape.json poses_mounted.json ANIM out.json"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
import sys, json, time, numpy as np
from multiprocessing import Pool
sys.path.insert(0, HERE)
SHAPE, POSES, ANIM, OUT = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
from cloth13 import make_cloth, KINDS
G = {}
W_PEN_M = float(sys.argv[sys.argv.index("--w_pen") + 1]) if "--w_pen" in sys.argv else 3.0     # leg penetration weight
W_HORSE_M = float(sys.argv[sys.argv.index("--w_horse") + 1]) if "--w_horse" in sys.argv else 3.0
REG_M = float(sys.argv[sys.argv.index("--reg") + 1]) if "--reg" in sys.argv else 0.002           # pull to the thigh start


def setup():
    from shape13 import Shape, load_params
    from skel13 import Skel13
    import fastr
    from itemframes import load
    r = np.load("rig_poses.npz"); v = np.load("views_mounted.npz"); bones = list(r["bones"])
    S = Shape(v["U"], v["BV"], v["BDOM"], bones); Vf = S.build(load_params(SHAPE), full=True); V = Vf[S.used]
    K = Skel13(S, r["R"], r["parent"], bones, Vf)
    rig, CV, CF, CW, top, par = make_cloth(K, V, *KINDS[ANIM], faces=S.faces)
    G.update(r=r, v=v, V=V, K=K, T=fastr.tris_of(S.faces), rig=rig, CV=CV, CF=CF, CW=CW, par=par, it=load(ANIM),
             P=json.load(open(POSES)), hs=np.load("horse_sdf.npz"), hm=np.load("horse.npz"),
             vk={tuple(int(x) for x in k): n for n, k in enumerate(v["keys"])}, fk={tuple(int(x) for x in k): n for n, k in enumerate(r["keys"])})


def thigh_init(rig, K, Sb):
    """skirt on horseback: front / side chains start along the thigh of their side, the back ones hang down"""
    from cloth13 import rotxz
    if rig.prefix != "skirt":
        return np.zeros(len(rig.names) * 2)
    x = np.zeros((rig.nc, rig.ns, 2))
    pb = K.ix["pelvis"]; Ppel = Sb[pb] @ K.R[pb]; base = Ppel @ np.linalg.inv(K.R[pb])
    for k in range(rig.nc):
        b0 = rig.bone(k, 0); R0 = base @ rig.R[b0]
        out = rig.R[b0][:3, 2]                                           # outward (rest)
        if out[1] > 0.5:                                                 # back of the skirt: hang down
            continue
        side = ".L" if out[0] >= 0 else ".R"
        th = K.ix["thigh" + side]; d = (Sb[th] @ K.R[th])[:3, 1]
        if abs(out[0]) < 0.3:                                            # front middle: between both thighs
            d = d + (Sb[K.ix["thigh.R" if side == ".L" else "thigh.L"]] @ K.R[K.ix["thigh.R" if side == ".L" else "thigh.L"]])[:3, 1]
        t = np.linalg.inv(R0[:3, :3]) @ (d / np.linalg.norm(d))
        az = np.arcsin(np.clip(-t[0], -1, 1)); ax = np.arctan2(t[2], t[1])
        x[k, 0] = (ax, az)
    return x.ravel()


def work(a):
    from posefit13 import Frame13
    from clothfit import MountedClothFrame
    from itemframes import canvas
    r, v = G["r"], G["v"]; out = {}; x = np.zeros(len(G["rig"].names) * 2)
    i = 0
    while "%d,%d" % (a, i) in G["P"]:
        f = G["fk"][(a, i)]; tag = "%d_%d" % (a, i)
        fr = Frame13(G["K"], None, None, None, None, r["Brel"], None, None, [], r["loc"][f], r["quat"][f])
        Sb = fr.skin(np.array(G["P"]["%d,%d" % (a, i)]["x"]))
        vi = [G["vk"][(a, i, d)] for d in range(5)]
        masks = np.array([canvas(G["it"].get((a, d)), i)[..., 3] > 0 for d in range(5)])
        cf = MountedClothFrame(G["rig"], G["CV"], G["CF"], G["CW"], Sb, G["K"], G["V"], G["T"], v["C"][vi], list(range(5)), masks, G["par"],
                               prev=x.copy() if i > 0 else None, HV=G["hm"]["v_" + tag], HT=G["hm"]["t_" + tag],
                               sdf=G["hs"]["g_" + tag], lo=G["hs"]["lo_" + tag], w_pen=W_PEN_M, w_horse=W_HORSE_M)
        xi = thigh_init(G["rig"], G["K"], Sb)
        if G["rig"].prefix == "skirt":
            cf.xref = xi; cf.reg = REG_M
        cands = [xi] + ([x] if i > 0 else [])
        x = max(cands, key=lambda c: cf.eval(c)[0])
        x = cf.fit(x)
        out["%d,%d" % (a, i)] = {"x": list(map(float, x)), "iou": float(cf.last["iou"]), "pen": float(cf.last["pen"]), "hpen": float(cf.last["hpen"])}
        i += 1
    return out


if __name__ == "__main__":
    P = json.load(open(POSES)); acts = sorted({int(k.split(",")[0]) for k in P})
    res = {}; t = time.time()
    with Pool(4, initializer=setup) as pool:
        for o in pool.imap_unordered(work, acts):
            res.update(o)
            print("%d frames  mean IoU %.4f  horse pen %.3f  %.0fs" % (len(res), np.mean([q["iou"] for q in res.values()]), np.mean([q["hpen"] for q in res.values()]), time.time() - t), flush=True)
    json.dump(res, open(OUT, "w"))
    print("done", ANIM, len(res), "frames mean IoU %.4f" % np.mean([q["iou"] for q in res.values()]))
