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
- Back axes (`"rigid"` recipe, `back_axes.vd`, 2026-11-13/14). User reports: "escape" from the back in 09 attack 1H slash dir 3 (frame 5/7), 14 attack 2H pierce dir 3, 18 attack bow dir 1, odd drift in 21 die forward dir 4, asymmetric in walk (war) dir 3, should be more static in 34 eat/drink dir 4. MEASURED (do not repeat): chest bone rotation is within 2 deg (max 6) of the rotation of the back skin patch; stand-off profile of the prop from the torso skin changes by ~6 mm mean / 12 mm p90 / 30 mm worst (1 px = 28 mm); hub is 2-17 mm off the torso in every frame. Tried and rejected, all not better than plain chest: bone mixes (chest+spine / pelvis: p90 15-20 mm), a Kabsch fit of a skin patch (rotation 10-60 deg off, hub gaps up to 600 mm: the push chased an arm), an own `back_prop` bone keyed per frame by Levenberg-Marquardt on the stand-off profile / the skin-following motion (p90 mean 10.9-13.4 vs 12.0, back rotation worse: up to 16 deg). A rigid prop cannot follow a back that bends: what is left is sub-pixel to 1 px.
  Open: (3) 98 mm deepest inside the body in 13_attack_2h_slash (the renderer pushes arms out, not the torso); (4) optional: cut the dark hub disc of the Meshy model. Quality (done, per item scene in the recipe): `{"uo_samples": 2048, "uo_outline": 0.62, "uo_edge_smooth": 1, "uo_edge_floor": 30, "uo_despeckle": 45}`: softer outline, 1-px spikes dropped, no pure black rim, single dark pixels cleaned.
