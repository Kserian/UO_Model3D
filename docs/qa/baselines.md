# QA baselines (essence only)

Run all: `python pipeline/run_qa.py` (`--quick` skips items and canvas). Needs bpy 4.2, numpy, scipy, pillow.

| Check | Script | Metric | Threshold | Last value |
|---|---|---|---|---|
| items | `test_items.py` | mean IoU of 6 item replicas vs original sprites | >= 0.715 | 0.723 (`items_after_natural_fit.json`) |
| body parts | `body_part_raster.py` + `body_part_qa.py` | IoU of body parts, 1050 frames | - | 0.8993 (`body_parts_after_natural_fit.json`) |
| pose errors | `pose_lib.py qa` | pixels off by >= 2 px from the other silhouette, 1050 frames | not above the last value | 2049 |
| natural motion | `pose_naturalness.py` | mean zig-zag (deg) of head / neck / hand.R, shoulder slide R (cm) | not above the last value | 4.8 / 8.7 / 24.2, 2.5 |
| canvas | `test_canvas.py` | every case pixel-identical to reference | all OK | OK |
| autofit | `test_autofit.py` | mean vertex error, 12 foreign replicas | <= 20 mm | 13.6 mm |
| robe | `test_robe.py` | lower-body IoU vs original robe 469 | >= 0.74 | 0.757 |
| cloak | `test_cloak.py` | silhouette IoU vs original cloak 468 (swing from `pipeline/cloak_pitch.json`) | >= 0.47 | 0.507 |
| materials | `test_materials.py` | "RESULT OK" | - | OK |
| import | `test_import_item.py` | chain from a foreign file runs, bbox as before | no error | OK |

Items per replica (IoU): shirt 0.715, plate 0.699, trousers 0.801, boots 0.771, gloves 0.572, helmet 0.782.

Natural motion refit (`pose_natural_fit.py`, 2026-10-16; before -> after): body IoU 0.8991 -> 0.8994, >= 2 px errors 2211 -> 2049, walk (0 / 1) zig-zag head 1.9 / 2.4 -> 1.0 / 0.6 deg, neck 5.3 / 4.4 -> 1.3 / 1.4, hand.R 29 / 35 -> 3.1 / 2.4, helmet point jump 1.74 / 1.81 -> 1.08 / 1.28 px, upper-arm twist R 18 / 13 -> 9 / 9 deg, clavicle location 2.6 / 2.2 -> 0 cm. Action 17 (symmetric arms) and 25 kept; frame 9/1 kept (test_canvas).

Mounted head yaw (`head_scan.py`, `pose_natural_fit.py` with HEAD_YAW_W=100 HEAD_LAMBDA=20, actions 23 / 24 only; before -> after): head yaw against the chest vs mounted stand 12-17 / 21-30 deg -> <= 3 / <= 8.5 deg (24, frame 0, is held by the silhouette), body IoU of the action 0.8893 -> 0.8863 / 0.8858 -> 0.8829 (whole 0.8994 -> 0.8993), zig-zag head 0.78 / 2.83 -> 0.74 / 2.44, neck 2.2 / 4.3 -> 0.7 / 1.8, helmet point jump 2.69 / 3.94 -> 2.59 / 3.89 px, waste_neck 2.96 / 3.20 -> 1.59 / 2.68. A weaker silhouette tolerance (HEAD_TOL 0.008) removed the frame-0 remainder but cost 0.0059 IoU in action 24: rejected.

Second group of original replicas (`test_items.py --items <name>`, not in the default run; Phase 2, `docs/qa/prior_thickness.json`, stand + attack_1h_slash, hand-set thickness): mean IoU of the 22 new ones 0.684, of all 27 0.694; they are informational (no threshold).

Envelope (`item_envelope_qa.py`, informational, no threshold): share of the item outside the union of the originals of its slot, mean over frames: six replicas 0.000-0.013 (gloves 0.138), example shirt 0.008; a wrong slot 0.42-0.72 (`docs/qa/item_envelope.md`).
