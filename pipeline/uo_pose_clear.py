# Make a bound item clear the ARMS (upper arm, forearm, hand) in the poses of the animations, by changing its REST shape. uo_fit_item.py pushes an item out of the skin in the rest
# pose only; an arm that swings down, forward or up then sinks into the plate at the side or at the armhole, and the renderer (BODY_GAP) has to bend the plate around it frame by
# frame (bulges, edges that jump, skin showing through). Here the arm is swept through a set of poses: where a posed vertex is closer to the arm skin than GAP, the vertex is pushed out
# along the arm's surface normal; the push is carried back to the rest shape through the vertex's own skinning matrix (the inverse of the weighted bone matrices) and the largest push over
# all frames wins (at most CAP). Pushes are smoothed over the mesh, applied, and the next round measures again. Legs are left to the renderer (a hem over the thighs is how plate looks).
# Run on the SELECTED bound items (uo_bind_item.py first) from Blender's Text Editor or from uo_make_item.py ("pose_clear" in a part of a recipe), then run uo_bind_item.py again
# (the shape corrections "uo_*" follow the skin under each vertex, so they are made again for the new rest shape).
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ACTIONS = "04_stand,00_walk_unarmed,02_run_unarmed,07_combat_idle_1h,15_combat_advance"      # arms at the sides, forward and back: where the plate side and the armhole meet the arm. Poses that cross the arm over the body (attack, spell) are left to the renderer
STEP = 2              # every STEP-th frame of each action
GAP = 0.012           # m: the item stays this far from the arm skin
CAP = 0.03            # m: the largest change of the rest shape at one vertex
ROUNDS = 2            # measure + push + smooth rounds
SMOOTH = 3            # smoothing passes of the pushes over the mesh edges
AVOID = ("upper_arm", "forearm", "hand", "finger")      # body parts (vertex group names start with) the item must clear
REPORT = True

body = bpy.data.objects["UO_Body"]
rig = bpy.data.objects["UO_Rig"]
sc = bpy.context.scene


def arm_triangles(mesh):
    names = {g.index: g.name for g in body.vertex_groups}
    isarm = np.zeros(len(body.data.vertices), bool)
    for v in body.data.vertices:
        w = {}
        for g in v.groups:
            w[names[g.group]] = w.get(names[g.group], 0.0) + g.weight
        isarm[v.index] = sum(x for k, x in w.items() if k.startswith(AVOID)) > 0.5 * max(sum(w.values()), 1e-9)
    return isarm


def weight_matrix(ob):
    """(n, bones) weights of the item's vertex groups that are bones of the rig, rows normalised"""
    names = [b.name for b in rig.data.bones]; col = {n: i for i, n in enumerate(names)}
    gname = {g.index: g.name for g in ob.vertex_groups}
    W = np.zeros((len(ob.data.vertices), len(names)))
    for v in ob.data.vertices:
        for g in v.groups:
            if gname[g.group] in col:
                W[v.index, col[gname[g.group]]] += g.weight
    s = W.sum(1, keepdims=True); W = np.where(s > 0, W / np.maximum(s, 1e-12), 0.0)
    return W, names


def skin_linear(W, names):
    """per vertex: the linear part of its weighted bone matrix (rest -> posed) in the current pose: (n, 3, 3); no weights = identity"""
    bones = rig.data.bones
    Lb = np.stack([np.array((rig.matrix_world @ rig.pose.bones[n].matrix @ bones[n].matrix_local.inverted() @ rig.matrix_world.inverted()).to_3x3()) for n in names])
    A = np.einsum("nb,bij->nij", W, Lb)
    none = W.sum(1) == 0
    A[none] = np.eye(3)
    return A


def evaluated_world(ob, dg):
    ev = ob.evaluated_get(dg); me = ev.to_mesh()
    co = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", co)
    Mw = np.array(ev.matrix_world); ev.to_mesh_clear()
    return co.reshape(-1, 3).astype(np.float64) @ Mw[:3, :3].T + Mw[:3, 3]


def neighbours(ob):
    e = np.empty(len(ob.data.edges) * 2, np.int32); ob.data.edges.foreach_get("vertices", e)
    return e.reshape(-1, 2)


def run_item(ob, acts, isarm):
    n = len(ob.data.vertices)
    E = neighbours(ob); W, bnames = weight_matrix(ob)
    deg = np.bincount(E.ravel(), minlength=n).astype(float)
    total = np.zeros((n, 3))
    for rnd in range(ROUNDS):
        rig.data.pose_position = "REST"; bpy.context.view_layer.update()
        best = np.zeros((n, 3)); bestn = np.zeros(n); hits = 0; nfr = 0
        rig.data.pose_position = "POSE"
        for a in acts:
            act = acts[a]
            rig.animation_data.action = act; rig["uo_direction"] = 0
            for i in range(0, int(act["uo_frames"]), STEP):
                sc.frame_set(1 + i * 3); rig.update_tag(); bpy.context.view_layer.update()
                dg = bpy.context.evaluated_depsgraph_get()
                eb = body.evaluated_get(dg); mb = eb.to_mesh(); mb.calc_loop_triangles(); Mw = eb.matrix_world
                co = [Mw @ v.co for v in mb.vertices]
                tri = [t.vertices[:] for t in mb.loop_triangles if isarm[t.vertices[0]] and isarm[t.vertices[1]] and isarm[t.vertices[2]]]
                bvh = BVHTree.FromPolygons(co, tri); eb.to_mesh_clear()
                P = evaluated_world(ob, dg)
                A = skin_linear(W, bnames)
                for k in range(n):
                    p = Vector(P[k]); loc, nrm, fi, d = bvh.find_nearest(p, 0.25)
                    if loc is None:
                        continue
                    s = (p - loc).dot(nrm)
                    if s >= GAP or (s < 0 and -s < 0.8 * d) or (s >= 0 and d > 1.5 * GAP):          # not above the skin by GAP, or a point beside an open edge of the arm triangles (the nearest skin is not straight under it)
                        continue
                    push = np.array(nrm) * (GAP - s)                          # posed push, along the arm's normal
                    try:
                        dr = np.linalg.solve(A[k], push)                      # the same push in the rest shape
                    except np.linalg.LinAlgError:
                        continue
                    nr = float(np.linalg.norm(dr))
                    if nr > bestn[k]:
                        bestn[k] = nr; best[k] = dr
                    hits += 1
                nfr += 1
        rig.data.pose_position = "REST"; bpy.context.view_layer.update()
        push = best * np.minimum(1.0, CAP / np.maximum(bestn, 1e-9))[:, None]
        for _ in range(SMOOTH):                                               # the pushes spread over the mesh (no spikes); a vertex keeps its own push where it is larger
            acc = np.zeros_like(push)
            np.add.at(acc, E[:, 0], push[E[:, 1]]); np.add.at(acc, E[:, 1], push[E[:, 0]])
            acc /= np.maximum(deg, 1)[:, None]
            push = np.where((np.linalg.norm(acc, axis=1) > np.linalg.norm(push, axis=1))[:, None], acc, push)
        mw3 = np.array(ob.matrix_world.to_3x3().inverted())
        local = push @ mw3.T
        sk = ob.data.shape_keys
        for blk in (sk.key_blocks if sk else [None]):
            data = blk.data if blk is not None else ob.data.vertices
            c = np.empty(n * 3, np.float32); data.foreach_get("co", c)
            data.foreach_set("co", (c.reshape(-1, 3) + local).ravel().astype(np.float32))
        ob.data.update()
        total += push
        if REPORT and "DBG" in globals():
            import numpy as _n; dd=_n.array(DBG); print("DBG hits",len(dd),"s pct",_n.round(_n.percentile(dd[:,0],[0,10,50,90,100]),3),"d pct",_n.round(_n.percentile(dd[:,1],[0,50,100]),3))
        if REPORT:
            print("uo_pose_clear: %s round %d | %d frames, %d vertices pushed (largest %.1f mm, mean of the pushed %.1f mm)" %
                  (ob.name, rnd + 1, nfr, int((bestn > 0).sum()), 1000 * bestn.max(), 1000 * (bestn[bestn > 0].mean() if (bestn > 0).any() else 0)))
        bpy.context.view_layer.update()
        if bestn.max() < 0.002:
            break
    return total


acts_all = {int(a["uo_action"]): a for a in bpy.data.actions if "uo_action" in a}
acts = {int(x[:2]): acts_all[int(x[:2])] for x in ACTIONS.split(",") if int(x[:2]) in acts_all}
isarm = arm_triangles(body.data)
saved = rig.data.pose_position
items = [o for o in bpy.context.selected_objects if o.type == "MESH" and o != body]
for ob in items:
    run_item(ob, acts, isarm)
rig.data.pose_position = saved
bpy.context.view_layer.update()
