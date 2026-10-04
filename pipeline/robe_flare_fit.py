"""Hem swing of loose garments, fitted on the ORIGINAL robes of the game (numpy, no Cycles): for every action / frame, 5 numbers (cloth_lib.robe_flare: the whole hem wider, shifted, stretched
along the stride) that, on top of the leg hull, best fit the sprites of several robes at once. Writes pipeline/robe_flare.json (used by render_uo_layer.py).

    python robe_flare_fit.py POSES.npz fit  OUT.json [--garments 469,447,970] [--acts 0,2,...] [--jobs 4] [--pw 1]
    python robe_flare_fit.py POSES.npz eval TABLE.json [--garments 469,447,970,455,971] [--acts ...] [--scale 1]

`fit`: per garment a replica tube (robe_calib.tube) whose rest shape is fitted on the stand frames (hull on, hem height -> margin / kappa as uo_bind_item.mark_cloth), then per frame Powell
over the 5 numbers maximising the summed IoU (rows below the hips, all 5 directions, all garments). The table is made relative to the stand (the mean of the stand frames is subtracted:
a new garment has its own rest shape, it only gets the change). `eval`: IoU of every garment with the table (0 numbers = hull only) - garments not used in `fit` are the test.
Mounted actions 23-29 are left out (the hem follows the legs there, CLOTH_MOUNTED).
"""
import argparse, json, os, sys
from multiprocessing import Pool
import numpy as np
from scipy import optimize

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import robe_calib as rc, cloth_lib as cl                                       # noqa: E402

MARGIN, KAPPA, MARGIN_SHORT, KAPPA_SHORT = 0.05, 0.8, 0.02, 0.5                 # uo_bind_item.py (CLOTH_*): long robe / garment above the knee
STAND = 4
G = {}


def hull_params(z_hem):
    t = min(max((z_hem - 0.15) / 0.15, 0.0), 1.0)
    return MARGIN + (MARGIN_SHORT - MARGIN) * t, KAPPA + (KAPPA_SHORT - KAPPA) * t


def setup(poses, ids, cache=None):
    """per garment: calibration object, rest-shape parameters, tube, base positions per frame"""
    for gid in ids:
        cal = rc.Calib(poses, os.path.join(HERE, "body13", "mul", "anim_%04d.vd" % gid))
        p = dict(rc.DEFAULT); p.update(hull=1, tent=1, drop=1.0, solve=0)
        for _ in range(2):                                                       # the hem height sets margin / kappa, which set the rest shape: twice
            p["margin"], p["kappa"] = hull_params(p["z_hem"])
            p = rc.fit_rest(cal, p)
        V0, T, E = rc.tube(p)
        G[gid] = dict(cal=cal, p=p, V0=V0, T=T,
                      ang=np.arctan2(V0[:, 1] + 0.02, V0[:, 0]), t=np.clip((p["z_top"] - V0[:, 2]) / (p["z_top"] - p["z_hem"]), 0, 1),
                      row_hip=rc.CANCH[1] - (p["hip"] - 0.07) * 36 * np.cos(np.radians(28.4557)), ip=cal.bones.index("pelvis"))
        print("garment %d: rx0 %.3f rx1 %.3f ry %.3f z_hem %.3f margin %.3f kappa %.3f" % (gid, p["rx0"], p["rx1"], p["ry"], p["z_hem"], p["margin"], p["kappa"]), flush=True)


def base(g, a, i):
    cal, p, V0, ip = g["cal"], g["p"], g["V0"], g["ip"]
    Sk = cal.skin[cal.index[(a, 0, i)]]
    X0 = (np.c_[V0, np.ones(len(V0))] @ Sk[ip].T)[:, :3]
    heads, tails = cal.caps.posed(Sk)
    X0 = X0 + cl.hull_push(V0, Sk[ip], heads, tails, cal.caps.radius, margin=p["margin"], kappa=p["kappa"], z_top=p["z_top"], z_hem=p["z_hem"], use_tent=True, drop=p["drop"])
    return X0, Sk


def counts(g, a, i, X0, Sk, coef, pw):
    d = cl.robe_flare(g["V0"], coef, z_top=g["p"]["z_top"], z_hem=g["p"]["z_hem"], pw=pw)
    X = X0 + d @ Sk[g["ip"]][:3, :3].T
    cal = g["cal"]; num = den = 0
    for dd in range(5):
        sp = cal.spr.get((a, dd))
        if sp is None or i >= len(sp) or not sp[i].any():
            continue
        D = cal.dirm[cal.index[(a, dd, i)]]
        m = rc.raster_mask(cal.project(X @ D[:3, :3].T + D[:3, 3]), g["T"])
        r0, g0 = m[int(g["row_hip"]):], sp[i][int(g["row_hip"]):]
        num += (r0 & g0).sum(); den += (r0 | g0).sum()
    return num, den


def joint_iou(ids, a, i, base_cache, coef, pw):
    """mean IoU over the garments (each its own pixels summed)"""
    s = []
    for gid in ids:
        n, d = counts(G[gid], a, i, *base_cache[gid], coef, pw)
        s.append(n / max(d, 1))
    return float(np.mean(s))


def fit_frame(args):
    ids, a, i, pw = args
    bc = {gid: base(G[gid], a, i) for gid in ids}
    s0 = joint_iou(ids, a, i, bc, np.zeros(5), pw)
    r = optimize.minimize(lambda x: 1 - joint_iou(ids, a, i, bc, x, pw), np.zeros(5), method="Powell", options=dict(xtol=0.01, ftol=1e-3, maxiter=4, direc=np.eye(5) * 0.08))
    x = np.clip(r.x, -0.4, 0.4)
    return a, i, s0, joint_iou(ids, a, i, bc, x, pw), [float(v) for v in x]


def frames(cal, acts):
    out = []
    for a in acts:
        nfr = int(cal.key[(cal.key[:, 0] == a) & (cal.key[:, 1] == 0)][:, 2].max()) + 1
        out += [(a, i) for i in range(nfr)]
    return out


def smooth(rows, loop):
    """[0.25, 0.5, 0.25] along the frames (cyclic for looping actions: walk, run, stand...), a single frame stays"""
    r = np.array(rows)
    if len(r) < 3:
        return r
    if loop:
        return 0.25 * np.roll(r, 1, 0) + 0.5 * r + 0.25 * np.roll(r, -1, 0)
    P = np.concatenate([r[:1], r, r[-1:]]); return 0.25 * P[:-2] + 0.5 * P[1:-1] + 0.25 * P[2:]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("poses"); ap.add_argument("mode", choices=["fit", "eval"]); ap.add_argument("table")
    ap.add_argument("--garments", default="469,447,970"); ap.add_argument("--acts", default=",".join(str(a) for a in range(35) if not 23 <= a <= 29))
    ap.add_argument("--jobs", type=int, default=4); ap.add_argument("--pw", type=float, default=1.0); ap.add_argument("--scale", type=float, default=1.0); ap.add_argument("--smooth", type=int, default=1)
    a = ap.parse_args()
    ids = [int(x) for x in a.garments.split(",")]; acts = [int(x) for x in a.acts.split(",")]
    setup(a.poses, ids)
    cal0 = G[ids[0]]["cal"]
    if a.mode == "fit":
        jobs = [(ids, ai, i, a.pw) for ai, i in frames(cal0, acts)]
        with Pool(a.jobs) as pool:
            res = pool.map(fit_frame, jobs, chunksize=2)
        raw = {}
        for ai, i, s0, s1, x in res:
            raw.setdefault(ai, []).append(x)
        print("fit: IoU hull only %.3f -> with per-frame swing %.3f (on the fitted frames, before smoothing and stand subtraction)" % (np.mean([r[2] for r in res]), np.mean([r[3] for r in res])))
        tab = {}
        for ai, rows in raw.items():
            tab[ai] = smooth(rows, ai in (0, 1, 2, 3, 4, 5, 6, 7, 8)) if a.smooth else np.array(rows)
        stand = np.mean(tab[STAND], 0)
        out = dict(comment="robe_flare_fit.py: hem swing coefficients (c0, c1c, c1s, c2c, c2s; m) per action and frame, relative to the stand, fitted jointly on the original robes %s; cloth_lib.robe_flare, pw %g" % (a.garments, a.pw),
                   pw=a.pw, actions={str(k): [[round(float(v), 4) for v in (row - stand)] for row in rows] for k, rows in tab.items()})
        json.dump(out, open(a.table, "w"), separators=(",", ":"))
        print("wrote", a.table)
    else:
        tb = json.load(open(a.table)); pw = tb["pw"]
        for gid in ids:
            by = {}
            for ai, i in frames(G[gid]["cal"], acts):
                rows = tb["actions"].get(str(ai))
                coef = np.array(rows[min(i, len(rows) - 1)]) * a.scale if rows else np.zeros(5)
                n0, d0 = counts(G[gid], ai, i, *base(G[gid], ai, i), np.zeros(5), pw)
                n1, d1 = counts(G[gid], ai, i, *base(G[gid], ai, i), coef, pw)
                by.setdefault(ai, []).append((n0 / max(d0, 1), n1 / max(d1, 1)))
            allv = np.array([v for r in by.values() for v in r])
            print("garment %d: IoU hull only %.3f -> with table %.3f | walk %.3f->%.3f run %.3f->%.3f atk %.3f->%.3f" % (
                gid, allv[:, 0].mean(), allv[:, 1].mean(), *np.mean(by[0], 0), *np.mean(by[2], 0), *np.mean(by[9], 0)), flush=True)
