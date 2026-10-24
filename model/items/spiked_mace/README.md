# Two-handed spiked mace (staff-like, held in the middle)

Made from one free image-to-3D model (`spiked_mace.glb`, 12 MB, **not in the repo**: keep it in `models/spiked_mace.glb` outside the repo when re-running; Meshy AI export, record the licence of the source).

Rebuild: `python pipeline/uo_make_item.py model/items/spiked_mace/spiked_mace.json --out OUT --vd`

- Part `polearm` (bone `polearm.L`, motion calibrated on the original staffs / spears / halberds), class `staff`, length 1.8 m, `"tip": "heavy"` (the spiked head is the heavy end), `"butt": -0.9` = the hands sit in the middle of the shaft (the staff default holds it 41% from the butt).
- Preview (6 actions x 3 directions x 3 moments) checked by eye: shaft held in the middle in combat idle, 2H slash / pierce / bash, run and death.
- QA (`item_qa.py`): inside the body 3.5 % (worst: area spell), deepest 125 mm.

## Files

- `Spiked_mace_6_actions.vd`: 5 directions of `12_attack_2h_bash`, `01_walk_armed`, `03_run_armed`, `23_mounted_walk`, `24_mounted_run`, `25_mounted_stand` (rebuild with `--vd --actions 12_attack_2h_bash,01_walk_armed,03_run_armed,23_mounted_walk,24_mounted_run,25_mounted_stand`). Length 1.62 m, spikes inflated 1.2 cm (`inflate`), outline floor 40.

## Tuning notes (2026-10-24)

- Grip: `"butt": -1.05` (hands 1.05 m from the butt = 0.57 m below the head): closer to the ball in 2H idle and 2H bash.
- Mounted actions (23-29): `follow_hand` re-keys `polearm.L` rigid on `hand.L` (`uo_follow_hand.py`, reference = mean hand-relative transform in `01_walk_armed`). The keys of the repo rig follow the original weapons, which sit 10-50 cm off the fitted hand in the mounted actions.
- Wood: `shaft_tint` (lower 72 % of the shaft x (2.3, 1.9, 1.4)); the head stays steel. Shaft thickness is the model's own (`shaft_widen` is available but off: +1 px was too thick). Outline: `uo_outline` 0.5, `uo_edge_floor` 52 (soft, dark grey on the ball, never black).
