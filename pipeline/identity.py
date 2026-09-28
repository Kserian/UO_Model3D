import pickle, numpy as np, jax, jax.numpy as jnp, optax
from body import *; from fit import *; from targets import targets
sf=pickle.load(open('shape_fit.pkl','rb'))
S=params_to_shape({k:jnp.asarray(v) for k,v in sf['params']['shape'].items()},{k:jnp.asarray(v) for k,v in sf['fixed'].items()})
BI={j:i for i,j in enumerate(BALL_IDX)}; HI={j:i for i,j in enumerate(HINGE_IDX)}
MIR=jnp.array([1.0,-1.0,-1.0])
def swap(pp, balls, hinges):
    b,h=pp['ball'],pp['hinge']
    for l in balls:
        il,ir=BI[JI[l+'.L']],BI[JI[l+'.R']]; bl,br=b[il],b[ir]; b=b.at[il].set(br*MIR).at[ir].set(bl*MIR)
    for l in hinges:
        il,ir=HI[JI[l+'.L']],HI[JI[l+'.R']]; hl,hr=h[il],h[ir]; h=h.at[il].set(hr).at[ir].set(hl)
    return dict(ball=b,hinge=h,trans=pp['trans'])
VARIANTS={'as_fitted':lambda p:p,'legs_LR':lambda p:swap(p,['hip','ankle'],['knee']),
          'arms_LR':lambda p:swap(p,['shoulder','wrist'],['elbow']),
          'both_LR':lambda p:swap(p,['hip','ankle','shoulder','wrist'],['knee','elbow'])}
def make(a, mounted=False):
    T=targets(a); Anp=T[...,3].astype(np.float32)/255
    y0,y1,x0,x1=crop_box(Anp,margin=10); A=jnp.asarray(Anp[...,y0:y1,x0:x1]); pix=PIX[y0:y1,x0:x1]
    gw=0.0 if mounted else 1.0
    single=jax.jit(jax.value_and_grad(lambda pp,al: frame_loss(S,pp,al,gw,pix=pix)[0]))
    @jax.jit
    def views_loss(pp,al):
        P,R=fk(S,pose_from_params(pp))
        return jnp.stack([jnp.mean((render_sil(S,P,R,d,pix=pix)-al[d])**2)*100 for d in range(5)])
    def refine(pp,al,n=300):
        opt=optax.adam(0.015); st=opt.init(pp)
        for _ in range(n):
            l,g=single(pp,al); up,st=opt.update(g,st,pp); pp=optax.apply_updates(pp,up)
        return pp
    return A, refine, views_loss
if __name__=='__main__':
    import sys
    r1=pickle.load(open('anim_fit_run1.pkl','rb')); r2=pickle.load(open('anim_fit2a.pkl','rb'))
    for name,res,a,frames in (('walk',r1,0,[0,5]),('run',r2,2,[0,5])):
        A,refine,vl=make(a)
        for i in frames:
            pp={k:jnp.asarray(v[i]) for k,v in res[a]['poses'].items()}
            out=[]
            for vn,f in VARIANTS.items():
                q=refine(f(pp),A[i]); l=np.asarray(vl(q,A[i]))
                out.append(f"{vn}: front+back {l[0]+l[4]:.2f} all {l.sum():.2f}")
            print(name,'frame',i,' | '.join(out), flush=True)
