# Repository review, 2026-10-20 (branch model_fixing5)

Method: every `pipeline/*.py` was searched for by module name in all tracked files (imports, subprocess calls, README, skills, docs); every path and `*.py` name written in the `.md` files and skills was checked against `git ls-files`. Nothing was deleted: this is a list for decision.

## 1. Scripts with no reference anywhere (13)
Not imported, not run by another script, not named in README, skills or docs. All are from 2026-10-12..14 (one-off analyses of the earlier work).

| Script | What it does (docstring) | Remark |
|---|---|---|
| `action_overlay.py` | overlay sheet of the 3D body against the original frames | diagnostic |
| `arm_mismatch.py` | arm-region mismatch per frame | diagnostic |
| `hand_fit_joint.py` | hand / finger pose shared by frames of an action | uses `hand_fit.py`; nothing uses it |
| `iou_action.py` | silhouette IoU per frame of one action | 12 lines, `body_part_qa.py` does more |
| `item_look.py` | shading / noise of an item against the sprites | diagnostic |
| `light_fit.py` | light fit on 880 original frames | result is in `uo-open-issues`: "do not change the light" |
| `split_model.py` | split a one-mesh model (cuirass + pauldrons) | may still be useful for foreign models |
| `stretch_glb.py` | scale a .glb | may still be useful for foreign models |
| `test_bind_sweep.py` | SMOOTH / STIFF weight sweep | decision made (weight variants did not help) |
| `test_tall_item.py` | 3.5 m pole on the 256 canvas | covered by `test_canvas.py` |
| `uo_render_gump_ragged.py` | paperdoll gump of the torn robe | its doc `docs/qa/robe_ragged.md` was removed |
| `uo_render_weapon_gump.py` | weapon paperdoll gump and item art (364 lines) | imports `uo_grey_metal.py`, `uo_hue_preview.py` (only users of them) |
| `weapon_motion_add.py` | put a fitted class into `weapon_motion.json` | part of the weapon calibration chain |

Scripts used only by one of the unreferenced ones: `hand_fit.py` (by `hand_fit_joint.py`), `uo_grey_metal.py`, `uo_hue_preview.py` (by `uo_render_weapon_gump.py`), `flail_fit.py` (calibration of the flail simulation `uo_flail.py`, which the renderer uses: keep). `light_items.py`, `body_silhouette_qa.py`, `test_density.py` are named in comments of other scripts (measurement tools, not dead).

## 2. Dead links: documents removed in `95ffe57` ("remove docs folder (requested by user)")
README.md, README_PL.md and the skills still point to them (20 / 21 / 10 mentions):
`docs/AUDYT_2026-10-03.md`, `docs/RAPORT_model3D_UO.txt`, `docs/qa/{arm_poses, autofit, cloak_physics, dress_meshy, dress_meshy_recipe.json, elbow_spell, jedi_tunic, layer_analysis, layer_priors, light_shadow, render_quality, robe_black, robe_physics, robe_ragged, slot_geometry, weapon_roll}.md`.
`docs/plans/original_items_calibration.md` mentions `pipeline/item_envelope_qa.py`, `pipeline/layer_priors.py`, `client/extract/layer_priors.json` (never in the repo: an unfinished plan). `README` names `pipeline/body13/build_v13.py` (absent; `pipeline/body13/mul/*.vd` stay).
Fixed in this commit: the robe paragraph of both READMEs, `cloth_lib.py` rows, the `uo_cloth_bake.py` mention (the script does not exist), the robe line of `uo-body-skeleton`. The other links are left: removing them is a decision about each sentence.

## 3. Stale text in code
- `uo_cloth_sim.py` docstring: says mounted actions are not simulated (key `mounted=1` simulates them) and points to `docs/qa/robe_physics.md`.
- `uo_cloth_sim.py` CFG defaults (goal 0.4, mscale 1, pushw 1, in_max 0.01, preroll 40) are not the settings that worked (t1: see README section 3); a robe made with `uo_make_item.py` and no `"sim"` gets the old ones.
- `robe_cloth_sim_test.py`, `robe_hull_eval.py`, `robe_calib.py`: experiments on the replica of robe 469 (the first one says itself "nothing in the render uses it"); their results live in the removed `robe_physics.md`.
- `pipeline/test_data/ref_render_uo_layer_ea55c0b.py.txt`: reference renderer for `test_canvas.py` (used, keep).

## 4. Data
- `client/extract/light_items.json`: referenced by nothing (produced by `light_items.py`).
- `client/extract/defs/Bodyconv.def.bak-vd2anim2`: a backup copy, named in `client/extract/README.md` only.
- `docs/paperdoll/*.png`, `model/example_clothing/podglad_koszula_na_oryginale.png`: referenced by nothing (images).
- Large: `model/UO_Body_0x190.blend` 14 MB, `docs/qa/robe_variants_screenshots_2026-10.pdf` 6 MB (renders of the user's robe; CLAUDE.md says not to commit those), `pipeline/uo_original_frames.json` 1.9 MB, `pipeline/UO_Original_Atlas.png` 1.5 MB, `pipeline/body13/mul` 13 MB (used by `cloak_calib.py` and others).
- Remote branches: `ccr-a6e2abad-4gys94`, `model-fixing4`, `model_fixing5`, `main`.

## 5. Proposal
1. Delete the 13 unreferenced scripts and the helpers only they use (`hand_fit.py`, `uo_grey_metal.py`, `uo_hue_preview.py`) (or move to `pipeline/archive/`), keep `split_model.py` and `stretch_glb.py` if foreign-model work continues.
2. Remove the dead `docs/...` links from README (EN, PL) and the skills, keeping the facts the sentences carry.
3. Update the `uo_cloth_sim.py` docstring and make t1 the default CFG (needs a re-test of `test_robe.py`, threshold 0.74).
4. Decide whether the screenshots PDF stays in the repo.
