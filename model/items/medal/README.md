# Ribbon medal (neck, hangs between the breasts, static on the body)

`Medal_walk_run_attack1h.vd`: actions 00 walk, 02 run, 09 attack 1H slash (5 directions); other actions: `--vd` without `--actions` (all 35, minutes).

Source: a Meshy-made glTF (`ribbon medal`, the user's file, **not in the repo**; check the licence). A flat loop of ribbon of 1.9 m does not fit a body, so `pipeline/make_medal_necklace.py` rebuilds it in body coordinates:
- the medal (disc, rim, recessed face and ring) is built procedurally, 17 cm and draped on the skin of the sternum (thickness kept, 3 mm off the skin, skin line smoothed over the mesh),
- the ribbon is a closed 6 cm strip (3.2 cm was 1 px at 36 px/m: a broken line in the sprites; recipe scene `uo_hide_erode` 2, `uo_outline` 1.0 = no dark rim: 0 is the darkest, 1 leaves the rim as it is) (3 mm thick, 12 mm off the skin: the posed skin of the neck and shoulders poked through a ribbon lying on it, `--ribbon-gap`) from the ring in a V up the chest, over the collar bones and the sides of the neck, round the nape; every point snapped to the skin (the body without the head, rest pose); the ribbon colour is painted into the texture (`--ribbon-rgb`, default dark red).

Rebuild (the .glb is made in a scratch folder):
```
python pipeline/make_medal_necklace.py MEDAL.glb medal_body.glb      # options: --medal-d, --ribbon-w, --ring-z, --gap, --ribbon-rgb
python pipeline/uo_make_item.py model/items/medal/medal.json --out OUT --vd --actions 00_walk_unarmed,02_run_unarmed,09_attack_1h_slash
```
The recipe (kind `vest`, `AUTOFIT` / `FIT` / `DENSIFY` off, `PART` all, `props` uo_behind_torso + uo_no_body_gap: the torso hides the necklace where it is behind it, e.g. the medal seen from the back): skin weights of the skin under each vertex, so the necklace follows the skin of the chest, shoulders and neck.

Weights: `"tune": {"uo_bind_item.py": {"MAP": "nearest"}}` (the default `under` took the head's weights for the ribbon at the base of the neck: 53 mm into the skin in the attack). Measured with ribbon 12 mm off the skin: inside the skin 0.3 %, deepest 14 mm, median 12.0 mm in every action (range 11.8-12.1). Earlier version (ribbon 3 mm off, `under`): (`pipeline/item_skin_gap.py`, posed body, walk / run / attack / spells / die): whole necklace median 3.7 mm off the skin (range 3.5-5.3 over all frames); rigid on the `chest` bone it had gone 57 mm into the skin in the attack. The medal alone: back 5 mm off the skin, constant over all actions (range 0.5 mm). Left: 3 % of the ribbon vertices inside the skin of the neck-shoulder valley (deepest 28 mm in the attack; the render keeps the necklace out of arms, hands and head, not out of the torso).
At 36 px/m the ribbon is about 1 px wide and the grey medal 3 px: it reads on the chest in the front view only.

## Medal cut in half (fixed)
The medal skinned like the skin under it folded up when the spine bent (its lower half is on spine / pelvis weights, the upper on the chest): in the walk the lower half of the disc was squashed into a flat sliver, so the sprite showed half a disc. Now the medal and the lower V (`"rigid_zone": {"below": 1.41, "xmax": 0.08, "bone": "chest"}` in `medal.json`: 1952 vertices 100 % on `chest`) are rigid; the rest of the ribbon follows the skin. The medal is built procedurally in `make_medal_necklace.py` (disc, rim, recessed face, ring; flat colour patches painted into flat spots of the normal map) because the file's own medal had red patches of the ribbon atlas on its faces and smooth shading that made it a lump. Medal 17 cm, face brighter than the rim, `METAL` off (no specular: the rim stays darker than the face). Measured: lower medal 17-24 mm off the skin in every action, inside the skin 0-1 %.

## Round cord, alignment (work in progress)
The ribbon is modelled as a round cord of 4.5 cm diameter (`--ribbon-w`): a flat strip changed its projected width with the angle it was seen at (edge-on on the shoulders it was a broken 1-px line); the cord has the same width from every side (flicker of the red pixel count between frames 0.24 -> 0.13). The path lies lower on the shoulders (z 1.49-1.51) so that it does not cover the face. `render_uo_layer.py` got `uo_align` (scene property, px): per frame the model body is moved by whole pixels onto the original body in a circle round the neck (shifts.json next to the frames); with the model's silhouette this was 0 px for 127 of 135 frames of walk / run / attack.
`item_gif.py --body-color R,G,B` tints the grey original body (a GIF with the skin colour of the game).
