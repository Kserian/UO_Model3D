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

10. **Detale tekstury (sesja 15, po prośbie użytkownika):** renderer `DESPECKLE` (domyślnie 28: pojedyncze ciemne piksele wewnątrz przedmiotu przejmują kolor otoczenia) kasował zapięcie przodu gambesonu (paski, guziki, ściegi); render ma 1 próbkę na piksel, a pasek ma ok. 1 px. Teraz `uo_prepare_item.py` ustawia własność sceny `uo_despeckle = 0` dla klas `tight`/`loose` (tkanina, skóra), a `render_uo_layer.py` ją czyta; zbroje (`hard`) zostają przy 28 (nity, głębokie fałdy). Nadpisanie w przepisie: `"tune": {"scene": {"uo_despeckle": 0}}`.
11. **Wygląd materiału (sesja 15, uwagi użytkownika o gambesonie: brak zapięcia, szum, brak głębi/cieniowania):** w `uo_materials.py`:
    (a) **błąd:** `Metallic` z tekstury (glTF metallicRoughness) był zawsze liczony jako metal, więc każdy taki przedmiot dostawał odblask `c^16` (białe plamy); teraz liczona jest średnia kanału (`linked_mean`), gambeson 0,0003 = nie metal, hełm = metal;
    (b) filtr tekstur `TEXTURE_FILTER`: tekstura gęstsza niż 54 tekseli/m (1,5 tekselu na piksel sprite'a) jest uśredniana pudełkiem (kolor i normalna z renormalizacją; pomijane: Alpha, <=128 px); render ma 1 próbkę na piksel, więc 1024 px na 1 m dawało szum, a cienkie paski/guziki pojawiały się i znikały;
    (c) `NORMAL_MAP`: mapa normalnych modelu oświetla przedmiot (`UO_Look_N`, wejście `Normal`); efekt mały po filtrowaniu (reliefu modelu prawie nie ma);
    (d) **cień własny** `SHADOW = 0.4` (zmierzone na oryginałach, `docs/qa/light_shadow.md`): grupa `UO_Look_NS` = emisja `amb + (1-amb)·s·c` + Diffuse oświetlony Słońcem rzucającym cień; Słońce `UO_Sun` tworzy `render_uo_layer.shadow_sun()` (siła `π(1-amb)(1-s)`, zmierzone: promieniowanie = albedo·E·cosθ/π; emisyjne materiały mają wtedy `emission_sampling NONE` i `diffuse_bounces 0`, inaczej szum). Test: `test_materials.py` przypadek `shadow` (cień trzyma 0,50 światła). Na gambesonie cień ma 1,9% pikseli (jak w oryginałach 3,3%).
    Miara: `pipeline/item_look.py` (shade = kontrast kształtu, noise = ziarno): gambeson przed 20,2 / 20,6 (z fałszywym odblaskiem), po 16,3 / 16,1; oryginały: szata 449 25,4 / 25,7, 469 21,5 / 17,6, płyta 527 22,3 / 15,0. **Głębia nadal poniżej oryginałów** (16 vs 21-25): oryginalne szaty mają głębokie fałdy w geometrii, a gambeson to gładka powłoka z płaskim reliefem; gamma światła nic nie daje (16,9-17,2). Jedyna droga to geometria fałd (np. rzeźba lub symulacja tkaniny), nie materiał.
    Uwaga: `DESPECKLE` (zob. wyżej, p. 10) i pułapka: `ps | grep` z wzorcem we własnej pętli `until` zawiesza komendę, bo wiersz polecenia zawiera ten wzorzec.

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

# Sesja 16 (2026-10-04): pomiar fizyki szaty (szczegóły: `docs/qa/robe_physics.md`, „Sesja 16")
Zlecenie: odwzorować z gry fizykę szaty i ruchy nóg; użytkownik dopuszcza symulację i pola sił, a rzeczy nieprzylegające do ciała (peleryny) mogą mieć nieco inną animację.
Wynik: **render bez zmian** (`test_robe` 0,757). Sprawdzone i odrzucone (nie powtarzać bez nowego powodu): tabela wychylenia rąbka per klatka dopasowana na 469+447+970 (to szum kształtu repliki, po odjęciu stand gorsza), sprężyna z tłumieniem (rąbek goni cel), regresja na prędkościach nóg.
Wdrożenie powłoki względem spoczynku nóg (`robe_hull_eval.py`) remisuje w `test_robe`. Nowe narzędzie: `pipeline/robe_hull_eval.py` (5 oryginalnych szat, ~1 min, wzorce 447/455/970/971 w `body13/mul/`).
Dalej: prawdziwy darmowy model szaty / kiltu (test na cudzym kształcie), potem ewentualnie symulacja z kolizją.

## Sesja 16, ciąg dalszy: symulacja tkaniny wdrożona (`pipeline/uo_cloth_sim.py`)
Na żądanie użytkownika ("szata ma się dobrze układać, ciało nie przebija, chód naturalny z realnym materiałem") luźne ubrania dostają hybrydową symulację Blendera (cel = kształt z powłoki nóg, kolizja z ciałem, miękki limit 0,12 m), szczegóły i pomiary: `docs/qa/robe_physics.md`, "Sesja 16: symulacja hybrydowa". `uo_make_item.py` robi to domyślnie dla `robe` / `skirt` (`--no-sim`, recepta `"sim"`), render czyta `cloth_sim.npz` obok `item.blend`.
Nowe opcje importu (recepta): `drop_materials` (wycięcie pasa z jednej siatki), `arms_down` (T-poza: kości ramion własnego szkieletu modelu, w zapasie obrót siatki), `arm_blend`; `materials.TEXTURE_PX` (uśrednienie tekstury). Modele testowe użytkownika (robe_free.glb, Myrddin_robe.fbx) nie są w repo (licencje nieznane).
Otwarte: boczne "skrzydła" rąbka w biegu poza zasięgiem nóg (oryginał), rękawy dzwonowe (kolizja z tułowiem, samokolizja wyłączona), wybrzuszenie uda w biegu na wąskiej szacie, symulacja nie obejmuje akcji konnych i peleryny.

## Sesja 17: pas z mieczem i sztyletem (`docs/qa/belt_swords.md`)
Pierwszy prawdziwy darmowy model slotu `waist` (CC BY 4.0, idemotts). Nowe: PART `belt` (uda w wagach), `hip.L`/`hip.R` (sztywno na udzie), `pelvis_share` i `reference.turn_back` w przepisie `uo_make_item.py`. Slot `waist` wiąże teraz PART `belt`. Po uwagach użytkownika: sztylet usunięty, miecz pogrubiony (`thicken`, ok. 2 px) i szary pod partial hue (`FLAT_GREY`). Do zrobienia: miecz przebija tułów przy czarze (ręka/tułów na pochwie); pochwa w cieniu zostaje ciemnoszara.


## Sesja 18: zbroja metalowa Quaternius (`docs/qa/armor_metal.md`)
Zlecenie: wygenerować darmową zbroję (jedna siatka: napierśnik + 2 naramienniki) w szarościach, z metalikiem, przylegającą do skóry bez przebić; podgląd póz (chód, bieg, atak, jazda).
Nowe: `pipeline/split_model.py` (spawanie i podział siatki na części, nierówna skala części), opcje części w `uo_make_item.py` (`cup`, `to_bone`, `scale`, `on_bone`, `cut_below`, `arm_share`, `clear_skin`, `tune` per część), `uo_prepare_item.py` `PART` (waga skinu inna niż slotu). Przepis: `docs/qa/armor_metal_recipe.json`, podgląd: `docs/qa/armor_metal/preview_*.png` (skóra pokolorowana, żeby było widać przebicia).
Wnioski: (1) model stylizowany (napierśnik 2× za szeroki) wymaga nierównej skali przed autofitem; (2) kopułę naramiennika najlepiej wiązać sztywno na `upper_arm` (kula wokół stawu), nie jak skórę; (3) napierśnik z wagami tylko tułowia (`PART torso`) nie daje dziur ze skóry, kończyny wypycha render; (4) `.blend` nie zmieniony (osadzony `uo_prepare_item.py` bez `PART`, `uo_make_item.py` czyta pliki).
Otwarte: postrzępiony dół na jeździe od przodu, pełny `.vd` nierenderowany, brak testu na innej zbroi.
Sesja 18, poprawka: skóra „przebijająca” przez napierśnik to były szczeliny w siatce (płaskie cieniowanie + zaokrąglające zagęszczenie): `split_model.py` eksportuje teraz gładkie normalne; nowe opcje części `smooth_shade`, `pose_clear` (`uo_pose_clear.py`: pozy ramion w kształcie spoczynkowym); `docs/qa/armor_metal.md`, część „Poprawka po uwagach”. Pułapka: `sheets` z pustego katalogu klatek daje IndexError, a `os.environ["R"]` w skryptach diagnostycznych bywa nadpisywane przez `exec` innego skryptu.

Paperdoll i ikona pasa z mieczem (docs/qa/belt_swords.md): `uo_gump_art.py` (czytnik / zapis gumpów i artów), `uo_render_paperdoll.py` (gump 260 x 237, art 44 x 32, wariant A grubszy / B cieńszy). Klient (uo_client/, poza repo): wypakowane `art.mul`, `artidx.mul`, `Gumpart.mul`, `Gumpidx.mul`, `tiledata.mul`.

## Sesja 19: biała tunika z „Jedi robes” (`docs/qa/jedi_tunic.md`)
Zlecenie: z zipa użytkownika (`Jedi robes.glb`, licencja nieznana, poza repo) zostawić tylko białą tunikę (`Outer tunic`, bez pasa), dopasować bez przebić skóry w żadnej akcji, materiał w minimalnej
odległości od ciała, bez dziwnego rozciągania; potem: przy czarach tunika nie może jechać za jedną ręką ani przepuszczać skóry. Przepis: `docs/qa/jedi_tunic_recipe.json` (`"conform": {"MOVE": [0, 0, -0.07]}`).

Co zmieniłem:
- **nowe** `pipeline/uo_conform_item.py`: rękawy przestawione na osie rąk UO, owinięcie tuniki jak membrana 1,5 cm od skóry (ściąganie wzdłuż normalnej materiału, wypychanie wzdłuż normalnej skóry,
  wewnątrz ręki od kości, krawędź maks. 1,25×), dół poniżej krocza wisi (wagi miednicy + `uo_cloth`), wagi jak skóra pod spodem, ale dalej niż 2 cm od skóry ręki (`TORSO_ARM_NEAR`, przejście
  `TORSO_ARM_FADE` 6 cm) tylko 35% wagi ramienia (`TORSO_ARM`); zapisuje własność `uo_conform` i atrybut `uo_region`.
- `pipeline/uo_make_item.py`: opcja przepisu `"conform"` (wyłącza fit / densify z `uo_prepare_item`, uruchamia `uo_conform_item.py` i `item_clearance.py`).
- `pipeline/cloth_lib.py`: `CONFORM_BONES` (każda część przedmiotu pilnuje całej skóry: tułów, nogi, głowa, ręce, dłonie), `conform_masks`, `conform_push` (8 mm, wygładzane po siatce,
  6 ostatnich rund bez wygładzania, `limbs`: wierzchołek < 7 cm od kości kończyny wypychany od kości).
- `pipeline/render_uo_layer.py` (`body_fix`): dla przedmiotów z `uo_conform` zamiast `push_out` jest `conform_push`; `CONFORM_TRIS`, `posed_limbs`, `LIMB_BONES`, `LIMB_R`. Inne przedmioty bez zmian.
- **nowe** `pipeline/item_clearance.py`: przebicia przedmiotu w każdej klatce po pchnięciu renderu (własna strefa, nogi, dłonie / głowa, inna strefa) i rozciągnięcie krawędzi; 35 akcji ok. 4 min.
- **nowe** `pipeline/item_skin_check.py`: podgląd `all` z niebieskim przedmiotem i kolorowymi częściami ciała, liczba pikseli skóry ręki / tułowia przez przedmiot, arkusz z zaznaczeniem
  (to pokazało przebicia, których warstwa `clothing` nie pokazuje). Pełne 35 akcji ok. 7 min.
- `model/UO_Body_0x190.blend`: wgrane tylko `render_uo_layer.py` i `cloth_lib.py`. Dokumentacja: `docs/qa/jedi_tunic.md`, `README.md`, `README_EN.md`, `CLAUDE.md` (wiersz „Przedmioty”).

Wynik (na modelu z poprawionym czarem 17 z innej sesji): `item_skin_check.py` 40 px czystej skóry w 19 z 1050 klatek (łuk 15 px: nadgarstek przy cięciwie; upadek 21: 12 px, miednica pod dołem),
`item_clearance.py` własna strefa 0,085% (najgorsza klatka 0,45%), najgłębiej 20,7 mm, rozciągnięcie p99 3,65 (skóra 2,80), barki względem klatki w czarze 17: 12,5 / 12,6 cm (symetrycznie).
`test_items` 0,718, `test_canvas` OK. Odrzucone próby z liczbami (zwykły fit, rzut na skórę, membrana bez limitu, statyczna kontrola póz, ostre odpięcie barku): `jedi_tunic.md`.
Pułapki: `item_qa.py` mierzy przed pchnięciem renderu i liczy każdy styk (7% / 107 mm dla tuniki): miarą są `item_clearance.py` i `item_skin_check.py`. Znak odległości do otwartego fragmentu
skóry jest zły przy jego brzegach: znak zawsze z całego ciała. Dwa zadania w tle piszące do jednego katalogu renderu psują `_tmp.png` (PNG CRC error).
Otwarte: akcja 21 (w kliencie „Die Backward”, u nas nazwana `21_die_forward`; 22 pewnie też ma zamienioną nazwę): w klatkach 4-5 prawe przedramię sterczy w górę (łokieć ok. 95°, nadgarstek ~30 cm
nad barkiem), oryginał ma ręce płasko na ziemi; IoU klatek 4-5 0,76-0,84 (akcja 0,852). Mankiet dzwonowy przy uniesionym przedramieniu jak prostokątny płat.

## Sesja 20 (2026-10-09): ręce w śmierci, atakach, łuku i bloku (`docs/qa/arm_poses.md`)
Zlecenie użytkownika: poprawić ułożenie rąk w akcji 17 (zrobione wcześniej) i w „śmierci do tyłu” (akcja 21 w kliencie, u nas `21_die_forward`; 22 = „Die Forward”, nazwy zamienione), potem przejrzeć inne akcje (ręce, barki, ciało).
Zrobione: ranking klatek wg niezgodności ręki (`arm_mismatch.py`), nakładki (`action_overlay.py`), wspólne dopasowanie obu rąk z wolnym kręgosłupem / klatką (`arm_joint_fit.py`), wdrożone tylko klatki z lepszym IoU:
21 kl. 2-5 (0,8516 -> 0,8633), 22 kl. 1-5 (0,8578 -> 0,8686), 9 kl. 1/4/5/6 (0,8762 -> 0,8843), 18 kl. 4-5, 14 kl. 6, 30 kl. 3. Ciało 1050 klatek 0,8922 -> 0,8934, `test_items` 0,719 (było 0,718), `test_canvas` OK.
Zmieniony binarny: `model/UO_Body_0x190.blend` (klucze tych akcji; osadzone skrypty bez zmian). Poprzedni stan: commit `e9544f6`.
Otwarte: klatki 1 i 4-5 akcji 21 nadal z niezgodnością ręki 265-320 px (sylwetka nie rozstrzyga zgięcia łokcia), akcja 17 kl. 3-5 (symetria rąk, decyzja użytkownika), jazda 23-29 (dopasowanie nie zna maski konia), barki / tułów w innych akcjach nieprzeglądane osobno. Reguła z tej sesji: dopasowanie robić obiema rękami naraz, wdrażać klatkę tylko gdy IoU nie spada.

## Sesja 21 (2026-10-09/10): czarna szata z symulatora tkaniny, Blender 5.2 (`docs/qa/robe_black.md`)
Zlecenie: pobrać model użytkownika (Google Drive, `.glb`, licencja nieznana, poza repo), zbudować środowisko na Blenderze 5.2+, dopasować i zanimować szatę bez przebić ciała, materiał ma się ruszać naturalnie, nogi nie mogą przebijać. Po pierwszej wersji uwagi: za duża, nie widać dłoni, stopy przebijają w biegu, rękawy rozdarte przy pachach; wolno skalować części.
Przepis: `docs/qa/robe_black_recipe.json`. Środowisko: Python 3.13 + `bpy==5.2.2` (potok przedmiotów działa); model synchronizowany nadal w `bpy 4.2`.
Co zmieniłem:
- `uo_cloth_sim.py`: **symulacja z sesji 16 nie trzymała celu** (pin zostawał na celu pierwszej klatki; zmierzone w bpy 4.2 i 5.2). Cel = klucze kształtu animowane krzywymi F; `thick` 0,02; `in_max` 0,01 m (tkanina poniżej pasa nie cofa się do osi miednicy: stopa nie wychodzi przez rąbek w biegu); rękawy z `uo_region` przedmiotu `conform`; `bpy_compat.action_fcurves`.
- `uo_import_item.py`: `OUTER_SHELL` (warstwa zewnętrzna zamkniętej bryły ubrania), `OUTER_REMESH` (remesh wokselowy: 284 panele -> 1 powłoka, szwy nie pękają), `BAKE_TEXTURE` (nowe UV + tekstura wypalona z oryginału), `WELD` 1e-6 przed decymacją (domyślnie).
- `uo_prepare_item.py` `HEM` (skrócenie szaty dłuższej od ciała), `uo_conform_item.py` `SPACE_SMOOTH` (przesunięcie owinięcia uśrednione w przestrzeni) i `FINAL_ITERS` 40 (wypchnięcie także z ręki od kości), `uo_bind_item.py` `CLOTH_*` w osobnych liniach, `item_skin_check.py` liczy też nogi.
- `model/UO_Body_0x190.blend`: wgrane tylko `uo_bind_item.py`, `uo_import_item.py`, `uo_prepare_item.py` (bpy 4.2).
Wynik (35 akcji, 1050 klatek): skóra tułowia przez szatę 0 px; ręce 1,8 px na klatkę (nadgarstki przy mankiecie); nogi: tylko stopy pod rąbkiem (0,15 m) i nogi jeźdźca; `item_clearance` 0,012% / 0,18% / 13 mm. `test_items` 0,719, `run_qa.py` bez zmian.
Pułapki: `os._exit(0)` bez `sys.stdout.flush()` gubi wydruk; Cloth pin nie widzi zmian siatki z handlera klatki (tylko deformację z animacji / modyfikatorów); model z symulatora bywa zestawem stykających się paneli: każda deformacja liczona po siatce rozsuwa szwy.
Otwarte: szeroki rozkloszowany dół w biegu z profilu (cena zakrycia wykroku), symulacja 0,7 s/klatkę.
