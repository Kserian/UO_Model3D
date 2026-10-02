"""Is UO metal matte? Fits sprite = A*(0.0798+0.9202*c) + ks*c^n (c = N.L of the UO light, taken from the replica rendered by test_items.py with the grey
UO_Look material of albedo 0.35) on the interior pixels of 04_stand, 5 directions, for pants 431 (cloth), plate 527 and helm 563 (metal).
Result of session 10: cloth ks = 0; plate/helm ks 0.4-0.6, n 13-20 (linear domain), see SESSION_HANDOFF.md.

    python metal_highlight_fit.py DIR
"""
import os, sys, numpy as np
from PIL import Image
from scipy import ndimage, optimize
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,os.path.join(HERE,"body13"))
from itemframes import canvas, load
S=os.path.abspath(sys.argv[1])        # the --tmp directory of: python test_items.py --items plate,helm,pants --actions 04_stand --tmp DIR
dec=lambda v:np.where(v<=0.04045,v/12.92,((v+0.055)/1.055)**2.4)
def data(item,anim):
    bl=load(anim);C=[];P=[]
    for d in range(5):
        spr=canvas(bl.get((4,d)),0); y0,x0=192-86,128-68
        rr=np.array(Image.open(f"{S}/{item}/clothing/frames/04_stand/dir{d}/00.png").convert("RGBA"))[y0:y0+120,x0:x0+136]
        m=ndimage.binary_erosion((rr[...,3]>0)&(spr[...,3]>0),iterations=2)
        C.append(rr[m][:,:3].mean(1)); P.append(spr[m][:,:3].mean(1))
    C=np.concatenate(C);P=np.concatenate(P)
    c=(dec(C/255)/0.35-0.0798)/0.9202
    return np.clip(c,0,1),P
for item,anim in (("pants",431),("plate",527),("helm",563)):
    c,P=data(item,anim)
    for name,dom in (("srgb",lambda v:v/255),("linear",lambda v:dec(v/255))):
        y=dom(P)
        def model(p,c,spec=True):
            A,ks,n=p; return A*(0.0798+0.9202*c)+(ks*c**n if spec else 0)
        best=None
        for n0 in (8,30,100,300):
            try:
                r=optimize.least_squares(lambda p:model(p,c)-y,[0.3,0.5,n0],bounds=([0,0,1],[1.5,2,2000]))
            except Exception as e: continue
            if best is None or r.cost<best.cost: best=r
        r0=optimize.least_squares(lambda p:model((p[0],0,1),c)-y,[0.3])
        print("%-5s %-6s lambert only: A=%.3f rms %.4f | +spec A=%.3f ks=%.3f n=%.0f rms %.4f"%(item,name,r0.x[0],np.sqrt(2*r0.cost/len(y)),*best.x,np.sqrt(2*best.cost/len(y))))
