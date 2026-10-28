# War drum (geometric) worn on the chest

`Drum_chest.vd`: all 35 actions x 5 directions, rigid on the bone `chest`. A geometric drum (`drum.glb`, made by `pipeline/make_drum_model.py`: shell, two heads, two hoops, a red band; 28 cm across, 22 cm deep; no strap).

Rebuild: `python pipeline/make_drum_model.py model/items/drum/drum.glb`, then `python pipeline/uo_make_item.py model/items/drum/drum.json --out OUT --vd` (~20 min; `--preview` alone gives `preview.png`, do not give both).

Recipe `"rigid": {"part": "front", "centre": [-0.02, -0.32, 1.325], "tilt": 0, "yaw": 90}`: rest-pose centre of the drum (m), heads to the sides (`yaw` 90: axis across the body), its back edge ~1 cm in front of the skin of the chest (the search moves it forward until the torso is clear by 1 cm).

Why this place (measured on the 578 frames of the 35 actions): the drum is a rigid body that every arm and leg of the 35 actions has to pass; per placement the share of frames with at least 3 skin vertices inside the drum was counted (mean over actions, so a long walk does not outweigh a short bite).

| Placement (Ø 28 cm, 22 cm deep, on `chest`) | legs | arms/hands |
|---|---|---|
| belly, z 1.00 m, heads forward | 72 % | 5 % |
| z 1.15 m, heads forward | 18 % | 15 % |
| z 1.25 m, heads forward | 5 % | 22 % |
| **z 1.325 m, heads to the sides (used)** | **1.8 %** | **21 %** |
| z 1.30 m, heads forward | 2.2 % | 22 % |

Lower is worse for the legs (thighs come up in walk and run), higher is worse for the arms; the least of both is at 1.30-1.35 m (under the chin, head 0 %). The rest of the arm share is hands going to the chest (bow, crossbow, salute, eating, two-hand blows), which no front item avoids. Heads to the sides were slightly better than forward (23 % vs 24 % in total).
`item_qa.py` of the finished item: inside the body 1.1 % of the vertices (worst: area spell), deepest 90 mm.
Not checked: the horse in the mounted actions (23-29), a drumming animation (the hands do not strike the drum), `test_items` baselines (the item is not a replica of an original).
