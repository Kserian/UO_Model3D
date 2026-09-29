"""numpy forward kinematics matching Blender pose bones (quaternion rotation, location, full inherit)"""
import numpy as np

def qmat(q):
    w, x, y, z = q / np.linalg.norm(q)
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
                     [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
                     [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])

def basis(loc, rot3, scale=None):
    M = np.eye(4); M[:3, :3] = rot3 if scale is None else rot3 * scale; M[:3, 3] = loc
    return M

def pose_mats(R, parent, bases):
    """R (B,4,4) rest (armature space), parent idx (B,), bases (B,4,4) -> pose matrices (B,4,4) armature space"""
    B = len(R); P = np.zeros((B, 4, 4)); Rinv = np.linalg.inv(R)
    for b in range(B):                        # bones are ordered parents first
        p = parent[b]
        P[b] = (R[b] if p < 0 else P[p] @ Rinv[p] @ R[b]) @ bases[b]
    return P

def rig_world(d):
    a = -d * np.pi / 4; c, s = np.cos(a), np.sin(a)
    M = np.eye(4); M[:2, :2] = [[c, -s], [s, c]]
    return M

def skin_mats(R, parent, bases, d, Brel):
    P = pose_mats(R, parent, bases)
    return rig_world(d) @ P @ np.linalg.inv(R) @ Brel
