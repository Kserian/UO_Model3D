"""Light and shadow of the ORIGINAL UO body frames against the 3D body (880 frames of actions 0-22, 30-34, all 5 directions, 495 k pixels).

    python light_raster.py ../model/UO_Body_0x190.blend lr/part_N.npz --actions ...   (4 runs, see SESSION_HANDOFF.md session 10)
    python -c "import light_data,numpy as np,glob; np.savez('light_table.npz', **light_data.load(sorted(glob.glob('lr/part_*.npz'))))"
    python light_fit.py light_table.npz

Model: light(pixel) = albedo[texel of the UV] * S(pixel), the albedo per texel (96x96 of the UV square) profiled out; S from the normal of the 3D body and the light.
Prints: Lambert in sRGB vs linear light, free light direction (all frames and per direction), model variants (ambient, exponent, wrap, hemisphere, AO, self-shadow),
the residual by self-shadow flag, ambient openness, cosine and body part.
"""
import numpy as np
from scipy import optimize
import sys
D=dict(np.load(sys.argv[1]))
dec=lambda v:np.where(v<=0.04045,v/12.92,((v+0.055)/1.055)**2.4)
m=D['edge']>=2
N=D['N'][m].astype(float); uv=D['uv'][m]; lit=D['lit'][m]; ao=D['ao'][m]; rgb=D['rgb'][m].astype(float)
lum8=rgb.mean(1)
tex=(np.clip(uv[:,0],0,.999)*96).astype(int)*96+(np.clip(uv[:,1],0,.999)*96).astype(int)     # 96x96 texels
ut,inv,cnt=np.unique(tex,return_inverse=True,return_counts=True)
print('pixels',m.sum(),'texels',len(ut),'median samples/texel',np.median(cnt))
def sph(p):
    th,ph=p[0],p[1]; return np.array([np.sin(th)*np.cos(ph),np.sin(th)*np.sin(ph),np.cos(th)])
def resid(y,S):
    # profile out the albedo per texel
    num=np.bincount(inv,y*S); den=np.bincount(inv,S*S); a=num/np.maximum(den,1e-12)
    return y-a[inv]*S
def run(name,dom,model,p0,bounds=None):
    y=dom(lum8)
    f=lambda p: resid(y,model(p))
    r=optimize.least_squares(f,p0,bounds=bounds if bounds else (-np.inf,np.inf))
    rms=np.sqrt(np.mean(r.fun**2)); print("%-34s %-6s rms %.4f  params %s"%(name,dom.__name__,rms,np.round(r.x,4))); return r
srgb=lambda v:v/255.0
srgb.__name__="srgb"
lin=lambda v:dec(v/255.0)
lin.__name__="linear"
L0=np.array([0.0012,-0.7572,0.6532]); th0=np.arccos(L0[2]); ph0=np.arctan2(L0[1],L0[0])
lamb=lambda p: p[2]+(1-p[2])*np.maximum(N@sph(p),0)
fixed=lambda p: 0.0798+0.9202*np.maximum(N@L0,0)
for dom in (srgb,lin):
    y=dom(lum8); print("%-34s %-6s rms %.4f"%("current UO_Look (fixed L, amb .0798)",dom.__name__,np.sqrt(np.mean(resid(y,fixed(None))**2))))
    run("free L + ambient",dom,lamb,[th0,ph0,0.08],([0,-10,0],[np.pi,10,1]))
print("---- normalised: share of the variance (after the per-texel albedo) that the light explains")
for dom in (srgb,lin):
    y=dom(lum8); base=np.sqrt(np.mean(resid(y,np.ones_like(y))**2))
    cur=np.sqrt(np.mean(resid(y,fixed(None))**2))
    print(dom.__name__,"albedo only rms %.4f | current light rms %.4f | explained %.1f%%"%(base,cur,100*(1-cur**2/base**2)))
# per direction free light (linear domain)
print("---- per direction (linear domain): best L, ambient, rms")
y=lin(lum8)
for d in range(5):
    sel=D['dir'][m]==d
    inv_d=inv  # same texel ids; fit with subset
    def fd(p):
        S_=p[2]+(1-p[2])*np.maximum(N[sel]@sph(p),0); num=np.bincount(inv[sel],y[sel]*S_,minlength=len(ut)); den=np.bincount(inv[sel],S_*S_,minlength=len(ut))
        return y[sel]-(num/np.maximum(den,1e-12))[inv[sel]]*S_
    r=optimize.least_squares(fd,[th0,ph0,0.08],bounds=([0,-10,0],[np.pi,10,1]))
    print("dir",d,"L",np.round(sph(r.x),3),"amb %.3f"%r.x[2],"rms %.4f"%np.sqrt(np.mean(r.fun**2)))

y=lin(lum8)
c=np.maximum(N@L0,0)
Sbase=0.0798+0.9202*c
def rms(S_): return np.sqrt(np.mean(resid(y,S_)**2))
print("base (current light) rms %.4f"%rms(Sbase))
# a per texel from base, ratio per pixel
num=np.bincount(inv,y*Sbase); den=np.bincount(inv,Sbase**2); a=num/den; pred=a[inv]*Sbase
ratio=y/np.maximum(pred,1e-4)
print("---- shadows: ratio original/predicted (median) by self-shadow flag, c bin")
for nm,sel in (("lit (ray to light free)",lit==1),("shadowed by the body itself",lit==0)):
    print("  %-30s n %6d  median ratio %.3f"%(nm,sel.sum(),np.median(ratio[sel])))
has_ao=ao<255
aoq=ao.astype(float)/255
print("---- ambient occlusion (8 rays, 0.4 m; only every 3rd frame), ratio by openness")
am=np.arange(0,256)
for lo,hi in ((0,.5),(.5,.75),(.75,.9),(.9,1.0001)):
    sel=(aoq>=lo)&(aoq<hi)&(ao<=255)&(D['ao'][m]!=255) if False else (aoq>=lo)&(aoq<hi)
    print("  openness %.2f-%.2f  n %6d  median ratio %.3f"%(lo,hi,sel.sum(),np.median(ratio[sel]) if sel.sum() else np.nan))
print("---- ratio by cosine n.L (current light)")
for lo,hi in ((0,.2),(.2,.4),(.4,.6),(.6,.8),(.8,.9),(.9,1.01)):
    sel=(c>=lo)&(c<hi); print("  c %.1f-%.1f n %6d  ratio median %.3f p10 %.3f p90 %.3f"%(lo,hi,sel.sum(),np.median(ratio[sel]),*np.percentile(ratio[sel],[10,90])))
print("---- model variants (rms, linear domain, albedo per texel profiled out)")
print("  Lambert + ambient (current)            %.4f"%rms(Sbase))
print("  no ambient (ambient 0)                 %.4f"%rms(c))
for k in (0.5,1.0,2.0):
    print("  Lambert^%.1f                           %.4f"%(k,rms(0.0798+0.9202*c**k)))
wrap=lambda w: np.maximum((N@L0+w)/(1+w),0)
for w in (0.2,0.5):
    print("  wrap lighting w=%.1f                    %.4f"%(w,rms(0.0798+0.9202*wrap(w))))
hemi=lambda k: Sbase*(1+k*(N[:,2]))
for k in (0.2,0.5): print("  + hemisphere (up lighter) k=%.1f        %.4f"%(k,rms(hemi(k))))
sel_ao=D['ao'][m]!=255
for k in (0.3,0.6,1.0):
    S_=Sbase*(1-k*(1-aoq)); 
    yy=y[sel_ao]; 
    def rm2(Sx):
        num=np.bincount(inv[sel_ao],y[sel_ao]*Sx[sel_ao],minlength=len(ut)); den=np.bincount(inv[sel_ao],Sx[sel_ao]**2,minlength=len(ut))
        return np.sqrt(np.mean((y[sel_ao]-(num/np.maximum(den,1e-12))[inv[sel_ao]]*Sx[sel_ao])**2))
    print("  AO darkening k=%.1f (AO frames only)   %.4f  vs base on same pixels %.4f"%(k,rm2(S_),rm2(Sbase)))
for k in (0.3,0.6):
    S_=Sbase*np.where(lit==1,1.0,1-k); print("  + self-shadow darkening k=%.1f          %.4f"%(k,rms(S_)))
print("---- by body part: median ratio, rms")
for p in range(len(D['parts'])):
    sel=D['part'][m]==p
    if sel.sum()>3000: print("  %-12s n %6d ratio median %.3f  rel.rms %.3f"%(D['parts'][p],sel.sum(),np.median(ratio[sel]),np.std(ratio[sel])))
print("---- self-shadow strength: S = amb + (1-amb)*c*(1 if lit else s)")
for s in (0.0,0.2,0.4,0.5,0.6,0.8,1.0):
    print("  s=%.1f  rms %.4f"%(s,rms(0.0798+0.9202*c*np.where(lit==1,1.0,s))))
sh=lit==0
print("shadowed pixels by part:",{str(D['parts'][p]):int(((D['part'][m]==p)&sh).sum()) for p in range(len(D['parts'])) if ((D['part'][m]==p)&sh).sum()>500})
print("share of pixels much darker than predicted (ratio<0.6):",round(float((ratio<0.6).mean()),3),"; of those flagged self-shadowed:",round(float(sh[ratio<0.6].mean()),3), "(base rate %.3f)"%sh.mean())
dk=ratio<0.45
print("pixels very dark (ratio<0.45) n %d: lit-flag share %.3f"%(dk.sum(),(~sh[dk]).mean()))
# shadowed share by action
for a in sorted(set(D['action'][m].tolist())):
    s_=D['action'][m]==a
    print("   action %2d shadowed %.3f  ratio_median_in_shadow %.2f"%(a,sh[s_].mean(), np.median(ratio[s_&sh]) if (s_&sh).sum()>20 else np.nan), end=";" if a%3 else "\n")
