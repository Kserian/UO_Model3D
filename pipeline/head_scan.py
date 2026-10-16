"""Head yaw per action and frame: how far the head is turned about the vertical, and how fast it jumps.

    python head_scan.py ../model/UO_Body_0x190.blend [--actions 23,24] [--out scan.json] [--per-frame]

Per action (UO frames = scene frames 1 + 3 i; loops wrap):
  world_yaw   yaw (deg, about armature Z, + = the plan's sign) of the head bone against its rest orientation: min .. max
  chest_yaw   twist (deg, about the chest's own Y) of the head against the chest, rest relation removed: min .. max
  jump        max |yaw(i) - mid(yaw(i-1), yaw(i+1))| (deg) of the world yaw
Needs: numpy "bpy==4.2.*".
"""
import sys, os, json
import numpy as np
import bpy

LOOP = {0, 1, 2, 3, 4, 5, 6, 7, 8, 15, 23, 24, 25}
STEP = 3


def unit(m):
    return m[:3, :3] / np.linalg.norm(m[:3, :3], axis=0, keepdims=True)


def yaw_z(R):
    return -np.degrees(np.arctan2(R[1, 0], R[0, 0]))


def twist_y(R):
    from scipy.spatial.transform import Rotation
    q = Rotation.from_matrix(R).as_quat()          # x y z w
    t = 2 * np.arctan2(q[1], q[3])
    return -np.degrees((t + np.pi) % (2 * np.pi) - np.pi)


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
    rh, rc = np.array(Bn["head"].matrix_local)[:3, :3], np.array(Bn["chest"].matrix_local)[:3, :3]
    rh, rc = rh / np.linalg.norm(rh, axis=0), rc / np.linalg.norm(rc, axis=0)
    rel0 = rc.T @ rh
    res = {}
    acts = sorted([x for x in bpy.data.actions if "uo_action" in x], key=lambda x: int(x["uo_action"]))
    for act in acts:
        aid = int(act["uo_action"])
        if only is not None and aid not in only: continue
        rig.animation_data.action = act
        n = int(act["uo_frames"]); loop = aid in LOOP
        w, c = [], []
        for i in range(n):
            sc.frame_set(1 + STEP * i); bpy.context.view_layer.update()
            H, C = unit(np.array(P["head"].matrix)), unit(np.array(P["chest"].matrix))
            w.append(yaw_z(H @ rh.T))
            c.append(twist_y(rel0.T @ (C.T @ H)))
        w, c = np.array(w), np.array(c)
        idx = list(range(n)) if loop else list(range(1, n - 1))
        jump = [abs(((w[i] - 0.5 * (w[(i - 1) % n] + w[(i + 1) % n]) + 180) % 360) - 180) for i in idx] if n >= 3 else [0]
        # unwrap the world yaw around its median so that min .. max is meaningful
        wu = np.degrees(np.unwrap(np.radians(w)))
        st = {"world_yaw": [float(wu.min()), float(wu.max())], "chest_yaw": [float(c.min()), float(c.max())], "jump": float(max(jump)),
              "chest_yaw_jump": float(max(abs(c[i] - 0.5 * (c[(i - 1) % n] + c[(i + 1) % n])) for i in idx)) if n >= 3 else 0.0}
        if per_frame: st["world_f"] = [round(float(x), 1) for x in wu]; st["chest_f"] = [round(float(x), 1) for x in c]
        res[act.name] = st
    print("%-26s %16s %16s %7s %7s" % ("action", "world yaw", "chest yaw", "jump", "cJump"))
    for nm, st in res.items():
        print("%-26s %7.1f..%-7.1f %7.1f..%-7.1f %7.1f %7.1f" % (nm, *st["world_yaw"], *st["chest_yaw"], st["jump"], st["chest_yaw_jump"]))
    if out: json.dump(res, open(out, "w"), indent=1)


if __name__ == "__main__":
    main()
