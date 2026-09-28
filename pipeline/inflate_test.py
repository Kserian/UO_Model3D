import os, sys, pickle, numpy as np
import jax.numpy as jnp
import posefit_mesh as PM
from posefit_mesh import evaluate, md
fin = pickle.load(open("final_poses.pkl", "rb"))
V = np.asarray(PM.V0)
tris = np.asarray(md["tris"])
fn = np.cross(V[tris[:, 1]] - V[tris[:, 0]], V[tris[:, 2]] - V[tris[:, 0]])
N = np.zeros_like(V)
for k in range(3):
    np.add.at(N, tris[:, k], fn)
N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)
W = np.asarray(md["W"]); b = md["bones"]
foot = W[:, [b.index("foot.L"), b.index("foot.R")]].sum(1)
ACTS = [0, 2, 4, 9, 16, 17, 20, 31, 33]
ank = {}
from posefit_mesh import P0
from body import JI
for side in ("L", "R"):
    ank[side] = np.asarray(P0[JI["ankle." + side]])
fl = W[:, b.index("foot.L")]; fr = W[:, b.index("foot.R")]
for g, fx in [(0.004, 0), (0.005, 0), (0.007, 0), (0.008, 0), (0.006, 0.10), (0.006, 0.20)]:
    Vs = V + N * g
    # lengthen feet: push foot vertices forward (-Y) proportionally to how far in front of the ankle they are
    for side, wf in (("L", fl), ("R", fr)):
        fwd = np.clip(ank[side][1] - V[:, 1], 0, None)
        Vs[:, 1] -= fx * fwd * wf
    Vn = jnp.asarray(Vs, jnp.float32)
    import jax

    def posed_v(pp, Vn=Vn):
        pose = PM.pose_from_params(pp)
        P, R = PM.fk(PM.S, pose)
        Rb = R[PM.BONE_JOINT]
        tb = P[PM.BONE_JOINT] - jnp.einsum("bij,bj->bi", Rb, PM.P0[PM.BONE_JOINT])
        X = jnp.einsum("bij,vj->vbi", Rb, Vn) + tb[None]
        return jnp.einsum("vb,vbi->vi", PM.W, X)
    PM._posed_j = jax.jit(posed_v)   # fresh function object -> fresh trace with the new rest mesh
    r = [evaluate(a, fin[a]["poses"])[0][:, 0].mean() for a in ACTS]
    print(f"inflate {g*100:.1f} cm, feet longer by {fx*100:.0f}%: mean worst-IoU {np.mean(r):.4f}  ", " ".join(f"{x:.3f}" for x in r), flush=True)
