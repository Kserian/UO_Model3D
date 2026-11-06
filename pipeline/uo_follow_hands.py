# The SELECTED instrument (upright, butt z = 0, strings to -Y; from uo_orient_weapon.py / uo_face_strings.py, placed and bound by uo_place_carry.py + uo_bind_item.py) is held with BOTH hands, the way one
# plays it: in every frame of ACTION its axis runs through the centres of the two hand solids (BONE = the right hand on the bowl at S_R m from the butt, BONE2 = the left hand on the neck at S_L), the
# strings face FRONT, and the middle of the two hands sits at the middle of the two grips. So both hands touch it in every frame, also when the arms move (the fidgets): the instrument is a rigid
# body that follows the two hands (no skin: the armature modifier is removed, the object is parented to the rig and carries a location and a rotation key per frame of ACTION; the rig turns per
# direction, so the object turns with it).
#   FRAME      the frame in which the hand-solid centres are measured (in the bones' own axes)
#   S_R, S_L   m along the shaft where the right / left palm holds; S_L None = S_R + the distance of the palms at FRAME (the palms keep their distance along the neck)
#   FRONT      the direction the strings face (world, made perpendicular to the axis)
#   TILT       degrees: the headstock end raised above the line of the hands
#   SHIFT      m, world axes: the whole instrument moved (in front of the belly: the line of the palms runs through the belly's skin, so the neck would stand inside the body; the hands then hold it from behind)
import bpy, math
import numpy as np
from mathutils import Vector, Matrix

ACTION = "04_stand"
FRAME = 1
BONE = "hand.R"
BONE2 = "hand.L"
S_R = 0.30
S_L = None
FRONT = [0.0, -1.0, 0.3]
TILT = 0.0
SHIFT = [0.0, 0.0, 0.0]

rig = bpy.data.objects["UO_Rig"]; body = bpy.data.objects["UO_Body"]
act = bpy.data.actions[ACTION]
f0, f1 = int(act.frame_range[0]), int(act.frame_range[1])
saved = (rig.data.pose_position, rig.animation_data.action if rig.animation_data else None)
rig.data.pose_position = "POSE"; rig.animation_data_create(); rig.animation_data.action = act
bpy.context.scene.frame_set(FRAME); bpy.context.view_layer.update()
ev = body.evaluated_get(bpy.context.evaluated_depsgraph_get()); me = ev.to_mesh()
LOCAL = {}
for b in (BONE, BONE2):
    gi = body.vertex_groups[b].index
    ids = [v.index for v in body.data.vertices if any(g.group == gi and g.weight > 0.5 for g in v.groups)]
    cen = sum((ev.matrix_world @ me.vertices[i].co for i in ids), Vector()) / len(ids)
    LOCAL[b] = (rig.matrix_world @ rig.pose.bones[b].matrix).inverted() @ cen
ev.to_mesh_clear()
pos = {}
for f in range(f0, f1 + 1):
    bpy.context.scene.frame_set(f); bpy.context.view_layer.update()
    pos[f] = (rig.pose.bones[BONE].matrix @ LOCAL[BONE], rig.pose.bones[BONE2].matrix @ LOCAL[BONE2])
d0 = (pos[FRAME][1] - pos[FRAME][0]).length if FRAME in pos else (pos[f0][1] - pos[f0][0]).length
rig.animation_data.action = saved[1]; rig.data.pose_position = saved[0]; bpy.context.view_layer.update()
s_l = S_L if S_L is not None else S_R + d0
s_mid = (S_R + s_l) / 2
print("uo_follow_hands: palms %.2f m apart at frame %d, grips at %.2f and %.2f m" % (d0, FRAME, S_R, s_l))

for ob in [o for o in bpy.context.selected_objects if o.type == "MESH"]:
    for m in [m for m in ob.modifiers if m.type == "ARMATURE"]:
        ob.modifiers.remove(m)
    co = np.empty(len(ob.data.vertices) * 3); ob.data.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
    near = co[np.abs(co[:, 2] - s_mid) < 0.03]
    c = near[:, :2].mean(0) if len(near) else co[:, :2].mean(0)               # the neck axis at the middle of the grips
    ob.parent = rig; ob.parent_type = "OBJECT"; ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.rotation_mode = "QUATERNION"; ob.scale = (1, 1, 1)
    ob.animation_data_create(); ob.animation_data.action = bpy.data.actions.new("%s_follow_hands" % ob.name)
    for f in range(f0, f1 + 1):
        pr, pl = pos[f]
        a = (pl - pr).normalized()
        if TILT:
            n = a.cross(Vector((0, 0, 1)))
            if n.length > 1e-6:
                a = (Matrix.Rotation(math.radians(TILT), 3, n.normalized()) @ a).normalized()
        fr = Vector(FRONT); fr = (fr - fr.dot(a) * a).normalized()
        x = (-fr).cross(a).normalized()
        R = Matrix(((x.x, -fr.x, a.x), (x.y, -fr.y, a.y), (x.z, -fr.z, a.z)))   # columns: model X, Y, Z in the pose
        loc = (pr + pl) / 2 + Vector(SHIFT) - R @ Vector((c[0], c[1], s_mid))
        ob.location = loc; ob.rotation_quaternion = R.to_quaternion()
        ob.keyframe_insert("location", frame=f); ob.keyframe_insert("rotation_quaternion", frame=f)
    for fc in ob.animation_data.action.fcurves:
        for k in fc.keyframe_points:
            k.interpolation = "LINEAR"
    print("uo_follow_hands: %s follows %s and %s over frames %d-%d" % (ob.name, BONE, BONE2, f0, f1))
