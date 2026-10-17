# Witcher sword harness (recipe `witcher_sword_harness.json`)

Source: `sword_back_harness_-_the_witcher.glb` (Sketchfab model, 41 meshes all named `defaultMaterial[.NNN]`, 53 MB; kept outside the repo, licence/attribution not recorded yet).
Run: put the file in `models/`, then `python pipeline/uo_make_item.py docs/items/witcher_sword_harness.json --out DIR --preview` (~70 s fit + preview; `--vd` adds the 35 actions).

Meshes (index = order of `uo_make_item.py --list`):

| meshes | what | in the recipe |
|---|---|---|
| 0 | mannequin shirt (reference, fitted to the body) | `reference` |
| 1, 5, 6 | shoulder strap, side loop | `straps` (harness, `widen` 7 cm: the straps are ~3 cm = 1 px in the render) |
| 2-4, 7-10, 14-16 | ring, buckles, rivets | `hardware` (harness) |
| 17, 21-25 | sword scabbard, binding bands, tip | `sheath` (rigid, `thicken` 8.5 cm) |
| 18, 19 | sword grip and horn pommel | `hilt` (rigid, `thicken` 7 cm) |
| 20, 26, 27 | scabbard throat clasp, ties | `fittings` (rigid) |
| 28-31 | knife on the back (grip, horn pommel, sheath) | removed |
| 32-40 | knife on the chest (sheath and its small parts) | removed |
| 11-13 | cloth wraps tying the back knife to the scabbard | removed |

Result on the body (stand, attack): `item_qa` mean inside body 1.7%, deepest 62 mm (the scabbard on the back; the render pushes it out), stand-off p90 24 cm (the sword itself).
Seen edge-on the scabbard is a narrow line (flat model, 36 px/m).
