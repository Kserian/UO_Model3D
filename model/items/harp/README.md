# Harp (hand harp without strings) for the right hand, both hands when standing

`Harp_right_hand.vd`: all 35 actions x 5 directions (1050 frames). Own model, built from primitives by `pipeline/make_harp_model.py` (`harp.glb`, 93 KB, in the repo): a small wooden harp with no strings, matte (no highlights), one walnut brown with a faint grain. Size 0.52 m (a hand harp, not taller than the torso of the body), 0.45 m wide.

Rebuild: `python pipeline/uo_make_item.py model/items/harp/harp.json --out OUT --vd` (the glb: `python pipeline/make_harp_model.py model/items/harp/harp.glb`).

- Held by the pillar (the thin side) at half of its height in the right hand; in all moving actions it rides like a 1H weapon (it copies the calibrated motion of `weapon1h.R`).
- Both hands touch the harp in stand (4), fidget_1/2 (5, 6), mounted_stand (25), salute (33), eat (34): `pipeline/uo_harp.py` turns the harp about the right grip (and slides it a little along the pillar) so that the pivot of the left fist is 0-5.5 cm from the wood, per frame, smooth in time, tilted 20-60 deg, away from the body. The arms are the original animation's, only the harp moves. `TWO_HAND` in the recipe (`"harp": {...}`) changes the list.
- QA (`item_qa.py`): inside the body 6.8 % (worst: area spell), deepest 98 mm.
