# Two-handed spiked mace (staff-like, held in the middle)

Made from one free image-to-3D model (`spiked_mace.glb`, 12 MB, **not in the repo**: keep it in `models/spiked_mace.glb` outside the repo when re-running; Meshy AI export, record the licence of the source).

Rebuild: `python pipeline/uo_make_item.py model/items/spiked_mace/spiked_mace.json --out OUT --vd`

- Part `polearm` (bone `polearm.L`, motion calibrated on the original staffs / spears / halberds), class `staff`, length 1.8 m, `"tip": "heavy"` (the spiked head is the heavy end), `"butt": -0.9` = the hands sit in the middle of the shaft (the staff default holds it 41% from the butt).
- Preview (6 actions x 3 directions x 3 moments) checked by eye: shaft held in the middle in combat idle, 2H slash / pierce / bash, run and death.
- QA (`item_qa.py`): inside the body 3.5 % (worst: area spell), deepest 125 mm.
