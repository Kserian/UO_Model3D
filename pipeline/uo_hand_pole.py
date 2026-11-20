# Hand poles (ski / walking poles): one pole in each hand, the handle through the fist, the spike towards the floor, in EVERY action of this file.
# Run after uo_orient_weapon.py (the SELECTED mesh is the pole: shaft along +Z, handle UP, spike at z = 0; TIP = the handle's axis in the recipe) and before uo_bind_item.py
# (the recipe binds each pole with PART "pole.R" / "pole.L" = rigid on its own bone).
# What it does:
# 1. copies the pole for each hand in HANDS ("pole.R", "pole.L"), puts it upright with the point HOLD m below the top of the handle on the CENTRE OF THE FIST of the hand at rest
#    (FIST: centre of the circle the finger joints of the rig make when they curl, in the hand's own axes, measured on the rig);
# 2. adds the bones pole.R / pole.L (no parent, so that the pole is not bent by the hand; item-only bones: the base .blend is not changed) and keys them in every action
#    (frame 1 + 3 i for pose i, as the weapon bones do): the grip point follows the fist exactly; the direction is NOT rigid with the hand:
#      - fore-aft: the pole tilts as the whole arm swings (shoulder -> wrist) relative to the stand pose, SWING_GAIN x the swing, on top of BASE_BACK (the spike trails a little);
#        so both hands get the same attitude in the stand and the pole swings with the arm in the walk;
#      - sideways: LATERAL_BASE (0 = plumb) + LATERAL_GAIN x the arm's sideways swing relative to the stand pose, never more than LATERAL_MAX degrees out or in.
#    A pole rigid on the hand would lean 20 deg sideways in the stand (the rest pose of the UO stand holds the hands turned inwards, forward), this keeps it within a few degrees.
# The pole is valid for the stand and the walks (04_stand, 00_walk_unarmed, 01_walk_armed); other actions get the same rule, but nothing there was checked.
# Running it again replaces the poles and the keys.
import math
import bpy
from mathutils import Matrix, Quaternion, Vector

HANDS = "RL"                   # "R", "L" or "RL"
HOLD = 0.12                    # m below the top of the handle where the fist is
BASE_BACK = 6.0                # deg: the spike trails behind (+) or leads (-) in the stand pose
SWING_GAIN = 0.7               # share of the arm's fore-aft swing (relative to the stand) the pole takes over
LATERAL_BASE = 0.0             # deg: sideways tilt in the stand (+ = spike outwards, - = inwards)
LATERAL_GAIN = 0.15            # share of the arm's sideways swing the pole takes over
LATERAL_MAX = 3.0              # deg: the pole is never tilted more than this sideways
REF_ACTION = "04_stand"        # the pose the arms are measured against
FIST = (0.019, 0.084, 0.012)   # m, centre of the fist in hand.R axes (hand.L: x mirrored); measured: circle through the joints of the middle finger
THICK = 1.0                    # factor on the thickness of the shaft and the handle (a 2 cm shaft is 0.7 px at 36 px/m: a 1-px dark line); the basket grows only by the same width, not by the factor
THICK_R = 0.016                # m, radius up to which a vertex counts as shaft / handle (the factor applies to it, beyond it the radius only grows by the same amount)
ACTIONS = None                 # None = every action with uo_action, or a list of action names

rig = bpy.data.objects["UO_Rig"]
sc = bpy.context.scene
src = [o for o in bpy.context.selected_objects if o.type == "MESH"]
if not src:
    raise RuntimeError("select the pole first (after uo_orient_weapon.py)")
src = src[0]
if THICK != 1.0:                                       # fatter shaft and handle, the basket moved out by the same amount (pole axis = the Z axis)
    for v in src.data.vertices:
        r = math.hypot(v.co.x, v.co.y)
        if r > 1e-9:
            r2 = r * THICK if r <= THICK_R else THICK_R * THICK + (r - THICK_R)
            v.co.x *= r2 / r; v.co.y *= r2 / r
z_top = max(v.co.z for v in src.data.vertices)          # object space == world here (uo_orient_weapon applies the transform)
if rig.mode != "OBJECT":
    bpy.ops.object.mode_set(mode="OBJECT")
rig.data.pose_position = "REST"
bpy.context.view_layer.update()


def fist_rest(side):
    h = rig.matrix_world @ rig.data.bones["hand." + side].matrix_local
    return h @ Vector((FIST[0] * (1 if side == "R" else -1), FIST[1], FIST[2]))


# --- the poles (rest: upright, the grip point on the fist) ---
coll = src.users_collection[0]
polebones = {}
for side in HANDS:
    ob = src.copy(); ob.data = src.data.copy(); ob.name = "pole_" + side; ob.data.name = "pole_" + side
    coll.objects.link(ob)
    ob.matrix_world = Matrix.Translation(fist_rest(side) - Vector((0, 0, z_top - HOLD)))
    polebones[side] = ob
bpy.data.objects.remove(src, do_unlink=True)

# --- bones ---
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode="EDIT")
rest = {}
for side in HANDS:
    n = "pole." + side
    if n in rig.data.edit_bones:
        rig.data.edit_bones.remove(rig.data.edit_bones[n])
    eb = rig.data.edit_bones.new(n)
    eb.parent = None
    M = Matrix.Translation(fist_rest(side)) @ Matrix.Rotation(math.radians(90), 4, "X")      # bone Y axis = world +Z
    eb.length = 0.12; eb.matrix = M
    rest[side] = M
bpy.ops.object.mode_set(mode="OBJECT")
for side in HANDS:
    b = rig.data.bones["pole." + side]
    b.inherit_scale = "NONE"; b.use_deform = True
    rig.pose.bones["pole." + side].rotation_mode = "QUATERNION"

# --- keys ---
rig.data.pose_position = "POSE"
keep_action = rig.animation_data.action
acts = [a for a in bpy.data.actions if "uo_action" in a and (ACTIONS is None or a.name in ACTIONS)]


def arm_angles(side, ref=None):
    """(fore-aft, sideways) swing of the arm in degrees: forward / outward positive; shoulder -> wrist"""
    sh = rig.matrix_world @ rig.pose.bones["upper_arm." + side].head
    wr = rig.matrix_world @ rig.pose.bones["hand." + side].head
    out = -1.0 if side == "R" else 1.0
    drop = max(sh.z - wr.z, 1e-3)
    return math.degrees(math.atan2(sh.y - wr.y, drop)), math.degrees(math.atan2(out * (wr.x - sh.x), drop))


def pose_at(act, frame):
    rig.animation_data.action = act
    sc.frame_set(frame)
    bpy.context.view_layer.update()


ref_act = bpy.data.actions[REF_ACTION]
ref = {}
pose_at(ref_act, 1)
for side in HANDS:
    ref[side] = arm_angles(side)

for side in HANDS:
    pb = rig.pose.bones["pole." + side]
    Mr = rest[side]; p0 = fist_rest(side)
    n = 0
    for act in acts:
        prev = None
        for i in range(int(act["uo_frames"])):
            fr = 1 + 3 * i
            pose_at(act, fr)
            H = rig.matrix_world @ rig.pose.bones["hand." + side].matrix
            g = H @ Vector((FIST[0] * (1 if side == "R" else -1), FIST[1], FIST[2]))
            fa, lat = arm_angles(side)
            back = BASE_BACK - SWING_GAIN * (fa - ref[side][0])                              # spike backwards when the arm swings back
            lat_t = max(-LATERAL_MAX, min(LATERAL_MAX, LATERAL_BASE + LATERAL_GAIN * (lat - ref[side][1])))
            out = -1.0 if side == "R" else 1.0
            s = Vector((out * math.sin(math.radians(lat_t)), math.tan(math.radians(back)), -1.0)).normalized()   # spike direction
            a = -s                                                                            # handle up
            D = Matrix.Translation(g) @ Vector((0, 0, 1)).rotation_difference(a).to_matrix().to_4x4() @ Matrix.Translation(-p0)
            B = Mr.inverted() @ D @ Mr                                                        # basis of a root bone
            loc, q, _ = B.decompose()
            if prev is not None and q.dot(prev) < 0:
                q = -q
            prev = q.copy()
            rig.animation_data.action = act
            pb.rotation_quaternion = q; pb.location = loc
            pb.keyframe_insert("location", frame=fr, group=pb.name)
            pb.keyframe_insert("rotation_quaternion", frame=fr, group=pb.name)
            n += 1
    print("uo_hand_pole: %s keyed on %d poses (%d actions)" % (pb.name, n, len(acts)))
rig.animation_data.action = keep_action
rig.data.pose_position = "REST"
for ob in polebones.values():
    ob.select_set(True)
print("uo_hand_pole: poles %s, fist at rest %s" % (list(polebones), {s: tuple(round(x, 3) for x in fist_rest(s)) for s in HANDS}))
