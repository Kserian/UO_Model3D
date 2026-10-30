# Harp (instrument) held in the right hand

The user's own model of a harp (`models/harp_orig.glb`, 44 MB, **not in the repo**; scan-like mesh of 302k vertices, one 4K PBR material). Item: part `weapon1h` (bone `weapon1h.R`), held by **one arm of the V**, not by a handle.

## 1. The model was wrong: repair (`build_harp.py`)

The original had strings, pin heads and eyelets on BOTH faces of the frame. `python model/items/harp/build_harp.py models/harp_orig.glb models/harp_half.glb 0.09 0.07 0.04 half` (FRAME_W FRAME_T STRING_R STRINGS; needs numpy, pillow, scipy; ~1 min):

- Metal is told from wood by the metal-roughness texture (blue channel > 128), strings from pins by thickness (thick blobs after an erosion of 4 mm = pin heads and eyelets). The glb is edited in its index / vertex buffers only: the textures stay byte-identical.
- **Back face** (Blender y > 0): strings deleted, pin heads and eyelets with the walls of their holes flattened onto the plane of the wood round them (UV and normal of that wood), loose debris of the old strings dropped. What is left of it: pale patches on the neck, a few 3 mm dark dots where the strings ended on the inner face of the arm.
- **Front face**: the old string ribbons (zero thickness, not fit to be made thicker) are replaced by 10 round cylinders on the old axes (radius 0.04 of a model unit = 1.2 cm at 0.65 m, 0.85 px: stable lines; the item is rigid on the hand bone, the strings do not move against the frame); pin heads and eyelets stay and ride on the grown surface.
- **Frame grown separately in its plane and across it** (the user: arms at least 3 px, better 4, thickness about 2 px, at 36 px/m): every vertex moves along its smoothed normal (welded by position so that UV seams do not open) by FRAME_W in the plane and FRAME_T across it. `widths.py harp.glb 0.65 240` measures the silhouette in game pixels (ridge of the distance transform = the width of the arms and the neck; 1 px = 27.8 mm at 0.65 m):

  | | arms: thinnest 5 % / median | thickness |
  |---|---|---|
  | original | 1.4 / 2.2 px | 1.4 px |
  | FRAME_W 0.065 (variant A) | 3.0 / 3.2 px | 2.1 px |
  | FRAME_W 0.09, FRAME_T 0.03 | 3.6 / 3.9 px | 2.1 px (thinnest bands 1.5 px: seen edge-on it was a 1-px line) |
  | **FRAME_W 0.09, FRAME_T 0.07 (the recipe)** | 3.6 / 3.9 px | 2.9 px (thinnest bands 2.3 px) |
  | FRAME_W 0.10 | 3.8 / 4.4 px | 2.0 px |

## 2. In the hand

Builds of the same repaired, grown model (`STRINGS`): `harp_R.json` / `harp_L.json` use `models/harp_half.glb` (every second string: 5 strings; the user's choice), `harp_R_none.json` uses `models/harp_none.glb` (no strings, the cleanest at game size: a plain wooden V). The pin heads stay in all (0.3 px).

**Left hand** (`harp_L.json`, part `weapon.L`: the grip of `weapon1h.R` mirrored onto `hand.L`, no original to calibrate on, like the horn): the mirror flips which side is free, so the same (thin) arm is held with `"grip_side": "-x"` and no `turn`; the harp then hangs outward. In the combat idle the left arm is down at the belly and the harp lies across it (the same for any item on `weapon.L`); in the attack it stands in front of the chest.

Recipe: `"weapon": {"class": "mace", "part": "weapon1h", "length": 0.65, "tip": "+z", "grip": 0.30, "grip_side": "+x", "turn": 180, "butt": -0.30}` (`uo_orient_weapon.py`: `GRIP_H` / `GRIP_SIDE` / `TURN`, new). The arm of the V at 0.30 m above its lowest point (not by the bottom tip) goes onto the grip line, so the hand closes on the arm and the harp hangs to -X, the side of the right hand that has > 0.45 m of free room (+X only 0.15-0.25 m: see the measurements below). `"butt": -0.30` puts the hand at that height. `"turn": 180` holds the OTHER arm of the V (the thin one with the scroll, held at the +X side) and turns the face with the strings the other way; without it the thick arm is held.

`"materials": {"METAL": false}`: no highlight on the item (it is wood). `"scene": {"uo_outline": 0.7, "uo_edge_smooth": 2}`: the 1-px outline is darkened to 0.7 of the wood (the default 0.38 is a near black rim: a rim in the colour of the wood, a little darker) and the render drops 1-px spikes and fills 1-px notches of the silhouette twice (rounder corners; 0 / 1 / 2 differ only slightly).

`python pipeline/uo_make_item.py model/items/harp/harp_R.json --out OUT --preview` (the recipe's `file` is `models/harp.glb`; `"decimate": 400000` keeps the strings: the usual 30000 would eat them).

## Packed files

`Harp_right_hand.vd` (285 KB) and `Harp_left_hand.vd` (341 KB): all 35 actions x 5 directions (1050 frames each, 256 x 256 canvas layer of the item only, like `Horn_*.vd`), made from `harp_R.json` / `harp_L.json` (every second string = 5 strings, arm grip at 0.38 m, outline 0.7, edge smoothing 2, 1024 samples per pixel, no highlight). `python pipeline/uo_make_item.py model/items/harp/harp_R.json --out OUT --vd` (and `harp_L.json`); about 65 minutes each with both running on 4 cores.

Texture quality: the 4096 px source textures go in whole; the material step box-averages them to the sprite scale (1.5 texels per game pixel, 67 px for this model) because the renderer samples a pixel in one point and an unfiltered 4K texture turns into speckles at 36 px/m. `"materials": {"TEXTURE_FILTER": false}` keeps the full texture (used for the big stills in section 3, where it is correct). QA of the grip: see the end of this file.

## 3. Pictures

- Game size (36 px/m): `--preview` (sprites of 0.65 m = 23 px; the 10 strings are 0.8 px apart at the top: they read as a grey haze between the arms, not as lines).
- Full quality: recipe with `"materials": {"TEXTURE_FILTER": false}` (keeps the 4096 px textures; the default filter box-averages them to 67 px for the sprite), then `python pipeline/item_still.py -- OUT/item.blend OUT/idle 07_combat_idle_1h 0 0,2,3,1 2.3 1500 160`.

## Measurements behind the grip (point clouds of the shape on `weapon1h.R`, all 35 actions)

Share of the item inside the body (grip zone of 6 cm left out): a V frame held by its tip with nothing below the hand 0.9 % (hand 4 cm above the lowest point), 3.1 % at 10 cm, 6.4 % at 19 cm (the class default `butt`); a column like the horn 1.45 % / 9.4 %. Free room round the shaft (closest body part 2 cm): -X and +Y almost always > 0.45 m; +X and -Y only 0.15-0.25 m in walk, run, 1H slash / pierce, fidget 2. Worst actions for every shape: 18 and 27 bow, 29 mounted 2H, 21 die forward (hands together or on the ground). `item_qa.py` of the final grip (arm at 0.38 m, FRAME_T 0.07): right hand 6.1 % inside the body (worst: 20_get_hit), deepest 99 mm; left hand 2.6 % (worst: 17_spell_area), deepest 144 mm (the horn: 4.3 % / 97 mm and 3.8 % / 88 mm).

## Reference

The client's own harps (art, from `art.mul` via `tiledata.mul`): `lap harp` 0x0EB2 (V frame, bowed pillar, scroll neck, no soundbox; 22 x 29 px), `standing harp` 0x0EB1, a big ornate one 0xA775. None is wearable: no original animation to match.
