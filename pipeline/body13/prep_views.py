"""from stage1_bound.blend: UO reference (v12 skeleton + mesh) and per-view skinning matrices / camera / original masks"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
import bpy, sys, json, base64, zlib, numpy as np
bpy.ops.wm.open_mainfile(filepath=sys.argv[1]); out = sys.argv[2]
ACTS = [int(x) for x in sys.argv[3].split(",")]; STEP = int(sys.argv[4])
sc = bpy.context.scene; rig = bpy.data.objects["UO_Rig"]; body = bpy.data.objects["UO_Body"]; v13 = bpy.data.objects["UO_Body_v13"]
cam = bpy.data.objects["UO_Camera"]; sc.camera = cam
ORIG = json.load(open(os.path.join(HERE, "..", "uo_original_frames.json")))["frames"]
bones = [b.name for b in rig.data.bones]
# reference data (rest)
rig.data.pose_position = "REST"; bpy.context.view_layer.update()
M = body.matrix_world.inverted() @ rig.matrix_world
U = np.array([[np.array(M @ b.head_local), np.array(M @ b.tail_local)] for b in rig.data.bones])
kb = body.data.shape_keys.key_blocks["Basis"]; BV = np.array([k.co[:] for k in kb.data])
names = [g.name for g in body.vertex_groups]; BW = np.zeros((len(BV), len(names)))
for v in body.data.vertices:
    for g in v.groups: BW[v.index, g.group] = g.weight
BDOM = np.array([names[i] for i in BW.argmax(1)])
rig.data.pose_position = "POSE"
Wm, Cm, masks, keys = [], [], [], []
acts = {int(a["uo_action"]): a for a in bpy.data.actions if "uo_action" in a}
for a in ACTS:
    if a not in acts: continue
    act = acts[a]; rig.animation_data.action = act
    for i in range(0, int(act["uo_frames"]), STEP):
        sc.frame_set(1 + 3 * i)
        for d in range(5):
            rig["uo_direction"] = d; rig.update_tag(); bpy.context.view_layer.update()
            dg = bpy.context.evaluated_depsgraph_get()
            re = rig.evaluated_get(dg); rmw = re.matrix_world; bmw = v13.evaluated_get(dg).matrix_world
            mats = []
            for bn in bones:
                pb = re.pose.bones[bn]; bone = re.data.bones[bn]
                mats.append(np.array(rmw @ pb.matrix @ bone.matrix_local.inverted() @ rmw.inverted() @ bmw))
            Wm.append(mats)
            c = cam.evaluated_get(dg)
            Cm.append(np.array(c.calc_matrix_camera(dg, x=136, y=120)) @ np.array(c.matrix_world.inverted()))
            masks.append(np.frombuffer(zlib.decompress(base64.b64decode(ORIG["%d,%d,%d" % (a, i, d)])), np.uint8).reshape(120, 136, 4)[..., 3] > 0)
            keys.append((a, i, d))
np.savez_compressed(out, W=np.array(Wm), C=np.array(Cm), masks=np.array(masks), keys=np.array(keys), bones=np.array(bones),
                    U=U, BV=BV, BDOM=BDOM, v13_mw=np.array(v13.matrix_world))
print("views", len(keys))
