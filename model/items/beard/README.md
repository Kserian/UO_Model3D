# Long wavy beard (layer 16, FacialHair)

`Beard_long_wavy.vd`: all 35 actions x 5 directions (1050 frames, 38 empty ones from behind where the beard is not visible), grey (R = G = B, the client dyes it with the item's hue), rigid on the head.

Source: a sculpt supplied by the user (1.48 M vertices, a closed "bag" of a beard with a moustache whose tips curl up; the file `beard.glb`, 88 MB, is **not in the repo**; record its licence / author when known). `beard_long_wavy.glb` here is the reduced, placed result (20 k vertices):

    python pipeline/uo_scale_remesh.py beard.glb model/items/beard/beard_long_wavy.glb --scale 0.23 --move 0 -0.226 1.525
    python pipeline/uo_make_item.py model/items/beard/beard_long_wavy.json --out OUT --vd      # all actions, ~17 min

- Size: the sculpt is 1.9 units tall; x0.23 = 0.44 m (the original long beard 801 is ~0.35 m, 11 px). Voxel remesh 3.5 mm keeps the lobes of the curls, the single strands (< 1 px = 2.7 cm) go.
- Fit to the face (measured on the original sprites, stand): the moustache arch of the sculpt sits at the mouth (z 1.68 m; original moustache 803 rows 92-93, goatee 800 rows 93-95), its back plane on the front of the face (y -0.226), tips of the moustache on the cheeks (z 1.74, the top of the original beard 801); profile: the beard sticks out 0-1 px in front of the chin like the original 801 (cols 94-98 vs 92-97).
- Placed by hand, not by `uo_autofit_item.py` (it has no idea of a beard and pushes a free-hanging one into the head): recipe `"prepare": {"AUTOFIT": false, "FIT": false}`.
- Render settings: `"scene": {"uo_head_hides": 1}` (the head hides what is behind it), `"behind_torso": true` (the neck / chest hide it from behind: dir 4 has 2 px instead of 39), `uo_min_piece` 0 (thin moustache tips), `BRIGHTNESS` 0.65 and `uo_contrast` 2.4 about 0.6: interior brightness 145-175 (original beard 131-175), std 17-27 (original 17-33).
- Not covered: the original beards also cover the cheeks / jaw up to the ear (801 rows 88-92); this sculpt starts at the moustache. A sideburn / cheek piece would have to be added to the model.
- Not tested in the game (hue, draw order against hair and helmet): make one tiledata item with layer 16 and the new animation id.
