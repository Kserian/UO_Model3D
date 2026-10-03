"""Roll of every original weapon about its own axis (the turn of a blade / axe head about the shaft), measured from the sprites of anim..anim5.

    python weapon_roll_fit.py WP.npz VDROOT META.json CLASSIFY.json OUTDIR [--procs 4] [--classes polearm.L,axe2h.L,...] [--anims 611,612]
    inputs: weapon_pose_export.py (WP.npz), mul2vd.py vd files (VDROOT/<file>/anim_<local>.vd), META.json + CLASSIFY.json from weapon_classify.py
    output: OUTDIR/roll_<class>.json  { phi: {"action,frame": degrees}, weapons: {anim id: {...}} }, OUTDIR/w_<anim id>.pkl (per-weapon cache)

Method (weapon_roll_lib.py): a weapon = shaft on the class line (weapon_motion.json) + a FLAT head T(s, u) (blade, axe head, spear leaf, bow limbs) that is
turned about the shaft by the roll phi. For each weapon the roll of every one of the 210 poses is found (all 5 directions share it) by (1) the projected
sprite area, (2) the side the head sticks out to, (3) alternating: learn the plate T as the cells that stay inside the sprite in 85% of the views, and
dynamic programming of the roll along each action (cost: pixels of the plate and the sprite further than 1 px from each other + smoothness). Weapons of one
class then share ONE roll per pose (it is the turn of the hand, our hand bone is only as good as the silhouette) and differ by a constant offset each.
"""
import os, sys, json, time, pickle
import numpy as np
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import weapon_roll_lib as L                                              # noqa: E402

NOT_WEAPON = {  # held things that have their own bone / role: shields, books, lights
    "shield": [576, 577, 578, 579, 580, 581, 582, 605, 992, 993, 1263, 1265, 1529, 1571],
    "book": [877, 878, 879, 880, 882, 883, 884, 984, 1062],
    "light": [500, 501, 502, 503, 504, 505, 1544, 1545, 1550],
}
SKIP = {a: k for k, v in NOT_WEAPON.items() for a in v}
INFO_MIN = 0.15            # (const - fit) / const: how much a per-pose roll helps over one fixed roll = how much roll there is to measure
TOL2_CHAMFER = 1.5         # px: from this class-line error on the tolerance of the comparison is 2 px instead of 1 px
CHAMFER_MAX = 2.2          # px: weapons whose class line is worse than this do not enter the class estimate


def load(args):
    wp, vdroot, meta, aid = args
    pose = _pose(wp); m = meta[str(aid)]
    masks, _ = L.load_masks(pose, os.path.join(vdroot, m["file"], "anim_%04d.vd" % m["local"]))
    return pose, masks


_POSE = {}
def _pose(wp):
    if wp not in _POSE:
        _POSE[wp] = L.Pose(wp)
    return _POSE[wp]


def stage1(job):
    wp, vdroot, meta, aid, cls, ext, outdir, tol = job
    path = os.path.join(outdir, "w_%d.pkl" % aid)
    if os.path.exists(path):
        return pickle.load(open(path, "rb"))
    t0 = time.time(); WM = json.load(open(os.path.join(HERE, "weapon_motion.json")))
    pose, masks = load((wp, vdroot, meta, aid))
    G = L.ClassGeom(pose, WM[cls], cls)
    f = L.fit_single(pose, G, masks, ext, tol=tol)
    cm, c0 = L.const_mismatch(f["P"], f["T"])
    res = dict(aid=aid, cls=cls, ext=ext, tol=tol, phi_pose=f["phi_pose"], T=f["T"], hist=f["hist"], const=cm, const_phi=c0, fit=f["hist"][-1] if f["hist"] else None,
               area_rms=f["area_rms"], views=int(len(f["P"].ok)), sprite_area=float(f["P"].crop.reshape(len(f["P"].crop), -1).sum(1)[f["P"].ok].mean()))
    pickle.dump(res, open(path, "wb"))
    print("stage1 %d %s: const-roll %.1f -> per-pose %.1f px/view (%.0fs)" % (aid, cls, cm, res["fit"] or -1, time.time() - t0), flush=True)
    return res


def stage3(job):
    """a weapon against the class roll: offset by a local scan (plate re-learned), mismatch with the class roll"""
    wp, vdroot, meta, aid, cls, phi_cls, res, outdir = job
    WM = json.load(open(os.path.join(HERE, "weapon_motion.json")))
    pose, masks = load((wp, vdroot, meta, aid))
    G = L.ClassGeom(pose, WM[cls], cls); P = L.PlateFit(pose, G, masks, res["ext"], tol=res.get("tol", 1)); pk = L.pose_groups(pose, P.ok)
    d0 = [res["phi_pose"][k] - phi_cls[k] for k in pk if k in phi_cls and k in res["phi_pose"]]
    r1, r2 = abs(np.exp(1j * np.array(d0)).mean()), abs(np.exp(2j * np.array(d0)).mean())
    delta = L.circ_mean(np.exp(2j * np.array(d0))) / 2 if r1 < 0.8 * r2 else L.circ_mean(np.exp(1j * np.array(d0)))
    best = None
    for dd in np.deg2rad(np.arange(-12, 13, 6)):
        pv = np.zeros(len(pose.key))
        for k, ns in pk.items():
            pv[ns] = phi_cls.get(k, 0.0) + delta + dd
        T = P.learn(pv, thr=0.85)[0]
        if len(T) < 5:
            continue
        mm = L.mismatch(P, T, pv)
        if best is None or mm < best[0]:
            best = (mm, delta + dd, T)
    out = dict(res)
    if best:
        np.save(os.path.join(outdir, "cells_%d.npy" % aid), best[2].astype(np.float32))
        cm2, c2 = L.const_mismatch(P, best[2])
        out.update(class_mismatch=float(best[0]), delta=float(best[1]), consistency360=float(r1), consistency180=float(r2), class_const=cm2, const_abs=c2)
    print("stage3 %d: class roll %.1f (const %.1f, own %.1f)" % (aid, out.get("class_mismatch", -1), res["const"], res["fit"] or -1), flush=True)
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    wp, vdroot, metaf, clsf, outdir = a[:5]
    procs = int(a[a.index("--procs") + 1]) if "--procs" in a else 4
    only_cls = a[a.index("--classes") + 1].split(",") if "--classes" in a else None
    only = {int(x) for x in a[a.index("--anims") + 1].split(",")} if "--anims" in a else None
    os.makedirs(outdir, exist_ok=True)
    meta = json.load(open(metaf)); C = json.load(open(clsf))
    jobs = []
    for aid, c in sorted(C.items(), key=lambda kv: int(kv[0])):
        aid = int(aid)
        if aid in SKIP or (only and aid not in only):
            continue
        cls = c["best"]
        if only_cls and cls not in only_cls:
            continue
        jobs.append((wp, vdroot, meta, aid, cls, tuple(c["classes"][cls]["extent"]), outdir, 2 if c["classes"][cls]["chamfer"] >= TOL2_CHAMFER else 1))
    print(len(jobs), "weapons")
    with Pool(procs) as p:
        res1 = p.map(stage1, jobs, chunksize=1)
    by = {}
    for r in res1:
        by.setdefault(r["cls"], []).append(r)
    pose = _pose(wp); WM = json.load(open(os.path.join(HERE, "weapon_motion.json")))
    for cls, lst in by.items():
        info = {r["aid"]: max(0.0, (r["const"] - r["fit"]) / r["const"]) if r["fit"] else 0.0 for r in lst}
        cand = [r for r in lst if info[r["aid"]] >= INFO_MIN and C[str(r["aid"])]["classes"][cls]["chamfer"] <= CHAMFER_MAX]
        if len(cand) < 2:
            print(cls, "too few informative weapons", [(r["aid"], round(info[r["aid"]], 2)) for r in lst], flush=True)
            continue
        # reference = the weapon the others agree with most (full 360 deg: its head has a side, so the sign of the roll is known); core = those that
        # agree with it mod 180
        def agree(r1, r2, m):
            ks = sorted(set(r1["phi_pose"]) & set(r2["phi_pose"])); d = np.array([r1["phi_pose"][k] - r2["phi_pose"][k] for k in ks])
            return abs(np.exp(m * 1j * d).mean())
        score = [sum(info[o["aid"]] * agree(r, o, 1) for o in cand) for r in cand]
        ref = cand[int(np.argmax(score))]
        core = [ref] + sorted([r for r in cand if r is not ref and agree(ref, r, 2) >= 0.7], key=lambda r: -info[r["aid"]])[:9]
        print(cls, "reference", ref["aid"], "core weapons:", [(r["aid"], round(info[r["aid"]], 2)) for r in core], flush=True)
        G = L.ClassGeom(pose, WM[cls], cls); fits = []
        for r in core:
            pose_, masks = load((wp, vdroot, meta, r["aid"]))
            P = L.PlateFit(pose, G, masks, r["ext"], tol=r.get("tol", 1)); pk = L.pose_groups(pose, P.ok)
            fits.append(dict(P=P, pk=pk, phi_pose=r["phi_pose"], aid=r["aid"]))
        w = [info[r["aid"]] for r in core]
        phi, delta, sym = L.merge_class(fits, weights=w, ref=0)
        phi, delta, Ts = L.refine_class(pose, fits, phi, delta, log=print, weights=w)
        print(cls, "core offsets (deg):", {f["aid"]: int(round(np.rad2deg(d))) for f, d in zip(fits, delta)}, flush=True)
        jobs3 = [(wp, vdroot, meta, r["aid"], cls, phi, r, outdir) for r in lst]
        with Pool(procs) as p:
            res3 = p.map(stage3, jobs3, chunksize=1)
        out = dict(cls=cls, core=[r["aid"] for r in core],
                   phi={"%d,%d" % k: float(np.rad2deg(v)) for k, v in sorted(phi.items())},
                   weapons={str(r["aid"]): dict(name=meta[str(r["aid"])]["name"], chamfer=C[str(r["aid"])]["classes"][cls]["chamfer"], info=info[r["aid"]],
                                                const=r["const"], own=r["fit"], cls_mismatch=r.get("class_mismatch"), class_const=r.get("class_const"),
                                                const_abs_deg=float(np.rad2deg(r.get("const_abs", 0))) % 360, delta_deg=float(np.rad2deg(r.get("delta", 0))) % 360,
                                                consistency360=r.get("consistency360"), consistency180=r.get("consistency180"), sprite_area=r["sprite_area"],
                                                core=r["aid"] in [c_["aid"] for c_ in core]) for r in res3})
        json.dump(out, open(os.path.join(outdir, "roll_%s.json" % cls.replace(".", "_")), "w"), indent=1)
