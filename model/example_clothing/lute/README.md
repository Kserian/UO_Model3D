Lute (Meshy glb from the user, not in the repo: put it at `models/lute.glb`) as a 1H weapon. Different holds per action = four items rendered into one OUT_DIR
(`run_render_headless.py item.blend OUT "LAYER='clothing'" "ONLY=[...]"`; runs add up into one .vd):
- `lute_stand.json`: stand + fidgets (04-06): across the belly, both palms on the neck (axis through hand.R and hand.L of 04_stand), strings forward; rigid on hand.R
- `lute_mounted.json`: mounted walk/run/stand (23-25): the same, palms of 25_mounted_stand
- `lute_carry.json`: walk and run (00-03): horizontal beside the body, headstock forward, strings out
- `lute_1h.json`: every other action, a 1H weapon on weapon1h.R held by the neck (butt -0.52)
Build each with `python pipeline/uo_make_item.py lute_X.json --out DIR --no-qa`.
`Lute_layer.vd`: all 35 actions from the four items (walk/run 00-03: carry, 04-06: stand, 23-25: mounted, the rest: 1h).
