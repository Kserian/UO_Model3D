# Original wearable animations vs body 400 (`vd_scan.py`)

Regenerate: `body_part_raster.py ../model/UO_Body_0x190.blend parts.npz`, `vd_scan.py <client> scan.json --parts parts.npz`, `vd_scan_report.py scan.json docs/qa/vd_scan.md client/extract/vd_scan_layers.json`.
Sanity: for the stand action the per-part cover equals `client/extract/layer_analysis.json` (frame 0 only; median |diff| 0.000, p95 0.031 over 3465 values).
Reading: the standoff outside the silhouette is a LOWER bound of the item thickness (inside the silhouette the item hides the body) and is integer (1 px = 2.78 cm). Clothing (shirt, pants, shoes, gloves, arms, helm, torso armour) has p50 = 1 px at every part with p10-p90 = 1-1: there is no spread to calibrate a thickness from; only loose parts (cloak, robes, dresses, hair, hand-held items) stand out further. Bands are proportional to the body bbox of the frame (head ... feet); parts are the nearest part of OUR 3D body.

393 animations with frames (anim 160, anim2 26, anim3 58, anim4 90, anim5 59), 211 tiledata animations without data in the client; 412001 frames over 35 actions x 5 directions.
Complete (all 35 x 5 blocks): 378; incomplete: 15 (anim3:619: 1 actions, anim3:625: 2 actions, anim4:421: 6 actions, anim4:432: 5 actions, anim4:433: 5 actions, anim5:602: 1 actions, anim5:603: 1 actions, anim5:631: 30 actions, anim:619: 1 actions, anim:622: 1 actions, anim:629: 2 actions, anim:638: 2 actions, anim:800: 26 actions, anim:803: 23 actions, anim:906: 23 actions).
Frame count differs from the body 400 in some blocks: anim2:570 (21 actions), anim4:655 (2 actions).
Frames without image (placeholder or empty): 1295 in 80 animations.
Pixels outside the 256x256 canvas (anchor 128,192): anim2:570 28164 px, anim3:620 1026 px, anim4:464 152 px.

Tiledata animations with no frames (item invisible in this client), by layer: 0 1, 15 26, Arms 10, Backpack 1, Bracelet 3, Cloak 3, Earrings 4, FacialHair 4, Gloves 12, Hair 28, Helm 9, InnerTorso 10, MiddleTorso 3, Neck 15, OneHanded 35, OuterLegs 1, OuterTorso 8, Pants 12, Ring 3, Shirt 5, Shoes 6, Talisman 13, TwoHanded 48, Waist 2.

## Stand (action 4), per layer: median [p10-p90] between animations

| layer | n | cover of body | outside share | z top (m) | z bottom (m) | standoff p50 (px) | standoff p90 (px) | max (px) |
|---|---|---|---|---|---|---|---|---|
| Arms | 14 | 0.235 [0.131-0.273] | 0.116 [0.051-0.202] | 1.70 [1.65-1.74] | 0.83 [0.80-0.86] | 1.0 [1.0-1.0] | 1.0 [1.0-2.0] | 2.0 [2.0-2.7] |
| Cloak | 5 | 0.126 [0.064-0.325] | 0.473 [0.102-0.521] | 1.74 [1.62-1.83] | 0.89 [0.34-1.14] | 2.0 [1.0-2.6] | 5.0 [1.8-7.4] | 7.0 [2.4-12.8] |
| Earrings | 1 | 0.062 [0.062-0.062] | 0.399 [0.399-0.399] | 1.97 [1.97-1.97] | 1.59 [1.59-1.59] | 1.0 [1.0-1.0] | 3.0 [3.0-3.0] | 4.0 [4.0-4.0] |
| FacialHair | 11 | 0.023 [0.009-0.035] | 0.067 [0.047-0.127] | 1.74 [1.71-1.78] | 1.46 [1.37-1.52] | 1.0 [1.0-1.0] | 1.0 [1.0-1.0] | 1.0 [1.0-2.0] |
| Gloves | 10 | 0.052 [0.013-0.153] | 0.176 [0.000-0.551] | 1.18 [1.11-1.43] | 0.73 [0.54-0.80] | 1.0 [0.0-2.1] | 1.0 [0.0-7.1] | 1.0 [0.0-9.1] |
| Hair | 37 | 0.072 [0.039-0.114] | 0.190 [0.086-0.412] | 1.90 [1.89-1.97] | 1.52 [1.21-1.62] | 1.0 [1.0-1.0] | 2.0 [1.0-3.0] | 2.0 [1.0-3.4] |
| Helm | 60 | 0.087 [0.050-0.139] | 0.328 [0.069-0.602] | 1.93 [1.90-2.10] | 1.48 [1.30-1.65] | 1.0 [1.0-3.0] | 3.0 [1.0-5.0] | 4.0 [1.0-7.1] |
| InnerTorso | 28 | 0.241 [0.180-0.518] | 0.114 [0.014-0.231] | 1.68 [1.65-1.78] | 0.83 [0.57-1.04] | 1.0 [1.0-1.0] | 2.0 [1.0-3.0] | 2.0 [1.0-5.0] |
| MiddleTorso | 7 | 0.355 [0.165-0.567] | 0.136 [0.060-0.156] | 1.71 [1.62-1.71] | 0.67 [0.65-0.95] | 1.0 [1.0-1.0] | 1.0 [1.0-2.0] | 3.0 [1.0-3.4] |
| Neck | 11 | 0.021 [0.017-0.044] | 0.018 [0.000-0.062] | 1.68 [1.62-1.74] | 1.43 [1.37-1.46] | 1.0 [0.0-1.0] | 1.0 [0.0-1.0] | 1.0 [0.0-1.0] |
| OneHanded | 53 | 0.017 [0.006-0.046] | 0.602 [0.419-0.814] | 1.49 [1.21-1.74] | 0.67 [0.39-0.77] | 5.0 [1.0-8.0] | 12.0 [3.0-20.8] | 14.0 [4.0-26.8] |
| OuterLegs | 7 | 0.309 [0.253-0.475] | 0.210 [0.189-0.289] | 1.24 [1.21-1.30] | 0.48 [0.06-0.51] | 1.0 [1.0-1.0] | 3.0 [2.6-3.0] | 5.0 [4.6-6.0] |
| OuterTorso | 26 | 0.881 [0.665-0.990] | 0.213 [0.123-0.328] | 1.87 [1.68-1.98] | -0.02 [-0.10-0.09] | 1.0 [1.0-2.0] | 2.5 [2.0-6.0] | 6.0 [4.0-11.5] |
| Pants | 30 | 0.384 [0.167-0.434] | 0.108 [0.062-0.231] | 1.21 [1.18-1.27] | 0.07 [0.01-0.58] | 1.0 [1.0-1.0] | 1.0 [1.0-3.0] | 2.0 [1.9-4.0] |
| Shirt | 13 | 0.368 [0.140-0.441] | 0.071 [0.010-0.165] | 1.68 [1.65-1.71] | 0.83 [0.59-1.06] | 1.0 [1.0-1.0] | 1.0 [1.0-2.0] | 2.0 [1.2-3.8] |
| Shoes | 10 | 0.143 [0.088-0.226] | 0.198 [0.034-0.262] | 0.50 [0.28-0.64] | -0.09 [-0.09--0.06] | 1.0 [1.0-1.0] | 1.0 [1.0-1.1] | 1.5 [1.0-2.2] |
| TwoHanded | 66 | 0.063 [0.014-0.184] | 0.646 [0.513-0.794] | 1.68 [1.27-2.38] | 0.42 [-0.09-0.70] | 4.0 [2.0-6.5] | 8.0 [5.0-17.0] | 12.0 [7.0-26.0] |
| Waist | 8 | 0.074 [0.052-0.116] | 0.101 [0.027-0.219] | 1.22 [1.18-1.28] | 0.72 [0.41-0.99] | 1.0 [1.0-1.0] | 1.5 [1.0-2.3] | 1.5 [1.0-3.6] |

## Stand, per layer and body part: share of the part covered (median [p10-p90]) and standoff p50 / p90 (px, median of the animations that have outside pixels at that part, n of them)

| layer | part | cover | n out | standoff p50 | standoff p90 |
|---|---|---|---|---|---|
| Arms | torso | 0.18 [0.04-0.26] | 2 | 1.0 [1.0-1.0] | 3.5 [2.3-4.7] |
| Arms | upper_arm | 0.83 [0.23-0.98] | 10 | 1.0 [1.0-1.0] | 1.5 [1.0-2.1] |
| Arms | forearm | 0.70 [0.57-0.86] | 7 | 1.0 [1.0-1.4] | 1.0 [1.0-2.6] |
| Cloak | head | 0.06 [0.01-0.06] | 2 | 2.5 [2.1-2.9] | 5.5 [5.1-5.9] |
| Cloak | neck | 0.48 [0.15-0.66] | 0 | - | - |
| Cloak | torso | 0.33 [0.20-0.54] | 4 | 2.0 [1.3-2.7] | 5.0 [3.6-7.8] |
| Cloak | upper_arm | 0.11 [0.03-0.44] | 3 | 2.0 [1.2-2.0] | 5.0 [3.4-5.0] |
| FacialHair | head | 0.18 [0.09-0.29] | 0 | - | - |
| FacialHair | neck | 0.13 [0.02-0.18] | 0 | - | - |
| Gloves | forearm | 0.27 [0.10-0.75] | 4 | 1.0 [1.0-1.7] | 1.0 [1.0-3.8] |
| Gloves | hand | 0.54 [0.13-0.90] | 3 | 1.0 [1.0-1.8] | 1.0 [1.0-4.2] |
| Hair | head | 0.59 [0.45-0.81] | 32 | 1.0 [1.0-1.0] | 2.0 [1.0-3.0] |
| Hair | neck | 0.36 [0.01-0.82] | 0 | - | - |
| Helm | head | 0.78 [0.55-0.96] | 53 | 1.0 [1.0-3.0] | 3.0 [1.2-5.0] |
| Helm | neck | 0.32 [0.00-0.95] | 0 | - | - |
| InnerTorso | neck | 0.58 [0.13-0.85] | 0 | - | - |
| InnerTorso | torso | 0.69 [0.48-0.99] | 18 | 1.0 [1.0-1.0] | 2.0 [1.0-2.0] |
| InnerTorso | upper_arm | 0.42 [0.15-0.72] | 13 | 1.0 [1.0-2.0] | 2.0 [2.0-4.0] |
| InnerTorso | forearm | 0.08 [0.00-0.41] | 2 | 5.5 [1.9-9.1] | 12.0 [3.2-20.8] |
| MiddleTorso | head | 0.07 [0.01-0.16] | 1 | 1.0 [1.0-1.0] | 2.0 [2.0-2.0] |
| MiddleTorso | neck | 0.77 [0.44-0.99] | 0 | - | - |
| MiddleTorso | torso | 0.91 [0.43-0.99] | 6 | 1.0 [1.0-1.0] | 1.0 [1.0-2.0] |
| MiddleTorso | upper_arm | 0.33 [0.05-1.00] | 4 | 1.0 [1.0-1.0] | 2.0 [1.3-2.0] |
| MiddleTorso | forearm | 0.18 [0.09-0.84] | 3 | 1.0 [1.0-1.0] | 1.0 [1.0-1.8] |
| MiddleTorso | hand | 0.22 [0.03-0.30] | 0 | - | - |
| MiddleTorso | thigh | 0.31 [0.00-0.47] | 5 | 1.0 [1.0-1.0] | 1.0 [1.0-2.6] |
| Neck | head | 0.07 [0.03-0.18] | 0 | - | - |
| Neck | neck | 0.54 [0.03-0.78] | 0 | - | - |
| OneHanded | forearm | 0.05 [0.01-0.15] | 19 | 1.0 [1.0-5.6] | 4.0 [2.0-14.0] |
| OneHanded | hand | 0.33 [0.16-0.42] | 44 | 8.5 [1.0-13.0] | 13.5 [3.0-22.0] |
| OuterLegs | torso | 0.40 [0.37-0.48] | 7 | 1.0 [1.0-1.0] | 2.0 [1.6-4.0] |
| OuterLegs | forearm | 0.21 [0.12-0.23] | 0 | - | - |
| OuterLegs | hand | 0.21 [0.20-0.23] | 0 | - | - |
| OuterLegs | thigh | 0.87 [0.81-1.00] | 7 | 1.0 [1.0-1.0] | 3.0 [2.6-4.0] |
| OuterTorso | head | 0.81 [0.02-1.00] | 15 | 1.0 [1.0-1.0] | 2.0 [1.0-3.6] |
| OuterTorso | neck | 0.92 [0.49-1.00] | 0 | - | - |
| OuterTorso | torso | 0.98 [0.89-1.00] | 26 | 1.0 [1.0-1.0] | 2.0 [1.0-4.0] |
| OuterTorso | upper_arm | 0.96 [0.93-1.00] | 23 | 1.0 [1.0-1.0] | 1.0 [1.0-2.0] |
| OuterTorso | forearm | 0.82 [0.24-1.00] | 23 | 1.0 [1.0-1.0] | 1.0 [1.0-2.0] |
| OuterTorso | hand | 0.26 [0.20-0.99] | 8 | 1.0 [1.0-7.4] | 2.0 [1.7-11.8] |
| OuterTorso | thigh | 1.00 [0.93-1.00] | 25 | 1.0 [1.0-2.0] | 3.0 [2.0-5.2] |
| OuterTorso | shin | 1.00 [0.82-1.00] | 24 | 1.0 [1.0-2.7] | 3.0 [2.0-8.9] |
| OuterTorso | foot | 0.60 [0.09-1.00] | 24 | 1.0 [1.0-2.0] | 3.0 [2.0-5.4] |
| Pants | torso | 0.34 [0.28-0.42] | 18 | 1.0 [1.0-1.0] | 1.0 [1.0-2.3] |
| Pants | forearm | 0.12 [0.10-0.19] | 0 | - | - |
| Pants | hand | 0.18 [0.11-0.22] | 2 | 1.0 [1.0-1.0] | 2.0 [2.0-2.0] |
| Pants | thigh | 0.98 [0.43-1.00] | 27 | 1.0 [1.0-1.4] | 1.0 [1.0-3.0] |
| Pants | shin | 0.88 [0.00-0.99] | 18 | 1.0 [1.0-1.0] | 1.0 [1.0-2.0] |
| Shirt | head | 0.08 [0.02-0.14] | 2 | 2.0 [1.2-2.8] | 3.5 [2.3-4.7] |
| Shirt | neck | 0.88 [0.21-1.00] | 0 | - | - |
| Shirt | torso | 0.83 [0.12-0.91] | 6 | 1.0 [1.0-1.0] | 2.0 [1.5-2.0] |
| Shirt | upper_arm | 0.64 [0.22-0.96] | 5 | 1.0 [1.0-1.0] | 2.0 [1.0-2.0] |
| Shirt | forearm | 0.42 [0.01-0.76] | 2 | 1.0 [1.0-1.0] | 1.5 [1.1-1.9] |
| Shoes | shin | 0.57 [0.12-0.96] | 6 | 1.0 [1.0-1.0] | 1.0 [1.0-2.0] |
| Shoes | foot | 0.94 [0.86-1.00] | 7 | 1.0 [1.0-1.0] | 1.0 [1.0-1.4] |
| TwoHanded | torso | 0.05 [0.00-0.18] | 47 | 4.0 [3.0-6.0] | 8.0 [6.0-11.4] |
| TwoHanded | forearm | 0.10 [0.03-0.58] | 30 | 3.0 [1.0-4.0] | 6.0 [3.9-9.1] |
| TwoHanded | hand | 0.29 [0.16-0.47] | 54 | 3.0 [2.0-8.1] | 6.0 [4.0-16.0] |
| TwoHanded | thigh | 0.06 [0.00-0.27] | 46 | 3.0 [2.0-4.0] | 5.0 [4.0-9.5] |
| Waist | torso | 0.20 [0.14-0.26] | 3 | 1.0 [1.0-1.0] | 1.0 [1.0-1.8] |
| Waist | forearm | 0.06 [0.04-0.12] | 0 | - | - |
| Waist | thigh | 0.06 [0.00-0.18] | 3 | 1.0 [1.0-1.0] | 2.0 [1.2-2.0] |

## All 35 actions, per layer: extent from the anchor (px, min / max over the animations of the layer) and median cover of the body

| layer | n | left (min) | right (max) | up (min) | down (max) | median cover | median outside share |
|---|---|---|---|---|---|---|---|
| Arms | 14 | -64 | 57 | -82 | 31 | 0.225 | 0.122 |
| Cloak | 5 | -62 | 59 | -75 | 38 | 0.137 | 0.441 |
| Earrings | 1 | -68 | 67 | -82 | 33 | 0.064 | 0.395 |
| FacialHair | 11 | -59 | 59 | -75 | 27 | 0.023 | 0.076 |
| Gloves | 10 | -69 | 57 | -86 | 34 | 0.057 | 0.175 |
| Hair | 37 | -68 | 66 | -81 | 33 | 0.072 | 0.170 |
| Helm | 60 | -86 | 81 | -99 | 53 | 0.095 | 0.293 |
| InnerTorso | 28 | -108 | 99 | -192 | 55 | 0.252 | 0.106 |
| MiddleTorso | 7 | -62 | 55 | -79 | 30 | 0.360 | 0.146 |
| Neck | 11 | -58 | 58 | -74 | 27 | 0.021 | 0.016 |
| OneHanded | 53 | -108 | 94 | -121 | 54 | 0.025 | 0.658 |
| OuterLegs | 7 | -43 | 42 | -60 | 21 | 0.342 | 0.254 |
| OuterTorso | 26 | -128 | 128 | -192 | 64 | 0.821 | 0.243 |
| Pants | 30 | -69 | 65 | -84 | 34 | 0.360 | 0.135 |
| Shirt | 13 | -66 | 64 | -82 | 35 | 0.362 | 0.071 |
| Shoes | 10 | -30 | 34 | -56 | 18 | 0.143 | 0.198 |
| TwoHanded | 66 | -115 | 128 | -138 | 64 | 0.051 | 0.670 |
| Waist | 8 | -44 | 43 | -60 | 23 | 0.080 | 0.145 |

## Per action: animations with data, median cover of the body and standoff p90 (px), over all layers except hand-held

| action | name | animations | median cover | median standoff p90 | blocks with frame-count mismatch |
|---|---|---|---|---|---|
| 0 | walk_unarmed | 274 | 0.126 | 2.0 | 0 |
| 1 | walk_armed | 275 | 0.128 | 2.0 | 1 |
| 2 | run_unarmed | 275 | 0.130 | 2.0 | 1 |
| 3 | run_armed | 275 | 0.129 | 2.0 | 1 |
| 4 | stand | 275 | 0.126 | 2.0 | 1 |
| 5 | fidget_1 | 274 | 0.125 | 2.0 | 0 |
| 6 | fidget_2 | 274 | 0.125 | 2.0 | 0 |
| 7 | combat_idle_1h | 274 | 0.133 | 2.0 | 0 |
| 8 | combat_idle_2h | 275 | 0.136 | 2.0 | 1 |
| 9 | attack_1h_slash | 275 | 0.132 | 2.0 | 1 |
| 10 | attack_1h_pierce | 275 | 0.126 | 2.0 | 1 |
| 11 | attack_1h_bash | 275 | 0.125 | 2.0 | 1 |
| 12 | attack_2h_bash | 275 | 0.135 | 2.0 | 1 |
| 13 | attack_2h_slash | 275 | 0.129 | 2.0 | 1 |
| 14 | attack_2h_pierce | 275 | 0.133 | 2.0 | 1 |
| 15 | combat_advance | 274 | 0.133 | 2.0 | 0 |
| 16 | spell_directed | 274 | 0.133 | 2.0 | 0 |
| 17 | spell_area | 274 | 0.118 | 2.0 | 0 |
| 18 | attack_bow | 275 | 0.131 | 2.0 | 2 |
| 19 | attack_crossbow | 275 | 0.130 | 2.0 | 2 |
| 20 | get_hit | 275 | 0.123 | 2.0 | 1 |
| 21 | die_forward | 275 | 0.141 | 2.0 | 1 |
| 22 | die_backward | 275 | 0.130 | 2.0 | 1 |
| 23 | mounted_walk | 275 | 0.131 | 2.0 | 1 |
| 24 | mounted_run | 275 | 0.128 | 2.0 | 1 |
| 25 | mounted_stand | 275 | 0.134 | 2.0 | 1 |
| 26 | mounted_attack_1h | 275 | 0.130 | 2.0 | 1 |
| 27 | mounted_attack_bow | 275 | 0.134 | 2.0 | 1 |
| 28 | mounted_attack_crossbow | 274 | 0.133 | 2.0 | 0 |
| 29 | mounted_attack_2h | 274 | 0.125 | 2.0 | 0 |
| 30 | block | 274 | 0.131 | 2.0 | 0 |
| 31 | punch | 274 | 0.130 | 2.0 | 0 |
| 32 | bow | 274 | 0.137 | 2.0 | 0 |
| 33 | salute | 274 | 0.126 | 2.0 | 0 |
| 34 | eat | 274 | 0.130 | 2.0 | 0 |

## Outliers in the stand frames (outside the Tukey fences of their layer on cover or standoff p90; layers with >= 5 animations)

| layer | animation | metric | value | fences | items |
|---|---|---|---|---|---|
| Arms | anim4:656 | cover | 0.423 | 0.07..0.38 | ,  |
| Arms | anim4:656 | standoff p90 | 6.000 | -0.50..3.50 | ,  |
| Cloak | anim:468 | cover | 0.432 | -0.07..0.30 | cloak, cloak |
| Cloak | anim:468 | standoff p90 | 9.000 | 0.00..8.00 | cloak, cloak |
| FacialHair | anim:803 | standoff p90 | 0.000 | 1.00..1.00 | mustache, mustache |
| Gloves | anim4:657 | cover | 0.486 | -0.11..0.23 | ,  |
| Gloves | anim4:453 | standoff p90 | 8.000 | -0.88..2.12 | stare rekawice |
| Gloves | anim4:657 | standoff p90 | 7.000 | -0.88..2.12 | ,  |
| Hair | anim:701 | cover | 0.180 | -0.00..0.14 | Long Hair |
| Helm | anim4:499 | cover | 0.213 | -0.01..0.18 | Vale_Haunted_South, Vale_Haunted_East |
| Helm | anim5:427 | cover | 0.912 | -0.01..0.18 | 15AnnRobe SOUTH, 15AnnRobe EAST |
| Helm | anim2:550 | standoff p90 | 9.000 | -1.00..7.00 | Khal_Ankur_Mask_east, Khal_Ankur_Mask_sout |
| Helm | anim:415 | standoff p90 | 18.000 | -1.00..7.00 | deer mask, deer mask |
| InnerTorso | anim4:655 | standoff p90 | 32.000 | -0.50..3.50 | ,  |
| OneHanded | anim:615 | cover | 0.059 | -0.01..0.05 | hatchet, hatchet |
| OneHanded | anim:616 | cover | 0.110 | -0.01..0.05 | heavy crossbow, heavy crossbow |
| OneHanded | anim:646 | cover | 0.066 | -0.01..0.05 | war hammer, war hammer |
| OneHanded | anim:649 | cover | 0.073 | -0.01..0.05 | bow, bow |
| OneHanded | anim:651 | cover | 0.064 | -0.01..0.05 | crossbow, crossbow |
| OuterLegs | anim4:443 | standoff p90 | 2.000 | 3.00..3.00 | Hakama, Hakama |
| OuterTorso | anim3:444 | cover | 0.582 | 0.60..1.10 | Dress_Wed_Human_Fema |
| OuterTorso | anim3:597 | cover | 0.371 | 0.60..1.10 | tabard |
| OuterTorso | anim4:457 | cover | 0.551 | 0.60..1.10 | Hakama-Shita, Hakama-Shita |
| OuterTorso | anim2:570 | standoff p90 | 47.000 | 0.50..4.50 | Parrot_Epaulets_Sout, Parrot_Epaulets_East |
| OuterTorso | anim3:481 | standoff p90 | 8.000 | 0.50..4.50 | Dress_Wedding_Human_, Dress_Wedding_Human_ |
| OuterTorso | anim:994 | standoff p90 | 9.000 | 0.50..4.50 |  |
| Pants | anim4:658 | standoff p90 | 4.000 | -0.50..3.50 | ,  |
| Shirt | anim4:682 | standoff p90 | 5.000 | -0.50..3.50 | amazon armor, amazon armor |
| Shoes | anim:476 | cover | 0.337 | 0.01..0.25 | thigh boots, thigh boots |
| Shoes | anim3:436 | standoff p90 | 2.000 | 1.00..1.00 | Shoes_Jester |
| TwoHanded | anim5:522 | cover | 1.000 | -0.10..0.23 | scale shield |
| TwoHanded | anim:582 | cover | 0.238 | -0.10..0.23 | heater shield, heater shield |
| TwoHanded | anim3:933 | standoff p90 | 29.000 | -4.88..24.12 | bladed staff, bladed staff |
| TwoHanded | anim:972 | standoff p90 | 30.000 | -4.88..24.12 | fishing pole, fishing pole |

34 outlier entries.
