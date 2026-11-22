# Ribbon medal (neck, hangs between the breasts, static on the body)

`Medal_walk_run_attack1h.vd`: actions 00 walk, 02 run, 09 attack 1H slash (5 directions); other actions: `--vd` without `--actions` (all 35, minutes).

Source: a Meshy-made glTF (`ribbon medal`, the user's file, **not in the repo**; check the licence). A flat loop of ribbon of 1.9 m does not fit a body, so `pipeline/make_medal_necklace.py` rebuilds it in body coordinates:
- the medal (disc + rim + ring: the non-red faces of the file) is kept, scaled to 9 cm and draped on the skin of the sternum (thickness kept, 3 mm off the skin, skin line smoothed over the mesh),
- the ribbon is a closed 3.2 cm strip (3 mm thick) from the ring in a V up the chest, over the collar bones and the sides of the neck, round the nape; every point snapped to the skin (the body without the head, rest pose); the ribbon colour is painted into the texture (`--ribbon-rgb`, default dark red).

Rebuild (the .glb is made in a scratch folder):
```
python pipeline/make_medal_necklace.py MEDAL.glb medal_body.glb      # options: --medal-d, --ribbon-w, --ring-z, --gap, --ribbon-rgb
python pipeline/uo_make_item.py model/items/medal/medal.json --out OUT --vd --actions 00_walk_unarmed,02_run_unarmed,09_attack_1h_slash
```
The recipe (kind `vest`, `AUTOFIT` / `FIT` / `DENSIFY` off, `PART` all, `props` uo_behind_torso + uo_no_body_gap: the torso hides the necklace where it is behind it, e.g. the medal seen from the back): skin weights of the skin under each vertex, so the necklace follows the skin of the chest, shoulders and neck.

Measured (`pipeline/item_skin_gap.py`, posed body, walk / run / attack / spells / die): whole necklace median 3.7 mm off the skin (range 3.5-5.3 over all frames); rigid on the `chest` bone it had gone 57 mm into the skin in the attack. The medal alone: back 5 mm off the skin, constant over all actions (range 0.5 mm). Left: 3 % of the ribbon vertices inside the skin of the neck-shoulder valley (deepest 28 mm in the attack; the render keeps the necklace out of arms, hands and head, not out of the torso).
At 36 px/m the ribbon is about 1 px wide and the grey medal 3 px: it reads on the chest in the front view only.
