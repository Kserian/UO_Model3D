"""Cloak (cape) against the ORIGINAL cloak of the game, in numpy (same machinery as robe_calib.py): a replica cape that hangs from the shoulders behind the body, posed by pose_capture.py,
pushed out by the legs (cloth_lib.hull_push), compared with the sprite frame by frame on the pixels OUTSIDE the silhouette of the body (the cloak behind the body is hidden by it).

    python cloak_calib.py POSES.npz [--sprite pipeline/body13/mul/anim_0468.vd] [--set k=v,...] [--sweep name=v1,v2,...] [--fit-rest]
"""
import argparse, itertools, os, sys, json
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import robe_calib as rc                                          # noqa: E402
import cloth_lib as cl                                           # noqa: E402

CW, CH = rc.CW, rc.CH
DEFAULT = dict(z_top=1.52, z_hem=0.60, ax=0.20, ay=0.20, arc=70.0, cy=0.0, hull=1, margin=0.03, kappa=0.6, drop=1.0, top_follow=1.0, n_around=24, n_rings=20, ramp=0.15)
BODY = os.path.join(HERE, "..", "client", "body_0x190_frames")


def cape(p):
    """a partial tube behind the body (+Y is the back): half angle `arc` around the back direction"""
    N, K = int(p["n_around"]), int(p["n_rings"]); V, T = [], []
    a0 = np.radians(90 - p["arc"]); a1 = np.radians(90 + p["arc"])
    for k in range(K + 1):
        z = p["z_top"] + (p["z_hem"] - p["z_top"]) * k / K
        t = (p["z_top"] - z) / (p["z_top"] - p["z_hem"])
        ax = p["ax"] * (0.85 + 0.25 * t); ay = p["ay"] * (0.8 + 0.3 * t)
        for i in range(N):
            a = a0 + (a1 - a0) * i / (N - 1)
            V.append((ax * np.cos(a), p["cy"] + ay * np.sin(a), z))
    for k in range(K):
        for i in range(N - 1):
            a, b, c, d = k * N + i, k * N + i + 1, (k + 1) * N + i + 1, (k + 1) * N + i
            T += [(a, b, c), (a, c, d)]
    return np.array(V), np.array(T)


_BODY_MASKS = {}


def body_mask(a, d, i):
    key = (a, d)
    if key not in _BODY_MASKS:
        import glob
        meta = json.load(open(os.path.join(BODY, "meta.json")))
        blk = next((b for b in meta["blocks"] if b["action"] == a and b["dir"] == d), None)
        ms = []
        if blk:
            for f in blk["frames"]:
                im = np.array(Image.open(os.path.join(BODY, "frames", "%02d_%s" % (a, blk["name"]), "dir%d" % d, f["file"])).convert("RGBA"))[..., 3] > 0
                ms.append(im)
        _BODY_MASKS[key] = ms
    ms = _BODY_MASKS[key]
    return ms[i] if i < len(ms) else None


class Cal(rc.Calib):
    def evaluate(self, p, acts=(4, 0, 2, 9, 16, 21)):
        V0, T = cape(p); n = len(V0)
        z = V0[:, 2]; t = np.clip((p["z_top"] - z) / (p["z_top"] - p["z_hem"]), 0, 1)
        ip, ic = self.bones.index("pelvis"), self.bones.index("chest")
        beta = np.clip(1 - (p["z_top"] - z) / max(p["z_top"] - 1.1, 0.05), 0, 1) * p["top_follow"]       # the shoulders follow the chest, the hanging part the pelvis
        Vh = np.c_[V0, np.ones(n)]
        res = []
        for a in acts:
            nfr = int(self.key[(self.key[:, 0] == a) & (self.key[:, 1] == 0)][:, 2].max()) + 1
            for i in range(nfr):
                S = self.skin[self.index[(a, 0, i)]]
                X0 = (1 - beta)[:, None] * (Vh @ S[ip].T)[:, :3] + beta[:, None] * (Vh @ S[ic].T)[:, :3]
                if p["hull"]:
                    heads, tails = self.caps.posed(S)
                    keep = np.array(["foot" not in self.bones[j] for j in self.caps.idx])
                    X0 = X0 + cl.hull_push(V0, S[ip], heads[keep], tails[keep], self.caps.radius[keep], centre_xy=(0.0, p["cy"]), margin=p["margin"], kappa=p["kappa"],
                                           z_top=p["z_top"], z_hem=p["z_hem"], ramp=p["ramp"], drop=p["drop"], rho_top=0.2)
                for dr in range(5):
                    D = self.dirm[self.index[(a, dr, i)]]
                    m = rc.raster_mask(self.project(X0 @ D[:3, :3].T + D[:3, 3]), T)
                    g = self.spr.get((a, dr))
                    if g is None or i >= len(g):
                        continue
                    g = g[i]; bm = body_mask(a, dr, i)
                    if bm is None:
                        continue
                    ok = ~bm                                          # outside the silhouette of the body only
                    r0, g0 = m & ok, g & ok
                    if not g0.any() and not r0.any():
                        continue
                    res.append(dict(a=a, d=dr, i=i, iou=(r0 & g0).sum() / max((r0 | g0).sum(), 1), dw=float(r0.sum() - g0.sum())))
        return res, {}


def summarize(res):
    s = dict(frames=len(res), iou=float(np.mean([r["iou"] for r in res])), px=float(np.mean([r["dw"] for r in res])), by={})
    for a in sorted({r["a"] for r in res}):
        q = [r for r in res if r["a"] == a]; s["by"][a] = (float(np.mean([r["iou"] for r in q])), float(np.mean([r["dw"] for r in q])))
    return s


def fmt(s):
    return "IoU(outside the body) %.3f | area %+.1f px | %s" % (s["iou"], s["px"], " ".join("%d:%.2f/%+.0f" % (a, v[0], v[1]) for a, v in s["by"].items()))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("poses"); ap.add_argument("--sprite", default=os.path.join(HERE, "body13", "mul", "anim_0468.vd")); ap.add_argument("--set", default="")
    ap.add_argument("--sweep", action="append", default=[]); ap.add_argument("--fit-rest", action="store_true"); ap.add_argument("--acts", default="4,0,2,9,16,21")
    a = ap.parse_args()
    cal = Cal(a.poses, a.sprite); p = dict(DEFAULT)
    for kv in filter(None, a.set.split(",")):
        k, v = kv.split("="); p[k] = float(v)
    acts = tuple(int(x) for x in a.acts.split(","))
    if a.fit_rest:
        from scipy import optimize
        keys = ("ax", "ay", "arc", "z_hem", "cy"); q = dict(p); q["hull"] = 0
        def cost(x):
            for k, v in zip(keys, x):
                q[k] = float(v)
            r, _ = cal.evaluate(q, (4,)); return 1 - np.mean([e["iou"] for e in r])
        r = optimize.minimize(cost, [q[k] for k in keys], method="Nelder-Mead", options=dict(xatol=0.003, fatol=1e-4, maxiter=150))
        p.update({k: float(v) for k, v in zip(keys, r.x)}); print("rest shape:", {k: round(p[k], 3) for k in keys})
    sweeps = [(sw.split("=")[0], [float(x) for x in sw.split("=")[1].split(",")]) for sw in a.sweep]
    for combo in itertools.product(*[v for _, v in sweeps]) if sweeps else [()]:
        q = dict(p); q.update({k: v for (k, _), v in zip(sweeps, combo)})
        print(" ".join("%s=%g" % (k, v) for (k, _), v in zip(sweeps, combo)) or "default", "|", fmt(summarize(cal.evaluate(q, acts)[0])), flush=True)
