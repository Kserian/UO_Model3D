# Hold the SELECTED instrument (upright from uo_orient_weapon.py, strings to -Y from uo_face_strings.py) in the RIGHT hand the way it is carried in the walk, run and stand: by the neck a little above the
# body, the instrument lying across the front of the body, the strings out. The hand is rigid on it (uo_bind_item.py PART "weapon" = hand.R).
# The pose is given in the pose of ACTION, in world axes (the body faces -Y, its left is +X, up is +Z); the script carries it back into the rest pose of the rig, in which the mesh is bound:
#   AXIS   world direction of the headstock (butt -> tip) in the pose; FRONT world direction the strings face (made perpendicular to AXIS); GRIP m from the butt where the hand holds the neck
#   BONE2  a second hand (hand.L): the instrument is then laid along the line between the two palms (AXIS is ignored), hand.R holding it at GRIP and hand.L at GRIP + the distance of the palms (both hands on the instrument);
#          the rest of the instrument is centred on the middle between the palms
#   FOLLOW the bone the instrument will be bound to (None = BONE): hand.R when the hands move it, "pelvis" for an idle where the arms swing but the instrument stays at the belly (bind PART "belly")
#   ELEV   degrees above the horizontal of the axis (None = as it comes from AXIS / the palms): the headstock is raised or lowered, the direction seen from above is kept
#   CLASS  True = the axis and the grip point are those of the 1H weapon line (weapon_motion.json weapon1h.R) in the pose of ACTION: a lute held like a sword, to be tilted with OUT / VERT
#   OUT    degrees: the headstock is tilted towards the body, the bowl swings out (away from the body, world -X: the right hand's side); VERT 0..1: the axis is blended towards vertical
#   LIE    True = the axis is the long axis of the body (pelvis -> head) in the pose, strings up: the instrument lies beside a body on the ground (deaths); SHIFT puts it beside the body
#   SIDE   m (with LIE): the grip point is pushed this far away from the body's long axis, to the side of the hand (the instrument lies beside the body, not under it)
#   SHIFT  m, extra shift of the grip point in world axes (from the middle of the palm); ROLL degrees, turn of the instrument about its own axis (strings towards FRONT = 0)
import bpy, math, json
import numpy as np
from mathutils import Vector, Matrix

ACTION = "04_stand"
FRAME = 1
BONE = "hand.R"
AXIS = [0.85, -0.40, 0.35]
FRONT = [0.0, -1.0, 0.3]
GRIP = 0.52
SHIFT = [0.0, 0.0, 0.0]
ROLL = 0.0
BONE2 = None
FOLLOW = None
CLASS = False
OUT = 0.0
VERT = 0.0
LIE = False
SIDE = 0.0
ELEV = None
PALM = 0.4                                  # share of the hand bone from the wrist to the middle of the palm

rig = bpy.data.objects["UO_Rig"]
bone = rig.data.bones[BONE]
saved = (rig.data.pose_position, rig.animation_data.action if rig.animation_data else None)
rig.data.pose_position = "REST"; bpy.context.view_layer.update()
fbone = rig.data.bones[FOLLOW or BONE]
Pr = rig.matrix_world @ fbone.matrix_local                                   # the bound bone (hand) at rest (world)
rig.data.pose_position = "POSE"
rig.animation_data_create(); rig.animation_data.action = bpy.data.actions[ACTION]
bpy.context.scene.frame_set(FRAME); bpy.context.view_layer.update()
Pp = rig.matrix_world @ rig.pose.bones[BONE].matrix                         # the same bone in the pose
Pf = rig.matrix_world @ rig.pose.bones[FOLLOW or BONE].matrix               # the bound bone in the pose
pelvis_pos = rig.matrix_world @ rig.pose.bones["pelvis"].head
body_axis = rig.matrix_world.to_3x3() @ (rig.pose.bones["head"].head - rig.pose.bones["pelvis"].head)   # pelvis -> head in the pose
rig.animation_data.action = saved[1]; rig.data.pose_position = saved[0]; bpy.context.view_layer.update()
palm = Vector((0, PALM * bone.length, 0))
G = Pp @ palm + Vector(SHIFT)                                               # grip point in the pose (world)
grip = GRIP
if BONE2:                                                                   # both hands: the axis runs through both palms
    bone2 = rig.data.bones[BONE2]
    rig.data.pose_position = "POSE"; rig.animation_data.action = bpy.data.actions[ACTION]
    bpy.context.scene.frame_set(FRAME); bpy.context.view_layer.update()
    G2 = rig.matrix_world @ rig.pose.bones[BONE2].matrix @ Vector((0, PALM * bone2.length, 0)) + Vector(SHIFT)
    rig.animation_data.action = saved[1]; rig.data.pose_position = saved[0]; bpy.context.view_layer.update()
    AXIS = list(G2 - G); span = (G2 - G).length
    G = (G + G2) / 2; grip = GRIP + span / 2                                 # the middle of the palms sits at the middle of the two grips
    print("uo_place_carry: palms %.2f m apart, grips at %.2f and %.2f m" % (span, GRIP, GRIP + span))

if CLASS:
    WM = json.loads(bpy.data.texts["weapon_motion.json"].as_string())["weapon1h.R"]
    AXIS = list(Pp.to_3x3() @ Vector(WM["dir"]))
    G = Pp @ Vector(WM["pivot"]) + Vector(SHIFT)
if LIE:
    AXIS = list(body_axis)
    if SIDE:
        ba = body_axis.normalized(); v = G - pelvis_pos; v = v - v.dot(ba) * ba
        G = G + v.normalized() * SIDE
a = Vector(AXIS).normalized()
if OUT:
    o = Vector((-1, 0, 0)); op = (o - o.dot(a) * a).normalized()
    a = (a * math.cos(math.radians(OUT)) - op * math.sin(math.radians(OUT))).normalized()
if VERT:
    a = (a + Vector((0, 0, VERT))).normalized()
if ELEV is not None:
    h = Vector((a.x, a.y, 0)).normalized()
    a = (h * math.cos(math.radians(ELEV)) + Vector((0, 0, math.sin(math.radians(ELEV))))).normalized()
f = Vector(FRONT); f = (f - f.dot(a) * a).normalized()
f = Matrix.Rotation(math.radians(ROLL), 3, a) @ f
x = (-f).cross(a).normalized()                                              # model +X in the pose: +Y (back) = -f, X = Y x Z
Rp = Matrix(((x.x, -f.x, a.x), (x.y, -f.y, a.y), (x.z, -f.z, a.z)))         # columns: model X, Y, Z in the pose

for ob in [o for o in bpy.context.selected_objects if o.type == "MESH"]:
    co = np.array([ob.matrix_world @ v.co for v in ob.data.vertices])
    near = co[np.abs(co[:, 2] - grip) < 0.03]
    c = near[:, :2].mean(0) if len(near) else co[:, :2].mean(0)             # the neck axis at the grip
    M_pose = Matrix.Translation(G) @ Rp.to_4x4() @ Matrix.Translation(-Vector((c[0], c[1], grip)))
    delta = Pf @ Pr.inverted()                                              # rest -> pose of the bound bone
    ob.matrix_world = delta.inverted() @ M_pose @ ob.matrix_world
print("uo_place_carry: grip %.2f m, axis %s, strings towards %s in %s" % (GRIP, tuple(round(v, 2) for v in a), tuple(round(v, 2) for v in f), ACTION))
