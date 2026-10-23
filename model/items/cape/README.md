# Cape on two clasps (cloth simulation)

`Cape_stand_walk_run_mountedrun_slash.vd`: 5 actions x 5 directions (165 frames): 04 stand, 00 walk (unarmed), 02 run (unarmed), 24 mounted run, 09 attack 1H slash. Made from one free glTF model
(`Meshy_AI_Medieval_Cape_Cloak`, 323k vertices, **not in the repo**: keep it in `models/cape.glb`; record the licence of the model when it is known).

Rebuild: `python pipeline/uo_make_cape.py model/items/cape/cape.json --out OUT --vd` (add `--all` for all 35 actions, about an hour; `--preview` = contact sheet with the body, `--no-sim` = no simulation).

- Side with the clasps and the folds that run down from them faces OUT, the middle of the cape lies on the back; scale 0.586 (clasps 0.34 m apart on the shoulders), leaned 5 deg (the top towards the front, the hem back).
- Only the two clasp patches are pinned (75 vertices); the rest is a Blender cloth (0.3 kg per vertex, tension / compression 1000, shear 500, bending 10, 16 substeps) that hangs, swings with the body and collides with the body and, riding, with the horse. Settings: header of `pipeline/uo_cape_sim.py`.
- Gravity is tilted towards the back of the character (`lean` 5 deg standing and fighting, x1.6 walking, x3.2 running, `lean_riding` 55 deg): the cape hangs OFF the back, trails in a run and streams over the croup in a gallop, instead of lying flat on the back.
- Riding: the cape would start inside the horse (its croup is right behind the rider), so it starts swung out to the back above the horse (`mount_start` 60 deg) and falls on it; the collider is the horse proxy of the first frame carried by the rider's pelvis (a proxy per frame, shown in turn, threw the cloth out of the next one: edges up to 10 x longer, the cape a stretched cone).
- The clasps sit 17 cm behind the middle of the body (the shoulder blades reach y = 0.127 m): hanging from clasps on the skin of the shoulder top the heavy cloth lay on the shoulder blades, so it hangs 1-3 cm clear of the back.
- QA (cloth against the posed body, before the renderer's `BODY_GAP`): vertices inside the body in the worst frame: stand 0, walk 0, run 0, mounted run 0, slash 315 of 9494 (the foot and the hand swing through the cloth in 1/8 s: Blender's cloth tunnels there; the renderer pushes them out of arms, hands, legs and head, 6 mm). Stretch of the edges (current / rest length, worst frame): walk p99 1.03, run 1.06, stand 1.01, mounted run 1.14, slash 1.44 with single edges up to 7.6 x where a limb caught the cloth.
- The chest hides the part of the cape that is more than 12 cm behind it (`uo_behind_torso`), the arms, hands, legs and head hide it where they are in front; nothing else cuts it.
