import pickle, sys, numpy as np, jax, jax.numpy as jnp
from body import *; from fit import *; from targets import targets
from vd import ACTIONS_PEOPLE
sf=pickle.load(open('shape_fit.pkl','rb'))
S=params_to_shape({k:jnp.asarray(v) for k,v in sf['params']['shape'].items()},{k:jnp.asarray(v) for k,v in sf['fixed'].items()})
res=pickle.load(open(sys.argv[1] if len(sys.argv)>1 else 'anim_fit.pkl','rb'))
@jax.jit
def sil(pp):
    P,R=fk(S,pose_from_params(pp)); return jnp.stack([render_sil(S,P,R,d) for d in range(5)])
out={}
for a in sorted(res):
    T=targets(a); F=len(T); worst=[]
    for i in range(F):
        o=np.asarray(sil({k:jnp.asarray(v[i]) for k,v in res[a]['poses'].items()}))>0.5
        s=T[i][...,3]>127
        iou=[(o[d]&s[d]).sum()/max((o[d]|s[d]).sum(),1) for d in range(5)]
        worst.append(min(iou))
    out[a]=worst
    flag=' <-- ' + ','.join(str(i) for i,w in enumerate(worst) if w<0.78) if min(worst)<0.78 else ''
    print(f"{a:2d} {ACTIONS_PEOPLE[a]:24s} mean-min-IoU {np.mean(worst):.3f} worst {min(worst):.3f}{flag}", flush=True)
pickle.dump(out,open('iou_stats.pkl','wb'))
