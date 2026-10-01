# Przekazanie między sesjami (SESSION_HANDOFF)

> **Przeczytaj ten plik na początku sesji.** Na końcu sesji zaktualizuj sekcje 6 (plan i status), 7 (dziennik) i 8 (następne
> kroki), zrób commit i `git push origin main`. Użytkownik pracuje w wielu krótkich sesjach, więc ten plik jest jedynym
> pewnym nośnikiem kontekstu. Nie zakładaj niczego, czego tu nie ma.

## 0. Zasady pracy (ustalone z użytkownikiem)

- **Język:** rozmowa po polsku. Komunikaty commitów po angielsku w stylu repo: `UOModel3D: <co i po co>`.
- **Gałąź:** pracujemy na `main` (commit i push na `main`). Pull requesta nie twórz, dopóki użytkownik o niego nie poprosi.
  Gałąź `claude/friendly-knuth-44xtfw` na GitHubie stoi na commicie `ea55c0b` (stan sprzed jakichkolwiek zmian) i jest
  trwałą kopią zapasową: **nie wypychaj na nią niczego**.
- **Kopia zapasowa:** zanim zmienisz pliki w `model/`, zapisz ich kopię poza repo (np. `/home/user/UO_Model3D_backup/`).
  Kontener sesji jest tymczasowy, więc kopia w nim nie przeżyje. Trwały punkt wyjścia to commit `ea55c0b`.
- **Klatki ciała zostają.** Oryginalne klatki ciała (`client/body_0x190_frames/`, atlas oryginałów w `.blend`) opisują
  ruch postaci, na nich opiera się dopasowanie póz i tryb `EXACT_BODY`. Nie usuwaj ich i nie uruchamiaj `strip_originals.py`.
- **Mierz, nie ufaj.** Ani README, ani skryptom nie wierz na słowo. Każda liczba, na której opierasz decyzję, ma pochodzić
  z własnego pomiaru na plikach. Przed zmianą zrób pomiar „przed”, po zmianie „po”.
- **Dane klienta UO:** tylko do użytku własnego, repo jest prywatne. Cały klient pobieraj do `uo_client/` (w `.gitignore`)
  i **nie commituj** surowych `anim*.mul`, `*.idx`, `tiledata.mul` (limit GitHuba 100 MB na plik). Za to zgodnie z poleceniem
  użytkownika **wyciągnięte potrzebne rzeczy idą do repo** (sekcja 2a), a link do klienta zostaje w tym pliku.
- **Komunikaty:** użytkownik prosi o mało i krótkie komunikaty, tylko ważne informacje (wynik, blokada, decyzja do podjęcia).
- **Sesje:** użytkownik odpala kolejne sesje ręcznie. Gdy temat jest zamknięty (zapisane w `SESSION_HANDOFF.md`, wypchnięte na `main`),
  powiedz mu to wprost, żeby wiedział, że może zacząć następną. Nie instaluj ani nie uruchamiaj niczego, czego odmówił (patrz sekcja 9).
- **Podglądy dla użytkownika:** aplikacja otwiera tylko pliki z katalogu repo i katalogu roboczego sesji (scratchpad).
  GIF-y i PNG-i do obejrzenia kładź tam.
- **Pliki binarne:** `model/UO_Body_0x190.blend` jest binarny, a skrypty są w nim osadzone jako teksty (sekcja 4). Zmianę
  w `pipeline/*.py` trzeba osobno wgrać do `.blend`. Opisz w commicie, który plik binarny się zmienił.

## 1. Cel projektu

**CEL NADRZĘDNY (od użytkownika, sesja 1): nasze body ma odwzorowywać body z UO tak, żeby przedmioty zrobione na naszym modelu
pasowały na oryginalny model UO** (oryginalne ciało i sprite'y z klienta). Oceniaj każdą zmianę tym kryterium: czy przedmiot zrobiony
na naszym ciele, wyrenderowany do `.vd`, zgadza się z oryginalnym ciałem i oryginalnym spritem przedmiotu. Konsekwencje:
- Oryginalne body UO to 1050 płaskich klatek; modelu 3D, którym je zrobiono, nie mamy. Nasze ciało (MakeHuman) jest ich rekonstrukcją
  (sylwetka IoU ok. 0,88 bez korekt). Wierność ciała to nie ozdoba, tylko warunek, żeby przedmioty pasowały.
- `test_items.py` (przedmiot zrobiony na naszym ciele vs oryginalny sprite) jest główną miarą celu. Najpierw wymaga wiarygodnego baseline'u (krok 2).
- Krok 5 (ciało poprawiane na podstawie sprite'ów ekwipunku: dłonie, stopy, głowa, kończyny) bezpośrednio realizuje ten cel i ma wysoki priorytet
  zaraz po baseline'ie.
- `EDGE_COVER` (krok 4) tylko ukrywa błąd ciała w renderze (dociąga przedmiot do oryginalnego obrysu), nie poprawia modelu. Nie zastępuje kroku 5.
- Poprawianie samej sylwetki ma granicę ok. 0,88 dla czystego szkieletu (raport 2.2). v12 miał 0,979 dzięki 1254 korektom kształtu na klatkę,
  które każdy przedmiot musiał kopiować (commit `1e3ec8f`, `pipeline/uo_transfer_corrections.py`). Możliwa opcjonalna warstwa korekt
  stosowana tylko w renderze (raport 4.9): decyzja użytkownika, patrz sekcja 9.

Model 3D nagiego ciała UO (body 0x190 / 400) służy do generowania animacji ubrań, zbroi, broni, butów i tarcz w formacie
`.vd` dla klienta Ultima Online (serwer: Nelderim). Kolejność prac wybrana przez użytkownika:

1. **Najpierw udoskonalić model i render** (sekcja 6, kroki 1–4).
2. **Potem tworzyć przedmioty:** ubrania, zbroje, broń, buty, tarcze, czyli wszystko, co postać może założyć.

Raport z analizy (`docs/RAPORT_model3D_UO.txt`, 2026-10-01) zaleca **rozwijać UO_Model3D, nie budować nowego modelu**:
kamera, proporcje i 210 póz × 5 kierunków są zrobione i potwierdzone pomiarem. Czysty szkielet daje strukturalną granicę
ok. 0,88 IoU, a nowy model trafiłby w tę samą granicę.

## 2. Klient UO

- **Link do klienta (Google Drive):** https://drive.google.com/file/d/1R80D0FN_RO7xuJ7X-yz13ZRdTemNZmIz/view?usp=drive_link
  Użytkownik prosi: link podawaj dalej (zostaje tutaj), a **wyciągnięte potrzebne rzeczy wrzucaj do repo**. Cały klient
  pobieraj do `uo_client/` (poza gitem), do repo idzie tylko wyciąg (sekcja 2a).
- **Czego potrzeba** (klient Nelderim sprzed zmian, z modelami):
  `anim.idx`, `anim.mul`, `Bodyconv.def`, `Equipconv.def`, `tiledata.mul`.
  Animacje własne Nelderim (`anim3`/`anim4`, np. 420 Cloth Hood, 422 Plecak) **nie są potrzebne**: decyzja użytkownika,
  oryginalnych animacji jest wystarczająco dużo.
- **Gdzie rozpakować:** `uo_client/` w katalogu repo (ignorowane przez git).
- **Pobieranie (działa, link jest publiczny):** `pip install gdown && mkdir -p uo_client && gdown 1R80D0FN_RO7xuJ7X-yz13ZRdTemNZmIz -O uo_client/client_download`
  (2,64 GB, ok. 20 s). Jeśli zwróci stronę logowania, link znów jest prywatny: poproś użytkownika o „Każdy mający link”.
- **Rozpakowanie:** to RAR5 (5 GB po rozpakowaniu, 2336 plików, główny katalog `NelderimServUO/`). Działa tylko oficjalny
  `unrar`: `apt-get update && apt-get install -y unrar` (UNRAR 7.00). `7zip` i `unrar-free` z apt nie obsługują RAR5, `unar`
  psuje duże pliki. Wypakowuj tylko potrzebne pliki, np.
  `cd uo_client && unrar x -y -idq client_download NelderimServUO/anim.idx NelderimServUO/anim.mul ...`.
  Klient zawiera też ustawienia i wtyczki użytkownika (RazorEnhanced itp.): nie wypakowuj i nie commituj ich.
- **Stan klienta:** `anim.mul`/`anim.idx` są bajt w bajt identyczne z `*_BACKUP_przed_vd`, czyli oryginalne. `anim2` i `anim4`
  zawierają własne animacje Nelderim (zmiany z 2026-09).
- **2a. Wyciąg w repo:** `client/extract/` (opis i polecenia odtwarzające w `client/extract/README.md`): pliki `.def`,
  `equipment_extent.json` (zasięg każdej animacji ludzi/ekwipunku względem zaczepu), `item_animations.json` (przedmioty ubieralne:
  warstwa, nazwa, plik animacji, zasięg). Skrypty: `pipeline/measure_equipment_extent.py`, `pipeline/extract_tiledata.py`.
  Pliki `.vd` konkretnych animacji wyciągaj `vdtool/mul2vd.py` wtedy, gdy są potrzebne (kalibracja broni, testy), i dodawaj do
  `client/extract/vd/`. Uwaga: `mul2vd.py` zakłada ID lokalne w pliku i tylko `anim.idx/.mul`; dla `anim2`..`anim5` trzeba mu podać
  inne pliki (`python vdtool/mul2vd.py anim3.idx anim3.mul wyjscie <id>`).
- **Wyciąganie animacji:** `python vdtool/mul2vd.py anim.idx anim.mul <katalog_wyjściowy> 527 563 ...` daje `anim_NNNN.vd`,
  a `python vdtool/vdtool.py extract plik.vd praca` rozpakowuje je do PNG. Narzędzie czyta tylko `anim.idx`/`anim.mul`
  i ID od 400 w górę to ludzie i ekwipunek (35 akcji × 5 kierunków).
- **Co jest w kliencie** (z raportu): 1109 przedmiotów ubieralnych, 614 unikalnych ID animacji, 354 mają komplet 35×5,
  353 z nich ma liczbę klatek identyczną z ciałem 400. To ok. 370 tys. klatek zsynchronizowanych z ciałem, czyli zbiór
  kalibracyjny i testowy dla broni, materiałów, QA i szablonów.
- Przykładowe ID: koszula 434, spodnie 431, płytówka 527, rękawice 530, buty 477, hełm 563, szata 469, katana 627,
  tarcza 582, spódnica 449, płaszcz 468, kij 648, berdysz 614, włócznia 641.

## 3. Decyzje podjęte

| Decyzja | Wartość |
|---|---|
| Rozwijać czy budować od nowa | Rozwijać UO_Model3D |
| Płótno renderu | Parametr `CANVAS`; **256×256 z zaczepieniem (128,192)** = 192 px w górę, 128 na boki, 64 w dół (dziś 136×120 / (68,86)). **Potwierdzone pomiarem** (sesja 1): mieszczą się 444 z 449 animacji ludzi/ekwipunku; z 392 animacji ubieralnych poza płótnem są 4, żadna to zwykła broń czy ubranie: `Lantern_off` (aura do 306 px), epolety z papugą (187 px), `Cloth Ninja Jacket` (+2 px w górę), jedna bez nazwy (anim id 871). Dla tych rób większe `CANVAS` ręcznie. Stare 136×120: poza płótnem 47/52 broni 1H (maks. +40 px), 57/66 TwoHanded (+238), 15/60 hełmów (+19); liczby zgadzają się z raportem. Konwencja: `right` i `down` liczone razem z kolumną/wierszem zaczepu. Wybór rozmiaru zostawił użytkownik. |
| Praca | Na `main`; backup w `/home/user/UO_Model3D_backup/` (tylko w sesji 1) i w gałęzi `claude/friendly-knuth-44xtfw` |
| Klatki ciała | Zostają |
| Anim3/anim4 z klienta | Niepotrzebne |

## 4. Środowisko i uruchamianie

- Python 3.11. Zainstalowane w sesji 1: `pip install numpy pillow scipy "bpy==4.2.*"` (`bpy 4.2.23`). Nie ma `numba`, `jax`,
  `scikit-image`; są potrzebne tylko do odtwarzania pipeline'u w `pipeline/` i `pipeline/body13/`, nie do renderu.
- Blender nie jest zainstalowany jako program, jest tylko moduł `bpy`. Plik otwierasz tak:
  ```python
  import bpy
  bpy.ops.wm.open_mainfile(filepath="model/UO_Body_0x190.blend")
  ```
- Silnik w pliku to `BLENDER_EEVEE_NEXT`; `render_uo_layer.py` sam przełącza na Cycles z 1 próbką na piksel.
- **Teksty osadzone w `.blend`** (to je uruchamia render, nie pliki z `pipeline/`): `render_uo_layer.py`, `uo_bind_item.py`,
  `uo_cloth_bake.py`, `uo_fit_item.py`, `uo_place_shield.py`, `uo_transfer_corrections.py`, `uo_vd_writer.py`,
  `uo_horse_masks.json`, `uo_original_frames.json`.
  Uwaga: README wymienia też `uo_shield_keys.py` jako skrypt w `.blend`, ale takiego tekstu w pliku nie ma
  (jest za to `uo_transfer_corrections.py`, którego README nie wymienia). Do wyjaśnienia.
- Skrypty z `pipeline/` są źródłem; zmiany wgrywa do `.blend` `pipeline/sync_blend_scripts.py` (`--check` pokazuje różnice, nazwy skryptów
  w argumentach kopiują je i zapisują plik). Stan po sesji 1: osadzony `render_uo_layer.py` = wersja z repo; `uo_vd_writer.py` różni się
  tylko komentarzem.
- **Narzędzia testowe** (bez GUI, `bpy` jako moduł): `pipeline/run_render_headless.py` (render ze zmienionymi ustawieniami, skrypt z pliku,
  `--pre` dla obiektów testowych), `pipeline/test_canvas.py` (16 przypadków, ok. 2 min), `pipeline/test_tall_item.py` (kij 3,5 m).
  Wzorzec testów: stara wersja `render_uo_layer.py` z commitu `ea55c0b` plus wyłączony dithering.

## 5. Ustalenia z kodu i `.blend` (zmierzone w sesji 1)

- **Ciało `UO_Body` (zmierzone):** 13 380 wierzchołków, 13 378 czworokątów (bez trójkątów), UV `UVMap`, bez shape keys, materiał `UO_Skin`,
  tekstury 1024×1024 (`UO_Body_Texture`, `UO_Body_Albedo_dir0..4`) i atlas oryginałów 4760×3600. Siatka z MakeHuman (CC0), mężczyzna.
  W pozie spoczynkowej (A-pose): wysokość 1,86 m, szerokość 1,43 m z rękami, głębokość 0,39 m, stopy na z = 0.
  Szkielet `UO_Rig`: 108 kości = 55 kości skórujących ciało (19 kości UO, skręty, palce, palce stóp) + łańcuchy materiału (24 spódnicy,
  28 płaszcza) + `shield.L`; 55 grup wag. Akcje: 35, razem 210 klatek UO na kierunek.
- Kamera `UO_Camera`: ortograficzna, `ortho_scale` = 3,7778 m (= 136 px ÷ 36 px/m), `shift_x/y` = 0, pozycja
  (−0,0139; −8,4477; 5,4698), obrót X 61,544°. Scena: 136×120, `uo_anchor_height` = 0,07 m, `uo_theta_deg` = 28,4557.
  Zaczep (68,86) wynika z położenia kamery, nie z przesunięcia obrazu.
- `pipeline/render_uo_layer.py` (667 linii), sztywne 136×120:
  linia 26 `ANCHOR`, linia 241 rozdzielczość sceny, linie 262–284 dekodowanie atlasu oryginałów i masek konia (`reshape(120, 136, 4)`),
  linie 361–411 rasteryzer holdoutu (`img`, `depth`, `px_ < 136`, `py_ < 120`, filtr 3×3), linia 651 `meta.json` (`canvas=[136, 120]`).
- **Atlas oryginałów** `UO_Original_Atlas` ma 4760×3600 px = 35×30 kafli po 136×120. Materiał ciała mapuje go węzłami
  `UOX_u` (mnożnik 0,0286 = 1/35) i `UOX_v` (0,0333 = 1/30, przesunięcie +29) z `TexCoord` kamery. Mapowanie jest sztywne dla
  kadru 136×120, więc po zmianie płótna trzeba przeliczyć stałe afinicznie, żeby `EXACT_COLORS` działał w warstwach
  `body`/`all`. Warstwa `clothing` tego nie potrzebuje (ciało jest tam tylko holdoutem).
- `uo_vd_writer.py` przycina klatki do zawartości i bierze zaczep jako parametr: nie wymaga zmian przy zmianie płótna.
- `pipeline/uo_bind_item.py:48–49`: `RIGID` ma `"crossbow": "hand.R"`, a `"bow": "hand.L"`. Raport mierzy, że kusza i cała
  broń 2H w UO idą za **lewą** dłonią.
- **Dithering:** Blender domyślnie dodaje do wyjścia 8-bit szum ±1 zależny od pozycji piksela. Przy zmianie płótna zmieniał kolory o 1–2
  poziomy (i psuł „dokładne” kolory z atlasu). Skrypt ustawia teraz `dither_intensity = 0`. Pozostały szum to zaokrąglenia: na dużych
  płótnach ok. 3 piksele na 45 klatek różnią się o 1 stopień RGB555 w `.vd`; sylwetki i punkty zaczepienia są identyczne.
- Światło UO w materiale `UO_Look` to czysty Lambert: `albedo × (0,0798 + 0,9202 · max(N·L, 0))`, L = (0,0012; −0,7572; 0,6532).

## 6. Plan i status

Numeracja jak w raporcie (rozdz. 4). Kolejność zmieniona względem raportu: testy regresyjne (4.6) zaraz po `CANVAS`, żeby
kolejne kroki miały liczby „przed/po”.

- [x] **1. Parametr `CANVAS` / `ANCHOR` (raport 4.1). ZROBIONE w sesji 1.** Domyślnie 256×256 / (128, 192).
  - [x] 1a. Pomiar zasięgu wszystkich klatek ekwipunku względem zaczepu → rozmiar płótna potwierdzony (sekcja 3).
  - [x] 1b. Parametr w `render_uo_layer.py`: `ortho_scale = W/36`, przesunięcie kamery policzone tak, żeby punkt
        (0, 0, 0,07 m) wylądował na `ANCHOR` (sprawdzić rzutowaniem), atlas i maski konia wklejone ze przesunięciem
        `ANCHOR − (68,86)`, rasteryzer na `W`×`H`, `meta.json`.
  - [x] 1c. Mapowanie `UOX_u`/`UOX_v` przeliczone dla nowego płótna.
  - [x] 1d. Narzędzie wgrywające `pipeline/*.py` do tekstów `.blend` i sprawdzające zgodność.
  - Odbiór: przy `CANVAS = (136,120)` wynik identyczny co do piksela z dzisiejszym; przy 256×256 po przycięciu do starego
    obszaru też identyczny; `EXACT_BODY` nadal daje klatki identyczne z oryginałem; zero przyciętych klatek dla klas z raportu 3.1.
- [x] **2. Testy regresyjne i raport QA (4.6). BASELINE USTALONY w sesji 2** (`docs/qa/items_baseline.json`, 6 przedmiotów × 6 akcji × 5 kierunków,
      płótno 256×256). Repliki (`test_items.py` + `test_items_pre.py`) dopasowane do sprite'ów: obcięcie wysokością `zrange` (z dolnej/górnej krawędzi
      sprite'a w `04_stand`, z = −wiersz/(36·cos 28,4557°) + 0,07), `cut_far` (krótkie rękawy koszuli, t ≤ 0,4), rękawice grubość 0,03 i cięcie 0,4.
      Naprawiony błąd testu: replika dziedziczyła wagi ciała (indeksy grup spoza zakresu), co rozciągało rękawice w smugi.
      **Baseline (IoU / nadmiar px / braki px / z tego paski ≤1 px):** koszula 0,662 / 37 / 56 / 40; płytówka 0,679 / 25 / 98 / 65; spodnie 0,721 / 16 / 90 / 69;
      buty 0,742 / 19 / 43 / 36; rękawice 0,496 / 29 / 45 / 25; hełm 0,764 / 6 / 20 / 17; średnia 0,677; przycięcia 0; liczba kolorów w bloku ≤ 18.
      **Wniosek:** 60–75% braków to paski ≤ 1 px przy krawędzi renderu, i nie zależą od grubości repliki (koszula 0,012–0,03 daje 43→37 px). To różnica
      obrysu ciała względem oryginału (krok 5) i/lub brak `EDGE_COVER` (krok 4). Najsłabsze akcje: 21_die_forward, 25_mounted_stand, rękawice w siedzeniu na koniu (0,23).
      Uwaga do testów: `--tmp` nie czyści katalogu, stare klatki zostają i fałszują liczbę klatek: przed każdym przebiegiem usuń `<tmp>/<item>`.
      Zostaje: baseline na `--all` (35 akcji, ok. 10× dłużej), repliki szaty, płaszcza, spódnicy (po `uo_cloth_bake.py`), katany i tarczy, raport HTML,
      porównanie z `body13/itemval.py` (wymaga `numba`, pytanie otwarte).
- [ ] **3. Broń w lewej dłoni (4.2).** Presety `crossbow → hand.L`, `weapon2h`, `staff`, `polearm`; kalibracja lewej dłoni
      albo osobnej kości `weapon2h` (jak `shield.L`); plik chwytów na klasę broni. Odbiór: błąd ≤ 1,5–2 px (dziś 5–6 px).
- [ ] **4. `EDGE_COVER` (4.3).** Domknięcie 1-pikselowych pasków skóry. Odbiór: 0 pikseli skóry przy krawędzi obcisłych przedmiotów.
- [ ] 5. **(WYSOKI PRIORYTET po baseline'ie, realizuje cel nadrzędny)** Analiza klatek ekwipunku pod kątem lepszego ciała: rękawice 530 / buty 477 / hełm 563 jako dodatkowe ograniczenie
      orientacji dłoni, stóp i głowy przy dopasowaniu póz. Pomysł z sesji 1, jeszcze nie sprawdzony.
- [ ] 6. Materiały (4.5), ciało kobiece/elfy (4.4), ścieżka A „przemalowanie z kotwiczeniem 3D” (4.7), spięcie z nelderim-asset-pipeline (4.8).
- [ ] 7. Dopiero potem: tworzenie ubrań, zbroi, broni, butów, tarcz (rozdz. 3 README).

## 7. Dziennik sesji

**Sesja 1 (2026-10-01).**
- Przeczytano README, historię i strukturę repo oraz raport (`docs/RAPORT_model3D_UO.txt`).
- Zainstalowano środowisko (sekcja 4) i potwierdzono w kodzie dwa twierdzenia raportu: sztywne 136×120 oraz `crossbow → hand.R`.
- Odczytano parametry kamery i węzłów atlasu z `.blend` (sekcja 5). Ustalono plan `CANVAS` i zasady pracy (sekcja 0).
- Użytkownik zmienił decyzję o pracy: zamiast kopii roboczej repo — kopia zapasowa modelu i praca na `main`.
- Klient (Google Drive, link publiczny) pobrany i wypakowany częściowo; wyciąg w `client/extract/` (sekcja 2a).
- Krok 1a zrobiony: `pipeline/measure_equipment_extent.py` i `pipeline/extract_tiledata.py`. Wyniki zgadzają się z tabelą
  z raportu (maks. nadmiar 239 px vs 238, hełmy +20 vs +19), więc pomiar i raport się wzajemnie potwierdzają.
- Krok 1 (`CANVAS`/`ANCHOR`) zrobiony w `pipeline/render_uo_layer.py`: kamera (ortho_scale = W/36, przesunięcie liczone tak, by punkt
  (0, 0, 0,07 m) trafił na `ANCHOR`), atlas oryginałów i maski konia wklejane z przesunięciem, mapowanie `UOX_*` przeliczane węzłami
  `UOC_x`/`UOC_y`, rasteryzer na W×H, `dither_intensity = 0`. 16 przypadków testu płótna i test kija przechodzą (stare płótno: identycznie
  co do piksela; inne: ta sama sylwetka i kolory ±1, poza starym obszarem pusto).
- `model/UO_Body_0x190.blend`: zmieniony tylko osadzony tekst `render_uo_layer.py` (plik +2 KB); pozostałe dane bez zmian.
  Kopia przed zmianą: commit `ea55c0b` (i `/home/user/UO_Model3D_backup` w sesji 1).
- Dodane pliki sesji 1: `SESSION_HANDOFF.md`, `CLAUDE.md`, `docs/RAPORT_model3D_UO.txt`, `client/extract/`, wpis `uo_client/` w `.gitignore`.
- Krok 2 rozpoczęty (patrz sekcja 6): `test_items.py` i `test_items_pre.py` działają, ale baseline nie jest ustalony. Sprite'y w
  `pipeline/body13/mul/` (12 plików) są bajt w bajt takie same jak z klienta, więc nadają się jako wzorzec.
- Odpowiedź na pytanie użytkownika o ciało: sekcja 5 (MakeHuman, 13 380 wierzchołków, 108 kości, A-pose).

**Sesja 2 (2026-10-01).**
- Środowisko postawione od zera (sekcja 4), kopia `model/` w `/home/user/UO_Model3D_backup/` (tymczasowa). `model/` w tej sesji NIE był zmieniany.
- Praca poszła na gałąź sesji `ccr-d692622b-hcwak7` (zadanie narzucało gałąź), nie na `main`; do scalenia z `main` przez użytkownika.
- Krok 2: repliki dopasowane do sprite'ów, naprawiony błąd wag, baseline zapisany (patrz sekcja 6). Zmienione pliki: `pipeline/test_items.py`,
  `pipeline/test_items_pre.py`, nowy `docs/qa/items_baseline.json`.

## 8. Następne kroki (sesja 3)

1. Kopia zapasowa `model/` poza repo, środowisko (sekcja 4).
2. Krok 5 (poprawa ciała, wysoki priorytet): baseline jest (sekcja 6). Najpierw sprawdź, skąd biorą się paski ≤ 1 px (obrys ciała vs sprite w `04_stand`:
   porównaj sylwetkę ciała z klatkami koszuli 434 / spodni 431 / butów 477 / hełmu 563 i policz, o ile px sprite wychodzi poza ciało), potem rękawice 530
   i buty 477 jako ograniczenie orientacji dłoni i stóp. Mierz skutek w `test_items.py` (przed/po względem `docs/qa/items_baseline.json`).
   Przed krokiem 5 zapytaj użytkownika o warstwę korekt per klatka (sekcja 9).
3. Krok 4 (`EDGE_COVER`) i krok 3 (broń w lewej dłoni; klient potrzebny do `.vd` kijów 648, berdysza 614, włóczni 641, kuszy, łuku,
   mapowanie w `client/extract/item_animations.json`) dopiero potem.
4. Na koniec zaktualizuj ten plik, commit i `git push origin main`, i powiedz użytkownikowi, że temat jest zamknięty.

## 9. Pytania otwarte do użytkownika

- **Decyzja do podjęcia:** czy dopuszczasz opcjonalną warstwę korekt kształtu per klatka (jak v12, IoU 0,979), stosowaną tylko w renderze, żeby
  ciało dokładniej odwzorowywało UO, przy czystym szkielecie i animacjach? Zapytaj użytkownika przed krokiem 5, bo zmienia to jego zakres.
- Czy wolno zainstalować `numba` i uruchomić stary `body13/itemval.py`, żeby porównać go z `test_items.py`? (Użytkownik odrzucił to w sesji 1
  bez podania powodu, więc zapytaj, zanim to zrobisz.)
- Czy `Nelderim_dane_klienta_SpriteMotion.zip` z raportu to ten sam zestaw co klient, który użytkownik udostępnia?
- Body 401 w dostarczonym `anim.mul` jest prawie kopią męskiego (raport 3.5). Sprawdzić w grze lub UOFiddlerze, jak wygląda naga
  postać kobieca na Nelderim. Ważne przed krokiem 6 (ciało kobiece).
