Lute (Meshy glb from the user, not in the repo: put it at `models/lute.glb`) as a 1H weapon. Different poses per action = several items (recipes `lute_*.json`), each rendered into one OUT_DIR
(`run_render_headless.py item.blend OUT "LAYER='clothing'" "ONLY=[...]"`; runs add up into one .vd). Build: `python pipeline/uo_make_item.py lute_X.json --out DIR --no-qa`.
Each pose was picked by `pipeline/item_collision.py` (share of the lute inside the body, not counting the grip) over several candidates (`uo_place_carry.py`: AXIS / OUT / VERT / ELEV / SHIFT / SIDE / LIE / CLASS).

| item | actions | pose |
|---|---|---|
| carry | 00-03 | horizontal beside the body, headstock forward, strings out, the neck through the palm, 5 cm out, rigid on hand.R |
| stand | 04 | across the belly, palms of both hands on the neck, 18 deg up; render with `HAND_OVER=0.12 HAND_OVER_GROW=1` (the hands on top of the neck; fidgets 05, 06 also `HAND_OVER_SIDE='.R'`: only the right hand, the left one beside the headstock cut it) |
| fid1, fid2 | 05, 06 | the same, 1 / 2 px higher, bound to the pelvis (the arms swing, the lute stays) |
| eat | 34 | like fid1 (the lute stays at the belly while the hand goes to the mouth) |
| m23, m24, m25 | 23, 24, 25 | mounted: like stand (23: the neck through both palms of its own pose, so it points at the left hand); 24 is bound to the pelvis like the fidgets (the hands bounce in the run and turned a hand-bound lute into the chest; inside the body 11.4 -> 0.6%), 25 higher and towards the right hand |
| d21, d22 | 21, 22 | the neck through the palm in every frame, lying along the body's long axis (`LIE`), strings up; 21: held in the middle of the neck with the bowl towards the head (`FLIP`), which puts it on the far side of the body in every direction as the user drew it |
| h15 | 15 | like h07 without the outward tilt (bowl closer to the body), nothing inside the body |
| h07 | 07, 20 | 1H line, tilted out 40 deg and more upright, rigid on hand.R |
| h26, h30, h33 | 26, 30, 33 | explicit axis per action (measured), rigid on hand.R; 26: axis chosen from 32 candidates so that the bowl is on the outer side of the hand in (nearly) every frame (`item_collision.py --outward`) |
| sp | 16, 17 | bound to forearm.R (no turning with the wrist), headstock up and out |
| handrigid | 08-14, 18, 19, 27-29, 31, 32 | 1h grip (butt -0.65), rigid on hand.R |

Arms on top of the lute (04, 05, 06, 22, 24, 25): render with `HAND_OVER=0.3 HAND_OVER_GROW=1 "HAND_OVER_PARTS=('hand','forearm','upper_arm')"`.
Render settings: `OWN_PARTS_NEVER_HIDE=False TORSO_HIDE_MARGIN=0.005 HOLDOUT_MARGIN=0.003` (recipe `weapon.occlude`).
Mounted actions (23-25): render with `HORSE_HOLDOUT=False`. With the holdout the horse (its head / neck in front of the rider's belly) cut the neck of the lute and the top of the bowl out of the layer; the rider is drawn over the mount, so the lute is not hidden by it. 25 also `HAND_OVER=0.3 HAND_OVER_GROW=2 HAND_OVER_SIDE='.R'`.

Files in this folder:
- `Lute_poses.blend` (bpy 4.2): the body, the rig and every pose as an object `Lute_<item>` (the table above; `Lute_carry` is in the collection Clothing, the others in the collection `Lute_poses`, which is not rendered). Custom properties `uo_actions` and `uo_render_flags` say for which actions and with which extra render settings. `python pipeline/lute_select_pose.py Lute_poses.blend Lute_stand OUT.blend` moves one pose into Clothing.
- `render_lute.sh OUT_DIR`: the whole render, pose by pose (about 15 minutes), into one `OUT_DIR/clothing.vd`.
- `frames/`: the rendered PNG frames and `meta.json` of `Lute_layer.vd` (vdtool layout; `python vdtool/vdtool.py pack frames out.vd` packs them again).
- `Lute_layer.vd`: the result. The source model is `models/lute.glb` (Meshy, from the user); `lute_*.json`: the item recipes.
