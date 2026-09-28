import pickle, numpy as np, jax, jax.numpy as jnp
from posefit_mesh import *
from vd import ACTIONS_PEOPLE
P = pickle.load(open("final_poses_v5.pkl","rb"))
foot_cols=[md["bones"].index(b) for b in md["bones"] if b.split(".")[0]=="foot"]
FV = np.asarray(md["W"])[:,foot_cols].sum(1)>0.5
pj = jax.jit(posed)
print("rest min z", float(np.asarray(V0)[:,2].min()), "rest foot min z", float(np.asarray(V0)[FV,2].min()))
for a in sorted(P):
    p=P[a]["poses"]; F=p["trans"].shape[0]
    fz=[];bz=[]
    for i in range(F):
        X=np.asarray(pj({k:jnp.asarray(v[i]) for k,v in p.items()}))
        fz.append(X[FV,2].min()); bz.append(X[:,2].min())
    fz=np.array(fz); bz=np.array(bz)
    print(f"{a:2d} {ACTIONS_PEOPLE[a]:24s} foot min {fz.min():+.3f} med {np.median(fz):+.3f} max {fz.max():+.3f} | body min {bz.min():+.3f}  trans_z {p['trans'][:,2].min():+.3f}..{p['trans'][:,2].max():+.3f}")
