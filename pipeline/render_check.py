import bpy, sys, os, math, numpy as np
from mathutils import Vector
blend=sys.argv[sys.argv.index('--blend')+1]; out=sys.argv[sys.argv.index('--out')+1]
bpy.ops.wm.open_mainfile(filepath=os.path.abspath(blend))
sc=bpy.context.scene
arm=bpy.data.objects['UO_Rig']
act_name = sys.argv[sys.argv.index('--action')+1] if '--action' in sys.argv else None
frame = int(sys.argv[sys.argv.index('--frame')+1]) if '--frame' in sys.argv else 1
if act_name: arm.animation_data.action=bpy.data.actions[act_name]
else: arm.animation_data.action=None
sc.frame_set(frame)
sc.render.engine='CYCLES'; sc.cycles.samples=16; sc.cycles.device='CPU'
# 1) turntable preview (perspective-free ortho, big)
cam=bpy.data.cameras.new('Prev'); cam.type='ORTHO'; cam.ortho_scale=2.2
co=bpy.data.objects.new('Prev',cam); sc.collection.objects.link(co)
uo_cam=sc.camera
sc.camera=co; sc.render.resolution_x, sc.render.resolution_y=(380,560); sc.render.film_transparent=False
sc.render.filter_size=1.5
paths=[]
for yaw in (0,45,90,180):
    a=math.radians(yaw); e=math.radians(8); d=6
    pos=Vector((d*math.sin(a)*math.cos(e), -d*math.cos(a)*math.cos(e), 1.0+d*math.sin(e)))
    co.location=pos; co.rotation_euler=(Vector((0,0,1.0))-pos).to_track_quat('-Z','Y').to_euler()
    p=f"{out}_turn{yaw}.png"; sc.render.filepath=os.path.abspath(p); bpy.ops.render.render(write_still=True); paths.append(p)
from PIL import Image
ims=[Image.open(p).convert('RGB') for p in paths]
m=Image.new('RGB',(sum(i.width for i in ims),ims[0].height)); x=0
for i in ims: m.paste(i,(x,0)); x+=i.width
m.save(out+'_turntable.png')
# 2) UO camera renders for 5 directions
sc.camera=uo_cam; sc.render.resolution_x, sc.render.resolution_y=(136,120); sc.render.film_transparent=True
sc.render.filter_size=0.5
uo=[]
for d in range(5):
    arm['uo_direction']=d; sc.frame_set(frame)
    p=f"{out}_uo{d}.png"; sc.render.filepath=os.path.abspath(p); bpy.ops.render.render(write_still=True); uo.append(p)
