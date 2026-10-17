# The SELECTED item (placed and bound rigid on BONE by uo_place_carry.py + uo_bind_item.py) follows the position of the hand in ACTION but does not turn with it: it keeps the orientation it has in the pose
# FRAME of ACTION and travels with the point LOCAL of the bone (the centre of the hand solid, in the bone's own axes; None = the same HANDMASS point as uo_place_carry.py). A dying body whirls its hand about;
# an instrument that turns with it spins, one that only travels falls with the hand.
# The skin (armature modifier) is removed; the object is parented to the rig and carries one location key per frame of ACTION (the rig turns per direction, so the object turns with it).
import bpy
from mathutils import Vector, Matrix

ACTION = "21_die_forward"
FRAME = 16
BONE = "hand.R"
LOCAL = None

rig = bpy.data.objects["UO_Rig"]; body = bpy.data.objects["UO_Body"]
act = bpy.data.actions[ACTION]
f0, f1 = int(act.frame_range[0]), int(act.frame_range[1])
saved = (rig.data.pose_position, rig.animation_data.action if rig.animation_data else None)
rig.data.pose_position = "POSE"; rig.animation_data_create(); rig.animation_data.action = act
bone = rig.data.bones[BONE]
rest = Matrix(bone.matrix_local)                                              # bone at rest, armature space
if LOCAL is None:
    bpy.context.scene.frame_set(FRAME); bpy.context.view_layer.update()
    gi = body.vertex_groups[BONE].index
    ev = body.evaluated_get(bpy.context.evaluated_depsgraph_get()); me = ev.to_mesh()
    ids = [v.index for v in body.data.vertices if any(g.group == gi and g.weight > 0.5 for g in v.groups)]
    cen = sum((ev.matrix_world @ me.vertices[i].co for i in ids), Vector()) / len(ids); ev.to_mesh_clear()
    LOCAL = (rig.matrix_world @ rig.pose.bones[BONE].matrix).inverted() @ cen
LOCAL = Vector(LOCAL)
pos = {}
for f in range(f0, f1 + 1):
    bpy.context.scene.frame_set(f); bpy.context.view_layer.update()
    pos[f] = rig.pose.bones[BONE].matrix @ LOCAL                              # armature space = the space of the objects parented to the rig
bpy.context.scene.frame_set(FRAME); bpy.context.view_layer.update()
D0 = rig.pose.bones[BONE].matrix @ rest.inverted()                            # rest -> pose of the bone at FRAME (what the rigid skin did to the item)
rig.animation_data.action = saved[1]; rig.data.pose_position = saved[0]; bpy.context.view_layer.update()

for ob in [o for o in bpy.context.selected_objects if o.type == "MESH"]:
    for m in [m for m in ob.modifiers if m.type == "ARMATURE"]:
        ob.modifiers.remove(m)
    ob.parent = rig; ob.parent_type = "OBJECT"; ob.matrix_parent_inverse = Matrix.Identity(4)
    M0 = D0 @ ob.matrix_basis                                                 # where the skinned item stood in the pose
    loc0, rot0, sc0 = M0.decompose()
    ob.rotation_mode = "QUATERNION"; ob.rotation_quaternion = rot0; ob.scale = sc0
    ob.animation_data_create(); ob.animation_data.action = bpy.data.actions.new("%s_follow" % ob.name)
    for f in range(f0, f1 + 1):
        ob.location = loc0 + (pos[f] - pos[FRAME])
        ob.keyframe_insert("location", frame=f)
    for fc in ob.animation_data.action.fcurves:
        for k in fc.keyframe_points:
            k.interpolation = "LINEAR"
    ob.location = loc0
    print("uo_follow_hand: %s follows %s of %s over frames %d-%d, orientation of frame %d, travel %.2f m" % (ob.name, BONE, ACTION, f0, f1, FRAME, max((pos[f] - pos[FRAME]).length for f in pos)))
