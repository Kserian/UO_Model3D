"""Per-frame fit of a BENT cape to the original cloak (468): for every action / frame the pitch of the cape about the shoulders (phi0 at the shoulders, phi1 at the hem, back = +) that
best fits the sprite outside the body silhouette over all 5 directions. Shows how the game's cloak swings back with the action (stand: hangs; walk: slightly trailing; run: streams out).

    python cloak_fit_frames.py POSES.npz OUT.json [--acts 0,2,4,9] [--step 2]
"""
import argparse, json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import cloak_calib as cc, robe_calib as rc                          # noqa: E402

REST = dict(cc.DEFAULT); REST.update(ax=0.33, ay=0.30, arc=75.0, z_hem=0.30, cy=0.0, hull=0)    # a wide cape from the shoulders to the shins (shape search on stand, walk, run, attack, mounted)


def bent_cape(p, phi0, phi1, spread=1.0, flat=1.0):
    """partial tube behind the body, hanging along a centre line that tilts from phi0 (shoulders) to phi1 (hem) radians backwards; ring offsets turn with it"""
    N, K = int(p["n_around"]), int(p["n_rings"]); L = (p["z_top"] - p["z_hem"]) / K
    a0 = np.radians(90 - p["arc"]); a1 = np.radians(90 + p["arc"])
    V, T = [], []
    cy, cz = p["cy"], p["z_top"]
    for k in range(K + 1):
        t = k / K; phi = phi0 + (phi1 - phi0) * t
        ax = p["ax"] * (0.85 + 0.25 * t) * spread; ay = p["ay"] * (0.8 + 0.3 * t) * flat
        for i in range(N):
            a = a0 + (a1 - a0) * i / (N - 1)
            ex, ey = ax * np.cos(a), ay * np.sin(a)
            V.append((ex, cy + ey * np.cos(phi), cz + ey * np.sin(phi)))
        if k < K:
            cy += L * np.sin(phi); cz -= L * np.cos(phi)
    for k in range(K):
        for i in range(N - 1):
            a, b, c, d = k * N + i, k * N + i + 1, (k + 1) * N + i + 1, (k + 1) * N + i
            T += [(a, b, c), (a, c, d)]
    return np.array(V), np.array(T)


def attach(cal, p, V0, S):
    n = len(V0); z = V0[:, 2]
    ip, ic = cal.bones.index("pelvis"), cal.bones.index("chest")
    Vh = np.c_[V0, np.ones(n)]
    beta = np.clip(1 - (p["z_top"] - np.maximum(z, 0)) / 0.45, 0, 1)         # the top follows the chest, the rest the pelvis (as in cloak_calib)
    beta = np.where(np.arange(n) < int(p["n_around"]) * 3, 1.0, beta) if False else beta
    return (1 - beta)[:, None] * (Vh @ S[ip].T)[:, :3] + beta[:, None] * (Vh @ S[ic].T)[:, :3]


def frame_iou(cal, p, V0, T, a, i, S, dirs=range(5)):
    X0 = attach(cal, p, V0, S); num = den = 0
    for dr in dirs:
        g = cal.spr.get((a, dr))
        if g is None or i >= len(g): continue
        bm = cc.body_mask(a, dr, i)
        if bm is None: continue
        D = cal.dirm[cal.index[(a, dr, i)]]
        m = rc.raster_mask(cal.project(X0 @ D[:3, :3].T + D[:3, 3]), T) & ~bm; g0 = g[i] & ~bm
        num += (m & g0).sum(); den += (m | g0).sum()
    return num / max(den, 1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("poses"); ap.add_argument("out"); ap.add_argument("--acts", default="0,2,4,9,16,21"); ap.add_argument("--step", type=int, default=2)
    a = ap.parse_args()
    cal = cc.Cal(a.poses, os.path.join(HERE, "body13", "mul", "anim_0468.vd")); p = dict(REST)
    p["n_around"] = 16; p["n_rings"] = 12
    grid0 = np.radians(np.arange(0, 100, 10)); grid1 = np.radians(np.arange(-10, 111, 10))
    out = {}
    for act in (int(x) for x in a.acts.split(",")):
        nfr = int(cal.key[(cal.key[:, 0] == act) & (cal.key[:, 1] == 0)][:, 2].max()) + 1
        out[act] = []
        for i in range(0, nfr, a.step):
            S = cal.skin[cal.index[(act, 0, i)]]; best = (-1, 0, 0, 1)
            for p0 in grid0:
                for p1 in grid1:
                    for fl in (1.0,):
                        V0, T = bent_cape(p, p0, p1, 1.0, fl)
                        s = frame_iou(cal, p, V0, T, act, i, S)
                        if s > best[0]: best = (s, p0, p1, fl)
            out[act].append((i, round(float(best[0]), 3), round(float(np.degrees(best[1])), 0), round(float(np.degrees(best[2])), 0), best[3]))
            print(act, out[act][-1], flush=True)
        json.dump(out, open(a.out, "w"))
