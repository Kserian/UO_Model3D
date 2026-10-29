# Long wavy beard (layer 16, FacialHair)

`Beard_long_wavy.vd`: all 35 actions x 5 directions (1050 frames, 38 empty ones from behind where the beard is not visible), grey (R = G = B, the client dyes it with the item's hue), rigid on the head.

Source: a sculpt supplied by the user (1.48 M vertices, a closed "bag" of a beard with a moustache whose tips curl up; the file `beard.glb`, 88 MB, is **not in the repo**; record its licence / author when known). `beard_long_wavy.glb` here is the reduced, placed result (20 k vertices):

    python pipeline/uo_scale_remesh.py beard.glb model/items/beard/beard_long_wavy.glb --scale 0.23 --move 0 -0.226 1.525
    python pipeline/uo_make_item.py model/items/beard/beard_long_wavy.json --out OUT --vd      # all actions, ~17 min

- Size: the sculpt is 1.9 units tall; x0.23 = 0.44 m (the original long beard 801 is ~0.35 m, 11 px). Voxel remesh 3.5 mm keeps the lobes of the curls, the single strands (< 1 px = 2.7 cm) go.
- Fit to the face (measured on the original sprites, stand): the moustache arch of the sculpt sits at the mouth (z 1.68 m; original moustache 803 rows 92-93, goatee 800 rows 93-95), its back plane on the front of the face (y -0.226), tips of the moustache on the cheeks (z 1.74, the top of the original beard 801); profile: the beard sticks out 0-1 px in front of the chin like the original 801 (cols 94-98 vs 92-97).
- Placed by hand, not by `uo_autofit_item.py` (it has no idea of a beard and pushes a free-hanging one into the head): recipe `"prepare": {"AUTOFIT": false, "FIT": false}`.
- Render settings: `"scene": {"uo_head_hides": 1}` (the head hides what is behind it), `"behind_torso": true` (the neck / chest hide it from behind: dir 4 has 2 px instead of 39), `uo_min_piece` 0 (thin moustache tips), `BRIGHTNESS` 0.65 and `uo_contrast` 2.4 about 0.6: interior brightness 145-175 (original beard 131-175), std 17-27 (original 17-33).
- Not covered: the original beards also cover the cheeks / jaw up to the ear (801 rows 88-92); this sculpt starts at the moustache. A sideburn / cheek piece would have to be added to the model.
- Not tested in the game (hue, draw order against hair and helmet): make one tiledata item with layer 16 and the new animation id.

## With sideburns: `Beard_long_wavy_sideburns.vd`
The sculpt plus the cheek whiskers of the original beard 801 (two strips beside the face in the front view, a patch from the front of the face to the ear in profile, wings at the sides of the head from behind). 1050 frames, no empty frame.

    python pipeline/uo_scale_remesh.py beard.glb model/items/beard/beard_long_wavy.glb --scale 0.23 --move 0 -0.226 1.525
    python pipeline/uo_cheek_shell.py model/items/beard/beard_long_wavy.glb model/items/beard/beard_long_wavy_sideburns.glb
    python pipeline/uo_make_item.py model/items/beard/beard_long_wavy_sideburns.json --out OUT --vd

- `uo_cheek_shell.py` copies the skin of the head on each cheek (outside |x| 2.9 cm, in front of the ear, from the jaw at z 1.61 up to 1.785), moves it out along the normals by 3 cm and smooths it; **what comes within 6 mm of the sculpt, or inside it, is cut away**, so the two never overlap: 0 intersecting triangle pairs, closest distance 6.4 mm, the sculpt is unchanged. Both go into one glb (one object, rigid on the head, same material).
- Parameters fitted to the original 801 stand sprites (coordinate search on IoU of the shell render against the 801 pixels above the beard, rows <= 92): front view covers 18 of 22 pixels, three-quarter 15 of 20, profile 19 of 19, behind-left 10 of 17; from behind (dir 4) the wings of the original (14 px at the ear-level edges of the head) are not reproduced (ours stand 1-2 px further out, 1 of 14 pixels match). Shell thickness 3 cm gives the best recall; 2.5 cm gives better precision (front 0.63 instead of 0.57) with a recall of 0.55 instead of 0.55-0.59.
- The sideburns are thicker than in the original in the front view (ours 87 px, original 51 px in the whole beard, 70 % of it is the sculpt).
- A seam: the cut leaves a 6 mm gap, the renderer draws its 1-px outline there (visible in the front view as a dark line where the strip meets the beard, like the dark edge of the original strips); a seamless join would need the shell and the sculpt to share their border.

## Hybrid: `Beard_long_hybrid.vd` (current)
Feedback on the sideburn shell ("unnatural, the beard should sit under the chin, the sideburns are weak, take the original ones and soften the join"): the sideburns are now the **pixels of the original beard 801**, the beard is the sculpt **moved under the chin**, and the join is softened. 1050 frames (8 empty from behind, dir 4, where the beard is hidden), exactly grey, <= 27 colours per block.

    python pipeline/uo_scale_remesh.py beard.glb model/items/beard/beard_under_chin.glb --scale 0.21 --voxel 0.007 --move 0.014 -0.205 1.493 --cut-z 1.665 --taper 0.22 0.03 0.85
    python pipeline/uo_jaw_zone.py model/items/beard/jaw_zone.glb 1.64 1.74
    python pipeline/uo_make_item.py model/items/beard/beard_under_chin.json --out BEARD --vd      # all actions
    python pipeline/uo_make_item.py model/items/beard/jaw_zone.json --out ZONE --vd
    python vdtool/vdtool.py extract <anim_801.vd> ORIG                                           # python vdtool/mul2vd.py anim.idx anim.mul out 801
    python pipeline/uo_hybrid_beard.py ORIG BEARD/render/clothing ZONE/render/clothing OUT
    python vdtool/vdtool.py pack OUT Beard_long_hybrid.vd

- Under the chin: the sculpt is x0.21 (0.85 wide, so 0.36 m long, 15 cm wide), its mouth arch at the chin (z 1.635), cut off flat at z 1.665 (no moustache, no tips on the cheeks), back plane 2 cm behind the previous placement; voxel remesh 7 mm (3.5 mm kept the slits between the strands, the body showed through them and the renderer drew an outline round every one: loops over the chest). Stand, dir 0-2: the mass sits on rows 93-98 like the original 801 (it had been 91-101 and 7 px wide).
- Sideburns: `jaw_zone.glb` is a wedge above a plane rising from the chin (z 1.64) to the ear (1.74), rigid on the head, rendered like an item: its silhouette in each frame is the face above the jaw line, whatever the head does (walk, die, mounted). The original pixels inside it are kept, the original pixels below it (the original beard proper) are dropped.
- Join (`uo_hybrid_beard.py`): the tone of the model beard is matched to the sideburn along the seam (gain 0.8-1.25, fading over 5 px), a 1-2 px gap between the two is filled with the colours above and below, dark outline pixels between the two (opaque on both sides, near the seam) take the colour of their light neighbours, no pixel of the model lighter than 200 (the originals peak at 197), all pixels exactly grey (R = G = B).
- Not checked in the game; the model part is a smooth bib (the sculpt's curls do not survive at 36 px/m, the original 801 is a smooth V as well).

### Fix: the shape and the hanging (2026-10-29, second round)
"In the front view it is thin at first and then wider": the sculpt is a diamond (widest in the middle; its top under the chin is the narrow arch of the moustache), the original beard 801 is widest at the jaw (7 px) and falls to a point (2 px). And a second effect: rigid on the head, a long beard turns with the head's roll in the fitted pose (the foot of the stand beard drifted 1-2 px sideways), which a hanging beard does not.
- `uo_scale_remesh.py --taper 0.22 0.03 0.85`: the width is brought to a profile of 0.22 m at the chin falling to 0.03 m at the tip ((1 - t) ** 0.85); measured from the 4-96 percentile of x per height (single strands that stick out do not set the width) and centred on x = 0. Front view, stand: widths 6-7 px under the chin falling to 3 px and a 1 px point, centred (99.0, the original 801 99.5).
- Recipe key `"hang": {"bone": "chest", "z_top": 1.64, "z_end": 1.45}` (`uo_make_item.py`): weights go from the head (above z_top) to the chest (below z_end), smoothstep in between, so the foot of the beard hangs with the torso instead of turning with the head. The `stretch` of the previous round (0.85 wide) is gone: the taper sets the width.
- Result: 1050 frames, 6 empty (behind, dir 3-4), exactly grey, <= 27 colours per block.

