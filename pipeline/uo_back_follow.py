# A rigid prop that sits ON THE BACK (crossed axes, a shield, a sword): in the listed ACTIONS it gets its own bone `back_prop`, keyed per frame to ONE rigid transform that keeps the
# prop's stand-off from the posed back skin what it is in the rest pose. The prop is never bent: one stiff transform per frame. In every other action the bone repeats the chest
# bone's transform, i.e. the prop behaves exactly as when it is bound to the chest.
# Why: in a few actions (2H bash, ...) the chest twists and leans differently from the skin of the back, the long handles are levers, and the flat X stands off the back (stand-off profile
# error of the chest binding up to 29 mm p90 in 12_attack_2h_bash). Measured on the whole set of 35 actions the chest bone is as good as anything else (its rotation is within 2 deg of the back skin, a fit
# for every action was not better on average: 12.0 -> 10.9 mm p90 with some frames worse), so it is used only where it is asked for.
# Method: start from the chest bone's transform, a few Levenberg-Marquardt steps on 6 rigid parameters minimise sum (distance(prop point, torso skin) - rest distance)^2 over the prop points near the
# back, a hinge keeps every point MIN_GAP off the skin, a small pull keeps the transform near the chest bone's where the distance does not decide.
# Runs in item.blend (the bone, its keys and the weights live in the item file only; the base model is not changed). Select the item(s) (bound by uo_bind_item.py) and run.
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ACTIONS = []                   # UO action numbers that get the per-frame fit to the back skin (the others repeat the chest bone's)
SHIFT = {}                     # {UO action: [dx, dy, dz] m, or one such triple per frame}: that action's prop is moved in the body's REST axes (x right, y back, z up; they turn with the chest): where the model's pose differs from the original sprite
BONE = "back_prop"
NEAR = 0.12                    # m: prop points closer than this to the skin in the rest pose decide the fit (the far ends of the handles and the blades follow)
MIN_GAP = 0.003                # m: no prop point closer than this to the torso skin (hinge); arms / hands across the back are pushed away by the renderer (BODY_GAP)
PULL = 0.25                    # weight of the pull towards the chest bone's transform (parameters: rotation vector * 0.1 m, translation m)
ITER = 8                       # Levenberg-Marquardt steps per frame
CLIP = 0.04                    # m: a residual larger than this counts as this (an arm or a fold of skin nearby does not drag the fit)
STEP = 3                       # scene frames between two UO frames (render_uo_layer.py STEP)
SAMPLE = 400                   # prop points used by the fit

rig, body = bpy.data.objects["UO_Rig"], bpy.data.objects["UO_Body"]
items = [o for o in bpy.context.selected_objects if o.type == "MESH"]
assert items, "select the item first"
sc = bpy.context.scene
Minv = rig.matrix_world.inverted()

# --- the bone (item file only): at the centre of the item, no parent
rig.data.pose_position = "REST"; bpy.context.view_layer.update()
v_rest = np.array([(Minv @ (o.matrix_world @ x.co))[:] for o in items for x in o.data.vertices])
centre = Vector(((v_rest.min(0) + v_rest.max(0)) / 2).tolist())
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode="EDIT")
if BONE in rig.data.edit_bones:
    rig.data.edit_bones.remove(rig.data.edit_bones[BONE])
eb = rig.data.edit_bones.new(BONE)
eb.head, eb.tail, eb.roll = centre, centre + Vector((0, 0, 0.1)), 0.0
bpy.ops.object.mode_set(mode="OBJECT")
pb = rig.pose.bones[BONE]
pb.rotation_mode = "QUATERNION"
rest_bone = rig.data.bones[BONE].matrix_local.copy()      # armature space
chest_rest = rig.data.bones["chest"].matrix_local.copy()
for o in items:
    for g in list(o.vertex_groups):
        o.vertex_groups.remove(g)
    o.vertex_groups.new(name=BONE).add(list(range(len(o.data.vertices))), 1.0, "REPLACE")

TORSO_GROUPS = ("pelvis", "spine", "chest", "neck")
_gi = {g.index for g in body.vertex_groups if g.name in TORSO_GROUPS}
torso = [sum(g.weight for g in v.groups if g.group in _gi) > 0.5 for v in body.data.vertices]


def torso_bvh(dg):
    """BVH of the posed torso skin in armature space (an arm or a hand across the back is not the back)"""
    e = body.evaluated_get(dg); m = e.to_mesh(); m.calc_loop_triangles()
    co = [Minv @ (e.matrix_world @ x.co) for x in m.vertices]
    bvh = BVHTree.FromPolygons(co, [t.vertices[:] for t in m.loop_triangles if all(torso[k] for k in t.vertices)]); e.to_mesh_clear()
    return bvh


def dist(bvh, pts):
    """signed distance of points (Nx3, armature space) from the skin (positive = outside); 0.6 where nothing is near"""
    out = np.empty(len(pts))
    for k, p in enumerate(pts):
        q = Vector(p.tolist()); loc, nrm, fi, d = bvh.find_nearest(q, 0.6)
        out[k] = (q - loc).dot(nrm) if loc is not None else 0.6
    return out


def rotvec(w):
    th = np.linalg.norm(w)
    if th < 1e-12:
        return np.eye(3)
    k = w / th; K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + np.sin(th) * K + (1 - np.cos(th)) * K @ K


def apply(x, c0, pts):
    """delta transform about c0: rotation vector x[:3] (rad), translation x[3:] (m)"""
    return (pts - c0) @ rotvec(x[:3]).T + c0 + x[3:]


# --- rest stand-off of the prop from the torso skin
rig.data.pose_position = "REST"; sc.frame_set(1); bpy.context.view_layer.update()
bvh_rest = torso_bvh(bpy.context.evaluated_depsgraph_get())
idx = np.arange(0, len(v_rest), max(len(v_rest) // SAMPLE, 1))
P = v_rest[idx]; g0 = dist(bvh_rest, P)
sel = np.where(g0 < NEAR)[0]
P, g0 = P[sel], g0[sel]
print("uo_back_follow: %d prop points near the back (of %d), rest stand-off mean %.1f mm, min %.1f mm" % (len(P), len(idx), 1000 * g0.mean(), 1000 * g0.min()))
rig.data.pose_position = "POSE"

acts = {int(a["uo_action"]): a for a in bpy.data.actions if "uo_action" in a}
n_keys, n_fit, e_before, e_after = 0, 0, [], []
for a, act in sorted(acts.items()):
    rig.animation_data.action = act
    last_q = None
    for i in range(int(act["uo_frames"])):
        f = 1 + i * STEP
        pb.matrix_basis = Matrix.Identity(4)
        sc.frame_set(f); rig.update_tag(); bpy.context.view_layer.update()
        F0 = rig.pose.bones["chest"].matrix @ chest_rest.inverted()                  # the chest bone's transform
        F = F0
        if a in SHIFT:
            sh = np.array(SHIFT[a][min(i, len(SHIFT[a]) - 1)] if isinstance(SHIFT[a][0], (list, tuple)) else SHIFT[a], float); R0 = F0.to_3x3()
            F = Matrix.Translation(R0 @ Vector(sh.tolist())) @ F0
            F0 = F
        if a in ACTIONS:
            bvh = torso_bvh(bpy.context.evaluated_depsgraph_get())
            F0n = np.array([list(r) for r in F0])
            Pc = P @ F0n[:3, :3].T + F0n[:3, 3]
            c0 = Pc.mean(0)

            def resid(x):
                d = dist(bvh, apply(x, c0, Pc))
                r = np.clip(d - g0, -CLIP, CLIP)
                hinge = 4.0 * np.minimum(d - MIN_GAP, 0.0)
                return np.concatenate([r, hinge, PULL * np.array([0.1 * x[0], 0.1 * x[1], 0.1 * x[2], x[3], x[4], x[5]])])
            x = np.zeros(6)
            r = resid(x); e0 = np.sqrt(np.mean(r[:len(P)] ** 2)); mu = 1e-3
            for _ in range(ITER):
                J = np.empty((len(r), 6))
                for j in range(6):
                    dx = np.zeros(6); dx[j] = 0.01 if j < 3 else 0.004
                    J[:, j] = (resid(x + dx) - r) / dx[j]
                step = np.linalg.solve(J.T @ J + mu * np.eye(6), -J.T @ r)
                step[:3] = np.clip(step[:3], -0.15, 0.15); step[3:] = np.clip(step[3:], -0.03, 0.03)
                r2 = resid(x + step)
                if (r2 ** 2).sum() < (r ** 2).sum():
                    x, r, mu = x + step, r2, mu * 0.5
                else:
                    mu *= 4
            e1 = np.sqrt(np.mean(r[:len(P)] ** 2)); e_before.append(e0); e_after.append(e1); n_fit += 1
            c = Vector(c0.tolist())
            F = Matrix.Translation(Vector(x[3:].tolist())) @ Matrix.Translation(c) @ Matrix(rotvec(x[:3]).tolist()).to_4x4() @ Matrix.Translation(-c) @ F0
        pb.matrix = F @ rest_bone                            # armature-space pose matrix; the bone's deformation is F
        pb.keyframe_insert("location", frame=f); q = pb.rotation_quaternion.copy()
        if last_q is not None and q.dot(last_q) < 0:
            q.negate()
        pb.rotation_quaternion = q; last_q = q.copy()
        pb.keyframe_insert("rotation_quaternion", frame=f)
        n_keys += 1
if e_before:
    print("uo_back_follow: %d keys in %d actions, %d frames fitted (actions %s): rms stand-off error vs rest: chest bone mean %.1f mm (worst %.1f) -> fitted mean %.1f mm (worst %.1f)" % (
        n_keys, len(acts), n_fit, ACTIONS, 1000 * np.mean(e_before), 1000 * np.max(e_before), 1000 * np.mean(e_after), 1000 * np.max(e_after)))
sc.frame_set(1)
