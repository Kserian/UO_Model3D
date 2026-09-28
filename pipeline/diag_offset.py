import sys
sys.argv=['refine_mesh.py','0']
exec(open('refine_mesh.py').read().split('params = dict(delta=')[0])
import pickle
from texbake import tri_raster
r=pickle.load(open('refine_mesh.pkl','rb'))
params=dict(delta=jnp.asarray(r['delta']), **{k:jnp.asarray(v) for k,v in r['poses'].items()})
def raster_mask(q):
    m=np.zeros((H,Wc),bool)
    def fn(t,xs,ys,bc): m[ys,xs]=True
    tri_raster(q[tris],fn,Wc,H)
    return m
rng=np.random.default_rng(1); pick=rng.choice(NS,25,replace=False)
proj={}
for s in pick:
    pp={k:params[k][s] for k in ('ball','hinge','trans')}
    p,_=forward(params['delta'],pp); proj[s]=np.asarray(p)
best=None
for ox in (-1.0,-0.5,0.0,0.5,1.0):
    for oy in (-1.0,-0.5,0.0,0.5,1.0):
        tot=[0,0]
        for s in pick:
            for d in range(5):
                m=raster_mask(proj[s][d]+np.array([ox,oy])); sm=masks[s,d]
                tot[0]+=(m&sm).sum(); tot[1]+=(m|sm).sum()
        iou=tot[0]/tot[1]; print(f"offset x {ox:+.1f} y {oy:+.1f}  IoU {iou:.4f}", flush=True)
        if best is None or iou>best[0]: best=(iou,ox,oy)
print('best',best)
