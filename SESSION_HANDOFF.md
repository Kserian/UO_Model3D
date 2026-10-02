# Przekazanie między sesjami (SESSION_HANDOFF)

> **Przeczytaj ten plik na początku sesji.** Na końcu sesji zaktualizuj sekcje 6 (plan i status), 7 (dziennik) i 8 (następne
> kroki), zrób commit i `git push origin main`. Użytkownik pracuje w wielu krótkich sesjach, więc ten plik jest jedynym
> pewnym nośnikiem kontekstu. Nie zakładaj niczego, czego tu nie ma.

## 0. Zasady pracy (ustalone z użytkownikiem)

- **Język:** rozmowa po polsku. Komunikaty commitów po angielsku w stylu repo: `UOModel3D: <co i po co>`.
- **Gałąź:** pracujemy na `main`. Wszystko, co jest przetestowane i działa, wrzucaj na `main` (commit i `git push origin main`) bez dopytywania; nietestowanych zmian nie wrzucaj. Jeśli zadanie sesji narzuca inną gałąź, wypchnij na nią, a po przetestowaniu przewiń też `main` (`git push origin HEAD:main`). Pull requesta nie twórz, dopóki użytkownik o niego nie poprosi.
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
  które każdy przedmiot musiał kopiować (commit `1e3ec8f`, `pipeline/uo_transfer_corrections.py`). Warstwa korekt w renderze (raport 4.9)
  odrzucona przez użytkownika (sekcja 3): poprawiamy model, nie maskujemy go.

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
| Warstwa korekt kształtu per klatka (v12) | **NIE** (sesja 2, potwierdzone w sesji 7: „korekt nie przywracamy póki co”). Ciało ma być poprawiane samo, w modelu 3D, tak by nowe przedmioty dobrze pasowały i wyglądały w grze. Powody (sesja 7): każdy przedmiot dostaje własne klucze kształtu na klatkę (cięższy, wolniejszy), korekta bierze „najbliższy punkt skóry” (zawodne dla obcych siatek i luźnych ubrań), korekty są policzone dla ciała męskiego (kobiece/elfy = od nowa), przedmiot traci przenośność do innych silników. Tańsza alternatywa do ewentualnego sprawdzenia: kilkanaście wspólnych kształtów korygujących sterowanych kątami stawów (pose-space deformation) jako część modelu, z walidacją na klatkach spoza próby. Zysku nie obiecano. |

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
  `uo_cloth_bake.py`, `uo_fit_item.py`, `uo_place_shield.py`, `uo_place_weapon.py`, `uo_weapon_bones.py`, `uo_transfer_corrections.py`, `uo_vd_writer.py`,
  `uo_horse_masks.json`, `uo_original_frames.json`, `weapon_motion.json`.
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
- [x] **3. Broń w lewej dłoni (4.2). ZROBIONE w sesji 5** (kość na klasę broni, patrz dziennik): `polearm.L` (kij, włócznia, halabarda, berdysz, oszczep, widły, kostur), `axe2h.L`
      (topory 2H, siekiera, młot), `bow.L` (łuk, kusze). Błąd (chamfer px, zmierzony na `.blend` i w pełnym renderze): kij 5,1 -> 0,6-0,8, włócznia 6,0 -> 0,7, topór 3,7 -> 1,4-1,8, łuk 3,1 -> 1,8-1,9.
      Plik chwytów: `pipeline/weapon_motion.json`. Dokładne liczby: `docs/qa/weapons_left_hand.json`.
- [~] **4. `EDGE_COVER` (4.3).** Główna przyczyna pasków znaleziona i naprawiona w sesji 6 (reguła `OWN_PARTS_NEVER_HIDE`, patrz dziennik): `test_items` 0,691 -> 0,717.
      Sam `EDGE_COVER` po tej naprawie daje już tylko +0,015-0,025 (symulacja offline), a zysk leży głównie przy talii/dole (nieprecyzyjne cięcia repliki), nie na bokach, więc **odłożony**; wracaj do niego tylko, jeśli paski ≤ 1 px nadal będą widoczne na prawdziwych przedmiotach.
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

- Krok 5 rozpoczęty: `pipeline/body_silhouette_qa.py` (sylwetka czystego ciała 3D vs 1050 oryginalnych klatek) i pomiar „przed”:
  `docs/qa/body_silhouette_baseline.json`. **IoU 0,876** (zgodne z raportem 0,88), stosunek pól 0,998 (ciało nie jest ogólnie grubsze/chudsze, błąd to kształt i poza),
  nadmiar 47 px, braki 50 px na klatkę, kierunki 0,872–0,880, najgorsze akcje 29, 25, 26, 17, 28, 21 (0,825–0,851). Render ciała 35 akcji trwa ok. 15 min
  (`run_render_headless.py ... LAYER='"body"' EXACT_BODY=False EXACT_COLORS=False CANVAS='(136,120)' ANCHOR='(68,86)'`, uruchamiaj w tle).

**Sesja 3 (2026-10-01).** Praca na gałęzi sesji `ccr-22f58077-ol0axl` (zadanie narzucało gałąź). **Użytkownik: nic nie pushować, zmiany mają zostać lokalnie** (commity lokalne, bez `git push`).
- Krok 5a: pomiar błędu per część ciała bez Cycles (szybki raster, 25 s na 1050 klatek): `pipeline/body_part_raster.py` + `body_part_qa.py`; zgodny z Cycles
  (różnica ok. 7 px/klatkę), po uwzględnieniu proxy konia w akcjach 23–29 IoU 0,879 (baseline Cycles 0,876). Błąd rozłożony równo na wszystkie części (uda, golenie, głowa, ramiona), brak jednej dominującej. Globalne przesunięcie o 0,25–0,5 px pogarsza wynik: zaczep jest dobry.
- Znalezione: kości `clavicle.L/R` mają Deform wyłączony, Blender pomija ich grupy i renormalizuje wagi (`pipeline/body_pose_export.py` to uwzględnia; LBS odtwarza ciało co do 0,1 mm).
- Krok 5c: `body_pose_export.py` (dane póz do npz) -> `body_shape_fit.py` (przesunięcia D wierzchołków spoczynkowych z kontur-ograniczeń: sygnowana odległość konturu modelu od konturu sprite'a, układ rozwiązywany rzadko z gładkością ważoną 1/długość krawędzi, naprawa odwróconych ścianek) -> `body_shape_apply.py` (zapis do `.blend`). Parametry finalne: `--iters 2 --lam 100000 --mu 100 --weighted --holdout 0 --maxd 0.04`.
- **Wynik (sylwetka 1050 klatek, Blender): IoU 0,879 -> 0,8945.** Na klatkach wyłączonych z dopasowania (akcje % 5 == 2) +0,013; bez jednego kierunku (dir 2) +0,019; bez dir 4 brak zysku (skrajny widok nie wynika z innych). Przedmioty (`test_items.py`, replika): średnia 0,677 -> 0,691 (koszula 0,662->0,681, płytówka 0,679->0,693, spodnie 0,721->0,752, buty 0,742->0,755, rękawice 0,496->0,503, hełm 0,764->0,762); zapisane w `docs/qa/items_after_shape.json`, części ciała przed/po w `docs/qa/body_parts_before.json` / `body_parts_after.json`.
- `model/UO_Body_0x190.blend` ZMIENIONY (binarny): siatka `UO_Body` przesunięta o `pipeline/body_shape_delta.npz` (średnio 1,4 cm, maks. 4 cm; 8 odwróconych ścianek na 26,7 tys., głównie kciuk i palce stóp). Wagi, UV, szkielet, teksty bez zmian. Kopia sprzed zmiany: commit `053e219` (plik `model/` w git) i `/home/user/UO_Model3D_backup/` (tylko ta sesja).
- Odrzucone w drodze: regularyzacja membranowa bez wag (2000+ odwróconych ścianek), przesunięcia tylko po normalnej (też odwracały ścianki), `bilap`.

**Sesja 4 (2026-10-01).** Gałąź sesji `claude/lucid-feynman-t86ia8` (zadanie narzucało gałąź), po testach przewinięta na `main`.
- Poprawka póz (kroki z sekcji 8 pkt 0): `pipeline/body_pose_fk_export.py` (dane FK 210 póz), `body_pose_lib.py` (FK w numpy; zgodne z Blenderem do 1e-5, **uwaga: kości forearm/hand/shin/foot mają `inherit_scale = NONE`**, FK to uwzględnia), `body_pose_fit.py` (per poza: korekty rotacji kości, opcjonalnie lokacji miednicy i skali; pochodne różnicami skończonymi, tłumiony Gauss-Newton, kontury jak w `body_shape_fit.py`, 5 kierunków dzieli jedną pozę), `body_pose_apply.py` (zapis do kluczy fcurves; nieużyty).
- **Wynik (kierunek 3 wyłączony z dopasowania):** IoU 0,8979 -> 0,8996 (+0,0017); w próbce dopasowania +0,009. Skala kości nic nie dodaje. Ablacja na 30 pozach: pomagają tylko nogi (+0,002) i ramiona (+0,001); tułów, głowa, miednica pogarszają. Średnie korekty 2–4,7°. Dane: `docs/qa/pose_fit_holdout.json`. **Wniosek: pozy są już tak dobre, jak pozwala sylwetka; nie wgrano do `.blend`** (`model/` bez zmian w tej sesji).
- Eksport póz z aktualnego `.blend` zajmuje 15 s (`body_pose_export.py`), więc dane do analiz odtwarzaj na żywo.

**Sesja 5 (2026-10-01).** Gałąź sesji `claude/festive-heisenberg-w4x6dy` (zadanie narzucało gałąź), po testach przewinięta na `main`.
- Środowisko od zera (sekcja 4), klient pobrany (`anim.idx/.mul`, `Bodyconv.def`, `Equipconv.def`, `tiledata.mul` rozpakowane do `uo_client/`), kopia `model/` w `/home/user/UO_Model3D_backup/` (tymczasowa).
- **Krok 3 (broń w lewej dłoni).** Narzędzia (numpy, bez Cycles): `pipeline/weapon_pose_export.py` (macierze kości dłoni i kamera dla 210 póz × 5 kierunków, 2 s) i `pipeline/weapon_fit.py`
  (maski sprite'ów broni z `anim.mul`, chamfer kij↔sprite jak w raporcie 8.3; polecenia `rigid`, `perpose`, `class`, `cross`, `xline`). Zaczep kamery: x = 36·X + 128,5 (zgodnie z istniejącymi narzędziami).
  Pomiar „przed” odtwarza raport: sztywny kij w `hand.L` 5,1 px (kij), 6,0 (włócznia), 3,1 (łuk); w `hand.R` 8,5-10 px; broń 1H (katana, miecze, maczugi, topory 1H, różdżki, krótka włócznia 639, wędka) siedzi w `hand.R` (1,6-2,2 px).
  Skala pozy kości dłoni sięga 0,9-1,3: kość broni ma `inherit_scale = NONE`, dopasowanie robione na macierzy bez skali (o ok. 0,1 px lepiej).
  Ruch jednego chwytu na klatkę (obrót + przesunięcie w osiach `hand.L`, wokół punktu linii najbliższego początku kości; zakres do 94°, średnio ok. 30°) dopasowany wspólnie na wielu broniach klasy. Klasy mają **różny** ruch:
  ruch kija nie przenosi się na topory i łuki (2,6-3,0 px), więc trzy kości. Weryfikacja: kij+berdysz+włócznia dopasowane, halabarda/czarny kij/gnarled 0,8-1,0 px poza próbą; oszczep/widły/kostur 0,7-0,95 px poza próbą.
  Głowa (cięższy koniec) wszystkich klas jest na końcu `+DIR` linii (zmierzone z pikseli).
- Wgrane do `model/UO_Body_0x190.blend` (BINARNY, zmieniony): 3 nowe kości (dzieci `hand.L`, osie jak `hand.L`, głowa kości w punkcie chwytu, bez wag na ciele) z kluczami 210 póz (`uo_weapon_bones.py`),
  osadzone teksty `uo_bind_item.py` (nowe presety), `uo_weapon_bones.py`, `uo_place_weapon.py`, `weapon_motion.json`. Ciało i jego deformacja bez zmian (sprawdzone: max różnica wierzchołków 0).
  `uo_bind_item.py`: `RIGID` ma `polearm`/`staff`/`weapon2h` -> `polearm.L`, `axe2h` -> `axe2h.L`, `bow`/`crossbow` -> `bow.L` (stary błąd `crossbow -> hand.R` usunięty; w starszym pliku bez tych kości spada do `hand.L`).
- Test w pełnym potoku (`pipeline/test_weapons.py` + `test_weapons_pre.py`: cienki walec w pozie spoczynkowej na linii klasy, `uo_bind_item.py`, `render_uo_layer.py`, 256×256, 8 akcji × 5 kierunków): kij 648 sztywno w `hand.L` 6,02 px -> `polearm.L` 0,77 px;
  berdysz 1,08; topór 611 `axe2h.L` 1,83; łuk 649 `bow.L` 1,89. Zgadza się z pomiarem numpy (siedem dziesiątych piksela różnicy to grubość walca).
- Dokumentacja: README.md i README_EN.md (tabela PART i skryptów).

**Sesja 6 (2026-10-01).** Gałąź sesji `ccr-9ece647f-fy9cvt` (zadanie narzucało gałąź), po testach przewinięta na `main`. Środowisko od zera (`pip install numpy pillow scipy "bpy==4.2.*"`), klient niepotrzebny (sprite'y w `pipeline/body13/mul/`).
- Wybór: krok 5 (rękawice). Pomiar pokazał, że sprite'y rękawic nie dają nowego ograniczenia: dłoń w `hand.R/L` ma błąd ok. 2-3 px/klatkę, tak jak reszta ciała, a obrys dłoni już wynika z klatek samego ciała. IoU rękawic 0,50 to głównie różnica między powłoką repliki a narysowanym sprite'em (palce, mankiet), nie błąd ciała.
- **Diagnoza braków przedmiotów (zmierzona na klatkach):** 70-85% pikseli „brak" (sprite ma, render nie) leży **wewnątrz sylwetki modelu ciała**, a nie poza nią. Czyli to nie błąd obrysu ciała (krok 5), tylko render: części ciała z `OCCLUDERS` (udo, goleń, ramię...) zasłaniały przedmiot, który same okrywają, i obcinały mu krawędzie. Test: `OCCLUDERS=[]` daje spodnie 0,757 -> 0,829.
- **Poprawka w `render_uo_layer.py`:** nowe `OWN_PARTS_NEVER_HIDE = True` + `worn_parts()`: części ciała, do których przedmiot jest oskórowany (próg 4% wag; przedmioty sztywne z jedną kością: weapon, shield, quiver nie okrywają niczego, poza `head`), nie zasłaniają go. `HIDER_TRIS` (holdout) osobno od `OCCLUDER_TRIS` (`BODY_GAP` nadal odpycha przedmiot od wszystkich okluderów).
- **Wynik (`test_items`, replika, 6 przedmiotów × 6 akcji × 5 kierunków, 256×256):** średnia 0,691 -> 0,717: koszula 0,681 -> 0,706, płytówka 0,693 -> 0,690 (bez zmian), spodnie 0,752 -> 0,799, buty 0,755 -> 0,768, rękawice 0,503 -> 0,558, hełm 0,762 -> 0,780. Dane: `docs/qa/items_after_own_parts.json`. Nadmiar px rośnie (koszula 37 -> 42), bo okluder przycinał też nadmiar repliki.
- Symulacja EDGE_COVER offline (dokładany pasek ≤ 1 px do oryginalnego obrysu): przed naprawą +0,04..0,07, po naprawie +0,015..0,025; ograniczony do pasa przy krawędzi modelu daje ~0. Patrz krok 4.
- `test_items.py`: nowa opcja `--set NAME=VALUE` (dowolne ustawienie `render_uo_layer.py`). `test_canvas.py`: wyłącza nową regułę w teście kanwy (referencja ea55c0b jej nie ma); wynik jak przed zmianą (15 OK, 256×256 clothing FAIL o 2 px = zaokrąglenia, jak w sesji 1).
- `model/UO_Body_0x190.blend` ZMIENIONY (binarny): tylko osadzony tekst `render_uo_layer.py` (sync). Kopia: `/home/user/UO_Model3D_backup/` (tymczasowa) i commit `a99e81f`.
- Uwaga do metryki: replika w `test_items` ma niedokładne cięcia (talia, dół, dekolt), więc część „braków" to artefakt repliki, nie renderu.

**Sesja 7 (2026-10-02).** Gałąź sesji `ccr-524e0ea0-tftgjx` (zadanie narzucało gałąź). Środowisko od zera (sekcja 4), `model/` NIE zmieniany. Tylko pomiar, bez zmian w kodzie.
- Punkt 0d(a), płytówka (0,690): nakładka `test_items --img` pokazuje, że braki leżą przy kołnierzu/ramionach (góra sprite'a) i na dole (rąbek), a nie przy obrysie ciała. Replika (skóra ciała +0,03 m) nie ma kołnierza, naramienników ani rozszerzonego dołu. Zmierzone: grubość repliki 0,03 jest optimum (0,045 -> IoU 0,686; 0,06 -> 0,661; nadmiar rośnie 37 -> 55 -> 81 px, braki spadają 85 -> 75 -> 68 px). **Wniosek: 0,69 to granica repliki, nie błąd renderu ani ciała; dalsze strojenie `test_items` dla płytówki nie ma sensu.** Reguła `OWN_PARTS_NEVER_HIDE` jest tu neutralna, nie szkodliwa.
- Brak w repo prawdziwego, ręcznie zrobionego przedmiotu (poza `model/example_clothing/Example_Shirt_layer.vd`), więc punkt 0d(a) w wersji „prawdziwy przedmiot” nadal czeka na przedmiot od użytkownika.
- **Nowe repliki w `test_items.py`:** `skirt` (anim 449) i `cloak` (468) = szablony `UO_Template_Skirt/Cloak` z `.blend` związane `uo_bind_item.py` (łańcuchy materiału, bez symulacji `uo_cloth_bake.py`); pole `template` w specyfikacji. Baseline: spódnica 0,789, płaszcz 0,704. Sprite'y 469 (szata), 582 (tarcza), 627 (katana) są w `body13/mul/`, ale na nie nie ma jeszcze replik (potrzebna geometria: tarcza = dysk wg `uo_place_shield.py`, katana = linia w `hand.R`).
- **Znaleziona wada renderu:** tułów (`OCCLUDERS` go pomija) nigdy nie zasłaniał przedmiotu, więc płaszcz wiszący za plecami był widoczny na piersi, a sprite 468 pokazuje tylko boki. Poprawka w `render_uo_layer.py`: `TORSO_HIDE_MARGIN = 0.12` (tułów zasłania przedmiot, gdy ten jest za nim o > 12 cm), **tylko gdy noszony jest płaszcz** (grupy `cloak_*`). Pomiar: płaszcz 0,704 -> 0,708 (nadmiar 152 -> 113 px, braki 115 -> 134 px: szablon płaszcza ma inny kształt niż sprite, to granica), inne przedmioty bez zmian co do liczby (0,717 dla 6). **Próba włączenia dla wszystkich przedmiotów odrzucona:** spodnie 0,799 -> 0,725, koszula 0,706 -> 0,691, płytówka 0,690 -> 0,667, bo UO rysuje rękaw/udo za tułowiem mimo wszystko. Spódnica z włączonym zasłanianiem miała 0,809 (+0,02), ale nie da się jej odróżnić od szaty (ta sama szablonowa spódnica, a szaty nie ma jak sprawdzić bez sprite'a 469 w repo), więc zostawione wyłączone. Dane: `docs/qa/items_after_cloak_torso.json`. `test_canvas.py`: jak w sesji 6 (15 OK, 256×256 clothing 2 px). `model/UO_Body_0x190.blend` ZMIENIONY (binarny): tylko osadzony `render_uo_layer.py` (sync).
- **Tarcza (582) jako replika-dysk w `test_items`:** sprawdzone i **odrzucone** (nie ma tego w kodzie): sprite to tarcza typu „heater” (szeroka u góry, szpic w dół, ok. 17×30 px), dysk o promieniu 0,3-0,6 m daje IoU 0,12-0,20 i miesza błąd kształtu repliki z błędem ustawienia. Do sensownego testu trzeba kształtu tarczy dopasowanego do sprite'a, nie dysku. Katana: replika to ten sam test co `test_weapons.py` (linia dopasowana do tego samego sprite'a), więc pominięta.
- **Prawdziwy przedmiot:** nowe narzędzie `pipeline/test_real_item.py` (renderuje kolekcję `Clothing` z `.blend` bez repliki i liczy te same metryki co `test_items`). `Example_Shirt` (ręcznie zrobiona koszula związana ze szkieletem) vs sprite 434: **IoU 0,600** (replika koszuli 0,706), nadmiar 60 px, braki 62 px (`docs/qa/real_example_shirt.json`). Nakładka: rękawy wystają szerzej niż w sprite'cie, a dół koszuli jest krótszy; to projekt przykładowej koszuli (inny krój niż 434), nie błąd ciała ani renderu, ale to jest pierwszy wiarygodny punkt odniesienia dla przedmiotów od użytkownika.
- **Użytkownik: przedmioty będą z darmowych modeli 3D** (nie robi własnych). Darmowych ubrań w tej sesji nie dało się pobrać (repo `makehuman-assets` niedostępne; `makehumancommunity/makehuman` jest klonowalne, ale katalog `hair` pusty, brak `.mhclo` ubrań), więc potok sprawdzony na „obcym” pliku zrobionym z repliki.
- **Nowe: `pipeline/uo_import_item.py`** (wgrany do `.blend`; BINARNY zmieniony: tylko nowy tekst): import `.glb/.gltf/.fbx/.obj/.dae/.stl/.ply`, pieczenie siatki (obcy szkielet/modyfikatory zaaplikowane, wagi, shape keys, parenty, szkielet, puste, światła, kamery wyrzucone), lista siatek w pliku i `SKIP` (pomocnicze siatki), `JOIN`, `TURN`, skala jednolita i ustawienie na ciele według `KIND`: zakresy wysokości z oryginalnych sprite'ów (431, 434, 449, 468, 477, 527, 528, 529, 530, 563; stand, średnia 5 kierunków) w tabeli `EXTENTS` w skrypcie; środek x/y z ciała na tej wysokości; ostrzeżenia (skala poza 0,3-3, ponad 20k wierzchołków). **Test** `pipeline/test_import_item.py` (+ `run_script_in_blend.py`, który kończy proces przez `os._exit`, bo moduł `bpy` potrafi wywalić segfault przy zamykaniu): replika koszuli zrobiona „obcą” (skala 1,15, przesunięcie, glTF Y-up z kośćmi UO w środku i dodatkową siatką „Icosphere”) -> import (`SKIP=icosphere`) -> `uo_fit_item` -> `uo_bind_item` -> render vs sprite 434: bbox odtworzony z błędem do ok. 4 cm w z i 3 cm w x/y, **IoU 0,670** (ta sama replika bez importu: 0,706; różnica z dopasowania skali do zakresu sprite'a, +5%). Ścieżki obj i fbx dają wynik identyczny jak glb.
- **Czego import NIE robi (do zrobienia przy pierwszym prawdziwym modelu):** nie ocenia, czy przód patrzy w -Y (jest `TURN`), nie dopasowuje poz/ramion (to `uo_fit_item.py`, `MATCH_ARMS`), nie zamienia materiałów/tekstur PBR obcego modelu na „UO look” (krok 6 „Materiały”: w teście tylko jeden materiał, `colors 2`), skaluje tylko po wysokości (model o innych proporcjach niż UO będzie za szeroki/wąski), i nie wie, czy to ubranie dla ciała innego niż męskie.

## 8. Następne kroki (sesja 8)

**Priorytety dla następnej instancji (ustalone z użytkownikiem w sesji 7, w tej kolejności):**
1. **Włosy z Sketchfab (CC BY 4.0, autor Curuata, https://sketchfab.com/3d-models/hair-cc7e804cc15340db92d9464b32f71a2c, 4200 wierzchołków, referencja: fanowska fryzura Genshin/Ayato).** Pobranie wymaga loginu Sketchfab, więc **użytkownik sam pobiera glTF i wrzuca do repo** (np. `assets/hair_curuata/`); nie obchodź logowania. Po pojawieniu się pliku: `uo_import_item.py` (do `EXTENTS` trzeba dodać `hair`, `hat`; patrz punkt 2) -> `uo_bind_item.py PART="hair"` -> render -> porównanie z oryginalnymi włosami UO (sprite'ów włosów nie ma w `pipeline/body13/mul/`, trzeba je wyciągnąć z klienta). Zapisz atrybucję autora w repo (plik `assets/.../LICENSE_ATTRIBUTION.md`).
2. **Analiza A: klatki wszystkich ubieralnych animacji z klienta** (`client/extract/item_animations.json` mapuje 392 animacje z klatkami na warstwy; klient pobierz wg sekcji 2: link publiczny, `gdown`, `unrar`; do `uo_client/`, poza gitem). Wynik: tabela dla każdej warstwy (włosy, czapki, szata, pas, naszyjnik, plecak, rękawice itd.): zakres wysokości w pozie spoczynkowej, odstęp od ciała (px / cm) na część ciała, grubość. Użyj do (a) rozszerzenia `EXTENTS` w `uo_import_item.py`, (b) sensownych domyślnych `MIN_GAP` w `uo_fit_item.py` per typ (dziś 15 mm to wartość z głowy). Nie spodziewaj się poprawy sylwetki ciała z tej analizy (sesja 6).
3. **Analiza B: kalibracja broni jednoręcznej w prawej dłoni** (jak krok 3 dla lewej, narzędzia `weapon_pose_export.py` / `weapon_fit.py`; dziś miecze, maczugi, topory 1H sztywno w `hand.R` z błędem 1,6-2,2 px; cel < 1 px). Osobna kość na klasę broni, jak `polearm.L`.
4. **Materiały (krok 6):** zamiana tekstur/PBR obcego modelu na „UO look” (kolory w palecie, 18 kolorów w bloku), bo to wyjdzie na wierzch przy pierwszym prawdziwym modelu.
5. Później/opcjonalnie: analiza C (statystyka zasłaniania per typ przedmiotu, uogólnienie `TORSO_HIDE_MARGIN`), pose-space deformation jako część modelu, `EDGE_COVER`.
Czego nie robić: korekt per klatka (v12), dalszego strojenia replik `test_items`, dalszego dopasowywania sylwetki ciała (granica ok. 0,90).

0f. (Sesja 7) **Pierwszy prawdziwy darmowy model** (użytkownik poda plik lub źródło): `uo_import_item.py` -> `uo_fit_item.py` -> `uo_bind_item.py` -> `test_real_item.py --anim <sprite referencyjny>`. Błędy tego łańcucha na prawdziwym modelu są teraz najważniejsze. Potem materiały (krok 6): zamiana tekstur obcego modelu na „UO look”, bo to druga rzecz, która wyjdzie na wierzch.

0e. (Sesja 7) Zostaje do wyboru: (a) rozszerzenie baseline'u `test_items` o inne ścieżki potoku (szata 469, płaszcz 468, spódnica 449 po `uo_cloth_bake.py`, katana 627, tarcza 582; sprite'y są w `pipeline/body13/mul/`), bo dziś testowane są tylko przedmioty „skóra + grubość”; (b) krok 7 (tworzenie przedmiotów), jeśli użytkownik poda pierwszy przedmiot; (c) krok 6 (materiały / ciało kobiece, wymaga odpowiedzi na pytanie o body 401 w sekcji 9). `test_items` dla ubrań typu skóra jest wyczerpany (średnia 0,717, patrz dziennik sesji 6 i 7).

0d. (Sesja 6) Zostaje: (a) prawdziwy przedmiot zamiast repliki (np. sprawdzić koszulę/spodnie/płytówkę zrobioną ręcznie) dla oceny reguły `OWN_PARTS_NEVER_HIDE`; płytówka nie zyskała (0,690), sprawdź czemu (okluder uda/ramion przy grubszej powłoce);
    (b) dokładniejsze cięcia repliki w `test_items.py` (zrange z sprite'a po akcjach), żeby metryka nie mieszała błędu repliki z błędem renderu; (c) krok 6 (materiały) albo krok 7 (tworzenie przedmiotów), skoro ciało i render są blisko granicy.

0c. (Sesja 5, gotowe) krok 3. Zostaje do rozważenia: **obrót broni wokół własnej osi (roll)** nie jest skalibrowany (kij to prosta, nie widać obrotu); topory i halabardy z płaskim ostrzem mogą być obrócone inaczej niż w UO.
    Sprawdzić na sprite'ach ostrza (np. 613, 624) i dodać do dopasowania człon obrotu wokół osi. Kostur pasterski 621, oszczep 626 i widły 636 już działają na `polearm.L`, siekiera 615 i młot 646 na `axe2h.L` (nie są w pliku jako wagi klasy, tylko sprawdzone poza próbą). Następne po tym: krok 4 (`EDGE_COVER`) albo krok 5 (dłonie/rękawice).


0. (Sesja 4) Poprawka póz sprawdzona i odrzucona jako słaba dźwignia (patrz dziennik). Sylwetka ciała ma granicę ok. 0,90, błąd rozłożony równo na części. Zamiast dalszej gonitwy za IoU sylwetki rozważ: (a) pozy palców/dłoni (rękawice 0,50 to najgorszy przedmiot w `test_items`), (b) kroki 3 i 4 (broń w lewej dłoni, `EDGE_COVER`), (c) rozszerzenie baseline'u `test_items` (szata, płaszcz, spódnica, katana, tarcza).


0b. (Sesja 3, gotowe) kształt ciała dopasowany, patrz dziennik. Następna dźwignia: **poprawka póz** (kości główne × 210 póz × 5 widoków) liniaryzacją konturów jak w `body_shape_fit.py`; poza zapisana w fcurves (kwaternion + skala + lokacja pelvis, klatki 1+3i); nowa siatka wymaga ponownego sprawdzenia. Potem dłonie (sprite+ w `hand.R` największy) i głowa.


1. Kopia zapasowa `model/` poza repo, środowisko (sekcja 4).
2. Krok 5 (poprawa ciała, wysoki priorytet, bez warstwy korekt: decyzja użytkownika). Pomiary „przed” są: `docs/qa/body_silhouette_baseline.json`
   (IoU 0,876, `pipeline/body_silhouette_qa.py`) i `docs/qa/items_baseline.json` (średnie IoU 0,677, `pipeline/test_items.py`). Plan analizy:
   a) rozbij błąd sylwetki na części ciała (głowa, tors, ramię, przedramię, dłoń, udo, goleń, stopa) dla wszystkich 1050 klatek: zrenderuj maski części
      (np. materiał/identyfikator na część) i policz nadmiar/braki na część, akcję i kierunek; znajdź błędy systematyczne vs pojedyncze pozy;
   b) użyj klatek ekwipunku jako dodatkowego ograniczenia kształtu (najpierw rękawice 530, buty 477, hełm 563, spodnie 431, koszula 434, płytówka 527,
      potem reszta, jeśli pomaga): obrys oryginalnego ciała „od zewnątrz” dla dłoni, stóp, głowy, kończyn;
   c) poprawiaj siatkę/pozy/wagi, a po każdej zmianie powtarzaj oba pomiary i zachowuj poprawkę tylko przy poprawie wyniku.
   Granica czystego szkieletu to ok. 0,88 (raport 2.2): spodziewaj się poprawy tam, gdzie błąd jest systematyczny, nie 0,98.
   Render ciała 35 akcji trwa ok. 15 min: uruchamiaj w tle.
3. Krok 4 (`EDGE_COVER`) i krok 3 (broń w lewej dłoni; klient potrzebny do `.vd` kijów 648, berdysza 614, włóczni 641, kuszy, łuku,
   mapowanie w `client/extract/item_animations.json`) dopiero potem.
4. Na koniec zaktualizuj ten plik, commit i `git push origin main`, i powiedz użytkownikowi, że temat jest zamknięty.

## 9. Pytania otwarte do użytkownika


- ~~Warstwa korekt per klatka~~: rozstrzygnięte w sesji 2, **nie** (patrz sekcja 3). Nie wracaj do tego bez prośby użytkownika.
- Czy wolno zainstalować `numba` i uruchomić stary `body13/itemval.py`, żeby porównać go z `test_items.py`? (Użytkownik odrzucił to w sesji 1
  bez podania powodu, więc zapytaj, zanim to zrobisz.)
- Czy `Nelderim_dane_klienta_SpriteMotion.zip` z raportu to ten sam zestaw co klient, który użytkownik udostępnia?
- Body 401 w dostarczonym `anim.mul` jest prawie kopią męskiego (raport 3.5). Sprawdzić w grze lub UOFiddlerze, jak wygląda naga
  postać kobieca na Nelderim. Ważne przed krokiem 6 (ciało kobiece).
