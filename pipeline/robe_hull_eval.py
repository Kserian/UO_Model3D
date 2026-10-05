"""Leg hull of loose garments against the five ORIGINAL robes / skirts of the game (numpy, no Cycles, ~1 min): which hull gives the best lower-body IoU?

    python robe_hull_eval.py POSES.npz [--garments 469,447,970,455,971] [--rel-kappa 0.15,0.25,0.4,0.6]

POSES.npz from pose_capture.py. Per garment a replica tube whose rest shape is fitted on the stand frames without hull (as in robe_physics.md), then robe_calib.evaluate on all actions except
the mounted 23-29: no hull / the production hull (absolute: the legs push the cloth out to their reach + margin; margin / kappa by hem height as in uo_bind_item.py) /
`hull_push_rel` (EXPERIMENT, not used in production: only what the legs reach beyond their REST reach pushes, by kappa times the excess). Sprites: body13/mul/anim_0447 (dress), 0455 (kilt),
0469 (robe), 0970 (shroud), 0971 (skirt), all from anim.mul. Result and why the relative hull was not adopted: docs/qa/robe_physics.md, "Sesja 16".
"""
import argparse, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import robe_calib as rc, cloth_lib as cl                                       # noqa: E402

MARGIN, KAPPA, MARGIN_SHORT, KAPPA_SHORT = 0.05, 0.8, 0.02, 0.5                 # production hull (absolute): long robe / garment above the knee, blended between hem 0.15 and 0.30 m


def abs_params(z_hem):
    t = min(max((z_hem - 0.15) / 0.15, 0.0), 1.0)
    return MARGIN + (MARGIN_SHORT - MARGIN) * t, KAPPA + (KAPPA_SHORT - KAPPA) * t


def hull_push_rel(Vrest, S_pelvis, heads, tails, radius, rest_heads, rest_tails, centre_xy=(0.0, -0.02), kappa=0.25, z_top=1.02, z_hem=0.05, ramp=0.15, nth=48, nz=36, drop=1.0):
    """hull relative to the rest pose of the legs: a garment is modelled around the legs at rest, so only the reach beyond the rest reach pushes the cloth (kappa times the excess, radially,
    a tent from the waist: 0 at the waist, the excess at the height of the leg)"""
    Sinv = np.linalg.inv(S_pelvis)
    C, R = cl.sample_capsules(heads, tails, radius)
    Cr = (np.c_[C, np.ones(len(C))] @ Sinv.T)[:, :3]
    C0, R0 = cl.sample_capsules(rest_heads, rest_tails, radius)
    zs = np.linspace(z_hem, z_top, nz)
    _, H = cl.hull_field(Cr, R, zs, centre_xy, nth); _, H0 = cl.hull_field(C0, R0, zs, centre_xy, nth)
    H, H0 = cl.smooth_field(H), cl.smooth_field(H0)
    E = np.where(H > 0, np.maximum(H - H0, 0.0), 0.0)
    E = cl.smooth_field(cl.tent(E, zs, z_top, 0.0, drop), 2, 1)
    u = Vrest[:, :2] - np.asarray(centre_xy); rho = np.linalg.norm(u, axis=1); ang = np.mod(np.arctan2(u[:, 1], u[:, 0]), 2 * np.pi)
    fa = ang / (2 * np.pi) * nth; i0 = np.floor(fa).astype(int) % nth; i1 = (i0 + 1) % nth; wa = fa - np.floor(fa)
    fz = np.clip((Vrest[:, 2] - z_hem) / (z_top - z_hem), 0, 1) * (nz - 1); k0 = np.minimum(np.floor(fz).astype(int), nz - 2); wz = fz - k0
    e = E[i0, k0] * (1 - wa) * (1 - wz) + E[i1, k0] * wa * (1 - wz) + E[i0, k0 + 1] * (1 - wa) * wz + E[i1, k0 + 1] * wa * wz
    free = np.clip((z_top - Vrest[:, 2]) / ramp, 0, 1)
    d_rest = np.zeros((len(Vrest), 3)); d_rest[:, :2] = (kappa * e * free)[:, None] * u / np.maximum(rho, 1e-9)[:, None]
    return d_rest @ S_pelvis[:3, :3].T


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("poses"); ap.add_argument("--garments", default="469,447,970,455,971"); ap.add_argument("--rel-kappa", default="0.15,0.25,0.4,0.6")
    a = ap.parse_args()
    ids = [int(x) for x in a.garments.split(",")]
    cals = {i: rc.Calib(a.poses, os.path.join(HERE, "body13", "mul", "anim_%04d.vd" % i)) for i in ids}
    caps = cals[ids[0]].caps; orig = cl.hull_push; kap = [0.25]
    rel = lambda V, S, h, t, r, **kw: hull_push_rel(V, S, h, t, r, caps.head, caps.tail, kappa=kap[0], z_top=kw["z_top"], z_hem=kw["z_hem"], drop=kw["drop"])
    acts = [x for x in range(35) if not 23 <= x <= 29]
    rest = {}
    for i, c in cals.items():
        p = dict(rc.DEFAULT); p.update(drop=1.0, solve=0); rest[i] = rc.fit_rest(c, p)

    def run(label, mode):
        row, dw = [], []
        for i, c in cals.items():
            p = dict(rest[i]); p["hull"] = 0 if mode == "none" else 1
            if mode == "abs":
                p["margin"], p["kappa"] = abs_params(p["z_hem"])
            cl.hull_push = rel if mode == "rel" else orig
            s = rc.summarize(c.evaluate(p, acts)[0]); row.append(s["iou"]); dw.append(s["dw_abs"])
        print("%-24s" % label, " ".join("%d:%.3f" % (i, v) for i, v in zip(ids, row)), "mean %.3f  hem width error %.2f px" % (np.mean(row), np.mean(dw)), flush=True)

    run("no hull", "none"); run("abs (production)", "abs")
    for k in (float(x) for x in a.rel_kappa.split(",")):
        kap[0] = k; run("rel kappa %.2f" % k, "rel")
