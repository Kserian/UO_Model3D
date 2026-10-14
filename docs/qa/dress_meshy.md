# Suknia balowa z Meshy (slot `robe`), 2026-10-14

Model: `Meshy_AI_Blue_Bow_Belle_1014091851_texture.glb`, wygenerowany przez użytkownika w Meshy (poza repo). Jedna siatka: 1,13 mln wierzchołków, 1,90 × 1,54 × 1,80 m,
tekstura 2048 px (kolor, metal / szorstkość, normalne). Suknia balowa na krynolinie, bufiaste rękawy do łokcia z koronką, falbany przy rąbku, wzór w kwiaty.
Przepis: `docs/qa/dress_meshy_recipe.json` (uruchamiany z katalogu z `.glb`). Pełny `--preview` (4 akcje) ok. 20 min (symulacja tkaniny 8 min), render warstwy 4 akcji 3,5 min.

```
python pipeline/uo_make_item.py dress_meshy_recipe.json --out OUT --preview --actions 04_stand,00_walk_unarmed,02_run_unarmed,09_attack_1h_slash
python pipeline/run_render_headless.py OUT/item.blend CL 'LAYER="clothing"' 'ONLY=["04_stand","00_walk_unarmed","02_run_unarmed","09_attack_1h_slash"]' 'CANVAS=(256,256)' 'ANCHOR=(128,192)'
python pipeline/item_look.py CL/clothing --originals 447,469
```

## Pierwsza wersja
Przepis czarnej szaty (`robe_black.md`) z trzema zmianami: `"tune": {"uo_autofit_item.py": {"TURN_BACK": false}}` (autofit obrócił suknię tyłem, wynik AMBIGUOUS), `HEM` 0,04
(suknia do ziemi) i `HEM_FLARE` 0,85 (rąbek 1,96 -> 1,71 m; użytkownik: „nie zwężaj sukni za bardzo, bo to taki styl”).
Uwagi użytkownika: „złagodź krawędzie, żeby nie były takie true black, dodaj cieniowania, trochę głębi, lepiej dopasuj, rozrywają się rękawy”.

## Zmiany (zmierzone; stanie + chód, 55 klatek)
| Problem | Przyczyna | Zmiana | Wynik |
|---|---|---|---|
| Rękawy rozdarte, dziury przy barkach z tyłu | `uo_conform_item.py` brał za rękaw wszystko dalej niż bark + 5 cm i wyżej niż bark − 60 cm, przy sukni balowej także górę spódnicy (484 i 503 wierzchołki). Oś „rękawa” wyszła 75° od ręki, koniec 40-48 cm za nadgarstkiem, `SLEEVE_END` ścisnął ostatnie 25 cm ×0,35-0,40, a `SLEEVE_CUFF` ściągnął „mankiet” z promienia 34-43 cm do 5 cm | `sleeve_piece`: z tych wierzchołków tylko kawałek siatki zaczynający się najbliżej stawu barkowego (i to, co go dotyka w 2 cm, np. osobny mankiet); przesunięcie rękawa nie sięga dalej niż jego koniec. Z przepisu usunięte `SLEEVE_CUFF` (ściskał dolną bufkę) | rękaw 6° od ręki (prawdziwy kierunek), bez skracania; krawędzie rozciągnięte względem modelu p99 6,06 -> 1,40, max 38,2 -> 3,7; `item_clearance` najgłębiej 249,8 -> 111,5 mm; `item_qa` 2,8 -> 1,5 % |
| Czarne krawędzie | automatyczna obwódka (`OUTLINE_TARGET` 0,38) jest jak w oryginałach (suknia 447: obwódka / piksel głębiej 0,41, 24 % pikseli obwódki ciemniejszych niż 24) | przepis `"scene": {"uo_outline": 0.75}` (na życzenie użytkownika, tylko ten przedmiot; kaptur ma 0,65) | obwódka / piksel głębiej 0,38 -> 0,62, średnia jasność obwódki 51 -> 78, pikseli < 24: 2 % -> 0 % |
| Płasko, bez głębi | światło UO pada prawie od kamery (L = 0,0012; −0,7572; 0,6532), więc pionowe fałdy prawie nie zmieniają N·L; spódnica modelu jest gładka (fałdy 2-3 cm na 10-20 cm) | `uo_conform_item.py` `OCCLUSION` (ten sam mechanizm co kaptur, `uo_hood_cover.occlusion_share` / `apply_shade`): kolor × (1 − 1,0 × udział promieni trafiających w 15 cm), nie niżej niż `SHADE_MIN` 0,35; światło UO bez zmian | `item_look` shade 17,2 -> 18,5 (oryginały: 447 26,9, 469 21,5), średnia 147 -> 139 |
| (próba) | szczegół oryginału (falbany, koronka, mapa normalnych Meshy) ginie w remeshu i decymacji | mapa normalnych oryginału wypalona przy teksturze (próba w tej sesji; w `main` jest już `BAKE_NORMAL` z sesji szaty podartej, z rozmyciem i bez mapy splotu, plus `BAKE_AO`) | w tej skali prawie bez zmian (sama mapa ×3 + cień własny 0,15: shade 16,0 -> 16,4). Liczby v3 w tej tabeli są z tą mapą |

Warianty głębi (geometria v2 bez symulacji, `item_look` shade): bez 16,0; mapa normalnych ×3 + cień własny 0,15: 16,4; `OCCLUSION` 0,8 / 6 cm: 17,0; 0,8 / 10 cm: 17,6;
**1,0 / 15 cm: 18,7**; 1,0 / 25 cm: 18,9. Na widocznej powierzchni 6-10 cm przyciemnia tylko o 0-20 % (mediana 2-4 %): zagłębienia sukni są szersze niż w kapturze.

## Otwarte
- Pełne `.vd` (35 akcji, ok. 1 h) nierenderowane; tylko podgląd 4 akcji.
- Głębia nadal poniżej oryginalnych sukni (447 ma drobne pionowe plisy, 1-3 px); model Meshy ich nie ma.
