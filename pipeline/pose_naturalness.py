"""How natural the motion of the rig is in 3D (what the silhouette IoU does not see), per action.

    python pose_naturalness.py ../model/UO_Body_0x190.blend [--actions 0,1,15] [--out stats.json] [--per-frame]

Per action (UO frames = scene frames 1 + 3 i; loops wrap, ends of one-shot actions are skipped in the 2nd differences):
  zig_<bone>   mean angle (deg) between the bone's armature-space orientation in a frame and the mid-orientation of its two neighbours (zig-zag)
  helm_px      max jump (px, UO camera, max of 5 directions) of a point rigid on the head, 13 cm above its root, against the mean of the neighbours
  hand_px      the same for the centre of the right fist (8 cm along hand.R) and wpn_px for a point 0.8 m along the 1H weapon bone weapon1h.R
  twist_uarm   mean |twist| (deg) of upper_arm.L / .R about its own axis relative to the chest, minus the rest pose (MakeHuman skinning folds the
               shoulder from about 15-20 deg of internal twist: the deltoid turns away from the chest)
  slide_R/L    mean distance (cm) of the shoulder joint from where it sits on the chest in the stand pose (clavicle rotation or location)
  clav_cm      max |location| (cm) of the clavicles (non-deforming bones: a shifted clavicle slides the arm along the chest skin -> dented shoulder)
  scale_jump   max frame-to-frame change of the per-frame girth scale (x / z) over the limbs and the head
  waste_neck   mean (|neck vs chest| + |head vs neck| - |head vs chest|) in deg: neck and head turning against each other
Needs: pip install numpy "bpy==4.2.*".
"""
import sys, os, json, math
import numpy as np
import bpy

LOOP = {0, 1, 2, 3, 4, 5, 6, 7, 8, 15, 23, 24, 25}
STEP = 3
ZIG_BONES = ["chest", "neck", "head", "clavicle.L", "clavicle.R", "upper_arm.L", "upper_arm.R", "forearm.L", "forearm.R", "hand.L", "hand.R"]
SCALE_BONES = ["upper_arm.L", "forearm.L", "hand.L", "upper_arm.R", "forearm.R", "hand.R", "thigh.L", "shin.L", "foot.L", "thigh.R", "shin.R", "foot.R", "head"]
CW, CH = 145, 133


def qang(a, b):
    """angle (rad) between two unit quaternions given as arrays (w, x, y, z)"""
    return 2 * np.arccos(np.clip(np.abs(np.sum(a * b, -1)), 0, 1))


def slerp_mid(a, b):
    s = np.where(np.sum(a * b, -1, keepdims=True) < 0, -1.0, 1.0)
    m = a + s * b
    return m / np.linalg.norm(m, axis=-1, keepdims=True)


def mat_quat(R):
    """rotation matrices (n, 3, 3) -> quaternions (n, 4) w x y z"""
    from scipy.spatial.transform import Rotation
    q = Rotation.from_matrix(R).as_quat()
    return q[:, [3, 0, 1, 2]]


def twist_deg(Rrel, axis=1):
    """twist angle (deg) of relative rotations (n, 3, 3) about local axis `axis`"""
    q = mat_quat(Rrel)
    t = 2 * np.arctan2(q[:, 1 + axis], q[:, 0])
    return np.degrees((t + np.pi) % (2 * np.pi) - np.pi)


def second_diff_idx(n, loop):
    return list(range(n)) if loop else list(range(1, n - 1))


def main():
    a = sys.argv[1:]
    blend = os.path.abspath(a.pop(0))
    only, out, per_frame = None, None, False
    while a:
        k = a.pop(0)
        if k == "--actions": only = {int(x) for x in a.pop(0).split(",")}
        elif k == "--out": out = a.pop(0)
        elif k == "--per-frame": per_frame = True
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc = bpy.context.scene
    rig = bpy.data.objects["UO_Rig"]; P = rig.pose.bones; Bn = rig.data.bones
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from arm_refit import setup
    sc.camera = bpy.data.objects["UO_Camera"]; setup(sc)
    # camera and rig world matrices per direction (the rig turns, the camera stays)
    CAM = []
    for d in range(5):
        rig["uo_direction"] = d; rig.update_tag(); bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get(); cam = sc.camera.evaluated_get(dg)
        CAM.append((np.array(cam.calc_matrix_camera(dg, x=CW, y=CH)) @ np.array(cam.matrix_world.inverted()) @ np.array(rig.matrix_world)))
    rig["uo_direction"] = 0; rig.update_tag(); bpy.context.view_layer.update()

    def screen(Xa):
        """armature-space points (n, 3) -> (5, n, 2) px"""
        h = np.c_[Xa, np.ones(len(Xa))]
        r = []
        for M in CAM:
            p = h @ M.T; p = p[:, :2] / p[:, 3:4]
            r.append(np.stack([(p[:, 0] + 1) * 0.5 * CW, (1 - p[:, 1]) * 0.5 * CH], 1))
        return np.array(r)

    rest = {b.name: np.array(b.matrix_local) for b in Bn}
    st_act = next(x for x in bpy.data.actions if x.get("uo_action") == 4); rig.animation_data.action = st_act; sc.frame_set(1); bpy.context.view_layer.update()
    SLIDE_REF = {}
    for side in ("L", "R"):
        mc, mu = np.array(P["chest"].matrix), np.array(P["upper_arm." + side].matrix)
        SLIDE_REF[side] = (mc[:3, :3] / np.linalg.norm(mc[:3, :3], axis=0)).T @ (mu[:3, 3] - mc[:3, 3])
    has_w = "weapon1h.R" in P
    acts = sorted([x for x in bpy.data.actions if "uo_action" in x], key=lambda x: int(x["uo_action"]))
    res = {}
    for act in acts:
        aid = int(act["uo_action"])
        if only is not None and aid not in only: continue
        rig.animation_data.action = act
        n = int(act["uo_frames"]); loop = aid in LOOP
        M = {b: [] for b in set(ZIG_BONES) | {"pelvis", "spine"}}
        pts, loc, scl = [], [], []
        for i in range(n):
            sc.frame_set(1 + STEP * i); bpy.context.view_layer.update()
            for b in M: M[b].append(np.array(P[b].matrix))
            hm, hd = np.array(P["head"].matrix), np.array(P["hand.R"].matrix)
            p = [hm[:3, 3] + 0.13 * hm[:3, 1] / np.linalg.norm(hm[:3, 1]), hd[:3, 3] + 0.08 * hd[:3, 1] / np.linalg.norm(hd[:3, 1])]
            if has_w:
                wm = np.array(P["weapon1h.R"].matrix); p.append(wm[:3, 3] + 0.8 * wm[:3, 1] / np.linalg.norm(wm[:3, 1]))
            pts.append(p)
            loc.append(max(np.linalg.norm(P["clavicle.L"].location), np.linalg.norm(P["clavicle.R"].location)))
            scl.append([[P[b].scale[0], P[b].scale[2]] for b in SCALE_BONES])
        R = {b: np.array([m[:3, :3] / np.linalg.norm(m[:3, :3], axis=0, keepdims=True) for m in v]) for b, v in M.items()}
        Q = {b: mat_quat(v) for b, v in R.items()}
        idx = second_diff_idx(n, loop)
        st = {}
        for b in ZIG_BONES:
            if n >= 3:
                z = [np.degrees(qang(Q[b][i], slerp_mid(Q[b][(i - 1) % n], Q[b][(i + 1) % n]))) for i in idx]
                st["zig_" + b] = float(np.mean(z))
                if per_frame: st["zigf_" + b] = [round(float(x), 2) for x in z]
            else:
                st["zig_" + b] = 0.0
        S = screen(np.array(pts).reshape(-1, 3)).reshape(5, n, -1, 2)
        for k, nm in enumerate(["helm_px", "hand_px", "wpn_px"][:S.shape[2]]):
            if n >= 3:
                j = [np.max(np.linalg.norm(S[:, i, k] - 0.5 * (S[:, (i - 1) % n, k] + S[:, (i + 1) % n, k]), axis=-1)) for i in idx]
                st[nm] = float(np.max(j))
                if per_frame: st[nm + "_f"] = [round(float(x), 2) for x in j]
            else:
                st[nm] = 0.0
        for side in ("L", "R"):
            ub, rc, ru = "upper_arm." + side, rest["chest"][:3, :3], rest["upper_arm." + side][:3, :3]
            Rrel = np.einsum("ij,njk->nik", (rc.T @ ru).T, np.einsum("nji,njk->nik", R["chest"], R[ub]))
            st["twist_uarm_" + side] = float(np.mean(np.abs(twist_deg(Rrel))))
        st["clav_cm"] = float(100 * max(loc))
        for side in ("L", "R"):                                   # shoulder joint moving on the chest (cm, mean over frames, from the stand pose)
            c, u = "chest", "upper_arm." + side
            J = [R[c][i].T @ (M[u][i][:3, 3] - M[c][i][:3, 3]) for i in range(n)]
            st["slide_" + side] = float(100 * np.mean([np.linalg.norm(j - SLIDE_REF[side]) for j in J]))
        sc_ = np.array(scl)
        st["scale_jump"] = float(np.abs(np.diff(sc_, axis=0)).max()) if n > 1 else 0.0
        st["scale_range"] = float(np.ptp(sc_, axis=0).max()) if n > 1 else 0.0

        def rel_ang(c, p):
            rr = np.einsum("nji,njk->nik", R[p], R[c]); r0 = rest[p][:3, :3].T @ rest[c][:3, :3]
            return np.degrees(qang(mat_quat(rr), np.tile(mat_quat(r0[None])[0], (n, 1))))
        st["waste_neck"] = float(np.mean(rel_ang("neck", "chest") + rel_ang("head", "neck") - rel_ang("head", "chest")))
        res[act.name] = st
    keys = ["zig_head", "zig_neck", "zig_chest", "zig_clavicle.R", "zig_upper_arm.R", "zig_forearm.R", "zig_hand.R", "zig_hand.L", "helm_px", "hand_px", "wpn_px",
            "twist_uarm_R", "twist_uarm_L", "slide_R", "slide_L", "clav_cm", "scale_jump", "waste_neck"]
    short = ["head", "neck", "chest", "clvR", "uarmR", "farmR", "handR", "handL", "helm", "hand", "wpn", "twR", "twL", "sldR", "sldL", "clav", "sclJ", "wNeck"]
    print("%-26s" % "action" + "".join("%7s" % s for s in short))
    for nm, st in res.items():
        print("%-26s" % nm + "".join("%7.2f" % st.get(k, 0) for k in keys))
    mean = {k: float(np.mean([st.get(k, 0) for st in res.values()])) for k in keys}
    print("%-26s" % "MEAN" + "".join("%7.2f" % mean[k] for k in keys))
    if out:
        json.dump({"actions": res, "mean": mean}, open(out, "w"), indent=1)


if __name__ == "__main__":
    main()
