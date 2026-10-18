# Plan: use the original wearable sprites to calibrate items (not the body)

For the instance that executes it. Read `CLAUDE.md` and the skills `uo-environment-tests`, `uo-client-data`, `uo-items-render`, `uo-open-issues`, `uo-body-skeleton` first. Conversation language: Polish; docs, skills, commits: English.

## Goal and non-goals

**Goal:** items made from foreign `.glb` models fit the original UO body (0x190) sprites better. The `.vd` files of the original wearables (and, later, of other creators) are 2D frames only (no geometry, no depth, no body under the item). So they can give **distributions and calibration data**, not 3D shapes.

**Expected payoff (from the earlier analysis, not yet measured):**
1. Per-slot defaults for autofit / conform (shell offset, sleeve end, hem, height ranges) from statistics of hundreds of originals instead of a few replicas.
2. Calibration of loose garments (robe, dress, kilt, cloak) on many originals instead of one robe (469).
3. A larger, per-slot validation set for `test_items` (now 6 replicas, easy to overfit).
4. A measure "how much of our item lies outside what originals of this slot ever cover" (measure only).

**Non-goals (do not do):**
- No body silhouette fitting, no changes to pose keys (only `pose_natural_fit.py`, natural motion first). The body sprite is already the better reference (body IoU 0.899).
- **No per-frame corrections**: no clamping/masking/shifting of one item in one frame, no `if action == X and frame == Y`. Every change must be a global parameter or algorithm, measured on all frames.
- No changes to light direction/ambient, no AO, no ground shadow.
- Do not commit client data (`anim*.mul`, `*.idx`, `tiledata.mul`), the user's sketches or renders, or third-party `.vd` files. Only aggregated statistics (JSON) and code.

## Rules of work

- Measure, don't trust: record before/after numbers for every change (`docs/qa/baselines.md` thresholds). Never push untested work.
- Commits: `UOModel3D: <what and why>`. Work and push on the branch named at the start of the session (not `main`, unless the user says so). Never push to `claude/friendly-knuth-44xtfw`. No PR unless asked.
- When a rule changes, update the matching skill (`.claude/skills/uo-*`) and `README.md` / `README_PL.md` / `docs/qa/baselines.md`.
- Keep messages to the user short: result, blocker, decision.

## Phase 0 - Environment and baseline (gate for everything else)

1. Set up Python + bpy 4.2 as in `uo-environment-tests`. Download the client as in `uo-client-data` into `uo_client/` (git-ignored, official `unrar` only).
2. Run `python pipeline/run_qa.py` and save the output as the "before" reference (expected: `test_items` 0.723, body parts 0.8993, autofit 13.6 mm, robe 0.757, cloak 0.507, `test_canvas` OK). If anything differs from `docs/qa/baselines.md`, stop and report before changing anything.
3. Inspect what already exists: `client/extract/layer_analysis.json` (385 original animations, **only action 4 stand, frame 0, 5 directions**; fields `cover`, `out[part]` n/p50/p90/max, `zlo/zhi`, `layers`), `client/extract/item_animations.json` (tiledata: layer per animation id, `stats_by_layer`), `pipeline/layer_analysis.py`, `pipeline/layer_analysis_report.py`, `pipeline/item_vs_original.py`, `pipeline/measure_equipment_extent.py`. Note: `client/extract/README.md` mentions `docs/qa/layer_analysis.md`, which was removed from the tree (commit 95ffe57); regenerate it with `layer_analysis_report.py` if needed.
4. Data quality filter (write it down once, reuse everywhere): use only originals (`anim`, `anim2`, `anim4` wearables; skip Nelderim-custom ids such as 420, 422), complete 35x5 animations only (417 of 449), and check each against the body-400 anchor/canvas (256x256, anchor 128,192).

## Phase 1 - Per-slot priors from all actions (offline, no Blender)

Deliverable: `pipeline/layer_priors.py` + `client/extract/layer_priors.json` (aggregated numbers only).

1. Extend the `layer_analysis.py` approach from `stand` to **all 35 actions x 5 directions x all frames** (or a fixed sample: first/middle/last frame per block, if runtime is a problem). Reuse its canvas, anchor, `PXM`, `COS`, part labels (`parts.npz` from `body_part_raster.py`) and the formula `z = 0.07 - row / (36 cos 28.4557)`.
2. Per layer (from `item_animations.json`: Shirt, Pants, Shoes, Gloves, Helm, Arms, Cloak, OuterTorso, MiddleTorso, InnerTorso, OuterLegs, InnerLegs, Waist, Neck ...) and per body part, aggregate: z range (p5/p50/p95), standoff outside the original body silhouette (p50/p90/max; this is a lower bound of the thickness, readable only at arms, legs, hem, neck), cover share, sleeve/hem end heights, and for every statistic the number of items and the spread between items (not only the mean).
3. Sanity checks: results for the stand frame must match the existing `layer_analysis.json` (same code path); report outliers (items with extreme values) and drop them by a stated rule, not by hand.
4. Output a short report `docs/qa/layer_priors.md` (tables per slot). Commit code + JSON + report.

**Gate 1:** the spread between items within a slot must be small enough to be a useful prior (e.g. the p50 standoff of shirts varies by less than ~1 px between items). If most slots are too noisy, stop and report; do not continue to Phase 3-4 on this basis.

## Phase 2 - Does a prior beat the hand-set value? (the real experiment)

`test_items.py` builds replicas as the body skin moved out by a **hand-set `thickness`** (shirt 0.012, plate 0.03, pants 0.012, boots 0.015, gloves 0.03, helm 0.02) and measures IoU vs. the original sprite.

1. Extend `ITEMS` in `test_items.py` with more originals per slot (several shirts, trousers, boots, gloves, helmets, plate parts; the sprite ids come from `item_animations.json`; add the `.vd` of each to `pipeline/body13/mul/` only if it is an original game asset, like the 17 already tracked). Keep the original 6 unchanged so `items_after_natural_fit.json` stays comparable; put the new ones in a second group (`--items`).
2. Run the old thickness vs. the thickness taken from the Phase 1 prior (leave-one-out: the prior for an item is computed **without** that item). Report IoU per item and per slot, before/after.
3. If the prior-derived value is not clearly better (mean IoU up and no slot clearly down), keep the hand-set values, document the result in `docs/qa/layer_priors.md`, and skip Phase 5 for those slots.

**Gate 2 (go/no-go for Phase 5):** at least a measurable improvement on held-out items, not only on the fitted ones.

## Phase 3 - Envelope measure (measure only, never a correction)

Deliverable: `pipeline/item_envelope_qa.py`, output informational at first.

1. For each (layer, action, direction, frame) build the union mask of the originals of that layer on the common canvas (and, for robustness, a "covered by at least k originals" mask).
2. For a rendered item (`RENDER_DIR` as in `item_vs_original.py`), report the share of its pixels outside the union envelope, per action and per slot, plus the worst frames (as a list for the human, not as a trigger for correction).
3. Run it on the six replicas and on the example items in `model/example_clothing` and `model/items` to see whether the number separates good from bad items. Add to `docs/qa/baselines.md` as "informational" with the first value; promote it to a threshold only after it has proved stable.

## Phase 4 - Loose garments on many originals

Open issues: robe physics calibrated on robe 469 (checked on 447 and 970), no kilt test, cloak has no real-model test.

1. List all originals with layers OuterTorso / OuterLegs / Cloak / robes / dresses / skirts / kilts from `item_animations.json`; pick a set with different cuts (long robe, short robe, dress, kilt, short cloak, long cloak).
2. `test_robe.py` and `test_cloak.py` currently use one sprite each (`--sprite`, `pipeline/cloak_pitch.json`). Run them against each original (their radii come from the stand pose of the sprite, as in the docstring), report IoU of the lower part, `wide`, `narrow`, `hem`.
3. Fit the global parameters (`FOLLOW` of the `robe` PART, `outer_shell`, `CLOTH_LIE*`, `SLEEVE_CUFF`, cloak pitch) **on a training half and check on a held-out half**. Accept a change only if it holds on the held-out originals and 469 does not drop below its current value (robe >= 0.74 threshold, last 0.757; cloak >= 0.47, last 0.507).
4. Add a kilt/skirt test (the same replica method, a sprite of an original kilt) and put its first value into `docs/qa/baselines.md`.

## Phase 5 - Apply priors to the item pipeline (only where Gate 2 passed)

1. Replace hand-set defaults in `uo_autofit_item.py` / `uo_conform_item.py` / `uo_import_item.py` (EXTENTS, unit detection, `SLEEVE_END`, shell offset, hem, slot z ranges) by values from `layer_priors.json`, **per slot**. Recipes with explicit values keep winning.
2. Use the same table to address the open slot issues (single slot table; missing Earrings, Ring, Bracelet, Talisman, Backpack; `waist` and `vest` untested): derive the z range and typical extent per slot from the originals, then test with one real model per slot where available.
3. Measure after each change: `test_autofit.py` (<= 20 mm, last 13.6), `test_items.py` (>= 0.715, last 0.723), `test_real_item.py`, `test_import_item.py`, `test_canvas.py` (all OK), `item_clearance.py` on the example items. A change that makes any of them worse is reverted.

## Phase 6 - Third-party `.vd` (only after the user supplies files and confirms the licence)

1. Ask the user for the files, their source and licence; keep them **outside the repo**, one fresh directory per source (untrusted data; read with `python -I`).
2. Intake filter: same canvas/anchor as the original body, complete frames, silhouette IoU with the original body 400 in the stand pose above a stated threshold (otherwise it was fitted to a different body), known layer. Reject the rest and list why.
3. Run Phases 1-4 with originals only and with originals + third-party; report whether the extra data changes the priors or the held-out results. Commit only aggregated numbers, never the files.

## Phase 7 - Close-out

1. Update `docs/qa/baselines.md` (new rows: envelope, kilt, extended items; before/after table like the natural-motion section), `README.md`, `README_PL.md`, and the skills (`uo-items-render`, `uo-open-issues`) for every rule that changed.
2. Run `python pipeline/run_qa.py` in full; all thresholds green; push to the session branch; report to the user in 5-8 lines: what improved (numbers), what did not (and was dropped), what is left.

## Stop conditions

- Gate 1 or Gate 2 fails: report with the numbers and stop; do not force the priors into the pipeline.
- Any baseline in Phase 0 differs from `docs/qa/baselines.md`: stop and report.
- A needed change would touch pose keys, light, or require a per-frame fix: stop and ask the user.
