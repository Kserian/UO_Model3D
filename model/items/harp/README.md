# Harp (instrument) held in the right hand

The user's own model of a harp (`models/harp_orig.glb`, 44 MB, **not in the repo**; scan-like mesh of 302k vertices, one 4K PBR material). Item: part `weapon1h` (bone `weapon1h.R`), held by **one arm of the V**, not by a handle.

## 1. The model was wrong: repair (`build_harp.py`)

The original had strings, pin heads and eyelets on BOTH faces of the frame. `python model/items/harp/build_harp.py models/harp_orig.glb models/harp.glb` (needs numpy, pillow, scipy; ~1 min):

- Metal is told from wood by the metal-roughness texture (blue channel > 128), strings from pins by thickness (thick blobs after an erosion of 4 mm = pin heads and eyelets). The glb is edited in its index / vertex buffers only: the textures stay byte-identical.
- **Back face** (Blender y > 0): strings deleted, pin heads and eyelets with the walls of their holes flattened onto the plane of the wood round them (UV and normal of that wood), loose debris of the old strings dropped. What is left of it: pale patches on the neck, a few 3 mm dark dots where the strings ended on the inner face of the arm.
- **Front face**: the old string ribbons (zero thickness, not fit to be made thicker) are replaced by 10 round cylinders on the old axes (radius 0.016 of a model unit = 5 mm at 0.65 m); pin heads and eyelets stay and ride on the grown surface.
- **Frame grown in every plane** (the first complaint: too thin): every vertex moves 0.045 model units (1.4 cm at 0.65 m) along its smoothed normal, welded by position so that UV seams do not open: the arms 4 -> 7 cm in the plane, 5 -> 8 cm thick.

## 2. In the hand

`harp_R.json`: `"weapon": {"class": "mace", "part": "weapon1h", "length": 0.65, "tip": "+z", "grip": 0.22, "grip_side": "+x", "butt": -0.22}` (`uo_orient_weapon.py`: `GRIP_H` / `GRIP_SIDE` / `TURN`, new). The arm of the V at 0.22 m above its lowest point (its middle across the slice) goes onto the grip line, so the hand closes on the arm and the harp hangs to -X, the side of the right hand that has > 0.45 m of free room (+X only 0.15-0.25 m: see the measurements below). `"butt": -0.22` puts the hand at that height. `"turn": 180` swaps the arm and the face with the strings.

`python pipeline/uo_make_item.py model/items/harp/harp_R.json --out OUT --preview` (the recipe's `file` is `models/harp.glb`; `"decimate": 400000` keeps the strings: the usual 30000 would eat them).

## 3. Pictures

- Game size (36 px/m): `--preview` (sprites of 0.65 m = 23 px; the 10 strings are 0.8 px apart at the top: they read as a grey haze between the arms, not as lines).
- Full quality: recipe with `"materials": {"TEXTURE_FILTER": false}` (keeps the 4096 px textures; the default filter box-averages them to 67 px for the sprite), then `python pipeline/item_still.py -- OUT/item.blend OUT/idle 07_combat_idle_1h 0 0,2,3,1 2.3 1500 160`.

## Measurements behind the grip (point clouds of the shape on `weapon1h.R`, all 35 actions)

Share of the item inside the body (grip zone of 6 cm left out): a V frame held by its tip with nothing below the hand 0.9 % (hand 4 cm above the lowest point), 3.1 % at 10 cm, 6.4 % at 19 cm (the class default `butt`); a column like the horn 1.45 % / 9.4 %. Free room round the shaft (closest body part 2 cm): -X and +Y almost always > 0.45 m; +X and -Y only 0.15-0.25 m in walk, run, 1H slash / pierce, fidget 2. Worst actions for every shape: 18 and 27 bow, 29 mounted 2H, 21 die forward (hands together or on the ground). **Not measured for the final grip on the arm**: run `item_qa.py` (`uo_make_item.py` without `--no-qa`) before packing a `.vd`.

## Reference

The client's own harps (art, from `art.mul` via `tiledata.mul`): `lap harp` 0x0EB2 (V frame, bowed pillar, scroll neck, no soundbox; 22 x 29 px), `standing harp` 0x0EB1, a big ornate one 0xA775. None is wearable: no original animation to match.
