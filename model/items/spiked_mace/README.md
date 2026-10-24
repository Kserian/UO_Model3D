# Two-handed spiked mace (staff-like, held in the middle)

Made from one free image-to-3D model (`spiked_mace.glb`, 12 MB, **not in the repo**: keep it in `models/spiked_mace.glb` outside the repo when re-running; Meshy AI export, record the licence of the source).

Rebuild: `python pipeline/uo_make_item.py model/items/spiked_mace/spiked_mace.json --out OUT --vd`

- Part `polearm` (bone `polearm.L`, motion calibrated on the original staffs / spears / halberds), class `staff`, length 1.8 m, `"tip": "heavy"` (the spiked head is the heavy end), `"butt": -0.9` = the hands sit in the middle of the shaft (the staff default holds it 41% from the butt).
- Preview (6 actions x 3 directions x 3 moments) checked by eye: shaft held in the middle in combat idle, 2H slash / pierce / bash, run and death.
- QA (`item_qa.py`): inside the body 3.5 % (worst: area spell), deepest 125 mm.

## Files

- `Spiked_mace_all_actions.vd`: all 35 actions x 5 directions (rebuild: `uo_make_item.py spiked_mace.json --vd`, ~15 min).

## Tuning notes (2026-10-24)

- Grip: `"butt": -1.05` (hands 1.05 m from the butt = 0.57 m below the head): closer to the ball in 2H idle and 2H bash.
- `follow_hand` (`uo_follow_hand.py`) re-keys `polearm.L` every frame: the grip follows the hand joint, the shaft turns with the hand but the twist about the shaft is removed (no wrist screw, no spin, no 300 deg flips). Mounted actions 23-29: first frame = shaft up and out (`dir` 0.3, -0.1, 1), the hand 0.5 m from the butt, so the lower end stays out of the horse. 20, 21, 22, 30-34 (hit, deaths, block, punch, bow, salute, eat): the first frame is the original key, so the weapon keeps its direction and sense; the original keys of the repo rig put the weapon 10-50 cm off the fitted hand and flip it by 300 deg in these actions (measured). Attacks / spells (9-19) keep the calibrated original motion; 14 and 19 still flip once (not changed).
- Wood: `shaft_wood` (procedural light wood on the lower 72 % of the shaft where the original texture is dark; steel and the head keep the model's texture). Shaft thickness is the model's own (`shaft_widen` is available but off: +1 px was too thick). Outline: `uo_outline` 0.5, `uo_edge_floor` 52 (soft, dark grey on the ball, never black).
