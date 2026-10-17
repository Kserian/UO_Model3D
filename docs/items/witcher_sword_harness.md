# Witcher sword harness (recipe `witcher_sword_harness.json`)

Source: `sword_back_harness_-_the_witcher.glb` (Sketchfab model, 41 meshes all named `defaultMaterial[.NNN]`, 53 MB; kept outside the repo, licence/attribution not recorded yet).
Run: put the file in `models/`, then `python pipeline/uo_make_item.py docs/items/witcher_sword_harness.json --out DIR --preview` (~70 s fit + preview; `--vd` adds the 35 actions).

Meshes (index = order of `uo_make_item.py --list`):

| meshes | what | in the recipe |
|---|---|---|
| 0 | mannequin shirt (reference, fitted to the body) | `reference` |
| 1, 5, 6 | shoulder strap, side loop | `straps` (harness, `widen` 7 cm: the straps are ~3 cm = 1 px in the render; `skin_wrap` 8 mm) |
| 2-4, 7-10, 14-16 | ring, buckles, rivets | `hardware` (harness, `skin_wrap` 8 mm) |
| 17, 21-25 | sword scabbard, binding bands, tip | `sheath` (rigid, `thicken` 8.5 cm) |
| 18, 19 | sword grip and horn pommel | `hilt` (rigid, `thicken` 7 cm) |
| 20, 26, 27 | scabbard throat clasp, ties | `fittings` (rigid) |
| 28-31 | knife on the back (grip, horn pommel, sheath) | removed |
| 32-40 | knife on the chest (sheath and its small parts) | removed |
| 11-13 | cloth wraps tying the back knife to the scabbard | removed |

Result on the body (stand, attack): `item_qa` mean inside body 1.7%, deepest 62 mm (the scabbard on the back; the render pushes it out), stand-off p90 24 cm (the sword itself).
Seen edge-on the scabbard is a narrow line (flat model, 36 px/m).

Straps and hardware: the fit pushes a harness 1.5 cm off the skin and the mannequin's shirt adds more, so the straps stood 3.0 cm (median, p90 5 cm) off the skin. `skin_wrap` lays them on the skin of the rest pose (8 mm, thickness kept) and binds them again to the weights of the skin under each vertex (`SMOOTH` 0): median height over the skin 3.0 -> 1.1 cm in stand, walk, attack and spell (p90 1.4-2.2 cm). Left over: the loop under the arm and the shoulder strap lie 2 mm or more in the arm skin in 4-11 % of the vertices; the renderer pushes items out of arms (`BODY_GAP`), not out of the torso (chest: 0 % in stand, 5 % in an attack).
