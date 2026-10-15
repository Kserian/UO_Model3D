---
name: uo-przedmioty-render
description: Potok tworzenia przedmiotów (zbroje, ubrania, broń, szaty) z darmowych modeli 3D, uo_make_item.py, przepisy JSON, autofit, conform, jakość tekstur, światło UO_Look, materiały, gęstość siatki i wagi. Użyj przy dodawaniu/naprawie przedmiotu, zmianie renderu, światła lub materiałów.
---

# Przedmioty i render: decyzje (ustalone z użytkownikiem)

| Temat | Decyzja |
|---|---|
| Przedmioty | Użytkownik używa darmowych modeli 3D. Jedno polecenie: `python pipeline/uo_make_item.py przepis.json --preview` (przepis: `file`, `kind` albo `weapon`, `skip`/`keep`; `--list` pokazuje siatki pliku). Łańcuch: `uo_import_item.py` (`PLACE = wrap`) -> `uo_materials.py` -> `uo_prepare_item.py` (**`uo_autofit_item.py`** skala/miejsce z kształtu skóry, densify, fit z miękkim limitem grubości `LIMIT`, bind) -> `render_uo_layer.py`. Broń: `uo_orient_weapon.py` -> `uo_place_weapon.py` -> `uo_bind_item.py`. Pomiary: `docs/qa/autofit.md`. Skala z jednej wysokości na slot (`PLACE = height`) jest tylko dla przedmiotów podobnych do wzorca |
| Szata z symulatora tkaniny | Zamknięta bryła z osobnych paneli: `"outer_shell": 0.006` (remesh, warstwa zewnętrzna, tekstura wypalona) + `"conform"` + `"prepare": {"HEM": 0.15}`. Przepis i pomiary: `docs/qa/robe_black.md`; to, co widzi użytkownik (warstwa ubrania na oryginalnym `body400`), mierzy `item_body_holes.py` |
| Koszule / tuniki z innego manekina | Przepis `"conform"` (`uo_conform_item.py`: rękawy na osie rąk, owinięcie 1,5 cm od skóry, pełna waga ramienia do 2 cm od skóry ręki, dalej 35%, render trzyma 8 mm od całej skóry w każdej klatce). Kontrola: podgląd `all` z kolorowymi częściami ciała; `docs/qa/jedi_tunic.md`, miara `item_clearance.py` |
| Gęstość siatki i wagi | Przedmiot low-poly zagęszczany (`uo_densify_item.py`), wagi jak skóra pod spodem (SMOOTH 4, STIFF 1): sprite'y nie odróżniają polityk wag (±0,002) |
| Jakość tekstur przedmiotów | (2026-10-14, użytkownik: „jak najlepsza jakość tekstury”) render z 512 próbkami (adaptacyjnie, próg 0,002, min. 64; przy 1 próbce połysk metalu szumiał), bez `DESPECKLE` (zjadał detale tekstury), obwódka liczona na cały render tak, by krawędź / piksel głębiej = 0,38 jak w oryginałach UO (`OUTLINE_TARGET`; własne `uo_outline` ma pierwszeństwo). Tone mapping zostaje Standard (Khronos PBR Neutral odbiega od UO). `test_items` 0,723, `test_canvas` 16/16; `docs/qa/render_quality.md` |
| Światło UO | Zostaje `UO_Look`: Lambert, L = (0,0012; −0,7572; 0,6532), ambient 0,0798 (zmierzone na 880 klatkach ciała i 393 animacjach). Odblask tylko na metalu (`uo_materials.py`). Brak AO i cienia na ziemi |
