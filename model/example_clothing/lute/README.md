Lute (Meshy glb from the user, not in the repo: put it at `models/lute.glb`) as a 1H weapon. Different holds per action = four items rendered into one OUT_DIR
(`run_render_headless.py item.blend OUT "LAYER='clothing'" "ONLY=[...]"`; runs add up into one .vd):
- `lute_stand.json`: stand + fidgets (04-06): across the belly, both palms on the neck (axis through hand.R and hand.L of 04_stand), strings forward; rigid on hand.R
- `lute_mounted.json`: mounted walk/run/stand (23-25): the same, palms of 25_mounted_stand
- `lute_carry.json`: walk and run (00-03): horizontal beside the body, headstock forward, strings out
- `lute_fidget.json`: fidgets (05, 06): the stand pose bound to the pelvis (the arms swing, the lute stays at the belly)
- `lute_handrigid.json`: actions without a 1H weapon in the original (all other actions: 07-20, 26-34): the 1h grip, rigid on hand.R (the calibrated weapon bone turned the lute about its axis and off the hand in spells)
- `lute_dead.json`: deaths (21, 22): hung beside the body, bound to the pelvis, so it lies along the body
- `lute_1h.json`: the calibrated 1H weapon bone (not used in the final .vd: it turned the lute about its axis and off the hand), a 1H weapon on weapon1h.R held by the neck (butt -0.52)
Build each with `python pipeline/uo_make_item.py lute_X.json --out DIR --no-qa`.
`Lute_layer.vd`: all 35 actions from the four items (walk/run 00-03: carry, 04-06: stand, 23-25: mounted, the rest: 1h).
Render: `OWN_PARTS_NEVER_HIDE=False TORSO_HIDE_MARGIN=0.005 HOLDOUT_MARGIN=0.003` (recipe `weapon.occlude`: the body, torso and gripping hand hide the lute exactly where they are in front of it).
