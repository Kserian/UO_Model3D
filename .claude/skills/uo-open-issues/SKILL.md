---
name: uo-open-issues
description: Open issues of UO_Model3D (slots, robe, cloak, pauldrons, body 401, glb/fbx) and what NOT to do. Use when planning work or unsure whether a change is allowed.
---

**Do not:** per-frame corrections, further tuning of `test_items` replicas, further body silhouette fitting (pose keys change only through `pose_natural_fit.py`: natural motion first, silhouette not worse), changes to light direction/ambient, AO or ground shadow.

**Open:**
- Robe physics is calibrated on one robe (469), checked on 447 and 970; no kilt test. Cloak: one real model (Meshy cape, 2026-10-22), moved by `uo_cloak_motion.py` (angles of the original 468; the cloth solver `uo_cloth_sim.py` was tried and rejected); riding is judged by eye (no original sprite of a cape on a horse to measure against); `test_cloak.py` still tests the old swing replica.
- Slots `waist`, `vest` untested on a real model; missing Earrings, Ring, Bracelet, Talisman, Backpack (unit detection assumes 0.15-3 m) and a single slot table.
- Pauldrons in one mesh with the torso stretch in spells; 3-4% of armour vertices end up inside the body in motion (`item_qa.py`); weight variants did not help.
- First real free model (e.g. Curuata's hair, CC BY 4.0, https://sketchfab.com/3d-models/hair-cc7e804cc15340db92d9464b32f71a2c): the user adds the glTF to the repo; record the attribution.
- Body 401 (female) in `anim.mul` ≈ copy of the male; check in game before working on it.
- `.glb`/`.fbx` are not in the repo: `pipeline/export.py --blend model/UO_Body_0x190.blend`.
