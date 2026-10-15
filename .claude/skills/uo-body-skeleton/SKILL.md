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
- **Head rotation stays smooth in time:** never fit it to silhouettes without a smoothness term (a 10-26° zigzag made rigid helmets jump).
- Shoulders −1 cm, arms ×0.95; do not narrow further.
- The sprites' self-shadow (s=0.4) is postponed; our render has none.
