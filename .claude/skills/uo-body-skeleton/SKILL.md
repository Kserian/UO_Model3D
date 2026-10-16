---
name: uo-body-skeleton
description: Settled decisions about the body and rig (bones, fingers, weapon bones, robes/cloak, area spell action 17, head rotation, shoulders/arms, canvas). Use before changing the rig, poses, animation keys, proportions or silhouette fitting.
---

User decisions; do not change without a request.

- We develop UO_Model3D (not rebuild; silhouette limit ~0.88-0.90 IoU). Canvas `CANVAS` 256×256, anchor (128,192), 36 px/m.
- **No per-frame shape corrections** (v12): fix the body in the model. Do not fit the silhouette further (limit ~0.90).
- Rig: 19 UO bones + 30 finger bones (`rig_restore_fingers.py`) + 5 weapon/shield bones (`polearm.L`, `axe2h.L`, `bow.L`, `weapon1h.R`, `shield.L`; `rig_restore_weapons.py`, calibration `weapon_*.py`, `docs/qa/weapon_roll.md`). No twist, toe or cloth-chain bones. Hair is rigid on the head (`uo_bind_item.py`, `RIGID`). Earlier state: `b86c314`.
- Robe/skirt (`PART robe`/`skirt`): hang from the pelvis, legs push the cloth out; Blender cloth simulation `uo_cloth_sim.py` (target = leg hull from `cloth_lib.py`, no bone chains; `docs/qa/robe_physics.md`). Cloak `PART cloak`: per-action pitch (`cloak_pitch.json`).
- Area spell (action 17): arms symmetric (left = mirror of right), torso only tilts, no twist (`arm_sym_fit.py --torso upper`, `arm_mirror_action.py`; `docs/qa/elbow_spell.md`). Shared finger pose (curl 20-35°, hand scale 1.045). Do not return to the old pose.
- Arms (and part of pelvis/legs) were fitted per frame from silhouettes in ~150 frames (`arm_joint_fit.py`, `docs/qa/arm_poses.md`).
- **Head rotation stays smooth in time:** never fit it to silhouettes without a smoothness term (a 10-26° zigzag made rigid helmets jump). Mounted walk / run (actions 23, 24): the rider is hidden by the horse, so `pose_natural_fit.py` also holds neck and head to the chest yaw of the mounted stand (HEAD_YAW_*; head turn of 23-30° had come from sprite noise). Other actions keep free head motion.
- **Natural motion with the same silhouettes (branch `model-fixing2`):** pose keys come from `pose_natural_fit.py` (numpy rig `pose_lib.py`, pixel-identical to Blender): smooth armature-space orientations, upper-arm twist near the stand pose while the arm hangs (more twist folds the MakeHuman shoulder), the shoulder joint does not slide on the chest (clavicles do not deform the skin: **no new clavicle location keys**; 49 frames keep old ones where the silhouette needs them), elbow a hinge; the silhouette is a constraint (no frame worse than before, `>= 2 px` errors not up). The head has one scale (1, 1, 0.942) in all refitted frames (17, 25 and 9/1 kept as before: arm symmetry / `test_canvas`). Weapon/shield bones keep their armature-space motion (fitted to the original weapons). Any new pose fitting must keep these priors; measure with `pose_naturalness.py` and `pose_lib.py qa`.
- Quaternion keys stay sign-continuous (`apply_pose_keys.py`): a flip spins the bone between keys in Blender playback.
- Shoulders −1 cm, arms ×0.95; do not narrow further.
- The sprites' self-shadow (s=0.4) is postponed; our render has none.
