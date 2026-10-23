**[English version → README.md](README.md)**

# UO Body 0x190: model 3D z animacji Ultima Online

Nagi mężczyzna (body 0x190 / 400) odtworzony w 3D z pliku animacji klienta UO `anim1_0x0190.vd`: 35 akcji × 5 kierunków, 1050 obrazków.
Realistyczne ciało (MakeHuman, CC0) w proporcjach postaci UO, szkielet 54 kości i wszystkie 35 animacji dopasowane do oryginalnych klatek.
Służy do projektowania warstw ubrań, zbroi, włosów i broni: plik `.blend` renderuje nowe klatki UO i od razu zapisuje je do `.vd`.

**Spis treści:** [1 Pliki](#1-pliki) · [2 Model](#2-jak-działa-model) · [3 Modelowanie przedmiotu](#3-modelowanie-przedmiotu) · [3a Szybka ścieżka](#3a-szybka-ścieżka-darmowy-model---przedmiot-jednym-poleceniem) · [4 Render](#4-render-do-klatek-i-pliku-vd) · [5 Docinanie](#5-docinanie) · [6 vdtool](#6-narzędzie-vdtool) · [7 Import do gry](#7-import-do-gry) · [8 Dokładność](#8-dokładność) · [9 Historia i narzędzia](#9-historia-i-narzędzia) · [10 Problemy](#10-ograniczenia-i-częste-problemy) · [11 Dla asystentów AI](#11-uwagi-dla-asystentów-ai)

---

## 1. Pliki

| Plik / folder | Co to jest |
|---|---|
| `model/UO_Body_0x190.blend` | Główny plik (Blender 4.2 – 5.2): ciało, szkielet, 35 akcji, kamera UO, scena warstwy ubrań, zastępniki konia, skrypty. |
| `model/UO_Body_Texture.png`, `UO_Body_Albedo_dir0..4.png` | Albedo (szare jak skóra UO, bez oświetlenia) i jego warianty dla 5 kierunków. |
| `model/example_clothing/` | Przykładowa warstwa (koszula) jako `.vd` z podglądem na oryginalnym ciele. |
| `model/items/horn/` | Receptury rogu dla prawej i lewej ręki. |
| `vdtool/` | `vdtool.py` rozpakowuje i pakuje `.vd` (rozdział 6), `mul2vd.py` zamienia `anim.mul` klienta. |
| `pipeline/` | Render, dopasowanie przedmiotów, testy, pomiary (rozdział 9). `body400.vd`, `horse200.vd` = oryginalne pliki klienta (body 0x190, koń 0xC8). |
| `client/` | Oryginalne klatki ciała (1050) i konia (300) jako PNG + `meta.json`; `extract/` = dane wyciągnięte z klienta. |
| `docs/qa/` | `baselines.md` (progi QA i ostatnie wartości), JSON-y z pomiarami, raporty o wariantach szaty (rozdział 3a). |

**Oryginalne klatki.** `.blend` zawiera oryginalne klatki klienta UO (dla trybów dokładnych, rozdział 2). Tylko do własnego użytku, nie udostępniaj. Żeby dodać je ze swojego klienta: skopiuj `anim1_0x0190.vd` do `pipeline/body400.vd`, potem w `pipeline/` uruchom `python build_originals.py` i `python pack_originals.py --blend ../model/UO_Body_0x190.blend`.

## 2. Jak działa model

**Siatka `UO_Body`:** MakeHuman (CC0), 13 380 wierzchołków, UV, palce, twarz; proporcje dopasowane do oryginalnych klatek. Poza spoczynkowa: A-pose. Metry, postać patrzy w −Y, Z do góry, **podłoga z = 0**. Brak shape keys: samo kości ustawiają sylwetkę w każdej klatce, więc przedmiot po prostu za nimi podąża.

**Szkielet `UO_Rig`** (54 kości: 19 kości UO, 30 kości palców, 5 kości broni i tarczy; `.L`/`.R`):
- `pelvis` (korzeń, niesie przesunięcie postaci) → `spine → chest → neck → head`; `chest → clavicle → upper_arm → forearm → hand`; `pelvis → thigh → shin → foot`. Obojczyki unoszą ramię, ale nie odkształcają siatki; mają klucze położenia tylko w 49 z 210 klatek, gdzie wymaga tego sylwetka.
- `finger1-1` … `finger5-3` (15 na rękę, `finger1` = kciuk, X = oś zgięcia): dłoń zaciśnięta jak na oryginale. Rękawice podążają za palcami.
- Kości przedmiotów: `polearm.L`, `axe2h.L`, `bow.L` (na `hand.L`), `weapon1h.R` (na `hand.R`), `shield.L` (na `forearm.L`), z kluczami we wszystkich 35 akcjach.
- Brak kości skrętu, palców stóp i łańcuchów tkaniny. Wagi z MakeHuman (bez „candy-wrapper”).
- **Obwód per klatka:** skala X/Z kości `upper_arm`, `forearm`, `hand`, `thigh`, `shin`, `foot`, `head` (Y = 1, następna kość jej nie dziedziczy) pogrubia lub cieni kończynę tam, gdzie wymaga tego oryginał; przedmioty związane z tymi kośćmi podążają. Głowa ma jedną skalę (1, 1, 0,942) we wszystkich klatkach, więc hełm nie pulsuje.

**Dopasowanie do klatek.** Poza każdej z 210 klatek jest dopasowana do wszystkich 5 kierunków oryginału naraz, potem przeliczona pod **naturalny ruch przy tych samych sylwetkach** (`pipeline/pose_natural_fit.py`): gładko w czasie, bez zygzaka głowy, bez skręcania i ślizgania ramienia, łokieć jak zawias; żadna klatka nie jest gorsza niż wcześniej. W czarze obszarowym (akcja 17) ręce są symetryczne, a tułów tylko się pochyla. Broń, tarcze i włosy są sztywne na dłoni, przedramieniu i głowie.

**Animacje.** Każda akcja UO to akcja Blendera `NN_nazwa` (fake user), własności `uo_action` i `uo_frames`; 1 klatka UO = 3 klatki sceny (24 fps), gładka interpolacja. Lewa i prawa strona zgadzają się z oryginałem. W akcjach konnych jeździec siedzi w powietrzu; koń to osobna animacja.

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

**`UO_Camera`** widzi jak kamera gry: ortogonalna, elewacja 28,45°, 36 px/m, oryginalne klatki 136×120 z punktem zaczepienia w pikselu (68, 86), 7 cm nad podłogą. `render_uo_layer.py` renderuje na większym płótnie (`CANVAS` 256×256, punkt (128, 192)), bo 136×120 ucina broń dwuręczną, włócznie i wysokie nakrycia głowy. Kierunek = własność `uo_direction` (0–4) w `UO_Rig`: 0 patrzy w kamerę, 2 to profil w lewo, 4 patrzy od kamery; 5–7 to odbicia 3–1 robione przez klienta.

**Materiał i światło UO.** Jedno światło przy kamerze, oszacowane z klatek i oddzielone od koloru ciała. `uo_look = 1` (domyślnie): albedo × (0,08 światła otoczenia + 0,92 światła UO), wygląda jak klatki gry; `uo_look = 0`: zwykły PBR do edycji i silników gier (`export.py` robi `.glb`/`.fbx` na żądanie, nie ma ich w repo). Grupa węzłów **`UO_Look`** daje przedmiotom to samo światło; „Skin hue” barwi skórę. **Tryby dokładne** (potrzebują oryginalnych klatek i Cycles): `EXACT_COLORS` maluje ciało oryginalną klatką rzutowaną z kamery; `EXACT_BODY` robi warstwę ciała identyczną z oryginałem i pozwala ciału zasłaniać przedmiot dokładnie po oryginalnym obrysie.

**Koń (akcje 23–29).** Kolekcja `Horse_Proxy` ma przybliżoną bryłę konia (0xC8) dla każdej klatki konnej; decyduje **co** jest za koniem, a **gdzie** jest koń, wynika z dokładnego obrysu jego klatek (`uo_horse_masks.json`), więc koń zasłania jeźdźca i przedmioty co do piksela.

**Skrypty wewnątrz `.blend`** (Text Editor, wybierz z listy w nagłówku). Pracuj zawsze w `UO_Body_0x190.blend` i wnoś do niego swoje przedmioty:

| Tekst | Do czego |
|---|---|
| `render_uo_layer.py` | Renderuje warstwę do klatek i `.vd` (Alt+P). |
| `uo_import_item.py` | Wprowadza obcy model (`.glb` `.fbx` `.obj` `.dae`) na ciało: piecze siatkę, skaluje do wysokości oryginalnego przedmiotu danego `KIND`, wkłada do `Clothing`. |
| `uo_materials.py` | Obce materiały w wygląd UO: kolor do `UO_Look`, alfa >= 0,5 = piksel, parametry PBR odrzucone, **metal dostaje połysk w stylu UO** (zmierzony na spritach płyty i hełmu); `SATURATION = 0` = szary przedmiot do farbowania w grze. Po `uo_import_item.py`. |
| `uo_densify_item.py` | Dzieli siatkę bez zmiany kształtu, żeby low-poly gładko się giął (krawędź 2 cm rękawice, 3-5 cm reszta). |
| `uo_autofit_item.py` | Jednostki, rozmiar i miejsce z kształtu skóry danego slotu (wymaga `scipy`). |
| `uo_fit_item.py` | Obraca rękawy na ramiona i wypycha przedmiot ze skóry. |
| `uo_prepare_item.py` | Jeden krok na slot (`KIND`): autofit → densify → fit → bind. |
| `uo_bind_item.py` | Wiąże przedmiot z ciałem: rodzic, Armature, wagi (rozdział 3). |
| `uo_hood_cover.py` | Sprowadza kaptur na czaszkę, a kołnierz kaptura na ramiona. |
| `cloth_lib.py` | Luźne ubrania: powłoka nóg i namiot od pasa, per klatka (numpy); wypchnięcie przez nogi w rendererze i cel symulacji tkaniny. |
| `uo_orient_weapon.py`, `uo_place_weapon.py`, `uo_place_shield.py` | Stawiają broń pionowo, kładą ją na linii chwytu jej klasy (obrót wokół drzewca jak oryginalny `REF_ANIM`, potem kość obraca ją o zmierzony roll), kładą tarczę na lewym przedramieniu. Przed `uo_bind_item.py`. |
| `uo_weapon_bones.py`, `uo_shield_keys.py`, `weapon_motion.json` | Kości broni i ich ruch (chwyt i 210 póz 4 klas broni); wczytanie ruchu do starszego pliku. |
| `uo_vd_writer.py`, `uo_job.py` | Zapis `.vd` i runner, który nie zamraża okna Blendera przy długim renderze (nie uruchamiać bezpośrednio). |
| `uo_horse_masks.json`, `uo_original_frames.json` | Dane: obrysy konia i oryginalne klatki. |

**Narzędzia poza plikiem (`pipeline/`):**

| Grupa | Skrypty |
|---|---|
| Przedmiot jednym poleceniem | `uo_make_item.py` (3a), `uo_conform_item.py`, `uo_cloth_sim.py`, `uo_cloth_pbd.py`, `item_gif.py` (arkusz klatek i GIF przedmiotu na oryginalnym ciele), `item_sheet.py` |
| Pomiary przedmiotu | `item_qa.py` (przebicia, grubość), `item_clearance.py`, `item_thickness.py`, `item_body_holes.py` (co widzi klient na oryginalnym ciele 400), `item_skin_check.py` (skóra przez przedmiot a w dziurach, stopy osobno) |
| Ciało i pozy | `pose_lib.py` (szkielet w numpy, co do piksela jak Blender; `qa`), `pose_natural_fit.py` + `apply_pose_keys.py`, `pose_naturalness.py`, `body_part_raster.py` + `body_part_qa.py`, `arm_*.py` (dopasowanie ręki, odbicie lewej ręki w akcji 17) |
| Testy | `run_qa.py [--quick]` (regresja z progami, `docs/qa/baselines.md`), `test_items.py`, `test_canvas.py`, `test_autofit.py`, `test_robe.py`, `test_cloak.py`, `test_materials.py`, `test_import_item.py`, `test_weapons.py`, `test_weapon_roll.py` (testy broni potrzebują sprite'ów z klienta; w repo jest tylko katana 627) |
| Kalibracja i analizy | `weapon_*.py`, `robe_calib.py`, `cloak_calib.py`, `cloak_fit_frames.py`, `layer_analysis*.py`, `light_*.py`, `slot_dynamics.py` |
| Środowisko | `sync_blend_scripts.py` (skrypty do `.blend`), `run_render_headless.py`, `build_originals.py` / `pack_originals.py`, `export.py`, `rig_*.py` (jednorazowe zmiany szkieletu) |

## 3. Modelowanie przedmiotu

1. **Otwórz `UO_Body_0x190.blend`**, zezwól na skrypty (Preferences → Save & Load → *Auto Run Python Scripts*).
2. **Poza spoczynkowa:** zaznacz `UO_Rig` → Object Data Properties → Pose → *Rest Position*; modeluj na A-pose, potem wróć do *Pose Position*.
3. **Dodaj przedmiot** (zamodeluj albo zaimportuj / dołącz) do kolekcji **`Clothing`**; wszystko w niej jest renderowane. Usuń `Example_Shirt` albo wyłącz.
   **Obcy model:** w `uo_import_item.py` ustaw `FILE` i `KIND` (`shirt`, `plate`, `arms`, `pants`, `legs`, `boots`, `gloves`, `helm`, `neck`, `hair`, `beard`, `hat`) i uruchom (Alt+P). Odrzuca szkielet pliku i wszystko poza siatką (`SKIP` dla oczu, ciała modelu, pomocników; `TURN = 180`, gdy patrzy tyłem), stawia przedmiot na wysokości oryginalnego przedmiotu UO tego rodzaju i wypisuje `PART`. Potem `uo_materials.py` (bez niego błyszczący metal renderuje się ok. 55/255 obok światła UO), `uo_fit_item.py`, `uo_bind_item.py`. Sprawdź licencję.
4. **Rzeczy, które się uginają (ubrania, zbroje, hełmy, buty, rękawice):**
   1. Każdy element będący osobnym przedmiotem w grze zrób osobnym obiektem. 136×120 px pokazuje mało szczegółów: do ok. 20 tys. wierzchołków w zupełności wystarczy (*Decimate*).
   2. **`uo_fit_item.py`** (opcjonalnie, w Rest Position): obraca rękawy na ramiona (`MATCH_ARMS`) i wypycha części bliższe skórze niż `MIN_GAP` (15 mm). Wypchnięcie przesuwa swoje otoczenie tak samo, gasnąc na max(`RADIUS` 4 cm, `SPREAD` × wypchnięcie), więc fałdy i nity idą razem. Duże ściany najpierw podziel. Ponowne uruchomienie nic nie zmienia; `MAX_GAP > 0` dociąga też odstające części.
   3. W **`uo_bind_item.py`** ustaw `PART` i uruchom (Alt+P): każdy wierzchołek podąża za skórą tuż pod nim (`MAP = "under"`), wagi wygładzone (`SMOOTH = 4`). Uruchom ponownie po każdej zmianie kształtu.

      | `PART` | Przedmiot | Za czym podąża |
      |---|---|---|
      | `"chest"` | napierśnik, kamizelka, tunika | skóra pod spodem; udo przy biodrze 70% na miednicy, rękawy na ramionach |
      | `"torso"` | coś tylko na tułowiu | pelvis, spine, chest, neck |
      | `"shoulders"` | naramienniki | chest, upper_arm |
      | `"arms"` | rękawy, zbroja ręki | upper_arm, forearm |
      | `"gloves"` | rękawice, karwasze | forearm, hand |
      | `"legs"` | spodnie, zbroja nóg | pelvis, thigh, shin |
      | `"boots"` | buty, nagolenniki | shin, foot |
      | `"helm"` | hełm, maska, sztywny kaptur | head |
      | `"hood"` | kaptur z kołnierzem | kaptur: head, kołnierz: neck i chest; potem `uo_hood_cover.py` (receptura `"hood_cover"`) |
      | `"neck"` | kryza, kołnierz | neck, chest, head |
      | `"all"` | pełny strój w jednym obiekcie | skóra pod spodem, każda kość |
      | `"cloak"` | płaszcz | wisi na piersi i **odchyla się do tyłu wokół ramion** per akcja (tabela `cloak_pitch.json` z oryginału 468; bez falowania boków) |
      | `"robe"`, `"skirt"` | szata, sukienka, spódnica, kilt | skóra do bioder; niżej miednica i wypchnięcie przez nogi (`cloth_lib.py`, własność `uo_cloth`), potem symulacja tkaniny (3a) |
      | `"hair"`, `"beard"`, `"hat"` | włosy, broda, czapka | sztywno na `head` |
      | `"weapon1h"` | miecz, buzdygan, młot, topór 1H, kilof | kość `weapon1h.R`, dopasowana do 13 oryginalnych broni (błąd 0,7-1,3 px); najpierw `uo_place_weapon.py` |
      | `"weapon"` / `"weapon.L"` | nieskalibrowana broń | sztywno na `hand.R` / `hand.L`; `weapon.L` wkłada przedmiot 1H (róg, latarnia) do lewej ręki na odbitym chwycie |
      | `"polearm"` (`"staff"`, `"weapon2h"`) | kij, włócznia, halabarda | kość `polearm.L` (0,6-1,1 px); najpierw `uo_place_weapon.py` |
      | `"axe2h"` | topór dwuręczny, toporek w lewej ręce | kość `axe2h.L` (1,2-1,7 px) |
      | `"shield"` | tarcza | sztywno na `shield.L` |
      | `"bow"` / `"crossbow"` | łuk / kusza | kość `bow.L` (1,6-2,1 px) |
      | `"quiver"` | kołczan | sztywno na `chest` |

      Dla `"chest"` linia typu `"thigh": (0.3, 0.1, 0.4)` mówi, ile wagi kości zostaje na niej: 30% na udzie przy biodrze, 100% od 40% jego długości.
   4. Ręcznie: Ctrl+P → *Armature Deform → With Empty Groups*, maluj lub kopiuj wagi (*Data Transfer*), usuń grupy kości, których przedmiot nie zakrywa.
   5. Skóra wystająca o kilka mm przez przedmiot w widoku 3D nie robi dziur: ciało zasłania przedmiot tylko tam, gdzie jest o więcej niż `HOLDOUT_MARGIN` (1 cm) przed nim.
5. **Broń, tarcza, włosy** (sztywne): `uo_bind_item.py` z odpowiednim `PART`. Miecz ustaw w Rest Position z rękojeścią w prawej dłoni i klingą od strony kciuka (tak leży na oryginalnych klatkach). Tarczę ustaw pionowo, licem do widoku z przodu (Numpad 1), uruchom `uo_place_shield.py` (zewnętrzna strona lewego przedramienia, `GAP` 1 cm), potem `PART = "shield"`; renderuj z `BODY_GAP = 0`.
6. **Materiał:** Add → Group → **`UO_Look`**, podłącz kolor lub teksturę do *Albedo*. Wszystko, co ma przyjmować barwę w grze, rób w skali szarości.
7. **Sprawdź ruch:** Dope Sheet → Action Editor → wybierz `NN_nazwa` i odtwórz (Space); widok gry = Numpad 0, kierunek = `uo_direction`. Szczególnie sprawdź ataki, czary i śmierć. Ubranie trzymaj 1-2 cm nad skórą.

## 3a. Szybka ścieżka: darmowy model -> przedmiot jednym poleceniem

Bez okna Blendera (`pip install numpy pillow scipy "bpy==4.2.*"`), z folderu repo:

```
python pipeline/uo_make_item.py --list model.glb            # siatki, wierzchołki, rozmiar (do wyboru "skip" / "keep")
python pipeline/uo_make_item.py recipe.json --preview       # item.blend + preview.png (6 akcji x 3 kierunki x 3 momenty)
python pipeline/uo_make_item.py recipe.json --vd            # to samo + 35 akcji do clothing.vd (15-30 min)
```

Receptura (`file` i `kind` wymagane; każde pole opisane w nagłówku `uo_make_item.py`):

```json
{"name": "gambeson", "file": "models/medieval_shirt.glb", "kind": "shirt", "skip": ["guy"]}
{"name": "sword", "file": "models/miecz.glb", "weapon": {"class": "sword", "part": "weapon1h"}}
```

Kroki (te same skrypty co w oknie Blendera): import (odrzuca `skip`, zostawia `keep`, zmniejsza powyżej 30 tys. wierzchołków) → `uo_materials.py` → `uo_prepare_item.py` (**autofit**: jednostki, rozmiar i miejsce z kształtu skóry, krótkie kurtki i szerokie naramienniki nie są rozciągane; densify; `uo_fit_item.py` z **miękkim limitem grubości** `LIMIT`; bind). Broń: `uo_orient_weapon.py` (czubek do góry, płaska strona na +X, długość klasy), `uo_place_weapon.py`, bind. Obok `item.blend` leży `qa.json` (`item_qa.py`): wierzchołki wewnątrz ciała w ruchu i odstęp od skóry. `AMBIGUOUS` znaczy, że dwa rozwiązania (przód / tył) pasują prawie tak samo: sprawdź `preview.png`, ustaw `turn` albo `scale`. W oknie Blendera `uo_autofit_item.py` wymaga `scipy` (zainstaluj w konsoli Pythona Blendera albo uruchom `uo_make_item.py` z zewnątrz); bez niego jest stare ustawienie z jednej wysokości na slot.

**Specjalne pola receptury:**
- `"conform"` (`uo_conform_item.py`): koszule, tuniki i kurtki zrobione na innym manekinie: rękawy przesunięte na osie ramion, przedmiot owinięty jak błona 1,5 cm od skóry (fałdy i UV zostają), render trzyma go 8 mm od skóry w każdej klatce. Pomiar: `item_clearance.py`.
- Model kilku przedmiotów z manekinem: `"reference": {"keep": ["=nazwa siatki manekina"], "kind": "shirt"}` dopasowuje manekina do ciała, a każdy wpis `"parts"` dostaje jego transformację (`{"name": "straps", "keep": [...], "kind": "harness"}`, `{"name": "sword", "keep": [...], "rigid": "quiver"}`; `=nazwa` = dokładna nazwa siatki). Rzeczy na plecach dostają `uo_behind_torso` i `uo_no_body_gap`. Cienkie części znikają przy 36 px/m: `"widen": {"width": 0.07}` (paski), `"skin_wrap": {"GAP": 0.008}` (paski położone na skórze), `"thicken": {"width": 0.085}` (płaska pochwa widziana z krawędzi).
- `"scene": {...}` = opcje renderu per przedmiot (rozdział 4), `"sim": {...}` = ustawienia symulacji tkaniny, `"prepare"`, `"materials"`, `"holes"`, `"bake_normal"` / `"bake_ao"` jak w nagłówku `uo_make_item.py`.

**Luźne ubrania (`kind`: `robe`, `skirt`).** Tkanina wisi od miednicy, a symulacja tkaniny Blendera (`pipeline/uo_cloth_sim.py`, domyślnie włączona w `uo_make_item.py`; `"sim": {...}` = jej ustawienia, `--no-sim` = wyłączona) pozwala nogom wypychać ją jak prawdziwy materiał. Każdy wierzchołek jest trzymany słabą sprężyną (pin `goal`) przy celu kinematycznym = przedmiot skinowany szkieletem + `pushw` × wypchnięcie przez nogi (`cloth_lib.hull_push`); tkanina koliduje z ustawionym ciałem; wynik zapisuje się jako różnica względem pełnego celu (`cloth_sim.npz`) i dodaje go `render_uo_layer.py`. Cel nie musi pasować do sprite'a oryginalnej szaty 469: liczy się fizyka (kolizje, rąbek) i wygląd. (Sama powłoka nóg, jedna klatka bez pamięci, dała IoU dolnej części ciała 0,641 → 0,757 względem oryginału 469.)

Ustawienia, które zadziałały na gęstej siatce (24 tys. wierzchołków; zestaw **t1**, jeszcze nie domyślne w `uo_cloth_sim.py`, podaj je w `"sim"`): `mscale 0.0333 goal 0.2 pushw 0.5 gravity 1.5 in_max -1 max_move 0 smooth 0.04 arm_goal 0.95 preroll 20 cycles 2 thick 0.02 dist 0.005`; jazda konno: `mounted 1 horse 1` (zastępczy korpus konia jest colliderem). Masa i sztywność w Blenderze zależą od liczby wierzchołków, więc `mscale` skaluje masę wierzchołka do siatki. Szata z symulatora tkaniny (zamknięta bryła z osobnych paneli, setki tysięcy wierzchołków) potrzebuje też `"outer_shell": 0.006` (remesh voxelowy skleja panele), `"prepare": {"HEM": 0.15}` i `"HEM_BAND"` (rąbek nad stopami, ciągła lamówka), `"conform": {"CLOTH_KAPPA": 1.0, "CLOTH_MARGIN": 0.06, "CLOTH_DROP": 0.3, "SLEEVE_CUFF": 0.05}` (owinięta wokół ciała, wisi od kolana, rękawy dzwonowe zwężone, żeby było widać dłonie), `"sim": {"arm_goal": 0.95, "smooth": 0.04}`, `"materials": {"GREY_CLOTH": {...}}` (szara jak szaty UO), `"scene": {"uo_cloth_lie": 1.0, "uo_hide_erode": 1, "uo_legs_under": 1, "uo_outline": 0.6}`; szata podarta zostawia dziury modelu (`"prepare": {"HEM_FLARE": {"factor": 0.65}}` zwęża mocno rozkloszowaną spódnicę).

**Swobodnie zwisająca tkanina (pas z rozcięciami, spódnica): `"sim": {"engine": "pbd", ...}`.** `pipeline/uo_cloth_pbd.py` (position based dynamics, numba) przypina do szkieletu tylko pas; wszystko poniżej zwisa swobodnie (grawitacja, tłumienie `damp`, więzy rozciągania i zginania), nogi i miednica to kapsuły, z których tkanina jest wypychana w każdym podkroku, a luźne kawałki modelu idą za skórą; nic nie przyciąga tkaniny do nóg. Zapisuje ten sam `cloth_sim.npz` co `uo_cloth_sim.py`, więc renderer się nie zmienia. Tkanina Blendera z przypięciem tylko w pasie zwijała spódnicę 16 tys. wierzchołków w sznury w chodzie w każdym wariancie (quality 8-24, margines 6-20 mm, masa x1-x3, goal 0-0,15); chód liczy się tu 8 s (w Blenderze 130-700 s), wszystkie 28 akcji 34 s. Ustawienia (klucz=wartość): `damp` (1,5; 3-6 = cięższa, spokojniejsza tkanina), `bend` (0,15), `stretch`, `iters`, `substeps`, `gravity`, `friction`, `margin`, `rpct`, `ramp`, `island`. Pas postawiony za wysoko: `NUDGE` w `uo_autofit_item.py` (m); `"prepare": {"FIT": false}` nie pozwala wypychaniu rozdąć obręczy szerszej niż ciało (pas girdle: 0,42 x 0,33 m rósł do 0,67 x 0,61 m); scena `"uo_behind_torso": 1` pozwala torsowi zasłonić wnętrze obręczy (ciemne wnętrze pasa). Receptura: `model/items/radiant_star_girdle/girdle.json`.

| `fabric` | Masa | Zginanie | Tłumienie | Policzone |
|---|---|---|---|---|
| `silk` | 0,15 | 0,05 | 1 | pełne 35 akcji × 5 kierunków |
| `cotton` | 0,3 | 0,5 | 5 | pełne 35 akcji × 5 kierunków |
| `wool` | 0,5 | 2 | 10 | pełne 35 akcji × 5 kierunków |
| `denim` | 1,0 | 10 | 25 | nie liczone |
| `leather` | 0,4 | 150 | 25 | nie liczone |

Sztywność w płaszczyźnie (tension, compression, shear) wynosi 5 dla wszystkich tkanin: presety Blendera (15-80) są podciągane przez pin i rąbek się unosił (cotton +0,26 m, wool +0,47 m w chodzie; przy 5: +0,04 / +0,05 m, silk +0,04). Wolna tkanina bez pinu (goal 0) rozpada się albo unosi rąbek; potrzebny jest margines kolizji 0,02 m (`thick`), 0,006 m przepuszcza nogi (piksele nóg przez tkaninę w chodzie + biegu, silk: 723 z t1 wobec 1862 przy cienkim). Raporty: `docs/qa/robe_variants_2026-10.md` / `.pdf` (co próbowaliśmy, z pomiarami), `docs/qa/robe_variants_screenshots_2026-10.pdf` (rendery każdego wariantu z ustawieniami). Zostaje: nogi widać w upadkach (die forward), spódnica ok. 1,7× szersza przy rąbku niż w oryginalnej szacie 469, rękawy ok. 10% grubsze.

## 4. Render do klatek i pliku `.vd`

1. Silnik: **Cycles** (skrypt ustawia go sam: przedmioty 512 próbek adaptacyjnych, warstwa ciała 1).
2. Otwórz **`render_uo_layer.py`** i ustaw opcje na górze:
   ```python
   LAYER = "clothing"          # "clothing" = warstwa przedmiotu, "body" = ciało, "all" = podgląd obu
   CANVAS = (256, 256)         # rozmiar renderu; .vd i tak przycina każdą klatkę do zawartości
   ANCHOR = (128, 192)         # piksel zaczepienia (256x256 / (128, 192) mieści 444 z 449 animacji ludzi i ekwipunku; stary rozmiar (136, 120), (68, 86))
   ONLY = ["04_stand"]         # test jednej akcji; [] = wszystkie 35
   OUTLINE = 0.38              # ciemny kontur 1 px ciała (1.0 = brak); przedmioty: OUTLINE_TARGET 0.38; nadpisuje go własność sceny uo_outline
   SAMPLES = 512               # próbki Cycles dla przedmiotów; nadpisuje je własność sceny uo_samples
   EDGE_FLOOR = 0              # kontur przedmiotu nigdy ciemniejszy niż to (0-255); własność sceny uo_edge_floor
   OUT_DIR = "//uo_render/"; WRITE_VD = True; VD_FILE = "//uo_render/%s.vd"
   HORSE_HOLDOUT = True        # akcje konne: koń zasłania przedmiot
   EXACT_BODY = True           # docięcie po oryginalnym obrysie ciała
   EXACT_COLORS = True         # kolory ciała z oryginału
   HOLDOUT_MARGIN = 0.01       # ciało zasłania przedmiot tam, gdzie jest > 1 cm przed nim (0 = zwykły holdout Cycles)
   OCCLUDERS = [...]           # części, które mogą zasłaniać przedmiot: ręce, dłonie, głowa, nogi; nigdy tułów
   OWN_PARTS_NEVER_HIDE = True # części, do których przedmiot jest związany, nigdy go nie zasłaniają
   DESPECKLE = 0               # N > 0: pojedyncze ciemne kropki w przedmiocie dostają kolor otoczenia (kasowało detale tekstury: wyłączone)
   FILL_HOLES = 4              # dziury do 4 px otoczone przedmiotem są zalewane
   BODY_GAP = 0.006            # w każdej klatce części przedmiotu bliższe niż 6 mm do rąk, dłoni, nóg, głowy są wypychane
   MIN_PIECE = 8               # oderwane kawałki poniżej 8 px są usuwane; największy zostaje
   ```
3. **Run Script** (Alt+P). Pełna warstwa to 1050 klatek, 15-30 minut na CPU. Warstwa ubrań jest renderowana bez ciała; skrypt z głębi liczy, co ciało zasłania.
4. Wynik w `uo_render/`: `clothing/frames/NN_akcja/dirK/NN.png` (pełne płótno), `clothing/meta.json`, **`clothing.vd`**.

**Render po kawałku:** kolejne uruchomienia z tym samym `OUT_DIR` się sumują (np. `ONLY = ["09_attack_1h_slash", ...]`, zmień ustawienie, wyrenderuj resztę); każdy bieg zapisuje `.vd` ze wszystkimi dotąd zrobionymi akcjami. Usuń `uo_render/`, żeby zacząć od zera. **Przerwanie:** ESC w oknie Blendera; w trybie tła utwórz pusty plik `STOP` w folderze wyjściowym (np. `uo_render/clothing/STOP`) albo Ctrl+C; gotowe klatki zostają. **Kilka przedmiotów:** renderuj każdy osobno (jeden w `Clothing`, zmień `VD_FILE`).

**Opcje renderu per przedmiot** (własności sceny; w recepturze `uo_make_item.py` pod `"scene"`). Zmieniają jeden przedmiot, nigdy ciało ani światło innych przedmiotów:

| Opcja | Domyślnie | Co robi | Zmierzony efekt |
|---|---|---|---|
| `uo_contrast` | 1 (wył.) | Krzywa kontrastu na pikselach samego przedmiotu, po konturze: `rgb = pivot + k × (rgb - pivot)`. k > 1: ciemniejsze fałdy, jaśniejsze światła; przedmiot wygląda cieniej i bardziej „malowany”, jak oryginały UO | Szata silk, rękawy w chodzie: rozrzut jasności (std) 31 → 45 (k 1,5) → 52 (k 1,8); oryginał 469: 54. Ciemne piksele wokół dłoni 30% → 55-59% (469: 56%). Złota lamówka bardziej nasycona, średnia jasność 109 → 98 (469: 113) |
| `uo_contrast_pivot` | 0,49 | Szarość (0..1) niezmieniana przez `uo_contrast` (ok. mediana szarej szaty) | Podnieś, żeby zachować wyższą średnią jasność |
| `uo_shade_sleeve` | 0 (wył.) | Gładki cień kontaktowy tam, gdzie rękaw spotyka tułów (wymaga `conform`): tułów obok ręki i wnętrze rękawa ciemnieją do tego ułamka na `uo_shade_width` px, per klatka, gradient, bez linii | Daje głębię z boku i w czarach z uniesionymi rękami; 0,6 lekko za mocno |
| `uo_shade_body` | 0 (wył.) | To samo przy częściach ciała zasłaniających przedmiot (dłonie, ręce, głowa) | Bardzo subtelne przy 0,6 |
| `uo_shade_width` | 3 | Szerokość w px (1 px = 2,8 cm) obu gradientów | 3-4 |
| `uo_outline` | auto (0,38) | Siła ciemnego konturu 1 px (1.0 = brak) | Jasnoszara szata: 0,6-0,8 |
| `uo_edge_floor` | 0 | Kontur nigdy ciemniejszy niż to na kanał | 24 = brak czystej czerni na czarnym przedmiocie |
| `uo_samples` | 512 | Próbki Cycles | 1024 dla połysku metalu, ciemnej skóry |
| `uo_inner_line` | 0 | Ciemna linia 1 px między rękawem a tułowiem (wymaga `conform`) | Rozrzut 30 → 40, ale wygląda jak narysowana linia: niezalecane |
| `uo_hide_erode` | 0 | Dłonie i głowa zasłaniają przedmiot o 1 px mniej | 1 dla szat: mniej dziur ze skórą przy mankietach i kołnierzu |
| `uo_legs_under` | 0 | Nogi nigdy nie zasłaniają przedmiotu | 1 dla długiej szaty |
| `uo_cloth_lie` | 0 | Upadki (21, 22): w jakim stopniu szata leży wzdłuż nóg; 0 = działa tam symulacja | 1.0 = leży wzdłuż nóg |

**Bazowy wygląd szaty lub spódnicy.** `uo_make_item.py` daje `"kind": "robe"` / `"skirt"` scenę `uo_shade_sleeve` 0,4, `uo_shade_width` 4, `uo_contrast` 1,5, chyba że `"scene"` w recepturze mówi inaczej (`"scene": {"uo_contrast": 1}` wyłącza krzywą). Szata silk w chodzie, strefa rękawa: rozrzut jasności 31 → 46 (469: 54), udział ciemnych pikseli wokół dłoni 38% → 55% (469: 56%). Cień wymaga `"conform"`, kontrast nie. Inne rodzaje nic nie dostają. Próbowane i bezużyteczne dla rękawów i dłoni (szata silk, 2026-10): siła własnego cienia, siła normal mapy, kontrast tekstury, cieniowanie okluzją (rozrzut zostaje ok. 31), przesunięcie światła UO w lewo, w prawo lub do góry (34-36 i ciemniejsza szata): światło UO leży prawie na osi kamery, więc cienkie ręce dostają płaskie cieniowanie.

## 5. Docinanie

- **Zasłonięte przez ciało:** warstwa ubrań zawiera tylko to, czego ciało nie zasłania. Z `EXACT_BODY = True` cięcie idzie po oryginalnym obrysie; model 3D decyduje tylko, co jest przed ciałem, a co za nim, więc przedmiot pasuje do oryginalnego ciała co do piksela.
- **Koń:** w akcjach konnych koń zasłania przedmiot dokładnie po obrysie z jego klatek.
- **Wygląd UO:** czerń pod krawędziami, przezroczystość 0/1 (bez półprzezroczystości), ciemny kontur 1 px (`OUTLINE`).
- **Przycinanie:** `.vd` zapisuje każdą klatkę przyciętą z punktem zaczepienia; PNG-i trzymają całe płótno, żeby klatki się pokrywały (`vdtool extract --raw` daje przycięte PNG).
- **`LAYER = "body"`:** `EXACT_BODY = True` = identyczne z oryginałem; `False` = czysty model 3D (~98% zgodności).

## 6. Narzędzie `vdtool`

`vdtool/vdtool.py` (Python 3.8+, `pip install pillow numpy`; komunikaty po polsku) rozpakowuje `.vd` do PNG i pakuje z powrotem w tej samej kolejności; rozpakowanie i spakowanie bez zmian daje plik identyczny bajt w bajt.

```bash
python vdtool.py info    plik.vd                   # typ, akcje, liczby klatek
python vdtool.py extract plik.vd work              # -> work/meta.json + work/frames/NN_akcja/dirK/NN.png
python vdtool.py extract plik.vd work --raw        # klatki przycięte do zawartości
python vdtool.py pack    work nowy.vd              # PNG + meta.json -> .vd
python vdtool.py verify  plik.vd nowy.vd           # co się zmieniło
python mul2vd.py anim.idx anim.mul out 701 468     # animacje klienta (np. włosy 701, płaszcz 468) -> .vd
```

- **Tryb płótna (domyślny):** wszystkie klatki mają jeden rozmiar i punkt zaczepienia z `meta.json`; przy pakowaniu każda jest przycinana. Najlepszy do edycji. **`--raw`:** oryginalne przycięte rozmiary; tylko do retuszu pikseli.
- **Zasady:** nie przesuwaj rysunku względem płótna (1 px = 1 px w grze); przezroczystość 0/1 (alfa ≥ 128 widoczne); jedna paleta 256 kolorów 15-bitowych na blok (więcej kolorów: redukcja median cut z ostrzeżeniem; czysta czerń staje się prawie czarną, bo `0x0000` to przezroczystość); części do barwienia rysuj w szarości (R = G = B); klatki można dodawać na końcu lub usuwać od końca, wszystkie 5 kierunków akcji powinno mieć tyle samo; nie zmieniaj nazw folderów ani `meta.json`.

**Format `.vd`** (little-endian):
```
int16 magic = 6, int16 animType = 0 (high, 22 akcje) | 1 (low, 13) | 2 (people, 35)
indeks: akcje*5 wpisów {int32 lookup, int32 length, int32 extra} (-1 = pusty); blok = akcja*5 + kierunek
blok:   uint16 palette[256] (RGB555), int32 frameCount, int32 frameOffset[frameCount] (od pozycji frameCount)
klatka: int16 centerX, centerY; uint16 width, height; serie {uint32 header, byte pixel[header & 0xFFF]}; 0x7FFF7FFF
header: bity 22..31 = (x - centerX) & 0x3FF, bity 12..21 = (y - centerY - height) & 0x3FF, bity 0..11 = długość serii
punkt zaczepienia w klatce = (centerX, centerY + height)
```

## 7. Import do gry

UOFiddler → **Animations → Animation Edit** → wybierz plik animacji i ID ciała lub przedmiotu → **Import from VD** → `.vd` → Save. `.vd` musi mieć ten sam typ co cel (ciała ludzkie i ich przedmioty: typ 2, people). Każdy przedmiot ma własne ID animacji.

## 8. Dokładność

- **Tryb dokładny (`EXACT_BODY = True`):** warstwa ciała identyczna z oryginałem (1050 klatek, `vdtool verify`).
- **Czysty model 3D:** średnie IoU sylwetki **0,899** w 1050 klatkach (`body_part_qa.py`, per akcja w `docs/qa/body_parts_after_natural_fit.json`) bez korekt kształtu; 2049 pikseli o ≥ 2 px obok (prawdziwe błędy pozy, `pose_lib.py qa`). Różnice to prawie tylko pasy 1 px wzdłuż krawędzi (oryginał rysowano z innego modelu 3D), bez dużych błędów, np. ręki w innym miejscu, więc wycięcia przedmiotów trafiają w rękę. Poprzedni model miał 0,880 bez swoich 1254 korekt i 0,979 z nimi, ale przedmioty musiały je kopiować.
- **Przedmioty UO:** repliki przedmiotów z `anim.mul` na obecnym szkielecie (`test_items.py`): średnie IoU **0,723** (koszula 0,715, płyta 0,699, spodnie 0,801, buty 0,771, rękawice 0,572, hełm 0,782; `docs/qa/items_after_natural_fit.json`). Broń, szaty i płaszcze mają własne testy (`test_weapons.py`, `test_robe.py`, `test_cloak.py`; wszystkie progi i ostatnie wartości w `docs/qa/baselines.md`).

## 9. Historia i narzędzia

Ciało to siatka MakeHuman (CC0, męska) przeniesiona na szkielet UO. Kamera UO i 210 póz × 5 kierunków zostały dopasowane do 1050 oryginalnych klatek (własny rasteryzer + skinning jak w Blenderze), potem kształt siatki dopasowano do obrysów wszystkich klatek, a ramiona i barki lekko zwężono na prośbę użytkownika. Światło UO wyprowadzono z klatek i usunięto z koloru, co dało albedo. Szkielet zredukowano do 19 kości UO, potem wróciły palce i kości broni (54); ręce, nogi i głowę przeliczono per klatka, a na końcu wszystkie pozy pod naturalny ruch.

Skrypty, które budowały ciało (wersje 1-13), usunięto razem z danymi pośrednimi; są w historii gita do commitu `b86c314`. Źródłem prawdy jest obecny `.blend`: zmiany robi się na nim (np. `pipeline/rig_simplify.py`) i opisuje w commicie. Pozostałe dane wejściowe: `pipeline/body400.vd`, `horse200.vd`, `client/`, sprite'y przedmiotów `pipeline/body13/mul/` (z `anim.mul`). Pomiary: `body_part_raster.py` + `body_part_qa.py`, `test_items.py`, `test_canvas.py`, `run_qa.py`.

## 10. Ograniczenia i częste problemy

**Ograniczenia:** rysunek mięśni jest miększy niż na spritach (tekstura uśrednia wiele klatek); palce i twarz pochodzą z MakeHuman (niewidoczne przy ~60 px); czysty model różni się od oryginału pasami 1 px przy krawędziach (~12% pikseli sylwetki), które tryby dokładne usuwają; koń to przybliżony okluder, nie model do edycji.

| Problem | Rozwiązanie |
|---|---|
| Text Editor jest pusty | Wybierz tekst z listy w nagłówku. Jeśli lista jest pusta, otwórz `UO_Body_0x190.blend` przez File → Open (nie importuj `.glb`/`.fbx` i nie dołączaj ciała do innej sceny). |
| Czarne albo dziwne ciało na renderze | Włącz *Auto Run Python Scripts*, otwórz plik ponownie, ustaw Cycles, sprawdź `LAYER`. |
| Tryby dokładne nic nie zmieniają | W pliku nie ma oryginalnych klatek: użyj `.blend` z tego repozytorium albo `pack_originals.py`. |
| Przedmiot przebija się przez ciało | `uo_bind_item.py` z właściwym `PART`; zrób przedmiot odrobinę większy. |
| Przedmiot rozciąga się za ręką lub nogą | Ma wagi kości, których nie zakrywa: `uo_bind_item.py` z właściwym `PART`. |
| Blender „wisi” przy skrypcie | Za dużo wierzchołków: *Decimate*. |
| Przedmiot stoi w miejscu | Brak modyfikatora *Armature* albo wag (rozdział 3). |
| Postać „skacze” w `vdtool` | Rysunek przesunięty względem punktu zaczepienia. |
| Poszarpane krawędzie po imporcie | Półprzezroczyste piksele: alfa 0 albo 255. |
| UOFiddler odrzuca plik | Inny typ animacji niż cel (ciała ludzkie: typ 2). |
| Render trwa długo | Testuj z `ONLY = ["04_stand"]`, pełny render na końcu. |

## 11. Uwagi dla asystentów AI

Pełny opis techniczny (format `.vd`, przestrzeń, kamera, kierunki, kości, wagi, holdout, BODY_GAP, koń, tryby dokładne, materiał, render) jest w sekcji 11 angielskiego `README.md`; to jedyna wersja utrzymywana w całości. Najważniejsze:

```
PRZESTRZEŃ : metry, Z do góry, postać patrzy w -Y, podłoga z = 0, punkt UO = świat (0, 0, 0,07).
KAMERA     : "UO_Camera", ortogonalna, elewacja 28,45 st., 36 px/m, 136x120 px, punkt w pikselu (68, 86).
KIERUNKI   : UO_Rig["uo_direction"] = d (0..4) obraca szkielet o -45 st. * d; 5..7 to odbicia 3..1 robione przez klienta.
SZKIELET   : 54 kości (rozdział 2); akcje "NN_nazwa", UO klatka i -> klatka sceny 1 + 3*i.
PRZEDMIOTY : uo_bind_item.py (PART -> dozwolone kości, waga = waga skóry pod spodem); sztywne: 100% na jednej kości.
HOLDOUT    : ciało zasłania piksel, gdzie depth_body < depth_item - HOLDOUT_MARGIN (0,01 m), tylko trójkąty z OCCLUDERS (bez tułowia).
LUŹNA TKANINA: własność uo_cloth: wypchnięcie przez nogi + cloth_sim.npz z uo_cloth_sim.py; render dodaje deltę, potem BODY_GAP.
KONIE      : koń = body 0xC8; parowanie akcji 23->0, 24->1, 25..29->2; zasłanianie tylko w obrysie konia (uo_horse_masks.json).
ZASADY     : nigdy nie zamieniaj lewej i prawej kończyny względem oryginalnych klatek; nowe warstwy mają te same 35 akcji, 5 kierunków
             i liczby klatek co ciało; nie rozpowszechniaj plików klienta UO ani `.blend` z tego repozytorium.
ODTWORZENIE: źródłem prawdy jest `.blend`; skrypty budujące są w historii gita (commit b86c314), rozdział 9.
```
