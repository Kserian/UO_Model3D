# QA baselines (essence only)

Run all: `python pipeline/run_qa.py` (`--quick` skips items and canvas). Needs bpy 4.2, numpy, scipy, pillow.

| Check | Script | Metric | Threshold | Last value |
|---|---|---|---|---|
| items | `test_items.py` | mean IoU of 6 item replicas vs original sprites | >= 0.715 | 0.722 (`items_after_head_smooth.json`) |
| body parts | `body_part_raster.py` + `body_part_qa.py` | IoU of body parts, 1050 frames | - | 0.899 (`body_parts_after_head_smooth.json`) |
| canvas | `test_canvas.py` | every case pixel-identical to reference | all OK | OK |
| autofit | `test_autofit.py` | mean vertex error, 12 foreign replicas | <= 20 mm | 13.6 mm |
| robe | `test_robe.py` | lower-body IoU vs original robe 469 | >= 0.74 | 0.757 |
| cloak | `test_cloak.py` | silhouette IoU vs original cloak 468 (swing from `pipeline/cloak_pitch.json`) | >= 0.47 | 0.507 |
| materials | `test_materials.py` | "RESULT OK" | - | OK |
| import | `test_import_item.py` | chain from a foreign file runs, bbox as before | no error | OK |

Items per replica (IoU): shirt 0.715, plate 0.691, trousers 0.802, boots 0.770, gloves 0.579, helmet 0.776.
