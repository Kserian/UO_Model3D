---
name: uo-items-render
description: Item pipeline from free 3D models (uo_make_item.py, JSON recipes, autofit, conform, robes), texture quality, UO_Look lighting, materials, mesh density and weights. Use when adding/fixing an item or changing render, lighting or materials.
---

- One command: `python pipeline/uo_make_item.py recipe.json --preview` (recipe: `file`, `kind` or `weapon`, `skip`/`keep`; `--list` shows the meshes). Chain: `uo_import_item.py` (`PLACE = wrap`) → `uo_materials.py` → `uo_prepare_item.py` (`uo_autofit_item.py`, densify, fit with `LIMIT`, bind) → `render_uo_layer.py`. Weapon: `uo_orient_weapon.py` → `uo_place_weapon.py` → `uo_bind_item.py`. Measurements: `docs/qa/autofit.md`. `PLACE = height` only for items similar to the reference.
- Robe from a cloth simulator (solid made of panels): `"outer_shell": 0.006` + `"conform"` + `"prepare": {"HEM": 0.15}` (`docs/qa/robe_black.md`); what the user sees is measured by `item_body_holes.py`.
- Shirts/tunics from another mannequin: `"conform"` (`uo_conform_item.py`: sleeves onto arm axes, wrap 1.5 cm off the skin, render keeps 8 mm off the skin); check with preview `all`, measure with `item_clearance.py`, `docs/qa/jedi_tunic.md`. `"conform": {"SLEEVE_END": 0.02}` shortens or lengthens the sleeves to end 2 cm past the wrist (gambeson: they ended 9 cm short; arm skin in the 3D check fell ~3x).
- Mesh/weights: densify low-poly (`uo_densify_item.py`), weights like the skin underneath (SMOOTH 4, STIFF 1).
- Texture quality: 512 samples (adaptive, threshold 0.002, min 64), no `DESPECKLE`, rim `OUTLINE_TARGET` (edge/one pixel deeper = 0.38; an own `uo_outline` wins), Standard tone mapping. `test_items` 0.723, `test_canvas` 16/16 (`docs/qa/render_quality.md`).
- Light: keep `UO_Look` (Lambert, L = (0.0012, −0.7572, 0.6532), ambient 0.0798). Specular only on metal (`uo_materials.py`). No AO, no ground shadow.
