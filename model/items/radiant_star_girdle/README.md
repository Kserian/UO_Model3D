# Radiant Star Girdle (a girdle with a skirt of silk panels, on the hips)

`Radiant_Star_Girdle.vd`: all 35 actions x 5 directions (1050 frames), layer `skirt`, made from one Meshy AI model (`Meshy_AI_Radiant_Star_Girdle_1022181159_texture.glb`, 47 MB, 265k vertices, textures 4096 px; **not in the repo**: keep it as `models/radiant_star_girdle.glb`, the folder is in `.gitignore`; record the licence when it is known).

Rebuild (about 10 min for the item and the cloth, ~15 min for the render):
`python pipeline/uo_make_item.py model/items/radiant_star_girdle/girdle.json --out OUT --vd`.
Rendering in several processes: give every process its own output folder (they share `_tmp.png` otherwise), then merge the `frames/` folders and run once more with `ONLY=["04_stand"]` to write the combined `.vd`.

What was decided (measured, see the commit messages and README section 3a):
- **On the hips, not too big.** The waistband (0.42 x 0.33 m at the model's scale) sits at z 1.0-1.1 m (`NUDGE` -0.25 m), `stretch` 0.87 x 0.85 narrows it to the hips (0.35 x 0.28 m) and `"prepare": {"FIT": false}` keeps the push-out fit from inflating the ring to 0.67 x 0.61 m. The hem ends above the ankles (`HEM` 0.12 m; the ankle joint is at 0.10 m): 9-17 cm above the ground standing and walking, it touches the ground only when the body crouches (attacks, falls).
- **Silk that is attracted to nothing.** `"sim": {"engine": "pbd", "damp": 3}` = `uo_cloth_pbd.py`: only the waistband follows the skeleton, the rest hangs free (gravity, stretch and bending constraints, air drag); legs and pelvis are capsules the cloth is pushed out of in every sub-step, so the legs go through the slits and the panels fall back by their own weight. Blender's cloth crumpled this skirt into ropes in the walk in every variant (quality, margins, mass x1-x3, pin 0-0.15). `damp` 3 is the calmer ("heavier") setting; 1.5 swings more.
- **Texture.** 4096 px baked from the original (no smearing by the 16k-vertex reduction), 1024 Cycles samples. A pixel filter of 1 px (the mean of each pixel) differs from the pixel-centre sample by <= 2 levels, so no extra option was kept.
- **No dark inside.** Scene `uo_behind_torso`: the torso hides the inside of the waistband ring (it showed as a dark brown area over the chest).
- **Smooth edges.** Scene `uo_edge_smooth` 3 (renderer: 1-px spikes of the outline dropped, 1-px notches filled): 8.3 -> 0.35 spikes and 4.4 -> 0.6 notches per frame, the area changes by 1 % (stand, walk, run, slash; 140 frames).
- **Stretch.** `uo_cloth_pbd.py` `iters` 60 (default): with 10 the hanging skirt stretched by 0.15 m under its own weight and lay on the ground, with 60 by 2 cm.
- Mounted actions (23-29): the hem follows the legs (not simulated), as for every skirt.

QA (`item_qa.py`, item inside the body in the posed frames): mean 14.1 % (worst 21_die_forward), deepest 127 mm. Higher than a fitted item (6.8 % with the fit) because the band is not pushed out of the skin; the renderer pushes it out of limbs, and the torso never hides items.

## Second version: lower on the hips (`girdle_low.json` -> `Radiant_Star_Girdle_low.vd`)

The band sits 7 cm lower (`NUDGE` -0.32 m: band at z 0.98-1.08 m, on the line of underwear), the hem stays at the same height above the ankles (`HEM` 0.13 m), so the skirt is about 5 cm shorter. Everything else as above. The cloth pins the whole band (`"sim": {"upper": -0.04}`; the pin height is taken from the recipe's `z_top`, which does not follow `NUDGE`). Hem (1st percentile of the simulated vertices) stand 0.153 m, walk 0.09-0.18 m, run 0.10-0.16 m; it touches the ground in crouching attacks and falls. QA: item inside the body 15.8 % (worst 21_die_forward), deepest 115 mm.

### Paperdoll gumps and item icon (`paperdoll_low/`, from the lower version)

`gump_male.png` / `gump_female.png` (260 x 237, like the body gumps 12 / 13 in `docs/paperdoll/`; put the item over the body gump) and `art.png` (44 x 40, the icon in the backpack); `*.bin` = the same as one `Gumpart.mul` entry (male gump id 50000 + the item's AnimID, female 60000 + AnimID; `Gumpidx.mul` extra = width << 16 | height = 17039597 for both) and one `art.mul` entry (index 0x4000 + the item id). Made by:
`PD_OUT=RAW PD_ART_H=40 python pipeline/run_script_in_blend.py OUT/item.blend pipeline/uo_render_paperdoll.py` (front view of the item at rest, 90.5 px/m, the body a holdout; the band is fitted to the underwear of each body gump: male x 79..112, top 127; female x 79..110, top 120) and
`python pipeline/uo_gump_finish.py RAW OUT/render/clothing/frames model/items/radiant_star_girdle/paperdoll_low`: the luminance of the gump (front light is much brighter: median 184) is mapped to that of the animation (5 / 50 / 95 percentile 58 / 129 / 191), 1-px spikes dropped, the rim pixels x 0.45, then encoded (`uo_gump_art.py`; read back: the alpha is identical, colours within the 5 bit rounding, <= 7). The icon is the item tilted 55 degrees, turned -35 degrees, fitted into 44 x 40.
