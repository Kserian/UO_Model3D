# Horn (instrument) for the right and the left hand

Recipes for a horn as two `.vd` files, right and left hand (35 actions x 5 directions, 1050 frames each). The rendered `.vd` files are not kept in the repo; build them with the commands below. Made from one free glTF model of a decorated war horn (`horn.glb`, 37 MB, **not in the repo**: kept in `models/horn.glb` (outside the repo) when re-running; record the author's licence when it is known).

Rebuild: `python pipeline/uo_make_item.py model/items/horn/horn_R.json --out OUT --vd` (and `horn_L.json`; `--vd` writes `OUT/render/clothing.vd`).

- Right hand: part `weapon1h` (bone `weapon1h.R`, motion calibrated on 13 original 1H weapons). QA: inside the body 4.3 % (worst: area spell), deepest 97 mm.
- Left hand: part `weapon.L` (grip of `weapon1h.R` mirrored onto `hand.L`, rigid on the hand: no original left-hand 1H item to calibrate on). QA: inside 3.8 %, deepest 88 mm.
- The bell points up, the mouthpiece sits in the hand; length 0.6 m (`"tip": "+x"` because `auto` cannot choose on a thin shell).
