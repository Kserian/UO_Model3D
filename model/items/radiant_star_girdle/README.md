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

### Filling the gap between the banner and its outer gold frame (`pipeline/uo_fill_banner_gap.py`)

The model has a central banner with a gold border and, 4 cm outside and 4 cm behind it, a thin outer frame (two vertical strips and a V); between them there are no faces, so the skirt's back or the body shows through. `python pipeline/uo_fill_banner_gap.py models/radiant_star_girdle.glb models/radiant_star_girdle_filled.glb --png mask.png` adds 28.5k triangles (0.128 m2, two pieces of 0.052 m2) to the glb itself (images and the rest byte for byte): the gap is found in the front view (the ring of the front-layer faces, holes filled), the depth is interpolated from the neighbours (+2 mm behind them), and every new triangle takes the colour chart of a plain-cloth triangle next to the border (the atlas is a mosaic of small charts, no map (x, z) -> uv exists). Not yet used by `girdle.json` (it still points at the original glb).

### Narrower side panels (`pipeline/uo_narrow_panels.py`)

In the game the side panels are 4-6 px wide each (measured on the stand frames, 1 px = 2.8 cm), so "4 px thinner" was taken as 4 px in all: every vertex outside |x| = 0.26 of the model moves towards the middle by the same factor k = 0.77 (|x'| = 0.26 + (|x| - 0.26) k; the waistband and the banner are not touched, the factor fades to 1 over z 0.70..0.76): the outer edge of each panel goes in by 0.10 model units = 2.0 px at the hem (the hem tips' span 1.41 -> 1.20 units, 28 -> 24 px). `python pipeline/uo_narrow_panels.py models/radiant_star_girdle_filled.glb models/radiant_star_girdle_filled_narrow.glb --k 0.77`. Not yet used by the recipes.

### Lower version with the filled gap and the narrower panels: stand + walk only (`Radiant_Star_Girdle_low_stand_walk.vd`)

`girdle_low.json` now points at `models/radiant_star_girdle_filled_narrow.glb` (gap filled by `uo_fill_banner_gap.py`, panels narrowed by `uo_narrow_panels.py`), `sim` gets `"glue": 0.025`. The `.vd` has only `04_stand` and `00_walk_unarmed` (60 frames); the other actions are rendered the same way (`--vd`). Autofit scale 0.639 (0.631 before: the narrower mesh). The strips of the filled gap are separate pieces of the mesh with a 3 mm grid (230 rows): the solver could not hold them up by their own edges (they fell to the ground, 900 vertices on each side), so `uo_cloth_pbd.py` ties such pieces to the cloth next to them (`glue`): hem 16 cm above the ground standing, 12-19 cm walking. QA of the item (not the render): inside the body 16.7 % (worst 09_attack_1h_slash).

### Full lower version from the filled, narrowed model (`Radiant_Star_Girdle_low_v2.vd`)

All 35 actions x 5 directions (1050 frames), `girdle_low.json` as it is now: PBD cloth (`damp` 3, `glue` 0.025, `upper` -0.04), falls simulated like the other actions, scene `uo_edge_smooth` 3, `uo_samples` 1024. Tried and taken back at the owner's request: scene `uo_cloth_lie` 1 (the falls laid along the legs by the renderer: the cloth stays on the body in all 60 death frames, 10 px from the body's centre on average, but it reads as a stiff bag; `uo_cloth_pbd.py` keeps the key `lie`, default = the scene property). Known: in some frames of the falls the 3D body in front of the cloth cuts it (the client shows the original body there); scene `uo_legs_under` 1 would stop the legs from cutting, but then a back panel seen through a slit in the walk would be drawn over the leg: not applied, left to be fixed by hand.

### v3: the middle strip is no longer lost in the run (`Radiant_Star_Girdle_low_v3.vd`)

In the run the thigh of the real body stood out of the capsule that `uo_cloth_pbd.py` pushes the cloth out of (radius = the 75th percentile of the skin's distance from the bone axis): 27-43 % of the banner's vertices sat inside the leg in run frames 3-5 (median 8-14 mm deep), so the 3D leg hid the banner (the game showed only the side panels). Capsule radius now the 95th percentile and margin 15 mm (`rpct` 95, `margin` 0.015, also in `girdle_low.json`): 0 % of the banner inside the legs in the run (all 10 frames), walk, advance; at most 2 % in the slash and the spell, 9 % of the banner in one frame of the forward fall (the rest 0-3 %). Item pixels in the 7 middle columns of the run, direction 0, per frame: v2 56-155 (72, 56 in frames 6-8), v3 96-154.
