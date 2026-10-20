# Robe variants tested, October 2026

UO_Model3D, branch model_fixing5: cloth physics, fit, fabrics and shading of one free robe model (24,366 vertices after conform)

PDF with the charts: `robe_variants_2026-10.pdf` (same folder).

## Summary

- Goal: a loose robe that moves like cloth (the legs push it out, no fixed leg-hull target) and still sits on the original body 400 like the original UO robes. About 45 physics configurations, 3 fabrics (silk, cotton, wool), 3 fit variants and 22 shading variants were tried.
- Physics: a free Blender cloth on this fine mesh needs a weak pin to its kinematic target (goal 0.2, pin target = skinned + 0.5 x leg push), a contact margin of 0.02 m (thin margins let the legs through), vertex mass scaled to the mesh (mscale 0.033) and in-plane stiffness 5 for every fabric (stiffer fabrics are pulled up by the pin: the hem climbed 0.26 m in cotton and 0.47 m in wool in the walk; at 5 it is 0.04-0.05 m).
- Fabrics: silk, cotton and wool differ only in mass, bending and damping after that fix; they move almost alike because the pin is the anchor. Denim and leather were never run.
- Shape: the loose and the tight fit differ by 0.7-0.9 cm (0.3 px); the sleeves are about 10% thicker than the original robe 469, the skirt is about 1.7 x wider at the hem, the waist is 2 cm per side wider.
- Look: the original robe is painted with dark creases (brightness spread in the sleeve zone 54, our smooth shell 31). A contrast curve reproduces it (k 1.8: 52); light direction, own shadow, normal map strength, occlusion and a 1 px inner line did not (or looked like a drawn line).
- Decision (2026-10-20): base look of a robe / skirt = uo_contrast 1.5, uo_shade_sleeve 0.4, uo_shade_width 4 (uo_make_item.py scene_of; the recipe's own scene wins). Four full 35-action .vd files were made: silk, cotton, wool, tight silk.

## 1. Metrics used

| Metric | Definition |
|---|---|
| hem lift | mean vertical offset (m) of the simulated hem (rest z < 0.3 m) from its kinematic target, averaged over the frames of an action; + = the hem climbed. Silk (the soft reference) gives +0.04. |
| leg px (item_skin_check.py) | pixels of thigh and shin (feet counted apart) in the 3D preview of body + item, over 100 frames of walk and run; split into 'through the cloth' (the leg is in front of an item pixel) and 'in holes' (no item pixel there). |
| holes (item_body_holes.py) | pixels of the ORIGINAL body 400 inside the closed outline of the clothing layer, i.e. what the client shows; legs only, hands and head apart. |
| stand-off | distance (cm) of item vertices from the skin in the rest pose, torso 1.05-1.50 m, sleeves, skirt below 0.9 m (BVH of the body). |
| torso band width | extra half-width (cm) of the item silhouette over the original body silhouette per row, z 1.02-1.55 m, against the original robe 469 (sprite) in the same frames. |
| arm zone ratio | item pixels in the arm (sleeve) or hand zone divided by the pixels of that body part; zones from body_part_raster.py labels, torso labels excluded. |
| brightness spread | standard deviation of luminance (0-255) of the item pixels in the sleeve or hand zone; also the 5th percentile and the share of pixels darker than (item median - 35). Original robe 469: sleeve 54, hand 52 (walk). |

## 2. Cloth physics

Settings of the final simulation (t1): `fabric=<name> mscale=0.0333 goal=0.2 pushw=0.5 gravity=1.5 in_max=-1 max_move=0 smooth=0.04 arm_goal=0.95 preroll=20 cycles=2 thick=0.02 dist=0.005 (riding: mounted=1 horse=1)`

### Free simulation (goal 0)

| ID | Change | Result | Verdict |
|---|---|---|---|
| P1 | goal 0, mass 0.3 kg per vertex, contact margin 0.02 m, clamps off | walk: largest cloth move 18.5 m, median 0.6 m | rejected: 0.3 kg x 24k vertices is 7 t of cloth; the skirt falls apart |
| P2 | mass from fabric density (cotton 3.7e-5, silk 1.5e-5 kg per vertex), margin 0.02 | largest move 1.2 / 1.27 m; the hem band (z < 0.4 m) is lifted by +0.68 m on average | rejected |

### Stand pose controls (hem z mean, start 0.249 m, rest 0.240 m)

| ID | Change | Result | Verdict |
|---|---|---|---|
| P3 | pin goal 0.4 (the old hybrid) | 0.249 (stable) | reference |
| P4 | collision off | 0.250 (stable) | the collision margin is the cause of P6 |
| P5 | mass 0.3, goal 0 | 0.162, hem radius 0.32 -> 0.22 | collapses downwards |
| P6 | physical mass, margin 0.02 | 0.314 (hem +6.5 cm, still rising) | the collision margin lifts the free hem; margins 0.002-0.008 do not |
| P7 | margin 0.002, dist 0.001 | 0.249 (stable) | legs tunnel in motion (see leg px) |
| P8 | margin 0.008, dist 0.002 | 0.251 |  |
| P9 | margin 0.02, quality 3 | 0.278 |  |
| P10 | mass 0.01 | 0.231 (droops 2 cm) | OK |
| P11 | physical mass, damping x 0.01 | 0.257 |  |

### Walk, free cloth, margin 0.006 (hem lift, m)

| ID | Change | Result | Verdict |
|---|---|---|---|
| P12 | cotton, physical mass | +0.28 | hem climbs to the knees; accordion folds |
| P13 | mass 0.01, damping 5 / 1 | +0.24 |  |
| P14 | mass 0.003, damping 1 / 0.1 | +0.29 |  |
| P15 | mass 0.01, damping 1 / 0.2 | +0.25 |  |
| P16 | bending 0.02, mass 0.01 | +0.24 | bending is not the cause |
| P17 | mass 0.02, bending 0.005 | +0.21 |  |
| P18 | mass 0.05, tension 100 | +0.26 |  |
| P19 | quality 16, margin 0.006 | +0.31 (10 min) | finer steps do not help |
| P20 | quality 24, margin 0.01 | +0.43 (17 min) |  |
| P21 | quality 16, margin 0.015 | +0.48 (18 min) |  |
| P22 | pinned band 0.05 m (ramp) | +0.24 |  |
| P23 | ramp 0.05, margin 0.015 | +0.34 |  |
| P24 | ramp 0.15 | +0.22 |  |
| P25 | pin goal 0.05 | +0.19 |  |
| P26 | pin goal 0.10 | +0.10 |  |
| P27 | pin goal 0.20 | +0.02 | chosen: the cloth hangs, the fabric parameters do the rest |

### Analysis of the free cloth

| ID | Change | Result | Verdict |
|---|---|---|---|
| P28 | edge lengths of the free result vs rest | median ratio 1.00 (not stretched); lowest 2% of vertices z: rest 0.16, target 0.06, sim 0.34 m | the cloth folds up like an accordion: metastable, nothing unfolds it |

### Pin target and weight (walk and spell, cotton)

| ID | Change | Result | Verdict |
|---|---|---|---|
| P29 | pin target = skinned + 0.5 x leg push (pushw 0.5) | hangs straighter than the hull (pushw 1); smaller knee bulge in the spell | chosen |
| P30 | pushw 0 (hangs from the pelvis only) | legs poke through the front of the robe | rejected |
| P31 | pushw 0, gravity x 2 | same, more exposure | rejected; gravity 1.5 kept with pushw 0.5 |

### 2.1 Leg exposure (silk, walk + run, 100 frames)

| Variant | Total | Through | In holes | Note |
|---|---|---|---|---|
| hull target (pushw 1), margin 0.006 | 671 | 352 | 319 | first batch of the work (hull target) |
| pushw 0.5, margin 0.006 | 2396 | 1360 | 1036 | legs come out of the hem in the stride |
| t1: margin 0.02, dist 0.005 | 1435 | 304 | 1131 | chosen; 7-10 x slower (22 vs 3 min per action) |
| t2: margin 0.015, quality 12, cq 6 | 2118 | 850 | 1268 |  |
| t3: margin 0.025, quality 12, cq 6 | 2376 | 761 | 1615 | about 1 h per action |
| n1: single-sided collider (normals), margin 0.006 | 2628 | 1564 | 1064 | a colleague's idea; no help |
| n2: single-sided + normal impulses, margin 0.006 | 2642 | 1522 | 1120 | no help |
| E1: envelope after the sim, margin 0.02 (on margin 0.006) | 693 | 196 | 497 | flattens the hem |
| E2: envelope, margin 0.04, tent | 492 | 74 | 418 | best numbers, bell-shaped skirt again; rejected by the user as unnatural |

Client view (item_body_holes.py): pushw 0.5, margin 0.006 71; t1 (margin 0.02) 85; E2 (envelope) 35.

Per action, silk, feet excluded:

| Action | Frames | t1 total | t1 through | thin total | thin through |
|---|---|---|---|---|---|
| walk | 50 | 49 | 28 | 31 | 19 |
| run | 50 | 156 | 66 | 840 | 754 |
| slash 1h | 35 | 23 | 23 | 20 | 20 |
| die forward | 30 | 409 | 385 | 976 | 802 |
| die backward | 30 | 212 | 175 | 270 | 222 |
| ride walk | 25 | 72 | 11 | 65 | 22 |
| ride run | 25 | 105 | 35 | 100 | 23 |

### 2.2 Fabrics

| Fabric | Mass (preset) | In-plane stiffness | Bending | Damping | Status |
|---|---|---|---|---|---|
| silk | 0.15 | 5 | 0.05 | 1 | complete (35 actions) |
| cotton | 0.3 | 5 (preset 15) | 0.5 | 5 | complete (35 actions) |
| wool | 0.5 | 5 (ours 25) | 2 | 10 | complete (35 actions) |
| denim | 1.0 | 5 (preset 40) | 10 | 25 | not run |
| leather | 0.4 | 5 (preset 80) | 150 | 25 | not run |

| ID | Fabric test (walk) | Hem lift | Verdict |
|---|---|---|---|
| F1 | cotton, tension / compression / shear 15, bending 0.5, damping 5 | walk hem lift +0.26 | baseline of the presets |
| F2 | wool, 25 / 25 / 20, bending 2, damping 10 | +0.47 (0.39 -> 0.53 inside the loop) | baseline of the presets |
| F3 | wool, damping x 0.1 / x 0.033 | +0.38 / +0.46 | damping is not the cause |
| F4 | cotton, damping x 0.033 | +0.19 |  |
| F5 | wool, bending x 0.1 / x 0.033 | +0.52 / +0.33 | bending is not the main cause |
| F6 | cotton, bending x 0.033 | +0.24 |  |
| F7 | cotton, tension 5 / 5 / 5 (A) | +0.04 | in-plane stiffness is the cause |
| F8 | cotton, tension 15, compression 5, shear 5 (B) | +0.21 |  |
| F9 | cotton, 5 / 5 / 5, mass x 2 (C) | +0.04 |  |
| F10 | wool, 5 / 5 / 5 | +0.05 | chosen: all presets use in-plane stiffness 5 |

Final hem lift (m) per action:

| Action | silk | cotton | wool |
|---|---|---|---|
| walk | +0.04 | +0.04 | +0.05 |
| run | +0.05 | +0.05 | +0.05 |
| slash | +0.05 | +0.05 | +0.05 |
| die fwd | +0.04 | +0.04 | +0.04 |
| die back | +0.06 | +0.05 | +0.05 |
| ride walk | +0.03 | +0.03 | +0.03 |
| ride run | +0.00 | +0.00 | -0.01 |

## 3. Fit variants and thickness against the original robe 469

| Variant | Torso stand-off p50 / p90 cm | Sleeves | Skirt | Result |
|---|---|---|---|---|
| loose (conform GAP 1.5 cm, LOOSE_K 0.25) | torso 2.2 / 3.3 | sleeves 2.4 / 4.0 | skirt 8.1 / 17.9 | reference |
| tight (GAP 1.0, LOOSE_K 0, FOLD_MAX 0.4 cm, POSE_GAP 0.6) | torso 1.5 / 2.7 | sleeves 1.5 / 2.5 | skirt unchanged | 0.7-0.9 cm closer: about 0.3 px, hardly visible; shoulders narrower by 1.5-2.5 cm per side |
| slim cuffs (tight + SLEEVE_CUFF 3.2 cm, CUFF_SPAN 0.25) | - | arm zone ratio 0.66-0.75 | - | sleeves slightly thinner than the original robe 469 (0.70-0.84); hand zone only -9% in the walk |

Torso band, extra half-width per row (cm), walk:

| Height | original robe 469 | ours silk (loose) | ours tight |
|---|---|---|---|
| shoulders 1.49-1.56 m | 4.5-6.5 | 4.7-6.9 | 3.4-4.3 |
| chest 1.1-1.45 m | 2.4-3.0 | 3.2-3.5 | 3.2-3.8 |
| waist 1.02-1.05 m | 1.0-1.6 | 3.6-3.7 | 3.4 |

Arm and hand zone ratio:

| Action | sleeve 469 | sleeve ours | sleeve slim | hand 469 | hand ours | hand slim |
|---|---|---|---|---|---|---|
| walk | 0.70 | 0.79 | 0.66 | 1.25 | 2.04 | 1.86 |
| slash | 0.78 | 0.84 | 0.72 | 1.13 | 1.36 | 1.30 |
| spell directed | 0.72 | 0.84 | 0.69 | 1.25 | 1.55 | 1.43 |
| spell area | 0.84 | 0.90 | 0.75 | 0.89 | 1.06 | 0.99 |

## 4. Shading variants (sleeve and hand zone, walk)

| ID | Setting | Sleeve std | Hand std | Note |
|---|---|---|---|---|
| - | original robe 469 | 54.3 | 51.9 | reference; sleeve p5 = 8, dark share around the hand 56% |
| - | ours silk, loose (no shading) | 30.0 | 27.5 | dark share around the hand 29.5% |
| - | slim cuffs, no shading | 30.6 | 27.0 |  |
| A | inner line 0.6 + outline 0.5 | 40.0 | 35.5 | a 1 px line round the arm: rejected as unaesthetic |
| B1 | inner line 0.4 + outline 0.3 | - | - | rendered, never measured |
| B2 | inner line 0.25 + outline 0.2 | - | - | rendered, never measured |
| C | baked occlusion shading (OCCLUSION 1.0, 8 cm) | 30.8 | 25.7 | no effect on arms: baked in the rest pose |
| D | A + C | 40.0 | 34.0 | same as A |
| L1 | own shadow 0.2 (was 0.4) | 30.9 | 27.4 | no effect: the light sits on the camera axis |
| L2 | own shadow 0.1 | 31.2 | 27.8 | no effect |
| L3 | own shadow 0.2 + normal map strength x 2 | 30.9 | 27.4 | no effect (the material has no normal map) |
| L4 | own shadow 0.2 + texture contrast 1.0 | 31.0 | 27.5 | no effect |
| R1 | light from the left | 34.2 | 28.5 | robe darker overall (mean 96 vs 109) |
| R2 | light from the right | 36.0 | 35.1 | robe darker overall |
| R3 | light from above | 28.4 | 25.8 | robe darker overall |
| K15 | contrast curve k 1.5 (offline) | 45.3 | 39.5 |  |
| K18 | contrast curve k 1.8 (offline and in the renderer) | 51.8 | 44.9 | renderer: 51.9 / 44.9; closest to 469 |
| K22 | contrast curve k 2.2 (offline) | 58.6 | 49.9 | too strong |
| S1 | contact shadow from the body 0.6 | 31.0 | 27.4 | very subtle |
| S2 | contact shadow sleeve-torso 0.6 | 31.6 | 27.9 | visible depth in the armpit, slightly strong |
| S3 | S1 + S2, width 4 px | 32.0 | 28.3 | too dark overall |
| T1 | sleeve shadow 0.4, width 4 | 31.0 | 27.4 | subtle |
| T2 | sleeve shadow 0.5, width 4 | 31.3 | 27.8 | subtle |
| T3 | T1 + contrast 1.4 | 43.2 | 37.8 |  |
| T4 | sleeve shadow 0.5 + contrast 1.5 | 46.2 | 40.5 | dark share around the hand 57%, p5 = 9 |
| BASE | sleeve shadow 0.4 + contrast 1.5 (decided) | 45.9 | 40.0 | base look of robe / skirt; mean sleeve brightness 97 (469: 113), lights 155-163 (469: 180) |

## 5. Decisions, deliverables and code

| File | Content |
|---|---|
| robe_silk_full35.vd, robe_cotton_full35.vd, robe_wool_full35.vd | 35 actions x 5 directions, the t1 physics, riding with the horse as a collider (without the base look: rendered before it was decided) |
| robe_silk_tight_full35.vd | the tight fit, same physics |
| GIFs (8 fps, each action twice, 5 directions) | silk, cotton, wool |

| Where | Keys |
|---|---|
| uo_cloth_sim.py | fabric (silk, cotton, wool, denim, leather), mscale, dscale, bscale, density, goal, pushw, gravity, thick, dist, quality, cq, cull, usenormal, mounted, horse, env / env_margin / env_tent, trace, nocollide |
| render_uo_layer.py (scene) | uo_contrast, uo_contrast_pivot, uo_shade_sleeve, uo_shade_body, uo_shade_width (README section 4) |
| uo_make_item.py | scene_of(): base look of kind robe / skirt |
| item_skin_check.py | feet in their own colour and count (leg px = thigh and shin) |
| item_gif.py | --crop auto, exact average fps |

### Lessons

- Background jobs die when the container is reclaimed after idle time: restart the missing jobs and check for DONE markers.
- Do not edit a shell script while it runs (the running copy skipped its last line).
- pkill -f with a pattern that occurs in its own command line kills the shell: kill by PID.
- Blender's per-vertex mass, stiffness and damping are not resolution independent: a 24k vertex mesh needs mass scaled down and the in-plane stiffness lowered.
- Measure what the client shows (item_body_holes.py), not only the 3D preview: the legs outside the robe silhouette are not 'holes' for that metric.

### Open issues

- Denim and leather were never simulated.
- The robe is about 1.7 x wider at the hem and 2 cm per side wider at the waist than the original robe 469 (the model has a belt and a wide flare; the pipeline has HEM_FLARE, not used).
- The 35-action .vd files were rendered before the base look (contrast and sleeve shadow) and the slim cuffs: they need a re-render.
- Riding: the robe lies along the legs like trousers (CLOTH_MOUNTED); the horse collider and the horse-cut variant look almost alike in the 3D preview.
- Leg exposure in the falls is the largest remaining one (die forward 385 px through the cloth over 30 frames).
- The sleeve brightness is 97 against 113 and the lights 155-163 against 180: try uo_contrast_pivot 0.55 and a lighter cloth.
