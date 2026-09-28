import numpy as np, jax, jax.numpy as jnp, optax, pickle, time
from body import *
from fit import *
from targets import targets
from viz import overlay_row
from PIL import Image

# frames used for the shape fit: stand, walk, run, fidget, spell_area, bow
sel = [(4,0)] + [(0,i) for i in range(0,10,2)] + [(2,i) for i in range(0,10,2)] + [(17,3),(16,3),(32,2),(6,2)]
T = np.stack([targets(a,i)[0] for a,i in sel])            # (F,5,H,W,4)
Anp = T[...,3].astype(np.float32)/255.0
y0,y1,x0,x1 = crop_box(Anp)
print('crop', y1-y0, x1-x0)
A = jnp.asarray(Anp[...,y0:y1,x0:x1])
pix = PIX[y0:y1,x0:x1]
F = len(sel)
ground_w = jnp.asarray([0.0 if a==21 else 1.0 for a,_ in sel])

S0 = init_shape()
fixed = {k:S0[k] for k in FIXED_KEYS}
params = dict(shape=shape_to_params(S0),
              poses=jax.tree.map(lambda x: jnp.stack([x]*F), init_pose_params()))

def total(params):
    S = params_to_shape(params['shape'], fixed)
    f = jax.vmap(lambda pp, a, g: frame_loss(S, pp, a, g, pix=pix, torso_w=0.3))
    l, d = f(params['poses'], A, ground_w)
    return jnp.sum(l) + shape_prior(S, S0), jnp.sum(d)

vg = jax.jit(jax.value_and_grad(total, has_aux=True))
sched = optax.exponential_decay(0.02, 1000, 0.3)
opt = optax.adam(sched); st = opt.init(params)
@jax.jit
def step(params, st):
    (l, d), g = vg(params)
    up, st = opt.update(g, st, params)
    return optax.apply_updates(params, up), st, l, d
t=time.time()
for it in range(1601):
    params, st, l, d = step(params, st)
    if it%250==0: print(it, float(l), float(d), f"{time.time()-t:.0f}s", flush=True)
pickle.dump(jax.tree.map(np.asarray, dict(params=params, fixed=fixed, sel=sel)), open('shape_fit.pkl','wb'))
S = params_to_shape(params['shape'], fixed)
print('theta deg', float(jnp.degrees(S['theta'])))
for k,v in S.items(): print(k, np.round(np.asarray(v),3))
rows=[]
for i in range(F):
    pose = pose_from_params(jax.tree.map(lambda x:x[i], params['poses']))
    P,R = fk(S,pose)
    rows.append(overlay_row(T[i], [render_sil(S,P,R,d) for d in range(5)], zoom=3))
W=rows[0].width; im=Image.new('RGB',(W,sum(r.height for r in rows)))
y=0
for r in rows: im.paste(r,(0,y)); y+=r.height
im.save('shape_fit.png')
