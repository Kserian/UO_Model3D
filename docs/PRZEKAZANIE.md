# Przekazanie sesji 15 (2026-10-03/04): przedmioty z darmowych modeli, szaty, peleryna, grubość

Dla następnej instancji. Zasady i decyzje: `CLAUDE.md` (nadrzędne). Tu: co zrobiono, co zmierzono, co odrzucono, co dalej. Stan kodu = `main` (ostatni commit sesji `73b2e92`).

## Zlecenie użytkownika
Przejrzeć projekt i ulepszyć tworzenie przedmiotów UO z darmowych modeli 3D; fizyka luźnych ubrań (szata) ma odtwarzać grę (nogi pchają tkaninę do przodu, umiarkowanie, zgodnie z ruchem nóg), skalibrowana na plikach klienta (`anim*.mul`).
Pliki użytkownika były tylko **próbkami** do sprawdzenia potoku (gambeson z manekinem, napierśnik Void Knight, zbroja Dread Dragon z OBJ 144k wierzchołków, hełm, miecz, muszkiet z 7 siatek, uprząż na miecz Wiedźmina): ulepszamy narzędzia pod **przyszłe** przedmioty,
a fizykę badamy na **oryginalnych** przedmiotach z klatek. Reguły: nadmiar elementów usuwać lub ustawiać, siatka gęsta (bez kanciastych animacji), przedmiot nie za gruby, ciało nie przebija, tkanina bez błędów (nogi nie wypychają za daleko, bez skoków między klatkami), oglądać wiele klatek, nie tylko stand. Komunikaty krótkie.

## Co jest nowe (wszystko na `main` i `claude/eloquent-keller-gj4g5b`)
1. **Jedno polecenie do przedmiotu:** `python pipeline/uo_make_item.py przepis.json [--preview|--vd] [--no-qa]` (`--list` pokazuje siatki pliku, `--preview` to arkusz, `--vd` pełny render; **nie łącz** preview z vd). Przepis: `file`, `kind` albo `weapon`, `skip`/`keep` (`=nazwa` = dokładne dopasowanie), `reference`+`parts` (wieloczęściowe: manekin jako wzorzec dopasowania), `tune` (`{"uo_fit_item.py": {"LIMIT": 0.04}}` -> env `UO_PREPARE_EXTRA`). Po przygotowaniu `item_qa.py` (przenikanie, odstęp) -> `qa.json`.
2. **Autodopasowanie `uo_autofit_item.py`:** skala, położenie i obrót 0/180° obcego modelu z kształtu skóry slotu (odległość ze znakiem po normalnych, deadband ±3 mm, kara za przebicie 3×, strefy slotu, priorytety skali). Test `test_autofit.py` na replikach: błąd wierzchołka 53,4 mm (stara metoda z jednej wysokości) -> **13,6 mm**. Sloty: shirt, plate, harness, arms, pants, legs, boots, gloves, helm, hat, hair, beard, neck, robe, skirt, cloak, waist, vest, quiver. Tabele `*_BY_KIND` w skrypcie; env `UO_AUTOFIT_<NAZWA>`.
3. **Import** (`uo_import_item.py`): `PLACE=wrap` (domyślnie; `height` tylko dla przedmiotów podobnych do wzorca), wykrywanie jednostek (0,15-3 m), `DECIMATE_TO=30000`, `KEEP`. **Bez scipy** (GUI Blendera) import schodzi na `PLACE=height`, a `uo_prepare_item` pomija autofit z ostrzeżeniem.
4. **Grubość** (`uo_fit_item.py`): miękki limit `LIMIT`/`LIMIT_K`/`LIMIT_BY_KIND` + `MIN_GAP`. Ta sesja: `LIMIT_K` 0,35 -> 0,30, plate 0,08 -> 0,05. Miara: `pipeline/item_thickness.py` (odstęp na klatkach od sylwetki oryginalnego ciała, p50/p90 w cm, porównywalny z oryginalnymi sprite'ami). Oryginały p90: koszula 3,9, plate 5,6 (p50 2,8), spodnie 2,8, hełm 3,9, ręce 6,2, nogi 5,6, buty 3,9, rękawice 3,9, spódnica 16,9, peleryna 48, szata 469 16,7.
   Nasze: Void Knight 11,5 -> **8,8** (p50 zostaje 5,6: model ma duże naramienniki), Dread Dragon 8,8 -> 8,3, gambeson 5,6, replika szaty 18,6. Ostrzejsze limity (3 cm K 0,5; 4 cm K 0,3) niewiele zmieniają. Szczegóły: `docs/qa/autofit.md`.
5. **Szaty i spódnice** (`cloth_lib.py`, `PART robe/skirt`, `uo_cloth`): dół wisi od miednicy; per klatka powłoka nóg (kapsuły ud i goleni, bez stóp) -> funkcja podparcia po kącie i wysokości -> „namiot” od pasa (`drop` 1,0 m/m) -> pchnięcie promieniowe `kappa·(h+margin−rho)`. Margines/kappa zależą od wysokości rąbka (długa szata 0,05/0,8, kilt 0,02/0,5, mieszane między 0,15 a 0,30 m). **Bez pamięci klatek** (nie ma czego akumulować, brak przeskoków: krok tkaniny / krok nóg mediana 0,72, max 1,15).
   Jazda (akcje 23-29): rąbek podąża za nogami wagami jak skóra (`uo_leg_*`, `CLOTH_MOUNTED`). Pomiar na oryginale 469 (Cycles): IoU dolnej części 0,613-0,641 -> **0,757**, błąd szerokości rąbka 11,1 -> 3,4 px; hull poprawia IoU na wszystkich 5 oryginalnych szatach/spódnicach/kiltach (+0,008…+0,043). Dokument: `docs/qa/robe_physics.md`.
6. **Peleryna** (nowe, `docs/qa/cloak_physics.md`): oryginał 468 w biegu i galopie **leci poziomo za plecami**; powłoka nóg nic nie daje (0,395 -> 0,393). Model: odchylenie do tyłu wokół linii ramion, kąt `phi0` na ramionach i `phi1` na rąbku (środek = całka kąta, tkanina się wygina), **tabela per akcja i klatka względem stand (20°/0°)** w `pipeline/cloak_pitch.json`, dopasowana `cloak_fit_frames.py` do 35 akcji × 5 kierunków naraz.
   `PART cloak` w `uo_bind_item.py` (`mark_cloak` -> `uo_cloth` typ `cloak`), `cloth_lib.cloak_bend`, gałąź w `render_uo_layer.cloth_push` (stała `CLOAK_SWING`, 0 = bez ruchu), slot `cloak` (krawędź górna na **1,52 m**; na duszku góra wygląda na 1,6, bo tył jest rzutowany wyżej). Test `test_cloak.py` (w `run_qa.py`, próg 0,47): IoU repliki 0,376 -> **0,507**, bieg 0,21 -> 0,49, galop 0,18 -> 0,51, atak/czar/upadek 0,45/0,47/0,32 -> 0,50/0,53/0,43; najlepszy możliwy na klatkę 0,604.
7. **Broń z darmowych modeli:** `uo_orient_weapon.py` (SVD osi długiej, czubek = węższy koniec, płaska strona +X; długości klas **zmierzone na oryginalnych broniach**: 1H 0,83-1,31 m, drzewcowe 2,4-2,7, łuk 1,34, kusza 1,09-1,44; tabela `LENGTHS`), potem `uo_place_weapon.py` + `uo_bind_item.py` (weapon1h -> `weapon1h.R`, bow -> `bow.L`). `docs/qa/weapons_free_models.md`.
8. **Render:** funkcje `uo_behind_torso` / `uo_no_body_gap` (przedmioty za plecami, sztywne), `body_fix` działa też gdy są luźne ubrania; osadzony skrypt w `.blend` daje piksel w piksel to samo co plik.
9. **Narzędzia QA:** `run_qa.py [--quick]` (items, canvas, autofit, robe, cloak, materials, import; `--quick` pomija items i canvas, ok. 6 min taniej), `item_sheet.py`, `item_gif.py`, `pose_capture.py` (macierze skórowania do numpy bez Blendera), `robe_calib.py`, `cloak_calib.py`, `cloak_fit_frames.py`, `test_robe.py`, `test_cloak.py`, `test_autofit.py`, `test_import_item.py`, `item_qa.py`, `item_thickness.py`.
   Stan testów na koniec: `test_items` 0,718 (bez zmian), `test_canvas` 16/16 OK, `test_materials` OK, `run_qa --quick` PASSED (autofit 13,6 mm, robe 0,757, cloak 0,507, import 18,2 mm).

## Wnioski do zapamiętania
- **Metoda:** zawsze liczba z własnego pomiaru przed/po (replika oryginału -> obcy plik -> odzysk; sylwetka vs duszek). Mierzone na klatkach, nie na siatce: „grubość” = piksele poza sylwetką oryginalnego ciała.
- **Duszek a z:** przedmioty za plecami rzutują się wyżej na ekranie (głębia 0,2 m ≈ +9 cm), więc „górna krawędź duszka” ≠ wysokość fizyczna.
- **Peleryna to pochylenie per akcja, nie kolizja i nie bezwładność klatka-klatka.** Tabela jest względna do stand, żeby model z własnym kształtem spoczynkowym dostał tylko zmianę. Kształt repliki do dopasowania wybrany siatką parametrów (szeroka rura 0,33×0,30 m, łuk ±75°, rąbek 0,30 m).
- Zbroje są ok. 2× za grube względem oryginału głównie przez **kształt modelu** (naramienniki, wypukłość), a nie brak limitu; dalsze zmniejszanie to ścinanie detali.
- 3-5% wierzchołków zbroi bywa w ciele w ruchu (do 11 cm w ataku); render wypycha je (`BODY_GAP`), więc sprite'y są czyste. Warianty wag nie pomogły.

## Odrzucone eksperymenty (nie powtarzać bez nowego powodu)
Solver PBD i grawitacyjne zwisanie szaty; podążanie szaty za udem (alfa), wiatr/opór, rampa marginesu; hull dla peleryny (brak efektu); zmiana jasności metalu w `uo_materials` (niezmierzona, cofnięta); sztuczne „flat” peleryny (spłaszczanie rury) dawało +0,02 IoU kosztem nieuogólniającej się wartości; priorytet krawędzi 1,17 m dominował testy replik (EDGE_WEIGHT 0,05); normalne skóry orientowane centroidem części łamały pary nóg/rąk (teraz z nawijania trójkątów całego ciała).

## Pułapki
- `.blend` zapisuj `bpy 4.2`; po zmianie skryptu `python pipeline/sync_blend_scripts.py model/UO_Body_0x190.blend <skrypt...>` (nowy plik tekstowy, np. `cloak_pitch.json`, też trzeba wymienić z nazwy). `--check` pokazuje różnice. `uo_prepare_item.source()` preferuje `UO_SCRIPTS` (pliki) przed kopią w `.blend`.
- Argparse nie przyjmuje ujemnych offsetów w osobnym argumencie: `--offset=-0,1,...`. `KEEP` bez `=` to podciąg (`defaultMaterial.*` pasuje do wszystkiego).
- Kilka renderów równolegle na tym samym `.blend` jest OK, ale **nie syncuj** w trakcie renderu.
- `pkill -f` z wzorcem z własnej komendy zabija powłokę; wzorzec w nawiasach `[w]zorzec`.
- Sketche użytkownika leżą poza repo (licencje nieznane): nie commitować ich ani wyników renderu.

## Otwarte (kolejność wg wartości)
1. Prawdziwy darmowy model szaty, peleryny i kiltu: żaden z mechanizmów nie był testowany na cudzym modelu tych slotów (peleryna tylko na syntetycznym `.glb` i replice).
2. Falowanie boków peleryny i bezwładność (tabela jest funkcją akcji i klatki); tylko jedna oryginalna peleryna (468), nie wiadomo czy inne trzepoczą inaczej.
3. Małe sloty: Earrings, Ring, Bracelet, Talisman, Backpack (wykrywanie jednostek zakłada 0,15-3 m); jedna tabela slotów (`docs/AUDYT_2026-10-03.md`, pkt 5-6). `waist`/`vest` ustawione przez analogię, niemierzone.
4. Naramienniki jako ciągła siatka z korpusem rozciągają się z ramieniem w czarach.
5. Pierwszy prawdziwy darmowy model (włosy Curuaty, CC BY 4.0: użytkownik pobiera i wrzuca, zapisać atrybucję).
6. Body 401 (kobieta) w `anim.mul` prawie kopia męskiego; sprawdzić w grze przed ciałem kobiecym.
