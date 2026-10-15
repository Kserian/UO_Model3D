# QA baselines (essence only)

Run all: `python pipeline/run_qa.py` (`--quick` skips items and canvas). Needs bpy 4.2, numpy, scipy, pillow.

| Check | Script | Metric | Threshold | Last value |
|---|---|---|---|---|
| items | `test_items.py` | mean IoU of 6 item replicas vs original sprites | >= 0.715 | 0.723 (`items_after_smooth_fit.json`) |
| body parts | `body_part_raster.py` + `body_part_qa.py` | IoU of body parts, 1050 frames | - | 0.900 (`body_parts_after_smooth_fit.json`) |
| canvas | `test_canvas.py` | every case pixel-identical to reference | all OK | OK |
| autofit | `test_autofit.py` | mean vertex error, 12 foreign replicas | <= 20 mm | 13.6 mm |
| robe | `test_robe.py` | lower-body IoU vs original robe 469 | >= 0.74 | 0.757 |
| cloak | `test_cloak.py` | silhouette IoU vs original cloak 468 (swing from `pipeline/cloak_pitch.json`) | >= 0.47 | 0.507 |
| materials | `test_materials.py` | "RESULT OK" | - | OK |
| import | `test_import_item.py` | chain from a foreign file runs, bbox as before | no error | OK |

Items per replica (IoU): shirt 0.715, plate 0.691, trousers 0.802, boots 0.770, gloves 0.579, helmet 0.776.

Motion smoothness (`action_smooth_fit.py`, 2026-10-15): body IoU 0.8991 -> 0.9001, errors >= 2 px 2210 -> 2158, helmet point jump 1.64 -> 1.60 px, neck/head zig-zag in walk 5.3 -> 2.0 / 1.9 -> 1.6 deg. Actions 6, 11, 12, 14, 16, 22, 24 kept as before (their >= 2 px errors rose); 17 untouched.
