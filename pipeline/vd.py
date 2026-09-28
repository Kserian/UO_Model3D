import struct, json, os
import numpy as np
from PIL import Image

ACTIONS_PEOPLE = [
 "walk_unarmed","walk_armed","run_unarmed","run_armed","stand","fidget_1","fidget_2",
 "combat_idle_1h","combat_idle_2h","attack_1h_slash","attack_1h_pierce","attack_1h_bash",
 "attack_2h_bash","attack_2h_slash","attack_2h_pierce","combat_advance","spell_directed",
 "spell_area","attack_bow","attack_crossbow","get_hit","die_forward","die_backward",
 "mounted_walk","mounted_run","mounted_stand","mounted_attack_1h","mounted_attack_bow",
 "mounted_attack_crossbow","mounted_attack_2h","block","punch","bow","salute","eat"]

def c16(c):
    r=(c>>10)&0x1f; g=(c>>5)&0x1f; b=c&0x1f
    return (r*255//31, g*255//31, b*255//31)

def read_vd(path):
    d=open(path,'rb').read()
    ft,at=struct.unpack_from('<hh',d,0)
    nact={0:22,1:13,2:35}[at]
    anims={}
    for i in range(nact*5):
        off,ln,ex=struct.unpack_from('<iii',d,4+12*i)
        a,dr=divmod(i,5)
        if off<=0 or ln<=0: continue
        pal=[c16(v) for v in struct.unpack_from('<256H',d,off)]
        start=off+512
        (fc,)=struct.unpack_from('<i',d,start)
        offs=struct.unpack_from('<%di'%fc,d,start+4)
        frames=[]
        for fo in offs:
            p=start+fo
            cx,cy,w,h=struct.unpack_from('<hhHH',d,p); p+=8
            img=np.zeros((h,w,4),np.uint8)
            xb=cx-0x200; yb=cy+h-0x200
            while True:
                (hdr,)=struct.unpack_from('<I',d,p); p+=4
                if hdr==0x7FFF7FFF: break
                hdr^=(0x200<<22)|(0x200<<12)
                x=xb+((hdr>>22)&0x3ff); y=yb+((hdr>>12)&0x3ff); n=hdr&0xfff
                idx=d[p:p+n]; p+=n
                for k,ci in enumerate(idx):
                    img[y,x+k,:3]=pal[ci]; img[y,x+k,3]=255
            frames.append(dict(cx=cx,cy=cy,w=w,h=h,img=img))
        anims[(a,dr)]=frames
    return at,nact,anims
