import bpy, numpy as np, math
from mathutils import Vector
def setup_scene(res=(360,560)):
    sc=bpy.context.scene
    sc.render.engine='CYCLES'; sc.cycles.samples=12; sc.cycles.device='CPU'
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.film_transparent=False
    w=bpy.data.worlds.new('W'); sc.world=w; w.use_nodes=True
    w.node_tree.nodes['Background'].inputs[0].default_value=(0.18,0.19,0.22,1); w.node_tree.nodes['Background'].inputs[1].default_value=0.6
    for name,rot,en in (('Key',(50,0,-35),3.0),('Fill',(60,0,140),1.2)):
        l=bpy.data.lights.new(name,'SUN'); l.energy=en
        o=bpy.data.objects.new(name,l); o.rotation_euler=[math.radians(a) for a in rot]; sc.collection.objects.link(o)
    cam=bpy.data.cameras.new('PrevCam'); cam.type='ORTHO'; cam.ortho_scale=2.1
    co=bpy.data.objects.new('PrevCam',cam); sc.collection.objects.link(co); sc.camera=co
    return co
def render_views(path_prefix, center_z=0.95, yaws=(0,45,90,180), elev=8, dist=6):
    co=bpy.context.scene.camera
    out=[]
    for y in yaws:
        a=math.radians(y); e=math.radians(elev)
        pos=Vector((dist*math.sin(a)*math.cos(e), -dist*math.cos(a)*math.cos(e), center_z+dist*math.sin(e)))
        co.location=pos
        d=(Vector((0,0,center_z))-pos); co.rotation_euler=d.to_track_quat('-Z','Y').to_euler()
        p=f"{path_prefix}_{y}.png"; bpy.context.scene.render.filepath=p
        bpy.ops.render.render(write_still=True); out.append(p)
    return out
def montage(paths,out):
    from PIL import Image
    ims=[Image.open(p) for p in paths]
    W=sum(i.width for i in ims); H=max(i.height for i in ims)
    m=Image.new('RGB',(W,H)); x=0
    for i in ims: m.paste(i,(x,0)); x+=i.width
    m.save(out)
