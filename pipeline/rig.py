"""Blender armature matching the fitted skeleton + conversion of fitted poses to pose-bone rotations."""
import numpy as np
import bpy
from mathutils import Matrix, Vector, Quaternion
from body import JI, JOINTS, ARM_REST_ANGLE

# joint -> (bone name, tail joint or callable, parent bone, align-roll Z vector)
FWD = (0.0, -1.0, 0.0)
UP = (0.0, 0.0, 1.0)


def bone_defs(S, P):
    S = {k: np.asarray(v, np.float64) for k, v in S.items()}
    sa, ca = np.sin(ARM_REST_ANGLE), np.cos(ARM_REST_ANGLE)
    J = lambda n: P[JI[n]]
    head_top = J("head") + np.array([0, 0, S["head_c"][2] + S["head_r"][2]])
    defs = [
        # name, joint, head, tail, parent, roll_z
        ("pelvis", "pelvis", J("pelvis"), J("spine"), None, FWD),
        ("spine", "spine", J("spine"), J("chest"), "pelvis", FWD),
        ("chest", "chest", J("chest"), J("neck"), "spine", FWD),
        ("neck", "neck", J("neck"), J("head"), "chest", FWD),
        ("head", "head", J("head"), head_top, "neck", FWD),
    ]
    for side, sx in (("L", 1), ("R", -1)):
        d = np.array([sx * sa, 0, -ca])
        defs += [
            ("upper_arm." + side, "shoulder." + side, J("shoulder." + side), J("elbow." + side), "chest", FWD),
            ("forearm." + side, "elbow." + side, J("elbow." + side), J("wrist." + side), "upper_arm." + side, FWD),
            ("hand." + side, "wrist." + side, J("wrist." + side), J("wrist." + side) + d * S["hand"], "forearm." + side, FWD),
            ("thigh." + side, "hip." + side, J("hip." + side), J("knee." + side), "pelvis", FWD),
            ("shin." + side, "knee." + side, J("knee." + side), J("ankle." + side), "thigh." + side, FWD),
            ("foot." + side, "ankle." + side, J("ankle." + side),
             J("ankle." + side) + np.array([0, -S["foot_len"] + S["heel_y"], -S["ankle_h"] + S["foot_r"][1]]),
             "shin." + side, UP),
        ]
    return defs


def build_armature(S, P, name="UO_Rig"):
    arm = bpy.data.armatures.new(name)
    ob = bpy.data.objects.new(name, arm)
    bpy.context.scene.collection.objects.link(ob)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    defs = bone_defs(S, P)
    for bname, joint, h, t, parent, rz in defs:
        eb = arm.edit_bones.new(bname)
        eb.head = Vector(h)
        eb.tail = Vector(t)
        eb.align_roll(Vector(rz))
        if parent:
            eb.parent = arm.edit_bones[parent]
            eb.use_connect = bool(np.allclose(arm.edit_bones[parent].tail, eb.head, atol=1e-5))
    bpy.ops.object.mode_set(mode="OBJECT")
    arm.display_type = "OCTAHEDRAL"
    ob.show_in_front = True
    return ob, {b[0]: b[1] for b in defs}


def rodrigues_np(r):
    th = np.linalg.norm(r)
    if th < 1e-9:
        return np.eye(3)
    k = r / th
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + np.sin(th) * K + (1 - np.cos(th)) * K @ K


def apply_pose(arm_ob, bone_joint, pose_rot, trans):
    """pose_rot: (NJ,3) axis-angle local rotations in world-aligned rest frames; trans: root translation."""
    for pb in arm_ob.pose.bones:
        if pb.name not in bone_joint:          # helper bones (clavicles): rest unless set by the caller
            pb.rotation_mode = "QUATERNION"
            pb.rotation_quaternion = (1, 0, 0, 0)
            pb.location = (0, 0, 0)
            continue
        j = JI[bone_joint[pb.name]]
        B = np.array(pb.bone.matrix_local.to_3x3())
        L = B.T @ rodrigues_np(np.asarray(pose_rot[j])) @ B
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = Matrix(L.tolist()).to_quaternion()
        if pb.parent is None:
            pb.location = Vector((B.T @ np.asarray(trans)).tolist())
        else:
            pb.location = (0, 0, 0)
