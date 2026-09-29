# UO Body 0x190: model 3D z animacji Ultima Online

Nagi mężczyzna (body 0x190 / 400) odtworzony w 3D z pliku animacji klienta UO `anim1_0x0190.vd`:
35 akcji × 5 kierunków, 210 klatek na kierunek, razem 1050 obrazków. Realistyczne ciało (MakeHuman, CC0) w proporcjach
postaci UO, szkielet 55 kości z palcami i łańcuchami materiału, wszystkie 35 animacji dopasowane do oryginalnych klatek.
Służy do projektowania nowych warstw ubrań, zbroi, włosów, płaszczy i broni: plik `.blend` renderuje nowe klatki UO
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
| `UO_Body_0x190.blend` | Główny plik (Blender 4.2+): ciało, szkielet, 35 akcji, szablony płaszcza i spódnicy, kamera UO, scena warstw ubrań, bryły konia, skrypty. |
| `UO_Body_0x190.glb` | glTF 2.0: siatka + szkielet + animacje + tekstura (Unity, Godot, three.js, Blender). |
| `UO_Body_0x190.fbx` | FBX: siatka + szkielet + animacje (Maya, 3ds Max, Unreal, Unity). |
| `UO_Body_Texture.png`, `UO_Body_Albedo_dir0..4.png` | Tekstura albedo (szara jak skóra w UO, bez światła) i jej warianty dla 5 kierunków UO. |
| `compare/*.gif` | U góry oryginalny sprite, pod spodem model wyrenderowany kamerą UO (5 kierunków). |
| `example_clothing/` | Przykładowa warstwa (koszula) w `Example_Shirt_layer.vd` i jej podgląd na oryginalnym ciele. |
| `vdtool/vdtool.py` | Narzędzie do rozpakowywania i pakowania `.vd` (rozdział 6). |
| `pipeline/` | Skrypty i dane, którymi zrekonstruowano model (rozdział 10). |
| `pipeline/body400.vd`, `pipeline/horse200.vd` | Oryginalne pliki klienta: ciało 0x190 (`anim1_0x0190.vd`) i koń 0xC8. |
| `client/body_0x190_frames/`, `client/horse_0xC8_frames/` | Oryginalne klatki ciała (1050) i konia (300) jako PNG + `meta.json` (`vdtool extract`). |

**Oryginalne klatki.** Plik `.blend` zawiera oryginalne klatki ciała z klienta UO (do trybów dokładnych, rozdział 2).
Jest tylko do własnego użytku. Nie udostępniaj go publicznie. Kopia bez oryginałów (`strip_originals.py`) ich nie ma. Żeby je dodać
z własnego klienta: skopiuj `anim1_0x0190.vd` jako `pipeline/body400.vd`, a w `pipeline/` uruchom
`python build_originals.py` oraz `python pack_originals.py --blend ../model/UO_Body_0x190.blend`.

## 2. Jak działa model

**Siatka `UO_Body`**
- Realistyczne ciało na bazie MakeHuman (CC0): 13 380 wierzchołków, UV, palce, stopy z palcami, twarz.
  Proporcje (grubość rąk, nóg, tułowia, głowa) dopasowane do oryginalnych klatek z ograniczeniami anatomicznymi.
- Pozycja spoczynkowa to A-pose. Jednostki to metry, postać patrzy w −Y, oś Z w górę. **Podłoga to z = 0.**
- Nie ma korekt kształtu (shape keys): sylwetkę w każdej klatce ustawiają same kości, więc przedmiot po prostu idzie
  za kośćmi.

**Szkielet `UO_Rig`** (55 kości ciała + łańcuchy materiału, sufiksy `.L`/`.R`):
- 19 kości UO: `pelvis → spine → chest → neck → head`, `chest → clavicle → upper_arm → forearm → hand`,
  `pelvis → thigh → shin → foot`. `pelvis` jest korzeniem i niesie przesunięcie postaci. Obojczyki unoszą bark.
- `upper_arm_twist`, `forearm_twist` (skręt ramienia i przedramienia), 15 kości palców na dłoń (`finger1-1` …
  `finger5-3`, `finger1` to kciuk), `toe` (palce stóp). Kolekcje kości: *Fingers*, *Twist*, *Toes*, *Cloth*.
- Wagi pochodzą z MakeHuman (gładkie stawy, bez „cukierków” w łokciach i barkach).
- **Grubość w klatce:** skala X/Z kości `upper_arm`, `forearm`, `hand`, `thigh`, `shin`, `foot`, `head` (Y = 1) lekko
  pogrubia lub wyszczupla kończynę tam, gdzie oryginał tego wymaga. Następna kość łańcucha tej skali nie dziedziczy
  (Inherit Scale = None), więc długość kończyn się nie zmienia. Przedmiot przypięty do tych kości pogrubia się razem ze skórą.
- **Palce:** w każdej klatce dłoń jest zaciśnięta tak jak na oryginale (zgięcie palców i kciuka dopasowane do klatek).
- **Łańcuchy materiału:** `skirt_K_S` (8 łańcuchów × 3 kości wokół miednicy) i `cloak_K_S` (7 × 4, z tyłu od barków).
  Ich ruch dopasowano do oryginalnych klatek spódnicy (anim 449) i płaszcza (anim 468) z `anim.mul`, także na koniu.

**Dopasowanie do klatek.** Poza każdej z 210 klatek jest dopasowana do 5 kierunków oryginału naraz (1050 obrazków),
bez żadnych korekt kształtu. Obrót prawej dłoni dopasowano dodatkowo do oryginalnych klatek katany (anim 627), więc
broń w dłoni leży jak w grze (klinga średnio co do 0,8 px).

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
- Rzut ortograficzny, elewacja 28,45°, 36 px/m, obraz 136×120, punkt zaczepienia w środku piksela (68, 86).
- Punkt zaczepienia jest 7 cm nad podłogą (`uo_anchor_height`), bo tak wynika ze wszystkich klatek.
- Kierunek UO ustawia właściwość `uo_direction` (0–4) na `UO_Rig`: 0 przodem, 2 profilem w lewo, 4 tyłem.
  Kierunki 5–7 to lustra 3–1, które robi klient.

**Materiał i światło UO.** Światło UO (jedno, przy kamerze, prawie od przodu) wyznaczyłem z klatek i oddzieliłem od koloru ciała.
- `uo_look = 1` (domyślnie): „wygląd UO”, albedo × (0,08 otoczenia + 0,92 światła UO). Render wygląda jak klatki z gry.
- `uo_look = 0`: zwykłe PBR (Principled BSDF), do edycji i silników gier. Tej wersji używają `.glb`/`.fbx`.
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
| `uo_fit_item.py` | Obraca rękawy zaznaczonego przedmiotu na ręce i wypycha go ze skóry (przed `uo_bind_item.py`, rozdział 3). |
| `uo_bind_item.py` | Podpina zaznaczony przedmiot do ciała jednym uruchomieniem: parent, Armature i wagi (rozdział 3). |
| `uo_cloth_bake.py` | Symulacja tkaniny dla szat, sukni, spódnic i płaszczy, po `uo_bind_item.py` (rozdział 3). |
| `uo_vd_writer.py` | Zapis `.vd`, używany przez render (nie uruchamiaj go ręcznie). |
| `uo_horse_masks.json`, `uo_original_frames.json` | Dane: obrysy konia i oryginalne klatki. |

Skrypty są w pliku `.blend`, nie w obiektach. Pracuj więc zawsze w `UO_Body_0x190.blend` (File → Open) i dołączaj
do niego swoje przedmioty, a nie odwrotnie.

## 3. Modelowanie przedmiotu

1. **Otwórz `UO_Body_0x190.blend`** i zezwól na skrypty: Preferences → Save & Load → *Auto Run Python Scripts*
   albo „Allow Execution” w żółtym pasku.
2. **Pozycja spoczynkowa:** zaznacz `UO_Rig` → Object Data Properties (ikona ludzika) → Pose → *Rest Position*.
   Modeluj na ciele w A-pose, a na koniec wróć do *Pose Position*.
3. **Dodaj przedmiot:** wymodeluj go albo zaimportuj (File → Import / Append) i wrzuć do kolekcji **`Clothing`**.
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
      | `"chest"` | napierśnik, kamizelka, tunika | skóra pod spodem; naramiennik na barku w 80% na obojczyku, rękaw niżej na ramieniu za ręką (płynne przejście), dół w 70% za miednicą |
      | `"torso"` | coś tylko na tułowiu | pelvis, spine, chest, neck |
      | `"shoulders"` | naramienniki | chest, upper_arm |
      | `"arms"` | rękawy, osłony ramion | upper_arm, forearm |
      | `"gloves"` | rękawice, karwasze | forearm, hand |
      | `"legs"` | spodnie, nagolenniki do pasa | pelvis, thigh, shin |
      | `"boots"` | buty, nagolenniki | shin, foot |
      | `"helm"` | hełm, kaptur, maska | head |
      | `"neck"` | obojczyk zbroi, kołnierz | neck, chest, head |
      | `"all"` | cała zbroja w jednym obiekcie | skóra pod spodem, wszystkie kości |
      | `"robe"` | szata, suknia | góra jak skóra, od pasa w dół łańcuchy spódnicy (płynne przejście 35 cm); rękawy zawsze za rękami |
      | `"skirt"` | spódnica, kilt | łańcuchy `skirt_*` (szablon `UO_Template_Skirt`) |
      | `"cloak"` | płaszcz, peleryna | łańcuchy `cloak_*` + karczek na barkach (szablon `UO_Template_Cloak`) |
      | `"hair"`, `"beard"`, `"hat"` | włosy, broda, czapka | sztywno na `head` (w UO włosy i brody są sztywne) |
      | `"weapon"` / `"weapon.L"` | broń | sztywno na `hand.R` / `hand.L` (UO trzyma broń w prawej dłoni) |
      | `"shield"` | tarcza | sztywno na `forearm.L` |
      | `"bow"` / `"crossbow"` | łuk / kusza | sztywno na `hand.L` / `hand.R` |
      | `"quiver"` | kołczan | sztywno na `chest` |

      Rękawice (`"gloves"`) idą też za palcami, rękawy (`"arms"`) za kośćmi skrętu, buty (`"boots"`) za palcami stóp.
      Szablony materiału (kolekcja *Templates*, niewidoczne w renderze) możesz skopiować jako bazę własnego płaszcza
      albo spódnicy: kształt zmieniaj w pozycji spoczynkowej, potem `uo_bind_item.py` z `PART = "cloak"` / `"skirt"`.

      Dla `"chest"` bark ustawiasz w linii tego typu: `"upper_arm": (0.2, 0.15, 0.45)` = przy stawie 20% za ręką,
      od 45% długości ramienia 100% (rękaw), pomiędzy płynnie. `"thigh": (0.3, 0.1, 0.4)` tak samo dla ud i poł.

   4. Skrypt robi parent do `UO_Rig`, modyfikator *Armature* i wagi, więc przedmiot rusza się razem ze skórą pod nim.
      Uruchom go ponownie po każdej zmianie kształtu przedmiotu (stare wagi zostaną zastąpione).
   5. Wersja ręczna (gdy chcesz własne wagi): Ctrl+P → *Armature Deform → With Empty Groups*, wagi pomaluj
      albo skopiuj modyfikatorem *Data Transfer* (Vertex Groups, *Nearest Face Interpolated*) i usuń grupy kości,
      których przedmiot nie zakrywa.
   6. Skóra przebijająca przedmiot o kilka mm (w podglądzie 3D) nie robi dziur w klatkach: przy renderze ciało zasłania
      przedmiot dopiero wtedy, gdy jest przed nim o więcej niż `HOLDOUT_MARGIN` (1 cm, rozdział 4).
   7. **Tkanina** (opcjonalnie: szata, suknia, spódnica, płaszcz). Zaznacz podpięty przedmiot, zapisz plik i uruchom
      **`uo_cloth_bake.py`**. Dół przedmiotu (to, co `uo_bind_item.py` dało na łańcuchy materiału) staje się tkaniną
      Blendera: opada, buja się i odbija od ciała. Barki, pierś i rękawy zostają przypięte do szkieletu.
      - `GOAL` (0,5): jak mocno materiał ciągnie do kształtu łańcuchów dopasowanych do oryginalnych klatek UO
        (0 = czysta tkanina, 1 = bez tkaniny). `MATERIAL`: `silk`, `cotton`, `wool` albo `leather`.
      - Każda akcja jest liczona osobno. Najpierw materiał układa się przez `PREROLL` klatek w pierwszej pozie.
        Akcje zapętlone w grze (chód, bieg, stanie) są liczone `LOOP_CYCLES` razy i brany jest ostatni cykl, więc
        pętla nie skacze. Akcje konne zostają bez symulacji (koń nie jest przeszkodą dla materiału).
      - Wynik trafia do `uo_cloth/<przedmiot>.npz` obok pliku `.blend`. `render_uo_layer.py` używa go sam, a po
        bake'u odtwarzanie akcji w podglądzie 3D też pokazuje tkaninę (po ponownym otwarciu pliku uruchom skrypt
        z `BAKE = False`, żeby wrócił podgląd).
      - Trwa to około pół godziny dla wszystkich akcji (mniej: niższe `SIM_VERTS`, `QUALITY` albo tylko wybrane
        `ACTIONS`). Po zmianie przedmiotu (kształt, dopasowanie, wagi) uruchom go ponownie; nieaktualny wynik jest
        pomijany. `REMOVE = True` wraca do samego podpięcia.
5. **Broń, tarcza, włosy** (rzeczy sztywne): `uo_bind_item.py` z `PART = "weapon"`, `"shield"`, `"hair"` itd.
   (tabela wyżej). Miecz ustaw w pozycji spoczynkowej tak, żeby rękojeść była w zaciśniętej prawej dłoni, a klinga
   wychodziła po stronie kciuka: tak leży broń na oryginalnych klatkach UO.
6. **Materiał:** Add → Group → **`UO_Look`**, kolor lub teksturę podepnij na wejście *Albedo*. Rzeczy, które w grze mają
   przyjmować kolor (hue), rób w odcieniach szarości.
7. **Sprawdź ruch:** Dope Sheet → Action Editor → wybieraj akcje `NN_nazwa` i odtwarzaj (Spacja). Widok z kamery gry:
   Numpad 0, kierunek zmieniasz `uo_direction`.
8. **Wskazówki:**
   - Ubranie rób ok. 1–2 cm nad skórą.
   - Sprawdzaj zwłaszcza ataki, czary i upadki.
   - Spódnice, szaty i płaszcze bindujesz presetami `"skirt"`, `"robe"`, `"cloak"` (idą za łańcuchami materiału),
     a naturalny ruch materiału daje potem `uo_cloth_bake.py` (krok 4.7).

## 4. Render do klatek i pliku `.vd`

1. Silnik renderowania: **Cycles** (skrypt i tak sam go ustawi, razem z 1 próbką na piksel).
2. Otwórz tekst **`render_uo_layer.py`** i ustaw opcje na początku:
   ```python
   LAYER = "clothing"          # "clothing" = warstwa przedmiotu, "body" = ciało, "all" = podgląd razem
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
   DESPECKLE = 28              # pojedyncze ciemne kropki w środku przedmiotu (głębokie detale, nity) dostają kolor
                               # otoczenia (0 = wył.)
   FILL_HOLES = 4              # dziurki do 4 px otoczone przedmiotem są wypełniane (0 = wył.)
   ```
3. Uruchom **Run Script** (Alt+P). Pełna warstwa to 1050 klatek, ok. 15–30 min na CPU. Warstwa ubrania renderuje się
   bez ciała, a to, co ciało zasłania, skrypt liczy z głębokości (z `HOLDOUT_MARGIN = 0` każda klatka renderuje się
   dwa razy: z ciałem i bez).
4. Wynik w `uo_render/`:
   - `clothing/frames/NN_akcja/dirK/NN.png`: klatki na płótnie 136×120,
   - `clothing/meta.json`: kolejność i punkt zaczepienia,
   - **`clothing.vd`**: gotowy plik.

**Render w częściach.** Kolejne przebiegi do tego samego `OUT_DIR` się sumują. Możesz np. ustawić broń pod ataki
i wyrenderować `ONLY = ["09_attack_1h_slash", ...]`, potem zmienić ułożenie i wyrenderować pozostałe akcje. Każdy przebieg
zapisuje `.vd` ze wszystkimi akcjami wyrenderowanymi do tej pory. Żeby zacząć od zera, usuń folder `uo_render/`.

**Przerwanie renderu:** utwórz pusty plik `STOP` w folderze wyjściowym (np. `uo_render/clothing/STOP`) albo naciśnij
Ctrl+C w konsoli Blendera (Window → Toggle System Console). Gotowe klatki PNG zostają.

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
- **Sam model 3D (`EXACT_BODY = False`):** średnia zgodność obrysu (IoU) **0,879** na 1050 klatkach, **bez żadnych
  korekt kształtu** (same kości). Wg kierunku: 0,876–0,893. Kolory na wspólnych pikselach są dokładne z `EXACT_COLORS`.

| # | akcja | IoU | # | akcja | IoU | # | akcja | IoU |
|---|---|---|---|---|---|---|---|---|
| 0 | walk_unarmed | 0.905 | 12 | attack_2h_bash | 0.882 | 24 | mounted_run | 0.858 |
| 1 | walk_armed | 0.901 | 13 | attack_2h_slash | 0.887 | 25 | mounted_stand | 0.853 |
| 2 | run_unarmed | 0.896 | 14 | attack_2h_pierce | 0.872 | 26 | mounted_attack_1h | 0.853 |
| 3 | run_armed | 0.896 | 15 | combat_advance | 0.881 | 27 | mounted_attack_bow | 0.865 |
| 4 | stand | 0.912 | 16 | spell_directed | 0.879 | 28 | mounted_attack_crossbow | 0.852 |
| 5 | fidget_1 | 0.909 | 17 | spell_area | 0.851 | 29 | mounted_attack_2h | 0.830 |
| 6 | fidget_2 | 0.896 | 18 | attack_bow | 0.868 | 30 | block | 0.884 |
| 7 | combat_idle_1h | 0.882 | 19 | attack_crossbow | 0.887 | 31 | punch | 0.884 |
| 8 | combat_idle_2h | 0.878 | 20 | get_hit | 0.896 | 32 | bow | 0.892 |
| 9 | attack_1h_slash | 0.860 | 21 | die_forward | 0.855 | 33 | salute | 0.902 |
| 10 | attack_1h_pierce | 0.879 | 22 | die_backward | 0.857 | 34 | eat | 0.893 |
| 11 | attack_1h_bash | 0.882 | 23 | mounted_walk | 0.859 |  |  |  |

Różnice to prawie wyłącznie 1-pikselowe paski wzdłuż krawędzi (oryginał rysowano innym modelem 3D). Dużych błędów, np.
ręki w innym miejscu niż na oryginale, nie ma, więc wycięcia w przedmiotach trafiają w rękę. Dla porównania: poprzedni
model bez swoich 1254 korekt miał 0,880, a z nimi 0,979 (ale przedmioty musiały kopiować te korekty).

**Przedmioty UO.** Test na prawdziwych przedmiotach z `anim.mul` (koszula, spodnie, buty, rękawice, hełm, zbroja
płytowa): przylegające do ciała przedmioty wyrenderowane na tym modelu odtwarzają oryginalne klatki (razem z wycięciami
na ręce) tak samo dobrze jak poprzedni model z korektami. **Materiał:** spódnica IoU 0,83 (konno 0,62), płaszcz 0,73
(konno 0,67) względem oryginalnych klatek spódnicy i płaszcza. **Broń:** klinga w dłoni średnio 0,8 px od klingi katany z UO.

## 9. Jak powstał model

**Obecne ciało (MakeHuman).**
1. **Kształt:** siatka MakeHuman (CC0, mężczyzna, umięśnienie 0,6) przeniesiona na szkielet UO: każda kończyna na swoją
   kość (długość i obwód), tułów mapą wysokości (szerokość, głębokość na 7 poziomach), szyja i głowa osobno, przejścia
   wagami MakeHuman. Grubości dopasowane do oryginalnych klatek z karą za nienaturalne kształty.
2. **Szkielet:** 19 kości UO bez zmian + skręt ramion, 15 kości palców na dłoń, palce stóp; wagi z MakeHuman.
3. **Pozy:** każda klatka dopasowana do 5 kierunków naraz (własny szybki rasteryzer + LBS jak w Blenderze), naprzemiennie
   z kształtem; grubość kończyn (skala X/Z kości) i zaciśnięcie dłoni też dopasowane w każdej klatce.
4. **Dłoń i broń:** chwyt miecza skalibrowany na oryginalnych klatkach katany (anim 627), potem obrót dłoni w każdej
   klatce tak, żeby klinga pokrywała się z oryginałem. Tarcza skalibrowana na tarczy heater (anim 582).
5. **Konno:** jeździec widoczny tylko tam, gdzie jest przed koniem, i nie może wchodzić w bryłę konia.
6. **Materiał:** łańcuchy kości spódnicy i płaszcza dopasowane klatka po klatce do oryginalnych klatek spódnicy (449)
   i płaszcza (468), z zasłanianiem przez ciało, bez przenikania nóg i konia.
7. **Tekstura:** kolory z oryginalnych klatek rzutowane na UV MakeHuman, światło UO usunięte (albedo), osobno dla
   5 kierunków.

**Pierwsza wersja modelu** (proporcje i kamera UO wyznaczone z klatek, na nich opiera się obecne ciało):
1. **Dekodowanie `.vd`:** paleta RGB555, klatki RLE, punkt zaczepienia.
2. **Kamera UO z samych klatek:** wspólne dopasowanie proporcji ciała i kamery do obrysów z 5 kierunków dało rzut
   ortograficzny, elewację 28,45°, 36 px/m, zaczepienie w środku piksela i podłogę 7 cm pod nim.
3. **Kształt:** parametryczne ciało zamienione na siatkę z czworokątów. Wierzchołki dopasowane do obrysów wszystkich klatek
   (symetria, gładkość), plus „napompowanie” o 6,5 mm kompensujące bias dopasowania.
4. **Szkielet:** kości w dopasowanych stawach, wagi bone heat, obojczyki.
5. **Pozy (gradientowo, JAX):** każda klatka dopasowana na siatce ze skinningiem (LBS jak w Blenderze) w 5 kierunkach naraz.
   Człony celu:
   - wierzchołki w obrysie,
   - każdy piksel krawędzi osiągnięty,
   - limity anatomiczne (zgięcie i skręt osobno, zawiasy łokci i kolan),
   - gładkość w czasie,
   - kara za wejście pod podłogę.
   Start jest od klatki najbliższej znanej pozie, więc bez zamiany L/P.
6. **Wyjście z minimów lokalnych:** przeszukanie wielostartowe (skręt i przechył tułowia, warianty rąk, nóg i orientacji
   ciała). Wybór zawsze po prawdziwym IoU zrasteryzowanej siatki, potem wygładzenie drgań A→B→A.
7. **Koń:** bryła wizualna z 5 widoków klatek konia, bez objętości jeźdźca, przycinana dokładnym obrysem konia.
8. **Korekty na klatkę:** przesunięcia wierzchołków dopasowane regułą renderera (piksel liczy się, gdy jego środek jest
   w trójkącie). Potem każdy błędny piksel przypisany do odpowiedzialnego trójkąta i korekta na kierunek.
   Wszystko zapisane jako shape keys sterowane driverami.
9. **Tekstura i wygląd UO:** światło UO wyznaczone z klatek i usunięte z koloru, dające albedo. Obróbka UO
   (czarne tło, alfa 0/1, kontur 0,38) zmierzona na oryginale.
10. **Tryby dokładne:** oryginalne klatki spakowane jako atlas; materiał rzutuje je z kamery UO, a skrypt renderu używa
    ich obrysu przy ciele i zasłanianiu ubrań.
11. **Weryfikacja:** rig w Blenderze odtwarza dopasowaną siatkę co do < 0,1 mm, a rasteryzer zgadza się z Cycles
    co do 1 piksela.

## 10. Odtworzenie modelu (pipeline)

**Obecne ciało** (folder `pipeline/body13/`, uruchamiane z tego folderu; wymagania: `numpy scipy numba pillow "bpy==4.2.*"`).
Zapisane wyniki (`*.json`, `*.npz`) pozwalają powtórzyć dowolny krok. Dane MakeHuman (CC0) są w `mh/`, klatki przedmiotów
UO z `anim.mul` (spódnica, płaszcz, katana, tarcza, koszula, spodnie, buty, zbroja, hełm) w `mul/`.

| Etap | Skrypty | Wynik |
|---|---|---|
| Dane z pierwszej wersji | `prep_views.py`, `dump_poses.py`, `dump_horse.py`, `dump_v12.py` | `views_*.npz`, `rig_poses.npz`, `horse.npz` |
| Kształt | `shape13.py`, `fit_shape2.py` | `shape_r2.json` |
| Szkielet 55 kości | `skel13.py` | (w pamięci, `build_v13.py`) |
| Pozy | `run_poses13.py`, `views_from_poses13.py`, `run_mounted13.py` (+ `horse_sdf.py`) | `poses13_*.json` |
| Broń i dłoń | `weaponfit.py`, `handfit.py`, `shieldfit.py` | `grip_katana2.json`, `poses13_r5.json`, `shield_heater.json` |
| Materiał | `cloth13.py`, `clothfit.py`, `run_cloth.py`, `run_cloth_mounted.py` | `cloth_449all.json`, `cloth_468all.json` |
| Tekstura | `bake13.py` | albedo 5 kierunków |
| Budowa pliku | `build_v13.py`, potem `../export.py` | `.blend`, `.glb`, `.fbx` |
| Pomiary i podglądy | `eval13.py`, `itemval.py`, `gen_items.py`, `make_gif.py` | IoU, losowe zestawy, GIF-y |

**Pierwsza wersja modelu** (skrypty w `pipeline/`):

Skrypty są w `pipeline/`, uruchamia się je z tego folderu. Wymagania: Python 3.11,
`pip install numpy pillow scipy scikit-image jax optax "bpy==4.2.*"`. Pliki klienta są już w `pipeline/`: ciało
`body400.vd` i koń (0xC8) `horse200.vd`. Pliki `*.pkl` to zapisane wyniki, więc kroki można wznawiać.

| Etap | Skrypty | Wynik |
|---|---|---|
| Proporcje i kamera | `run_shape.py` | `shape_fit.pkl` |
| Siatka, szkielet, scena | `build.py` (`basemesh.py`, `sdfmesh.py`, `rig.py`, `texbake.py`) | `.blend` |
| Kształt z klatek | `refine_mesh.py`, `inflate_test.py` | `refine_mesh.pkl`, `refine_infl.pkl` |
| Światło i tekstura | `delight_bake.py`, `perdir_bake.py` | albedo, `uo_light.pkl` |
| Pozy na siatce | `posefit_seq.py`, `posefit_search.py`, `posefit_polish.py`, `jitter_fix.py`, `reeval.py` | `final_poses_v10.pkl` |
| Koń | `horse_hull.py`, `add_horse_proxy.py` | bryły i obrysy konia |
| Budowa wersji | `patch_final.py` → `uo_layers_setup.py` → `add_horse_proxy.py` → `export.py` | `.blend`, `.glb`, `.fbx` |
| Korekty kształtu | `corr_fit.py` (etap 1), `corr_fit34.py` (piksele + kierunki), `add_exact.py` | shape keys w `.blend` |
| Tryby dokładne | `build_originals.py`, `add_exact.py`, `pack_originals.py`, `strip_originals.py` | wersja finalna |
| Pomiary | `render_body_vd.py --pure`, `compare2.py`, `err_parts.py`, `gross.py`, `zoom.py` | IoU, GIF-y |

Ważne ustawienia: `UO_DELTA=refine_mesh.pkl` przy dopasowaniu póz, `refine_infl.pkl` przy ocenie i budowie;
`UO_CLAV=1` włącza obojczyki.

## 11. Ograniczenia i częste problemy

**Ograniczenia**
- Rysunek mięśni jest bardziej miękki niż na sprite'ach, bo tekstura uśrednia wiele klatek.
- Palce i twarz pochodzą z MakeHuman (na klatkach ~60 px ich nie widać).
- Sam model 3D różni się od oryginału głównie 1-pikselowymi paskami na krawędziach (ok. 12% pikseli sylwetki).
  Tryby dokładne (`EXACT_BODY`) usuwają to z renderów: ciało jest zawsze oryginalne, model decyduje tylko, co jest
  przed, a co za nim.
- Na koniu dolna część spódnicy i płaszcza może wchodzić w konia: przy renderze koń ją zasłania (jak w UO).
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
