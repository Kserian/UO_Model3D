Lute (Meshy glb from the user, not in the repo: put it at `models/lute.glb`) as a 1H weapon. Different poses per action = several items (recipes `lute_*.json`), each rendered into one OUT_DIR
(`run_render_headless.py item.blend OUT "LAYER='clothing'" "ONLY=[...]"`; runs add up into one .vd). Build: `python pipeline/uo_make_item.py lute_X.json --out DIR --no-qa`.
Each pose was picked by `pipeline/item_collision.py` (share of the lute inside the body, not counting the grip) over several candidates (`uo_place_carry.py`: AXIS / OUT / VERT / ELEV / SHIFT / SIDE / LIE / CLASS).

| item | actions | pose |
|---|---|---|
| carry | 00-03 | horizontal beside the body, headstock forward, strings out, the neck through the palm (no offset: the lute stays in the hand in every frame), rigid on hand.R |
| stand | 04 | across the belly, palms of both hands on the neck, 18 deg up; render with `HAND_OVER=0.2` (the right hand on top of the neck) |
| fid1, fid2 | 05, 06 | the same, 1 / 2 px higher, bound to the pelvis (the arms swing, the lute stays) |
| eat | 34 | like fid1 (the lute stays at the belly while the hand goes to the mouth) |
| m23, m24, m25 | 23, 24, 25 | mounted: like stand, 23/24 closer to the torso and towards the left hand, 24 pitched 8 deg down, 25 higher and towards the right hand |
| d21, d22 | 21, 22 | in the hand, lying beside the body along its long axis (`LIE`, `SIDE`), strings up; 22: bowl turned towards the left hand (`BOXTO`) |
| h07 | 07, 15, 20 | 1H line, tilted out 40 deg and more upright, rigid on hand.R |
| h26, h30, h33 | 26, 30, 33 | explicit axis per action (measured), rigid on hand.R; 26: axis chosen from 32 candidates so that the bowl is on the outer side of the hand in (nearly) every frame (`item_collision.py --outward`) |
| sp | 16, 17 | bound to forearm.R (no turning with the wrist), headstock up and out |
| handrigid | 08-14, 18, 19, 27-29, 31, 32 | 1h grip (butt -0.65), rigid on hand.R |

Arms on top of the lute (04, 05, 06, 22, 24, 25): render with `HAND_OVER=0.3 HAND_OVER_GROW=1 "HAND_OVER_PARTS=('hand','forearm','upper_arm')"`.
Render settings: `OWN_PARTS_NEVER_HIDE=False TORSO_HIDE_MARGIN=0.005 HOLDOUT_MARGIN=0.003` (recipe `weapon.occlude`).
