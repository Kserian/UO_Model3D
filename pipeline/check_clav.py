import bpy, pickle, numpy as np, sys
import jax.numpy as jnp
bpy.ops.wm.open_mainfile(filepath="out_ct/UO_Body_0x190.blend")
import os; os.environ["UO_DELTA"] = "refine_infl.pkl"
from posefit_mesh import posed
P = pickle.load(open("test_clav_poses.pkl", "rb"))
sc = bpy.context.scene; rig = bpy.data.objects["UO_Rig"]; body = bpy.data.objects["UO_Body"]
rig["uo_direction"] = 0
for a, name in ((17, "17_spell_area"), (4, "04_stand")):
    rig.animation_data.action = bpy.data.actions[name]
    for i in range(P[a]["poses"]["trans"].shape[0]):
        sc.frame_set(1 + 3 * i)
        dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh()
        co = np.zeros(len(me.vertices) * 3); me.vertices.foreach_get("co", co); ev.to_mesh_clear()
        M = np.array(body.matrix_world); co = co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
        X = np.asarray(posed({k: jnp.asarray(v[i]) for k, v in P[a]["poses"].items()})) + np.array([0, 0, sc["uo_anchor_height"]])
        print(name, i, "max |blender - fit| = %.2f mm" % (np.abs(co - X).max() * 1000))
