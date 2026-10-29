"""Motion of a drum worn on the chest when its wearer dies face down (in this model the action 22_die_backward: 21_die_forward ends on the back): it comes off the strap and ends lying on the ground at the RIGHT side of the body, head up, touching the side of the torso and the right arm a little.

    python drum_death_motion.py ITEM.blend [--action 22_die_backward] [--out ITEM_DIR/item_motion.npz] [--touch 0.02] [--start 0.1]

ITEM.blend: an item made by uo_make_item.py with a "rigid" recipe with "motion": true (custom property uo_motion), the drum with its axis across the body in the rest pose. Writes item_motion.npz next to it:
"ACTION_i" -> the 4x4 matrix (armature space) that takes the drum from its rest pose to its pose in UO frame i; render_uo_layer.py (motion_fix) moves the item by it in those frames.
The frames: the drum follows the chest (the matrix of the chest bone against its rest pose) while the body is still upright, and goes over to the final place along a smoothstep from --start (share of the action)
to the last frame, the rotation by a slerp, the place by a line. The final place (found from the body of the last frame): on the ground (the lowest point of the body), the axis vertical, the badge looking away from the body,
centred so that the drum side overlaps the torso by --touch m at the side of the torso and the right arm by --touch m at its lower edge (the drum lies beside the waist, between the arm and the legs).
"""
import argparse, os, sys
import numpy as np
import bpy
from scipy.spatial.transform import Rotation, Slerp

STEP = 3


def mat(m):
    return np.array([list(r) for r in m], np.float64)


def region(name):
    n = name.split(".")[0]; side = name[-2:] if name[-2:] in (".L", ".R") else ""
    if n in ("upper_arm", "forearm", "clavicle"):
        return "arm" + side
    if n == "hand" or n.startswith("finger"):
        return "hand" + side
    if n in ("thigh", "shin", "foot"):
        return "leg" + side
    if n == "head":
        return "head"
    return "torso"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("blend"); ap.add_argument("--action", default="22_die_backward")
    ap.add_argument("--out"); ap.add_argument("--touch", type=float, default=0.02); ap.add_argument("--start", type=float, default=0.1)
    a = ap.parse_args()
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(a.blend)), "item_motion.npz")
    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(a.blend))
    sc = bpy.context.scene; rig = bpy.data.objects["UO_Rig"]; body = bpy.data.objects["UO_Body"]
    item = next(o for o in bpy.data.objects if o.type == "MESH" and o.get("uo_motion"))
    rig.data.pose_position = "REST"; rig.animation_data.action = None; bpy.context.view_layer.update()
    Mr = np.array(rig.matrix_world)
    co = np.empty(len(item.data.vertices) * 3, np.float32); item.data.vertices.foreach_get("co", co); co = co.reshape(-1, 3).astype(np.float64)
    Mo = np.linalg.inv(Mr) @ np.array(item.matrix_world); V0 = co @ Mo[:3, :3].T + Mo[:3, 3]
    c0 = (V0.min(0) + V0.max(0)) / 2; ext = V0.max(0) - V0.min(0)
    radius = float(max(ext[1], ext[2]) / 2); depth = float(ext[0])
    chest_rest = mat(rig.data.bones["chest"].matrix_local)
    names = [g.name for g in body.vertex_groups]
    lab = np.empty(len(body.data.vertices), object)
    for v in body.data.vertices:
        acc = {}
        for g in v.groups:
            r = region(names[g.group]); acc[r] = acc.get(r, 0.0) + g.weight
        lab[v.index] = max(acc, key=acc.get) if acc else "torso"
    act = bpy.data.actions[a.action]; rig.animation_data.action = act
    n = int(act["uo_frames"]); rig.data.pose_position = "POSE"
    Mchest, final_body = [], None
    for i in range(n):
        sc.frame_set(1 + i * STEP); bpy.context.view_layer.update()
        Mchest.append(mat(rig.pose.bones["chest"].matrix) @ np.linalg.inv(chest_rest))
        if i == n - 1:
            eb = body.evaluated_get(bpy.context.evaluated_depsgraph_get()); me = eb.to_mesh()
            P = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", P); P = P.reshape(-1, 3).astype(np.float64)
            final_body = P @ np.array(eb.matrix_world)[:3, :3].T + np.array(eb.matrix_world)[:3, 3]; eb.to_mesh_clear()
    P = final_body; ground = float(P[:, 2].min())
    arm = P[np.isin(lab, ["arm.R", "hand.R"])]; tor = P[lab == "torso"]
    head = P[lab == "head"].mean(0); hips = P[np.isin(lab, ["leg.L", "leg.R"])].mean(0)
    L = (head - hips); L[2] = 0; L /= np.linalg.norm(L)                      # along the lying body, towards the head
    S = arm.mean(0) - tor.mean(0); S[2] = 0; S -= (S @ L) * L; S /= np.linalg.norm(S)   # sideways, towards the right arm
    l_arm = float((arm @ L).min())                                          # the edge of the right arm that looks towards the feet
    l_c = l_arm - radius + a.touch
    band = tor[np.abs(tor @ L - l_c) < 0.1]
    s_side = float((band @ S).max())                                        # the right side of the torso at that place
    s_c = s_side - 0.0 + radius - a.touch
    xyc = l_c * L[:2] + s_c * S[:2]
    xc, yc = float(xyc[0]), float(xyc[1])
    x_side, y_lo = s_side, l_arm
    zc = ground + depth / 2
    Cf = np.array([xc, yc, zc])
    Rf = Rotation.from_euler("z", -90, degrees=True) * Rotation.from_euler("y", -90, degrees=True)   # axis across -> vertical; the badge (looking -y) turned to -x
    M_rest = np.eye(4); M_rest[:3, :3] = Rf.as_matrix(); M_rest[:3, 3] = Cf - Rf.as_matrix() @ c0
    print("drum_death_motion: drum radius %.3f depth %.3f, rest centre %s; body axis %s (to the head), right %s; ground z %.3f; arm edge at %.3f, torso side at %.3f along them -> final centre (%.3f, %.3f, %.3f)" % (radius, depth, c0.round(3), L[:2].round(2), S[:2].round(2), ground, l_arm, s_side, xc, yc, zc))
    sm = lambda x: x * x * (3 - 2 * x)
    res = {}
    for i in range(n):
        w = sm(float(np.clip((i / max(n - 1, 1) - a.start) / (1 - a.start), 0, 1)))
        R0, R1 = Rotation.from_matrix(Mchest[i][:3, :3]), Rotation.from_matrix(M_rest[:3, :3])
        Ri = Slerp([0, 1], Rotation.concatenate([R0, R1]))(w).as_matrix()
        # the rotation about the drum's own centre, the centre goes from where the chest carries it to the final place
        ci = Mchest[i][:3, :3] @ c0 + Mchest[i][:3, 3]; cf = Cf
        cc = (1 - w) * ci + w * cf
        M = np.eye(4); M[:3, :3] = Ri; M[:3, 3] = cc - Ri @ c0
        res["%d_%d" % (int(a.action[:2]), i)] = M
        print("  frame %d: share %.2f, centre %s" % (i, w, cc.round(3)))
    np.savez(out, **res)
    print("drum_death_motion: saved", out)
