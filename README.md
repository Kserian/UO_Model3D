# UO Body 0x190: model 3D z animacji Ultima Online

Nagi mężczyzna (body 0x190 / 400) odtworzony w 3D z pliku animacji klienta UO `anim1_0x0190.vd`:
35 akcji × 5 kierunków, 210 klatek na kierunek, razem 1050 obrazków. Realistyczne ciało (MakeHuman, CC0) w proporcjach
postaci UO, szkielet 19 kości UO plus palce rąk i kości broni (54 kości), wszystkie 35 animacji dopasowane do oryginalnych klatek.
Służy do projektowania nowych warstw ubrań, zbroi, włosów i broni: plik `.blend` renderuje nowe klatki UO
i od razu zapisuje je do `.vd`.

English version: [`README_EN.md`](README_EN.md).

**Spis treści**
1. [Zawartość](#1-zawartość)
2. [Jak działa model](#2-jak-działa-model)
3. [Modelowanie przedmiotu](#3-modelowanie-przedmiotu)
4. [Render do klatek i pliku `.vd`](#4-render-do-klatek-i-pliku-vd)
5. [Docinanie](#5-docinanie)
6. [Narzędzie `vdtool`](#6-narzędzie-vdtool)
7. [Import do gry](#7-import-do-gry)
8. [Dokładność](#8-dokładność)
9. [Jak powstał model](#9-jak-powstał-model)
10. [Odtworzenie modelu (pipeline)](#10-odtworzenie-modelu-pipeline)
11. [Ograniczenia i częste problemy](#11-ograniczenia-i-częste-problemy)

---

## 1. Zawartość

| Plik / folder | Co to jest |
|---|---|
| `UO_Body_0x190.blend` | Główny plik (Blender 4.2 – 5.2): ciało, szkielet, 35 akcji, kamera UO, scena warstw ubrań, bryły konia, skrypty. |
| `UO_Body_Texture.png`, `UO_Body_Albedo_dir0..4.png` | Tekstura albedo (szara jak skóra w UO, bez światła) i jej warianty dla 5 kierunków UO. |
| `example_clothing/` | Przykładowa warstwa (koszula) w `Example_Shirt_layer.vd` i jej podgląd na oryginalnym ciele. |
| `vdtool/vdtool.py` | Narzędzie do rozpakowywania i pakowania `.vd` (rozdział 6). |
| `pipeline/` | Skrypty potoku: render, dopasowanie przedmiotów, testy, pomiary (rozdział 10). |
| `pipeline/body400.vd`, `pipeline/horse200.vd` | Oryginalne pliki klienta: ciało 0x190 (`anim1_0x0190.vd`) i koń 0xC8. |
| `client/body_0x190_frames/`, `client/horse_0xC8_frames/` | Oryginalne klatki ciała (1050) i konia (300) jako PNG + `meta.json` (`vdtool extract`). |

**Oryginalne klatki.** Plik `.blend` zawiera oryginalne klatki ciała z klienta UO (do trybów dokładnych, rozdział 2).
Jest tylko do własnego użytku. Nie udostępniaj go publicznie. Żeby je dodać
z własnego klienta: skopiuj `anim1_0x0190.vd` jako `pipeline/body400.vd`, a w `pipeline/` uruchom
`python build_originals.py` oraz `python pack_originals.py --blend ../model/UO_Body_0x190.blend`.

## 2. Jak działa model

**Siatka `UO_Body`**
- Realistyczne ciało na bazie MakeHuman (CC0): 13 380 wierzchołków, UV, palce, stopy z palcami, twarz.
  Proporcje (grubość rąk, nóg, tułowia, głowa) dopasowane do oryginalnych klatek z ograniczeniami anatomicznymi.
- Pozycja spoczynkowa to A-pose. Jednostki to metry, postać patrzy w −Y, oś Z w górę. **Podłoga to z = 0.**
- Nie ma korekt kształtu (shape keys): sylwetkę w każdej klatce ustawiają same kości, więc przedmiot po prostu idzie
  za kośćmi.

**Szkielet `UO_Rig`** (54 kości: 19 kości UO, 30 palców i 5 kości broni i tarczy, sufiksy `.L`/`.R`; kości wyłącznie od ruchu postaci):
- `pelvis → spine → chest → neck → head`, `chest → clavicle → upper_arm → forearm → hand`, `pelvis → thigh → shin → foot`.
  `pelvis` jest korzeniem i niesie przesunięcie postaci. Obojczyki unoszą bark; nie deformują siatki (Deform wyłączony).
- `finger1-1` … `finger5-3` (15 kości na dłoń, `finger1` to kciuk, oś X kości = oś zgięcia). W każdej klatce dłoń jest zaciśnięta tak jak na oryginale
  (zgięcie palców i kciuka dopasowane do klatek UO). Rękawice (`"gloves"`) idą za palcami.
- Kości ruchu przedmiotów: `polearm.L`, `axe2h.L`, `bow.L` (dzieci `hand.L`), `weapon1h.R` (dziecko `hand.R`), `shield.L` (dziecko `forearm.L`), z kluczami
  w 35 akcjach (przywrócone na prośbę użytkownika; zależą tylko od dłoni i przedramienia, więc palce ich nie zmieniają).
- Nie ma kości skrętu, palców stóp ani łańcuchów materiału (usunięte w sesji 14; wagi palców stóp przeszły na stopę).
  Przed uproszczeniem (commit `b86c314`) szkielet miał 112 kości.
- Wagi pochodzą z MakeHuman (gładkie stawy, bez „cukierków” w łokciach i barkach).
- **Grubość w klatce:** skala X/Z kości `upper_arm`, `forearm`, `hand`, `thigh`, `shin`, `foot`, `head` (Y = 1) lekko
  pogrubia lub wyszczupla kończynę tam, gdzie oryginał tego wymaga. Następna kość łańcucha tej skali nie dziedziczy
  (Inherit Scale = None), więc długość kończyn się nie zmienia. Przedmiot przypięty do tych kości pogrubia się razem ze skórą.

**Dopasowanie do klatek.** Poza każdej z 210 klatek jest dopasowana do 5 kierunków oryginału naraz (1050 obrazków),
bez żadnych korekt kształtu. Broń, tarcza i włosy są sztywne na kości dłoni, przedramienia i głowy.

**Animacje.** Każda akcja UO to akcja Blendera `NN_nazwa` (z fake userem). 1 klatka UO = 3 klatki sceny (24 fps),
z płynną interpolacją. Chód i bieg są zapętlone. Właściwości akcji: `uo_action` (numer) i `uo_frames` (liczba klatek).

| # | akcja | # | akcja | # | akcja |
|---|---|---|---|---|---|
| 0 | walk_unarmed | 12 | attack_2h_bash | 24 | mounted_run |
| 1 | walk_armed | 13 | attack_2h_slash | 25 | mounted_stand |
| 2 | run_unarmed | 14 | attack_2h_pierce | 26 | mounted_attack_1h |
| 3 | run_armed | 15 | combat_advance | 27 | mounted_attack_bow |
| 4 | stand | 16 | spell_directed | 28 | mounted_attack_crossbow |
| 5 | fidget_1 | 17 | spell_area | 29 | mounted_attack_2h |
| 6 | fidget_2 | 18 | attack_bow | 30 | block |
| 7 | combat_idle_1h | 19 | attack_crossbow | 31 | punch |
| 8 | combat_idle_2h | 20 | get_hit | 32 | bow |
| 9 | attack_1h_slash | 21 | die_forward | 33 | salute |
| 10 | attack_1h_pierce | 22 | die_backward | 34 | eat |
| 11 | attack_1h_bash | 23 | mounted_walk | | |

Lewa i prawa strona zgadza się z oryginałem (kończyn nigdy nie zamieniano). W akcjach konnych postać siedzi w powietrzu,
bo koń jest w UO osobną animacją.

**Kamera `UO_Camera`** patrzy dokładnie jak kamera gry.
- Rzut ortograficzny, elewacja 28,45°, 36 px/m, obraz 136×120, punkt zaczepienia w środku piksela (68, 86). Tak są zapisane oryginalne
  klatki ciała. `render_uo_layer.py` renderuje na większym płótnie (`CANVAS`, domyślnie 256×256 z zaczepem (128, 192), 36 px/m bez zmian),
  bo 136×120 ucina broń dwuręczną, włócznie i wysokie nakrycia głowy (rozdział 4).
- Punkt zaczepienia jest 7 cm nad podłogą (`uo_anchor_height`), bo tak wynika ze wszystkich klatek.
- Kierunek UO ustawia właściwość `uo_direction` (0–4) na `UO_Rig`: 0 przodem, 2 profilem w lewo, 4 tyłem.
  Kierunki 5–7 to lustra 3–1, które robi klient.

**Materiał i światło UO.** Światło UO (jedno, przy kamerze, prawie od przodu) wyznaczyłem z klatek i oddzieliłem od koloru ciała.
- `uo_look = 1` (domyślnie): „wygląd UO”, albedo × (0,08 otoczenia + 0,92 światła UO). Render wygląda jak klatki z gry.
- `uo_look = 0`: zwykłe PBR (Principled BSDF), do edycji i silników gier. Tej wersji używa `export.py` (generuje `.glb`/`.fbx` na żądanie, nie ma ich w repo).
- Grupa węzłów **`UO_Look`** daje to samo światło przedmiotom. Węzeł „Skin hue” opcjonalnie barwi skórę.
- **Tryby dokładne** (wymagają oryginalnych klatek w pliku i silnika Cycles):
  - `EXACT_COLORS`: ciało jest „pomalowane” oryginalną klatką UO rzutowaną z kamery, więc ma dokładnie oryginalne kolory.
  - `EXACT_BODY`: warstwa ciała jest identyczna z oryginałem, a w warstwie ubrania ciało zasłania przedmiot dokładnie
    po oryginalnym obrysie.

**Koń (akcje 23–29).** Kolekcja `Horse_Proxy` zawiera przybliżoną bryłę konia (body 0xC8) dla każdej klatki konnej.
Bryła decyduje, **co** jest za koniem, a **gdzie** koń jest, wyznacza dokładny obrys z jego klatek (tekst
`uo_horse_masks.json`). Dzięki temu koń zasłania jeźdźca i przedmioty co do piksela.

**Skrypty w pliku `.blend`** (Text Editor; wybierz je z listy tekstów w nagłówku edytora):

| Tekst | Rola |
|---|---|
| `render_uo_layer.py` | Render warstwy do klatek i `.vd` (uruchamiasz Alt+P). |
| `uo_materials.py` | Materiały obcego modelu (PBR, tekstury) → „UO look”: podpina kolor (tekstura, kolor, atrybut koloru) pod węzeł `UO_Look`, zachowuje przezroczystość (alpha ≥ 0,5 = piksel w sprite'cie), wyrzuca parametry PBR (roughness, mapy normalnych, odbicia otoczenia), ale **metal dostaje odblask w stylu UO** (zmierzony na sprite'ach napierśnika i hełmu: `SPEC_STRENGTH` 1,0 × albedo, `SPEC_POWER` 16; płyta 2,0/19, kolczuga 0,7/11, patrz `docs/qa/light_shadow.md`); `SATURATION = 0` daje szary przedmiot do farbowania w grze. Uruchom po `uo_import_item.py`. |
| `uo_import_item.py` | Wprowadza obcy model (darmowy, `.glb` `.fbx` `.obj` `.dae`…) na ciało: wypieka siatkę bez obcego szkieletu i wag, skaluje i ustawia na wysokości oryginalnego przedmiotu UO danego typu (`KIND`), wrzuca do `Clothing` (przed `uo_fit_item.py`, rozdział 3). |
| `uo_fit_item.py` | Obraca rękawy zaznaczonego przedmiotu na ręce i wypycha go ze skóry (przed `uo_bind_item.py`, rozdział 3). |
| `uo_densify_item.py` | Zagęszcza siatkę zaznaczonego przedmiotu (podział bez zmiany kształtu, opcjonalnie `SMOOTH`), żeby low-poly przedmiot zginał się gładko w łokciach, kolanach i biodrach, a nie łamał wzdłuż kilku długich krawędzi; docelowa długość krawędzi zależy od slotu (`EDGE_BY_KIND`, rękawice 2 cm, reszta 3–5 cm). Przed `uo_fit_item.py`. |
| `uo_prepare_item.py` | Jeden krok dla slotu (`KIND`): `uo_densify_item.py` → `uo_fit_item.py` → `uo_bind_item.py` z ustawieniami tego slotu (tabela `SLOTS`). Wyniki i uzasadnienie: `docs/qa/slot_geometry.md`. |
| `uo_autofit_item.py` | Jednostki, skala i miejsce zaznaczonego przedmiotu z kształtu skóry slotu (nie z jednej wysokości na slot): `docs/qa/autofit.md`. Wywołuje go `uo_prepare_item.py` (`AUTOFIT`). |
| `uo_orient_weapon.py` | Stawia obcą broń pionowo (czubek w górę, płaska strona na +X, długość klasy: miecz 1 m, muszkiet 1,3 m...), przed `uo_place_weapon.py`. |
| `cloth_lib.py` | Luźne ubrania (szata, spódnica): powłoka nóg i namiot od pasa, per klatka, numpy (`docs/qa/robe_physics.md`); używa go `render_uo_layer.py` dla przedmiotów z własnością `uo_cloth`. |
| `uo_bind_item.py` | Podpina zaznaczony przedmiot do ciała jednym uruchomieniem: parent, Armature i wagi (rozdział 3). |
| `uo_weapon_bones.py` | Dodaje kości broni (lewa dłoń: `polearm.L`, `axe2h.L`, `bow.L`; prawa: `weapon1h.R`) i klucze ich ruchu z `weapon_motion.json` (uruchamiane już w pliku; do ponownego wgrania ruchu). |
| `uo_place_weapon.py` | Stawia zaznaczoną broń (trzon po osi +Z, czubek w górę) na linii chwytu jej klasy, przed `uo_bind_item.py`. Głowicę (ostrze, topór) modeluj jako płaską płytkę w płaszczyźnie XZ, szeroką stroną na +X; skrypt obraca broń wokół trzonu tak jak w oryginalnej broni `REF_ANIM` (np. 624 halabarda, 613 topór kata, 623 szabla), a kość kręci nią dalej wg zmierzonego rollu (`weapon_motion.json`, pole `roll`). Łuki: roll nieokreślony. |
| `weapon_motion.json` | Dane: chwyt (punkt, kierunek, położenie dolnego końca) i ruch 4 klas broni (3 w lewej dłoni, 1H w prawej), 210 póz każda. |
| `uo_place_shield.py` | Stawia zaznaczoną tarczę na lewym przedramieniu jak w UO i dosuwa ją do ręki (przed `uo_bind_item.py`, rozdział 3). |
| `uo_shield_keys.py` | Podmienia ruch kości tarczy `shield.L` w starszym pliku na najnowszy (tarcza i jej podpięcie zostają). |
| `weapon_roll_fit.py`, `weapon_roll_lib.py`, `weapon_roll_apply.py`, `weapon_classify.py`, `test_weapon_roll.py` | Pomiar rollu (obrotu wokół własnej osi) wszystkich oryginalnych broni z `anim`..`anim5`, klasyfikacja broni do kości, zapis do `weapon_motion.json`, test renderu płytki ze sprite'em. Wyniki: `docs/qa/weapon_roll.md`. |
| `uo_vd_writer.py` | Zapis `.vd`, używany przez render (nie uruchamiaj go ręcznie). |
| `uo_job.py` | Uruchamia długie skrypty (render) krok po kroku z modalnego operatora: okno Blendera nie „wiesza się” (pasek postępu na dole, ESC przerywa). Używany przez `render_uo_layer.py` (nie uruchamiaj go ręcznie). |
| `uo_horse_masks.json`, `uo_original_frames.json` | Dane: obrysy konia i oryginalne klatki. |

Skrypty narzędziowe poza plikiem (`pipeline/`): `uo_make_item.py` (darmowy model -> przedmiot jednym poleceniem, rozdział 3a), `uo_cloth_sim.py` (symulacja tkaniny luźnych ubrań, wynik `cloth_sim.npz` obok `item.blend`), `item_vs_original.py` (sylwetka przedmiotu vs oryginał), `robe_hull_eval.py` / `robe_cloth_sim_test.py` (porównania powłoki nóg i symulacji na oryginalnych szatach), `item_sheet.py` / `item_gif.py` (arkusz klatek i animowany GIF przedmiotu na oryginalnym ciele), `item_qa.py` (przenikanie i grubość przedmiotu w ruchu), `item_thickness.py` (grubość na klatkach względem oryginalnych sprite'ów), `pose_capture.py` / `robe_calib.py` / `cloak_calib.py` / `cloak_fit_frames.py` (kalibracja fizyki luźnych ubrań na oryginałach, `docs/qa/robe_physics.md`), `test_autofit.py` / `test_robe.py` / `test_cloak.py` / `run_qa.py` (testy autodopasowania i szat oraz jedna regresja z progami: `python pipeline/run_qa.py [--quick]`), `sync_blend_scripts.py` (wgranie skryptów do `.blend`), `run_render_headless.py` (render bez GUI), `test_*.py` (testy), `body_part_raster.py` / `body_part_qa.py` (sylwetka ciała vs oryginał), `light_*.py`, `layer_analysis*.py`, `slot_dynamics.py` (analizy klatek z klienta), `build_originals.py` / `pack_originals.py` (oryginalne klatki do `.blend`), `export.py` (glb/fbx), `rig_simplify.py`, `rig_restore_fingers.py`, `rig_restore_weapons.py` (jednorazowe zmiany szkieletu), `weapon_*.py` i `test_weapons.py` / `test_weapon_roll.py` (kalibracja i testy broni; potrzebują sprite'ów z klienta, tylko katana 627 jest w repo).

Skrypty są w pliku `.blend`, nie w obiektach. Pracuj więc zawsze w `UO_Body_0x190.blend` (File → Open) i dołączaj
do niego swoje przedmioty, a nie odwrotnie.

## 3. Modelowanie przedmiotu

1. **Otwórz `UO_Body_0x190.blend`** i zezwól na skrypty: Preferences → Save & Load → *Auto Run Python Scripts*
   albo „Allow Execution” w żółtym pasku.
2. **Pozycja spoczynkowa:** zaznacz `UO_Rig` → Object Data Properties (ikona ludzika) → Pose → *Rest Position*.
   Modeluj na ciele w A-pose, a na koniec wróć do *Pose Position*.
3. **Dodaj przedmiot:** wymodeluj go albo zaimportuj (File → Import / Append) i wrzuć do kolekcji **`Clothing`**.
   **Model z zewnątrz (np. darmowy):** ustaw w tekście **`uo_import_item.py`** `FILE` (ścieżka do `.glb`, `.fbx`, `.obj`, `.dae`…)
   i `KIND` (`shirt`, `plate`, `arms`, `pants`, `legs`, `boots`, `gloves`, `helm`, `neck`, `hair`, `beard`, `hat`) i uruchom (Alt+P). Skrypt
   wypieka siatkę (bez szkieletu i wag z pliku), wyrzuca z pliku wszystko poza siatką, skaluje i ustawia przedmiot tak, żeby
   jego wysokość pokryła się z oryginalnym przedmiotem UO tego typu na ciele (zakresy z oryginalnych sprite'ów), i wypisuje
   `PART` do `uo_bind_item.py`. Siatki w pliku są wylistowane: oczy, ciało modelu i kształty pomocnicze wyłącz przez `SKIP`.
   Jeśli przedmiot patrzy tyłem, ustaw `TURN = 180`. Potem **`uo_materials.py`** (materiały obcego modelu w „UO look”; bez tego błyszczący metal
   z modelu wyjdzie w renderze o ok. 55/255 inny niż światło UO; metal dostaje odblask jak w UO), `uo_fit_item.py` i `uo_bind_item.py` (punkty niżej). Sprawdź licencję
   modelu. Testy: `pipeline/test_import_item.py` (obcy plik), `pipeline/test_materials.py` (materiały).
   Wszystko w tej kolekcji trafia do renderowanej warstwy. `Example_Shirt` usuń albo wyłącz w renderze.
4. **Ubranie, zbroja, hełm, buty, rękawice** (rzeczy, które się uginają): skrypt **`uo_bind_item.py`**.
   1. Każdy przedmiot, który w grze jest osobny (napierśnik, naramienniki, rękawice, buty, hełm), rób jako osobny
      obiekt. W klatce 136×120 px widać niewiele szczegółów, więc siatka do ok. 20 tys. wierzchołków w zupełności
      wystarczy (za gęstą zmniejsz modyfikatorem *Decimate*).
   2. **Dopasowanie do ciała** (opcjonalnie, w pozycji spoczynkowej): zaznacz przedmiot i uruchom **`uo_fit_item.py`**.
      Najpierw rękawy (`MATCH_ARMS`): jeśli przedmiot był robiony pod ręce ustawione inaczej (niżej, bardziej do
      przodu, zgięte w łokciu), skrypt sam znajduje ten kąt i obraca rękawy na ręce postaci. Przedmioty bez rękawów
      zostają bez zmian. Potem części bliżej skóry niż `MIN_GAP` (15 mm) albo w ciele zostają wypchnięte. Pchnięcie
      przesuwa cały obszar wokół w jedną stronę i wygasa płynnie na max(`RADIUS` = 4 cm, `SPREAD` × pchnięcie), więc
      zamiast guzów rękaw poszerza się albo przesuwa w całości, a fałdy, nity i wzory idą razem z nim. Duże ściany
      podziel wcześniej (Tryb edycji, A, PPM → Pod podziel, Liczba cięć 2), bo mogą przecinać ciało między
      wierzchołkami. Ponowne uruchomienie nic już nie zmienia. `MAX_GAP > 0` dodatkowo dociąga odstające miejsca
      (zmienia wygląd, domyślnie wyłączone). Położenie i rozmiar ustaw sam.
   3. Zaznacz przedmiot, otwórz tekst **`uo_bind_item.py`**, ustaw `PART` (typ przedmiotu) i uruchom (Alt+P).
      Każdy wierzchołek przedmiotu idzie za skórą, która leży **pod nim** (wzdłuż normalnej, `MAP = "under"`),
      a wagi są wygładzane na przedmiocie (`SMOOTH = 4`).

      | `PART` | Przedmiot | Za czym idzie |
      |---|---|---|
      | `"chest"` | napierśnik, kamizelka, tunika | skóra pod spodem; udo przy biodrze w 70% za miednicą, rękawy za ręką |
      | `"torso"` | coś tylko na tułowiu | pelvis, spine, chest, neck |
      | `"shoulders"` | naramienniki | chest, upper_arm |
      | `"arms"` | rękawy, osłony ramion | upper_arm, forearm |
      | `"gloves"` | rękawice, karwasze | forearm, hand |
      | `"legs"` | spodnie, nagolenniki do pasa | pelvis, thigh, shin |
      | `"boots"` | buty, nagolenniki | shin, foot |
      | `"helm"` | hełm, kaptur, maska | head |
      | `"neck"` | obojczyk zbroi, kołnierz | neck, chest, head |
      | `"all"` | cała zbroja w jednym obiekcie | skóra pod spodem, wszystkie kości |
      | `"cloak"` | peleryna | wisi od klatki piersiowej i **odchyla się do tyłu wokół ramion** zależnie od akcji (bieg, jazda: leci za plecami; tabela z oryginału 468, `docs/qa/cloak_physics.md`) |
      | `"robe"`, `"skirt"` | szata, sukienka, spódnica, kilt | do bioder jak skóra; poniżej **miednica**, a nogi wypychają tkaninę per klatka (`cloth_lib.py`, własność `uo_cloth`; `docs/qa/robe_physics.md`) |
      | `"hair"`, `"beard"`, `"hat"` | włosy, broda, czapka | sztywno na `head` (w UO włosy i brody są sztywne) |
      | `"weapon1h"` | miecz, maczuga, młot, topór 1H, kryss, kilof | kość `weapon1h.R` na prawej dłoni, ruch dopasowany do 13 oryginalnych broni (0,7–1,3 px zamiast 1,4–2,1 px); najpierw `uo_place_weapon.py` z `PART = "weapon1h"` |
      | `"weapon"` / `"weapon.L"` | broń bez kalibracji | sztywno na `hand.R` / `hand.L` |
      | `"polearm"` (`"staff"`, `"weapon2h"`) | kij, włócznia, oszczep, widły, halabarda, berdysz, laska, kostur | kość `polearm.L` na lewej dłoni, ruch dopasowany do oryginalnych broni (0,6–1,1 px zamiast 5–6 px); najpierw `uo_place_weapon.py` |
      | `"axe2h"` | topór dwuręczny, siekiera i młot w lewej dłoni | kość `axe2h.L` (jak wyżej, błąd 1,2–1,7 px) |
      | `"shield"` | tarcza | sztywno na `shield.L` (kość tarczy na przedramieniu, ruch jak tarcza z UO) |
      | `"bow"` / `"crossbow"` | łuk / kusza | kość `bow.L` na lewej dłoni (błąd 1,6–2,1 px zamiast 3 px) |
      | `"quiver"` | kołczan | sztywno na `chest` |

      Dla `"chest"` w linii tego typu ustawiasz, ile wagi kości zostaje na niej: `"thigh": (0.3, 0.1, 0.4)` = przy biodrze 30% za udem
      (reszta za miednicą), od 40% długości uda 100%, pomiędzy płynnie.

   4. Skrypt robi parent do `UO_Rig`, modyfikator *Armature* i wagi, więc przedmiot rusza się razem ze skórą pod nim.
      Uruchom go ponownie po każdej zmianie kształtu przedmiotu (stare wagi zostaną zastąpione).
   5. Wersja ręczna (gdy chcesz własne wagi): Ctrl+P → *Armature Deform → With Empty Groups*, wagi pomaluj
      albo skopiuj modyfikatorem *Data Transfer* (Vertex Groups, *Nearest Face Interpolated*) i usuń grupy kości,
      których przedmiot nie zakrywa.
   6. Skóra przebijająca przedmiot o kilka mm (w podglądzie 3D) nie robi dziur w klatkach: przy renderze ciało zasłania
      przedmiot dopiero wtedy, gdy jest przed nim o więcej niż `HOLDOUT_MARGIN` (1 cm, rozdział 4).
5. **Broń, tarcza, włosy** (rzeczy sztywne): `uo_bind_item.py` z `PART = "weapon"`, `"shield"`, `"hair"` itd.
   (tabela wyżej). Miecz ustaw w pozycji spoczynkowej tak, żeby rękojeść była w zaciśniętej prawej dłoni, a klinga
   wychodziła po stronie kciuka: tak leży broń na oryginalnych klatkach UO. Tarczę postaw pionowo, licem do widoku z
   przodu (Numpad 1), zaznacz i uruchom **`uo_place_shield.py`**: sama stanie na zewnętrznej stronie lewego
   przedramienia (jak tarcza heater z UO) i dosunie się do ręki na `GAP` = 1 cm; potem `PART = "shield"`. W
   renderze tarczy ustaw `BODY_GAP = 0`, żeby się nie wyginała.
6. **Materiał:** Add → Group → **`UO_Look`**, kolor lub teksturę podepnij na wejście *Albedo*. Rzeczy, które w grze mają
   przyjmować kolor (hue), rób w odcieniach szarości.
7. **Sprawdź ruch:** Dope Sheet → Action Editor → wybieraj akcje `NN_nazwa` i odtwarzaj (Spacja). Widok z kamery gry:
   Numpad 0, kierunek zmieniasz `uo_direction`.
8. **Wskazówki:**
   - Ubranie rób ok. 1–2 cm nad skórą.
   - Sprawdzaj zwłaszcza ataki, czary i upadki.
   - Szaty, sukienki i spódnice: `PART = "robe"` / `"skirt"` (tkanina wisi od miednicy, nogi ją wypychają, a na to symulacja tkaniny Blendera z kolizją z ciałem: `pipeline/uo_cloth_sim.py`, w `uo_make_item.py` włączona domyślnie dla `robe` / `skirt`, `--no-sim` wyłącza; bez łańcuchów kości). Peleryny: `PART = "cloak"` (`kind: cloak`), odchylenie do tyłu per akcja i klatka z tabeli `cloak_pitch.json` (IoU z oryginałem 468: 0,376 -> 0,507, `docs/qa/cloak_physics.md`); bez falowania boków.

## 3a. Najszybsza ścieżka: darmowy model -> przedmiot jednym poleceniem

Bez okna Blendera (`pip install numpy pillow scipy "bpy==4.2.*"`), z katalogu repo:

```
python pipeline/uo_make_item.py --list model.glb            # co jest w pliku: siatki, wierzchołki, rozmiar (do wyboru "skip" / "keep")
python pipeline/uo_make_item.py przepis.json --preview      # item.blend + preview.png (6 akcji x 3 kierunki x 3 momenty animacji)
python pipeline/uo_make_item.py przepis.json --vd           # to samo + wszystkie 35 akcji do clothing.vd (15-30 min)
```

Przepis `przepis.json` (wymagane `file` i `kind`; opis wszystkich pól w nagłówku `pipeline/uo_make_item.py`):

```json
{"name": "gambeson", "file": "models/medieval_shirt.glb", "kind": "shirt", "skip": ["guy"]}
{"name": "miecz", "file": "models/miecz.glb", "weapon": {"class": "sword", "part": "weapon1h"}}
```

Co się dzieje (to są te same skrypty, co w oknie Blendera): import (wyrzuca siatki z `skip`, zostawia `keep`, zmniejsza siatkę ponad 30 tys. wierzchołków, gładkie cieniowanie) -> `uo_materials.py` (wygląd UO) ->
`uo_prepare_item.py` = **`uo_autofit_item.py`** (jednostki, skala i miejsce z kształtu skóry, nie z jednej wysokości na slot; krótkie kurtki i szerokie naramienniki nie są rozciągane; `docs/qa/autofit.md`) ->
zagęszczenie (gęste siatki, żeby się gładko zginało) -> `uo_fit_item.py` (wypchnięcie ze skóry, **miękki limit grubości** `LIMIT`: naramienniki i kołnierze nie są grubsze niż oryginały UO) -> `uo_bind_item.py`.
Broń (`weapon`): `uo_orient_weapon.py` stawia ją pionowo (czubek w górę, płaska strona na +X, długość klasy), potem `uo_place_weapon.py` i `uo_bind_item.py`.
Obok `item.blend` powstaje `qa.json` (`pipeline/item_qa.py`, kilka sekund): ile wierzchołków jest w ciele w ruchu (przenikanie przed wypchnięciem z ciała przez render) i jak daleko przedmiot stoi od skóry (grubość). Skrypt pisze w raporcie `AMBIGUOUS`, gdy dwa rozwiązania (np. przód/tył) pasują prawie tak samo: wtedy sprawdź `preview.png` i ustaw `turn` albo `scale` w przepisie.

W oknie Blendera `uo_autofit_item.py` wymaga `scipy` (Blender go nie ma): `import subprocess, sys; subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'scipy'])` w konsoli Pythona Blendera albo po prostu `uo_make_item.py` z zewnątrz. Bez scipy `uo_import_item.py` wraca do starego ustawiania z jednej wysokości na slot (z ostrzeżeniem), a `uo_prepare_item.py` pomija dopasowanie.

Model z kilku przedmiotów i manekinem w pliku (np. uprząż z mieczem na plecach): `"reference": {"keep": ["=nazwa siatki manekina"], "kind": "shirt"}` dopasowuje manekina do ciała, a jego przekształcenie dostają wszystkie `"parts"`
(`{"name": "paski", "keep": [...], "kind": "harness"}`, `{"name": "miecz", "keep": [...], "rigid": "quiver"}`; `=nazwa` = dokładna nazwa siatki). Rzeczy sztywne na plecach dostają własności `uo_behind_torso` (z przodu zasłania je tułów) i `uo_no_body_gap` (nie są odginane od kończyn).

**Luźne ubrania (`kind`: `robe`, `skirt`).** Tkanina wisi od miednicy, a nogi **wypychają ją tam, gdzie sięgają** (powłoka nóg, namiot od pasa, jedna klatka bez pamięci: bez przeskoków i bez przenikania),
wypchnięcie 5 cm i 0,8 drogi do nóg jak w oryginalnych szatach UO. Pomiar na oryginale 469: IoU dolnej części 0,641 -> 0,757 (`docs/qa/robe_physics.md`). Własność `uo_cloth` ustawia `uo_bind_item.py` (`PART` `robe` / `skirt`), a stosuje `render_uo_layer.py`.

## 4. Render do klatek i pliku `.vd`

1. Silnik renderowania: **Cycles** (skrypt i tak sam go ustawi, razem z 1 próbką na piksel).
2. Otwórz tekst **`render_uo_layer.py`** i ustaw opcje na początku:
   ```python
   LAYER = "clothing"          # "clothing" = warstwa przedmiotu, "body" = ciało, "all" = podgląd razem
   CANVAS = (256, 256)         # rozmiar renderu w px (szer., wys.); .vd i tak przycina każdą klatkę do zawartości
   ANCHOR = (128, 192)         # punkt zaczepienia w płótnie. 256×256 / (128, 192) mieści 444 z 449 animacji ludzi i ekwipunku
                               # klienta Nelderim (poza nim: latarnia, epolety z papugą). Stary rozmiar: (136, 120) i (68, 86)
   ONLY = ["04_stand"]         # test jednej akcji; [] = wszystkie 35 akcji
   OUTLINE = 0.38              # ciemny kontur 1 px jak w UO (1.0 = bez konturu)
   OUT_DIR = "//uo_render/"    # folder obok pliku .blend
   WRITE_VD = True
   VD_FILE = "//uo_render/%s.vd"
   HORSE_HOLDOUT = True        # akcje konne: koń zasłania przedmiot
   EXACT_BODY = True           # docinanie po obrysie oryginalnego ciała
   EXACT_COLORS = True         # kolory ciała z oryginału (LAYER = "body" / "all")
   HOLDOUT_MARGIN = 0.01       # ciało zasłania przedmiot, gdy jest przed nim o > 1 cm (płytkie przebicia skóry
                               # nie robią dziur); 0 = zwykły holdout Cycles
   OCCLUDERS = [...]           # części ciała, które mogą zasłaniać przedmiot: ręce, dłonie, głowa, nogi;
                               # tułów nigdy (przedmioty leżą na nim)
   OWN_PARTS_NEVER_HIDE = True # części ciała, do których przedmiot jest oskórowany (spodnie: uda, golenie), nigdy go nie
                               # zasłaniają: przedmiot je okrywa, a ich skóra przed powłoką obcinała paski po bokach
   DESPECKLE = 28              # pojedyncze ciemne kropki w środku przedmiotu (głębokie detale, nity) dostają kolor
                               # otoczenia (0 = wył.)
   FILL_HOLES = 4              # dziurki do 4 px otoczone przedmiotem są wypełniane (0 = wył.)
   BODY_GAP = 0.006            # w każdej klatce części ubrania bliżej niż 6 mm rąk, dłoni, nóg lub głowy są wypychane
                               # na zewnątrz - ręka przebijająca rękaw w ruchu nie robi dziury (0 = wył.)
   MIN_PIECE = 8               # oderwane kawałki przedmiotu mniejsze niż 8 px (brzeg kołnierza / mankietu uciętego
                               # przez głowę lub dłoń) są usuwane; największy kawałek zostaje zawsze (0 = wył.)
   ```
3. Uruchom **Run Script** (Alt+P). Pełna warstwa to 1050 klatek, ok. 15–30 min na CPU. Warstwa ubrania renderuje się
   bez ciała, a to, co ciało zasłania, skrypt liczy z głębokości (z `HOLDOUT_MARGIN = 0` każda klatka renderuje się
   dwa razy: z ciałem i bez).
4. Wynik w `uo_render/`:
   - `clothing/frames/NN_akcja/dirK/NN.png`: klatki na płótnie `CANVAS` (domyślnie 256×256),
   - `clothing/meta.json`: kolejność i punkt zaczepienia,
   - **`clothing.vd`**: gotowy plik.

**Render w częściach.** Kolejne przebiegi do tego samego `OUT_DIR` się sumują. Możesz np. ustawić broń pod ataki
i wyrenderować `ONLY = ["09_attack_1h_slash", ...]`, potem zmienić ułożenie i wyrenderować pozostałe akcje. Każdy przebieg
zapisuje `.vd` ze wszystkimi akcjami wyrenderowanymi do tej pory. Żeby zacząć od zera, usuń folder `uo_render/`.

**Przerwanie renderu:** w oknie Blendera naciśnij **ESC** (postęp widać w pasku stanu na dole; okno nie zawiesza się, ale na czas
renderu blokuje inne akcje). W trybie tła (`blender -b`, moduł `bpy`) utwórz pusty plik `STOP` w folderze wyjściowym
(np. `uo_render/clothing/STOP`) albo naciśnij Ctrl+C. Gotowe klatki PNG zostają.

**Kilka przedmiotów:** każdy renderuj osobno. W `Clothing` zostaw jeden przedmiot i zmień `VD_FILE`, np.
`"//uo_render/helm.vd"`.

## 5. Docinanie

- **Zasłanianie przez ciało:** warstwa ubrania zawiera tylko to, czego ciało nie zasłania, tak jak w UO.
  Z `EXACT_BODY = True` granica biegnie dokładnie po obrysie oryginalnego ciała. Model 3D decyduje tylko, co jest przed,
  a co za ciałem, więc przedmiot pasuje do oryginalnego ciała co do piksela.
- **Koń:** w akcjach konnych przedmiot zasłania koń, dokładnie po obrysie z jego klatek.
- **Wygląd UO:** czarne tło pod krawędziami, przezroczystość 0/1 (UO nie obsługuje półprzezroczystości) i ciemny kontur
  1 px (`OUTLINE`).
- **Przycinanie klatek:** `.vd` zapisuje każdą klatkę przyciętą do zawartości, razem z punktem zaczepienia. PNG-i mają
  celowo pełne płótno, żeby klatki się pokrywały. Przycięte PNG da `vdtool extract --raw`.
- **`LAYER = "body"`:** z `EXACT_BODY = True` ciało jest identyczne z oryginałem, a z `False` to czysty model 3D
  (~98% zgodności).

## 6. Narzędzie `vdtool`

`vdtool/vdtool.py` (Python 3.8+, `pip install pillow numpy`) rozpakowuje `.vd` do PNG i pakuje z powrotem w tej samej
kolejności (akcja → kierunek → klatka). Rozpakowanie i spakowanie bez zmian daje plik identyczny bajt w bajt.

```bash
python vdtool.py info    plik.vd                   # typ, akcje, liczba klatek
python vdtool.py extract plik.vd praca             # -> praca/meta.json + praca/frames/NN_akcja/dirK/NN.png
python vdtool.py extract plik.vd praca --raw       # klatki przycięte do zawartości
python vdtool.py pack    praca nowy.vd             # PNG + meta.json -> .vd
python vdtool.py verify  plik.vd nowy.vd           # co się zmieniło
python mul2vd.py anim.idx anim.mul wynik 701 468   # animacje z plików klienta (np. włosy 701, peleryna 468) -> .vd
```

- **Tryb płótna (domyślny):** wszystkie klatki mają ten sam rozmiar i wspólny punkt zaczepienia (`meta.json → anchor`).
  Przy pakowaniu każda klatka jest sama przycinana, a środek wyliczany. Najlepszy do edycji i dorysowywania.
- **`--raw`:** oryginalne, przycięte rozmiary. Nie zmieniaj wymiarów ani liczby klatek, nadaje się tylko do retuszu pikseli.

**Zasady edycji:**
1. Nie przesuwaj rysunku względem płótna: 1 px na płótnie to 1 px w grze.
2. Przezroczystość jest 0/1: alfa ≥ 128 to piksel widoczny, poniżej to przezroczysty.
3. Każdy blok (akcja + kierunek) ma jedną paletę 256 kolorów 15-bit. Przy > 256 kolorach narzędzie redukuje paletę
   (median cut) i ostrzega. Czysta czerń jest zamieniana na prawie czarną, bo `0x0000` to przezroczystość.
4. Elementy barwione hue rysuj w szarości (R = G = B).
5. Klatki możesz dodawać (kolejny numer) i usuwać (od końca). Każdy z 5 kierunków akcji powinien mieć tyle samo klatek.
6. Nie zmieniaj nazw folderów ani `meta.json`. Pusta klatka jest dozwolona.

**Format `.vd`** (little-endian):
```
int16 magic = 6, int16 animType = 0 (high, 22 akcje) | 1 (low, 13) | 2 (people, 35)
indeks: liczba_akcji*5 wpisów {int32 lookup, int32 length, int32 extra}  (-1 = brak); blok = akcja*5 + kierunek
blok:   uint16 palette[256] (RGB555), int32 frameCount, int32 frameOffset[frameCount] (od pozycji frameCount)
klatka: int16 centerX, centerY; uint16 width, height; serie {uint32 header, byte pixel[header & 0xFFF]}; 0x7FFF7FFF
header: bity 22..31 = (x - centerX) & 0x3FF, bity 12..21 = (y - centerY - height) & 0x3FF, bity 0..11 = długość serii
punkt zaczepienia w klatce = (centerX, centerY + height)
```

## 7. Import do gry

UOFiddler → **Animations → Animation Edit** → wybierz plik animacji i ID ciała lub przedmiotu → **Import from VD** →
wskaż plik `.vd` → zapisz (Save). Plik `.vd` musi mieć ten sam typ co cel (ciała ludzkie i ich przedmioty mają typ 2,
people). Każdy przedmiot ma osobne ID animacji.

## 8. Dokładność

- **Tryb dokładny (`EXACT_BODY = True`):** wyrenderowana warstwa ciała jest identyczna z oryginałem (wszystkie 1050 klatek,
  sprawdzone `vdtool verify`).
- **Sam model 3D (`EXACT_BODY = False`):** średnia zgodność obrysu (IoU) **0,892** na 1050 klatkach (`body_part_qa.py`), **bez żadnych
  korekt kształtu** (same kości). IoU na akcję: `docs/qa/body_parts_after_fingers.json`. Kolory na wspólnych pikselach są dokładne z `EXACT_COLORS`.

Różnice to prawie wyłącznie 1-pikselowe paski wzdłuż krawędzi (oryginał rysowano innym modelem 3D). Dużych błędów, np.
ręki w innym miejscu niż na oryginale, nie ma, więc wycięcia w przedmiotach trafiają w rękę. Dla porównania: poprzedni
model bez swoich 1254 korekt miał 0,880, a z nimi 0,979 (ale przedmioty musiały kopiować te korekty).

**Przedmioty UO.** Test replik przedmiotów z `anim.mul` (`test_items.py`: koszula, napierśnik, spodnie, buty, rękawice, hełm) na obecnym szkielecie:
średnia IoU z oryginalnymi klatkami **0,718** (koszula 0,714, napierśnik 0,690, spodnie 0,800, buty 0,768, rękawice 0,557, hełm 0,781; `docs/qa/items_after_fingers.json`).
Błąd kształtu dłoni względem oryginału (piksele modelu poza sprite'em na klatkę): 3,9 -> 1,4 (lewa) i 4,3 -> 2,0 (prawa) po przywróceniu palców.
Nie ma już testów spódnicy, płaszcza i broni (usunięte z szkieletu).

## 9. Jak powstał model

Ciało to siatka MakeHuman (CC0, mężczyzna) przeniesiona na szkielet UO; kamera UO (rzut ortograficzny, elewacja 28,45°, 36 px/m, zaczep w środku
piksela, podłoga 7 cm pod nim) i 210 póz × 5 kierunków dopasowano do 1050 oryginalnych klatek (własny rasteryzer + skinning jak w Blenderze),
potem kształt siatki dopasowano do obrysów wszystkich klatek, a barki i ramiona lekko zwężono na prośbę użytkownika. Światło UO (jedno, przy kamerze,
Lambert) wyznaczono z klatek i usunięto z koloru, dając albedo. Oryginalne klatki są spakowane w `.blend` jako atlas do trybów dokładnych.
W sesji 14 szkielet zredukowano do 19 kości (patrz rozdział 2).
Pomiary i decyzje: `docs/RAPORT_model3D_UO.txt`, `docs/AUDYT_2026-10-03.md`, `docs/qa/`.

## 10. Odtworzenie i narzędzia

Skrypty, którymi zbudowano ciało (wersje 1-13: dopasowanie póz, kształtu, korekt, tkaniny, broni, tarczy) zostały usunięte z repo razem z danymi pośrednimi:
są w historii gita do commitu `b86c314` (`git show b86c314:pipeline/body13/build_v13.py`). Obecny `.blend` jest źródłem prawdy; zmiany robi się na nim
(np. `pipeline/rig_simplify.py`) i opisuje w commicie. Dane wejściowe, które zostały: oryginalne pliki klienta `pipeline/body400.vd`, `pipeline/horse200.vd`,
klatki `client/`, sprite'y przedmiotów `pipeline/body13/mul/` (z `anim.mul`), wyciąg z klienta `client/extract/`.

Żeby odtworzyć oryginalne klatki w `.blend`: `python build_originals.py`, potem `python pack_originals.py --blend ../model/UO_Body_0x190.blend` (w `pipeline/`).
Pomiary: `body_part_raster.py` + `body_part_qa.py` (sylwetka ciała), `test_items.py` (przedmioty), `test_canvas.py` (płótno), `layer_analysis.py`, `light_*.py`, `slot_dynamics.py`.

## 11. Ograniczenia i częste problemy

**Ograniczenia**
- Rysunek mięśni jest bardziej miękki niż na sprite'ach, bo tekstura uśrednia wiele klatek.
- Palce i twarz pochodzą z MakeHuman (na klatkach ~60 px ich nie widać).
- Sam model 3D różni się od oryginału głównie 1-pikselowymi paskami na krawędziach (ok. 12% pikseli sylwetki).
  Tryby dokładne (`EXACT_BODY`) usuwają to z renderów: ciało jest zawsze oryginalne, model decyduje tylko, co jest
  przed, a co za nim.
- Koń to przybliżona bryła do zasłaniania, a nie model do edycji.

**Częste problemy**

| Problem | Rozwiązanie |
|---|---|
| Text Editor jest pusty | Wybierz tekst z listy w nagłówku edytora. Jeśli lista jest pusta, otwórz `UO_Body_0x190.blend` przez File → Open (nie importuj `.glb`/`.fbx` i nie dołączaj ciała do innej sceny). |
| Czarne albo dziwne ciało na renderze | Włącz *Auto Run Python Scripts* i otwórz plik ponownie. Ustaw Cycles. Sprawdź `LAYER`. |
| Tryby dokładne nic nie zmieniają | W pliku nie ma oryginalnych klatek: użyj `.blend` z tego repozytorium albo `pack_originals.py`. |
| Przedmiot przebija się przez ciało | Uruchom `uo_bind_item.py` z właściwym `PART` i zrób przedmiot odrobinę większy. |
| Przedmiot rozciąga się za ręką lub nogą | Ma wagi kości, których nie zakrywa. Uruchom `uo_bind_item.py` z właściwym `PART`. |
| Blender „wisi” przy skrypcie | Przedmiot ma za dużo wierzchołków. Zmniejsz go (*Decimate*). |
| Przedmiot stoi w miejscu | Brak modyfikatora *Armature* albo wag (rozdział 3). |
| Postać „skacze” w `vdtool` | Rysunek przesunięty względem punktu zaczepienia. |
| Poszarpane krawędzie po imporcie | Półprzezroczyste piksele: ustaw alfę 0 albo 255. |
| UOFiddler odrzuca plik | Inny typ animacji niż cel (ciała ludzkie: typ 2). |
| Render trwa długo | Testuj z `ONLY = ["04_stand"]`, pełny render zrób na końcu. |
