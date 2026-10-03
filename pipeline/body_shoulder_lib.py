"""Parametric edit of the rest mesh `UO_Body`: shoulder width and arm thickness (used by body_shoulder_apply.py and the sweep in docs/qa/shoulder_arm_sweep.json).

edit(co0, W, gi, bones, shift, arm, fore, arm_y, fore_y):
  shift   metres each shoulder moves toward the midline (smooth in |x| 0.10..0.22 m and z 1.20..1.42 m, off again above 1.50..1.56 m: deltoid and upper-arm top)
  arm     radial scale of upper arm (weights upper_arm + upper_arm_twist) about the bone axis; fore = same for the forearm (default = arm)
  arm_y   extra scale of the front-back thickness only (rest pose, axis y); fore_y = same for the forearm (default = arm_y)
co0 (N,3) rest coordinates, W (N, groups) vertex weights, gi group name -> column, bones name -> (head, tail) in rest pose.
"""
import numpy as np


def sstep(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t)


def weights(me, ngroups):
    W = np.zeros((len(me.vertices), ngroups))
    for v in me.vertices:
        for g in v.groups:
            W[v.index, g.group] += g.weight
    return W


def edit(co0, W, gi, bones, shift=0.0, arm=1.0, fore=None, arm_y=1.0, fore_y=None, sz=(1.20, 1.42, 1.50, 1.56), sx=(0.10, 0.22)):
    co = co0.copy(); x = co0[:, 0]; z = co0[:, 2]
    fore = arm if fore is None else fore
    fore_y = arm_y if fore_y is None else fore_y
    if shift:
        G = sstep(abs(x), *sx) * sstep(z, sz[0], sz[1]) * (1 - sstep(z, sz[2], sz[3]))
        co[:, 0] -= np.sign(x) * shift * G
    for side in "LR":
        for b, tw, s, sy in (("upper_arm", "upper_arm_twist", arm, arm_y), ("forearm", "forearm_twist", fore, fore_y)):
            if s == 1.0 and sy == 1.0:
                continue
            w = W[:, gi[b + "." + side]] + W[:, gi[tw + "." + side]]
            h, t = bones[b + "." + side]
            ax = t - h
            p = h + np.clip(((co - h) @ ax) / (ax @ ax), 0, 1)[:, None] * ax
            co += (s - 1.0) * w[:, None] * (co - p)
            co[:, 1] += (sy - 1.0) * w * (co[:, 1] - p[:, 1])
    return co
