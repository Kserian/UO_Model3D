Lute (Meshy glb from the user, not in the repo: put it at `models/lute.glb`) as a 1H weapon, one `Lute_layer.vd` (35 actions) from three renders into one OUT_DIR
(`run_render_headless.py item.blend OUT "LAYER='clothing'" "ONLY=[...]"`, runs add up):
- `lute_carry.json` -> `item.blend` (hangs beside the leg, strings out, rigid on hand.R): actions 00-06 (walk, run, stand, fidgets)
- `lute_mounted.json` (same pose taken from 25_mounted_stand): actions 23-25
- `lute_1h.json` (1H weapon on weapon1h.R, held by the neck, butt -0.52): all other actions
Build each with `python pipeline/uo_make_item.py lute_X.json --out DIR --no-qa`.
