import numpy as np
from PIL import Image
def overlay_row(tg, occs, zoom=4):
    """tg: (5,H,W,4) uint8, occs: (5,H,W) float -> composite image: sprite with red model silhouette outline tint"""
    tiles=[]
    for d in range(len(tg)):
        t=tg[d].astype(np.float32)
        base=np.full(t.shape[:2]+(3,),40.0)
        a=t[...,3:4]/255
        base=base*(1-a)+t[...,:3]*a
        o=np.asarray(occs[d])[...,None]
        # model: blue tint where model only, red where sprite only
        col=base.copy()
        col=col*(1-0.45*o)+np.array([60,120,255])*0.45*o
        tiles.append(np.clip(col,0,255).astype(np.uint8))
    row=np.concatenate(tiles,1)
    im=Image.fromarray(row)
    return im.resize((im.width*zoom,im.height*zoom),Image.NEAREST)
