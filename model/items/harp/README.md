# Harp (Celtic hand harp, strings removed) for the right hand, both hands when standing

`Harp_right_hand.vd`: all 35 actions x 5 directions (1050 frames).

Model: the user's glTF of a carved Celtic harp (Google Drive link given in the session, 44 MB, 300k vertices, 4096 px textures, **not in the repo**; **author and licence unknown: record them**). `pipeline/harp_prepare_model.py IN.glb harp.glb` makes `harp.glb` (2.2 MB, the file used here): the 20 string pieces are cut out (pale grey texture, longer than 0.4 m; the pale slivers left at the pins too), the thin arm of the V is turned upright on x = y = 0 (the side the harp is held by), 60k faces, 1024 px JPEG textures. The tuning pins' holes stay (not visible at 36 px/m). Matte (`METAL: false`), the colours of the model's own wood texture.

Rebuild: `python pipeline/uo_make_item.py model/items/harp/harp.json --out OUT --vd`.

- Size: 0.68 m high, 0.55 m wide (`HEIGHT` 0.68, `WIDEN` 1.25: the model is stretched along X so that the harp reaches the left hand, 0.5-0.6 m from the right one in the standing poses, without being taller than the torso); the shell is pushed out by `THICKEN` 1.9 cm (a 2 cm frame is under 1 px at 36 px/m).
- Held by the thin arm (the pillar) at half of its height in the right fist. Per action (all settings in `uo_harp.py`, the recipe's `"harp"` overrides them):
  - one hand (default): the pillar upright at the back, the rest of the harp (the sound box) forward; orientation = the chest's (no sword-like swinging); walking and running (`STEADY`: 0-3, 23, 24) = ONE orientation for the whole cycle, only the grip follows the hand.
  - walk, walk armed (`FLAT_WALK` 0, 1): tilted to the ground, the plane parallel to the floor (rolled 90 deg about the forward axis), turned 30-45 deg outward about the vertical so it clears the hip (picked automatically: 5-10 of 750 sample points in the body).
  - area spell, mounted 1H attack (`YAW_OUT` 17, 26): the usual hold (pillar upright, the rest forward), turned 12 deg about the axis of the held side (the pillar) so the sound box leans outward, towards the arm.
  - both deaths (`FLAT_DIE` 21, 22): held in the hand, lying flat (plane horizontal), the sound box pointing away from the body.
  - both hands (`TWO_HAND` 4, 5, 6, 25, 33, 34: stand, fidget 1+2, mounted stand, salute, eat): the pivot of the left fist 0-5 cm from the wood (outside it), the triangle faces the front (`FRONT_PLANE`), in stand and mounted stand the harp is ahead of the chest (`FRONT`: 23 / 28 cm), mounted stand like stand; in salute and eat the pillar stays within ~17 deg of the axis of the right fist (`FIST_FREE`: salute 7-24, eat 18-50 deg: the hand goes to the mouth), so it is really held. Per frame, smooth in time. The arms are the original animation's, only the harp moves.
- QA (`item_qa.py`): see the last build's `qa.json` (inside the body ~4 %, deepest ~95 mm).
