---
name: uo-przedmioty-render
description: Potok przedmiotów z darmowych modeli 3D (uo_make_item.py, przepisy JSON, autofit, conform, szaty), jakość tekstur, światło UO_Look, materiały, siatka i wagi. Użyj przy dodawaniu/naprawie przedmiotu lub zmianie renderu/światła.
---

- Jedno polecenie: `python pipeline/uo_make_item.py przepis.json --preview` (przepis: `file`, `kind` albo `weapon`, `skip`/`keep`; `--list` pokazuje siatki). Łańcuch: `uo_import_item.py` (`PLACE = wrap`) → `uo_materials.py` → `uo_prepare_item.py` (`uo_autofit_item.py`, densify, fit z `LIMIT`, bind) → `render_uo_layer.py`. Broń: `uo_orient_weapon.py` → `uo_place_weapon.py` → `uo_bind_item.py`. Pomiary: `docs/qa/autofit.md`. `PLACE = height` tylko dla przedmiotów podobnych do wzorca.
- Szata z symulatora (bryła z paneli): `"outer_shell": 0.006` + `"conform"` + `"prepare": {"HEM": 0.15}` (`docs/qa/robe_black.md`); widok użytkownika mierzy `item_body_holes.py`.
- Koszule/tuniki z innego manekina: `"conform"` (`uo_conform_item.py`: rękawy na osie rąk, owinięcie 1,5 cm od skóry, render trzyma 8 mm od skóry); kontrola: podgląd `all`, miara `item_clearance.py`, `docs/qa/jedi_tunic.md`.
- Siatka/wagi: low-poly zagęszczaj (`uo_densify_item.py`), wagi jak skóra (SMOOTH 4, STIFF 1).
- Jakość tekstur: 512 próbek (adaptacyjnie, próg 0,002, min. 64), bez `DESPECKLE`, obwódka `OUTLINE_TARGET` (krawędź/piksel głębiej = 0,38; własne `uo_outline` ma pierwszeństwo), tone mapping Standard. `test_items` 0,723, `test_canvas` 16/16 (`docs/qa/render_quality.md`).
- Światło: zostaje `UO_Look` (Lambert, L = (0,0012; −0,7572; 0,6532), ambient 0,0798). Odblask tylko na metalu (`uo_materials.py`). Brak AO i cienia na ziemi.
