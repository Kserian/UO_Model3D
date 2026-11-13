---
name: uo-open-issues
description: Open issues of UO_Model3D (slots, robe, cloak, pauldrons, body 401, glb/fbx) and what NOT to do. Use when planning work or unsure whether a change is allowed.
---

**Do not:** per-frame corrections, further tuning of `test_items` replicas, further body silhouette fitting (pose keys change only through `pose_natural_fit.py`: natural motion first, silhouette not worse), changes to light direction/ambient, AO or ground shadow.

**Open:**
- Robe physics is calibrated on one robe (469), checked on 447 and 970; no kilt test. Cloak has no side waving and no real-model test.
- Slots `waist`, `vest` untested on a real model; missing Earrings, Ring, Bracelet, Talisman, Backpack (unit detection assumes 0.15-3 m) and a single slot table.
- Pauldrons in one mesh with the torso stretch in spells; 3-4% of armour vertices end up inside the body in motion (`item_qa.py`); weight variants did not help.
- First real free model (e.g. Curuata's hair, CC BY 4.0, https://sketchfab.com/3d-models/hair-cc7e804cc15340db92d9464b32f71a2c): the user adds the glTF to the repo; record the attribution.
- Body 401 (female) in `anim.mul` ≈ copy of the male; check in game before working on it.
- `.glb`/`.fbx` are not in the repo: `pipeline/export.py --blend model/UO_Body_0x190.blend`.
- Back axes (`"rigid"` recipe, `back_axes.vd`, 2026-11-13): user reports (more to come): (1) action 09 attack 1H slash, dir 3 (frame 5/7) and action 14 attack 2H pierce, dir 3 (frame 6/7): the axes "escape" from the back (hub/handles stand off the torso, frame 5/7) - the chest bone swings away from the back surface there; check the gap per frame (item vs posed skin), maybe weight part of the rigid item on spine / pelvis; (1b) Walk (war), dir 3, frame 7/10: the axes sit asymmetrically (one side higher/shifted; the chest twists in the walk: check whether the model is mirrored by the pose, or the rigid item should follow spine too); (2) 98 mm deepest inside the body in 13_attack_2h_slash; (3) optional: cut the dark hub disc of the Meshy model.
