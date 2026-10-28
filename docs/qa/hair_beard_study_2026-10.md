# Hair and beards in the UO client: how they are drawn, and how we can add new ones (2026-10-28)

Measured on the Nelderim client (`anim.mul` + `tiledata.mul` + `Bodyconv.def`). The sprites of the originals were extracted with
`vdtool/mul2vd.py` + `vdtool.py extract` and laid over body 0x190 on a common anchor (the PNGs of one `.vd` already share a canvas and an anchor).

## Which animations are hair / beards
- Items of `tiledata.mul` with the wearable flag and layer 11 (Hair) / 16 (FacialHair) point to equipment animations of the people layout (35 actions x 5 directions, 175 blocks).
- Original game, `anim.mul`: hair 700, 701 (long), 702 (ponytail), 703, 710, 712, 900-903; beards 800 (goatee), 801 (long), 802 (short), 803 (mustache), 904-906. 175 blocks each, ~1050 frames (goatee / mustache 149-152 blocks).
- Elven hair `anim5` 636-639, 646-652 (via `Bodyconv.def`); gargoyle horns `anim5` 345-372 and `anim2` 537-548 (no frames in the extract).
- `anim2` 517-536 (hair) and 521-524 (beards) are Nelderim additions (`Male_H_Hair_01`..., "Beard_Hair_01"...); same layout, same size class.

## Size and shading (stand, 5 directions; dir 0 = front, dir 4 = back)
| Sprite | W x H px (dirs 0-4) | Pixels in stand dir 0 |
|---|---|---|
| 701 long hair | 13x11, 15x17, 15x21, 15x23, 15x23 | 89 (hair seen from the front) .. 254 (from the back) |
| 801 long beard | 8x11, 6x10, 5x8, 3x7, 7x5 | 51 |
| 802 short beard | 8x8, 7x7, 5x5, 3x5, 7x5 | 39 |
| goatee / mustache | 4x3 / 4x2 | few |
- A beard is **tiny**: the longest original (801) is 11 px tall (~30 cm at 36 px/m), 14-51 px per frame, from behind almost nothing. A hair sprite is 90-250 px.
- Hair and beards are **grey** (R = G = B up to 8/255; palette 256 entries, 14-24 used per frame) and are dyed by the client with the item's hue (`hues.mul`, colour = hue[red >> 3]); see `pipeline/uo_hue_preview.py`.
- Shading is the same light as the body (from the upper left): hair interior mean 97-145, 1-px outline 30-45 (dark grey, not black); beard interior 131-175 (brighter than hair), outline 38-86. Left half brighter than the right in dirs 1-2 (+17..+25), front top brighter than bottom.
- **Rigid on the head:** over the walk / run cycle the hair top stays 0..-1 px from the body's head top, and the beard 5-6 px below it; x offset constant within +-0.3 px. Only when the head tilts (slash, die) the offset changes. Pixel count changes per frame (re-rendered, not a copy): hair 148 -> 177 px in the walk. So every frame is an own render of a 3D model rigidly on the head - exactly what `uo_bind_item.py` `RIGID` (`hair`, `beard`) produces.

## What our pipeline already does
`kind` `hair` / `beard` exist in `uo_make_item.py` (rigid on `head`, zones 1.52-1.89 / 1.52-1.72 m, `OUT_BY_KIND`, densify off). The model has per-frame head poses for all 1050 original frames, so a new hair / beard renders on the same pose as the original sprites.

## Proof of concept: a procedural long beard through the pipeline (not committed)
A throw-away beard (cheek shell + tapered tube 20 cm below the chin, solidified 1.8 cm) written to glb, run with `uo_make_item.py` (`"kind": "beard"`), rendered for `04_stand` only
(`run_render_headless.py ... LAYER="clothing" "ONLY=['04_stand']"`: 4 s; `uo_make_item.py --vd` renders all 35 actions, 15-30 min), laid over the original body next to the original 801:
- Works end to end: import -> autofit -> fit (0 vertices inside the skin) -> bind -> render -> `.vd`; sprite 9x10 px (front) vs 8x11 of the original 801; outline and grey look are right.
- **Brightness is off:** interior mean 60-86 vs 131-175 of the original beard: a beard needs a base colour ~0.75 (or `uo_materials.py` BRIGHTNESS), not 0.45.
- **Render defaults are wrong for a beard** (found by trying):
  - Head-skinned items are never hidden by the head (`OWN_PARTS_NEVER_HIDE`), so cheeks / hanging part show through the head and neck from behind (dirs 3-4). Fix: recipe `"scene": {"uo_head_hides": 1}` (a dir 3 clean, dir 4 keeps a 1-2 px strip at the base of the neck). `uo_behind_torso` is the wrong switch (for things hanging on the back).
  - `uo_autofit_item.py` has no notion of a beard (it wraps the head skin): it moves a hand-placed beard (z +1.5..4 cm, y +2.4..3 cm). Give `SCALE_RANGE` (0.99, 1.01) and `USE_EDGE` false to keep size; a model made for the UO head should be placed by the user in the right spot (chin z ~1.565, front y ~-0.22 m, neck front y -0.124 at z 1.51, chest y -0.17..-0.18 at z 1.30-1.36).
  - The first shell (cheeks wrapped 95 deg round the head) looked like a hat from the back: a beard shell stops at about +-60 deg.
- The result reads clearly from the front only with a proper model; the crude procedural shape is not good enough to ship (not committed).

## Options for "new hair / long beards"
1. **New 3D hair / beard from a free model** (recommended): `kind` `hair` / `beard`, rigid on the head, grey (`SATURATION` 0, brightness like the originals) so the client hue dyes it. Output a `.vd` for a new equipment animation id (tiledata item with layer 11 / 16 and `Bodyconv.def` / `anim2..5` slot of the server), same as the horn items. Needs: the model's licence, a brightness calibration against 701 / 801, and the `uo_head_hides` + no-autofit-move recipe above.
2. **Long beard from the original 801 + our extension:** the 801 sprite is only the chin; a longer beard = a new animation that contains the original 801 pixels plus the part below the chin rendered by us on the fitted head pose (same canvas, same anchor; the hue is applied to the sum). Feasible because both are grey and rigid on the head; the join at the chin needs the extension to start under the original sprite (the original goes over it). Not tried beyond the composite above.
3. **2D painting on the sprites** (no 3D): possible for a few frames, not for 1050: the head moves and tilts per frame, so an extension must follow the head pose of each frame - the 3D route gives that for free.
- Draw order / hue flags (PartialHue is not set on hair; the client dyes every pixel) are client-side: test in the game once with one new item.

## Result with a real sculpt (user's long wavy beard, 2026-10-28)
`model/items/beard/` (`Beard_long_wavy.vd`, recipe, README). Measured against the original stand sprites 801 / 803 / 800 (dir 0-4):
- Placement from the sprites, not from the head mesh: the body renders at 36 px/m, camera elevated ~30 deg, so a point 1 m higher is 31.2 rows up and 10 cm further forward is ~1.8 rows lower. The head mesh's lowest vertices are neck, not chin: chin ~1.63 m, mouth ~1.68, nose ~1.75, eyes ~1.79 (my first guess, from the head vertex group, was 8 cm too low).
- Profile (dir 2): face front col 94-96; original 801 cols 94-98; ours 92-97 after moving the back plane of the sculpt onto the face (a first placement 6.5 cm further forward stuck out 3 px).
- From behind: dir 4 39 px -> 2 px with `behind_torso`; the original has 14 px (ear-level wings).
- Bulk 65 px front (original 51), 38 px profile (28); bottom row 102 vs 98 of the original (longer, as intended).
- 1050 frames, all palettes grey (R = G = B within 8), no empty frame except behind the head (38, dir 2-4 of some actions).

