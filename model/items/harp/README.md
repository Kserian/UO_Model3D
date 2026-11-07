# Harp (Celtic hand harp, strings removed) for the right hand, both hands when standing

`Harp_right_hand.vd`: all 35 actions x 5 directions (1050 frames).

Model: the user's glTF of a carved Celtic harp (Google Drive link given in the session, 44 MB, 300k vertices, 4096 px textures, **not in the repo**; **author and licence unknown: record them**). `pipeline/harp_prepare_model.py IN.glb harp.glb` makes `harp.glb` (2.2 MB, the file used here): the 20 string pieces are cut out (pale grey texture, longer than 0.4 m; the pale slivers left at the pins too), the thin arm of the V is turned upright on x = y = 0 (the side the harp is held by), 60k faces, 1024 px JPEG textures. The tuning pins' holes stay (not visible at 36 px/m). Matte (`METAL: false`), the colours of the model's own wood texture.

Rebuild: `python pipeline/uo_make_item.py model/items/harp/harp.json --out OUT --vd`.

- Size 0.56 m (a hand harp, not taller than the torso of the body), ~0.37 m wide; the shell is pushed out by `THICKEN` 1.9 cm (a 2 cm frame is under 1 px at 36 px/m).
- One hand (all other actions): held by the thin arm (the pillar) from behind, at half of its height, in the right hand: the pillar upright at the back, the rest of the harp (the sound box) pointing forward. The orientation is the chest's, so it follows a lean or a fall but does not swing about with the arm like a sword; in walking and running (`STEADY`: 0-3, 23, 24) it is ONE orientation for the whole cycle (the mean of the chest's), only the grip follows the hand: no swaying.
- Both hands touch the harp in stand (4), fidget_1/2 (5, 6), mounted_stand (25), salute (33), eat (34): `pipeline/uo_harp.py` turns the harp about the right grip (and slides it along the pillar) so that the pivot of the left fist is 0-6 cm from the wood, per frame, smooth in time, tilted 25-70 deg, away from the body. The arms are the original animation's, only the harp moves. `TWO_HAND` in the recipe (`"harp": {...}`) changes the list.
- QA (`item_qa.py`): inside the body 7.0 % (worst: stand, the two-hand pose), deepest 125 mm.
