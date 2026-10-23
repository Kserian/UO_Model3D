# Cape on two clasps (cloth simulation)

`Cape_stand_walk_run_mountedrun_slash.vd`: 5 actions x 5 directions (165 frames): 04 stand, 00 walk (unarmed), 02 run (unarmed), 24 mounted run, 09 attack 1H slash. Made from one free glTF model
(`Meshy_AI_Medieval_Cape_Cloak`, 323k vertices, **not in the repo**: keep it in `models/cape.glb`; record the licence of the model when it is known).

Rebuild: `python pipeline/uo_make_cape.py model/items/cape/cape.json --out OUT --vd` (add `--all` for all 35 actions, about an hour; `--preview` = contact sheet with the body, `--no-sim` = no simulation).

- Side with the clasps and the folds that run down from them faces OUT, the middle of the cape lies on the back; scale 0.586 (clasps 0.34 m apart on the shoulders), leaned 5 deg (the top towards the front, the hem back).
- Only the two clasp patches are pinned (75 vertices); the rest is a Blender cloth (0.3 kg per vertex, tension / compression 1000, shear 500, bending 10, 16 substeps) that hangs, swings with the body and collides with the body and, riding, with the horse proxy. Settings: header of `pipeline/uo_cape_sim.py`.
- The clasps sit 17 cm behind the middle of the body (the shoulder blades reach y = 0.127 m): hanging straight from clasps on the skin the cape would lie on the shoulder blades (measured: the heavy cloth was pressed onto them and stretched, edges up to 8x in the walk), so it hangs 1-3 cm clear of the back.
- QA (`pipeline/uo_cape_sim.py` result against the posed body, before the renderer's `BODY_GAP`): stand / mounted run 0 vertices inside the body; walk 1 of 9494; run up to 45; slash up to 518 (the foot and the hand swing through the cloth in 1/8 s: Blender's cloth tunnels; the renderer pushes them out of arms, hands, legs and head, 6 mm).
- The chest hides the part of the cape that is more than 12 cm behind it (`uo_behind_torso`), the arms, hands, legs and head hide it where they are in front; nothing else cuts it.
