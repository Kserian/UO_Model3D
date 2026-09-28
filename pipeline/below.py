import sys,pickle,numpy as np,jax.numpy as jnp
from posefit_mesh import *
from posefit_mesh import _posed_j
P=pickle.load(open(sys.argv[1],"rb"))
Wn=np.asarray(md["W"]); bones=md["bones"]
for a in [int(x) for x in sys.argv[2].split(",")]:
    p=P[a]["poses"]
    for i in range(p["trans"].shape[0]):
        X=np.asarray(_posed_j({k:jnp.asarray(v[i]) for k,v in p.items()}))
        b=X[:,2]<GROUND-0.008
        parts={}
        for j in Wn[b].argmax(1): parts[bones[j]]=parts.get(bones[j],0)+1
        print(a,i,"min z %+.3f"%X[:,2].min(),"n below",b.sum(),sorted(parts.items(),key=lambda t:-t[1])[:4])
