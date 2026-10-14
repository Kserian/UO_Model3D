# Podarta szata mnicha z dziurami (darmowy model, slot `robe`), sesja 24

Model: plik `.glb` od użytkownika (Google Drive, licencja nieznana; pliku nie ma w repo). Długa szata z lnu, kaptur opuszczony na plecy, sznur w pasie z dwoma zwisającymi końcami,
rękawy dzwonowe, postrzępiony rąbek i mankiety, **ok. 110 dziur i rozdarć na wylot**, łaty. Poza A (ręce ok. 45° w dół). Jedna siatka: 773 765 wierzchołków, 1 420 260 trójkątów,
jedna tekstura koloru 4096 px (beżowy len, nasycenie p50 0,13), metaliczność 0, mapa normalnych. Zamknięta bryła (0 krawędzi brzegowych, 1 kawałek) grubości ok. 1,5 cm (p50 15,6 mm), jak czarna szata z `robe_black.md`.
Zlecenie: nałożyć szatę na model, dopasować, ciało nie może przebijać materiału, tkanina ma się poprawnie ruszać we wszystkich akcjach.
**Decyzja użytkownika: dziury są zrobione specjalnie, ciało ma przez nie prześwitywać** (pierwsza wersja z zaszytymi dziurami, `FILL_HOLES`, została wycofana).

Przepis `docs/qa/robe_ragged_recipe.json` (z katalogu z `robe_ragged.glb`; `--preview` ok. 25 min, `--vd` ok. 60 min, z czego symulacja 165 klatek 43 min w 4 procesach; Blender 5.2):
```
{"name": "robe_ragged", "file": "robe_ragged.glb", "kind": "robe", "outer_shell": 0.006, "decimate": 20000,
 "materials": {"GREY_CLOTH": {"value": 0.6, "contrast": 0.5, "flatten": 0.05}},
 "prepare": {"HEM": 0.15, "HEM_FLARE": {"factor": 0.65, "from": 0.95}},
 "conform": {"CLOTH_KAPPA": 1.0, "CLOTH_MARGIN": 0.06, "SPACE_SMOOTH": 0.04, "SLEEVE_END": 0.02, "CLOTH_DROP": 0.3, "SLEEVE_CUFF": 0.05},
 "sim": {"arm_goal": 0.95, "smooth": 0.04},
 "scene": {"uo_outline": 0.6, "uo_hide_erode": 1, "uo_legs_under": 1, "uo_despeckle": 28, "uo_cloth_lie": 1.0}}
```
To przepis czarnej szaty (`robe_black.md`) bez złotego pasa i bez `fill`, z nowym `HEM_FLARE`.

## Kroki i liczby z raportu
- Import: remesh wokselowy 6 mm (773 765 -> 342 952 wierzchołków, jedna bryła), warstwa zewnętrzna (358 591 z 685 608 ścian), decymacja do 22,7 tys., tekstura wypalona 2048 px. Dziury przechodzą przez remesh (są większe niż 6 mm) i zostają w powłoce.
- Autofit: skala 1,019, przesunięcie w górę 0,79 m. Model jest dłuższy od ciała (rąbek 18 cm pod podłogą): `HEM` skraca część poniżej 0,70 m ×0,62, rąbek na 0,15 m.
- `GREY_CLOTH`: cała tkanina na szarość (brak złota), mediana 0,368 -> 0,600, kontrast 0,5 (jak szata 469, farbowalna hue).
- `conform`: rękawy z pozy A na osie rąk UO (15° od ręki, 2-3 cm od osi), skrócone z 10-11 cm za nadgarstkiem do 2 cm, koniec zwężony do 5 cm; po owinięciu 0 wierzchołków w skórze; odstęp od skóry p50 / p90 6,2 / 21 cm (model 9,3 / 21,1).
- `item_clearance.py` (35 akcji, 210 klatek, po pchnięciu renderu): materiał w skórze własnej strefy średnio 0,030 % wierzchołków, najgorsza klatka 0,43 %, najgłębiej 22,7 mm; w nogach 0,00 %; dłonie / głowa 0,01 %. (Czarna szata: 0,012 % / 0,18 % / 13 mm; postrzępione brzegi tej szaty mają więcej krótkich, odstających krawędzi.)

## Za szeroki dół: `HEM_FLARE` (nowe, `uo_prepare_item.py`)
Model ciągnie się po ziemi i jest mocno rozkloszowany; po skróceniu `HEM` (×0,62 w pionie, szerokość bez zmian) dół stoi stożkiem. Pomiar sylwetki warstwy ubrania wobec oryginalnej szaty 469
(szerokość dolnych 30 % wysokości sylwetki, px, średnia / maksimum w akcji, `cmpw` w scratchpadzie sesji):

| akcja, kierunek | pierwsza wersja | `HEM_FLARE` 0,65 | oryginał 469 |
|---|---|---|---|
| stand, kier. 0 (przód) | 39 | **29** | 22 |
| stand, kier. 2 (bok) | 25 | 22 | 17 |
| marsz, kier. 2 | 33 / 44 | 31 / 43 | 33 / 42 |
| bieg, kier. 2 (profil) | 40 / 53 | 39 / 53 | 45 / 57 |
| bieg, kier. 0 | 40 / 40 | 30 / 33 | 23 / 24 |

`HEM_FLARE` = `{"factor": 0.65, "from": 0.95, "r_min": 0.12}`: odległość od osi spódnicy (środek tkaniny na wysokości `HEM_FROM`) powyżej `r_min` skalowana od 1 na wysokości `from` do `factor` przy rąbku
(liniowo). Szerokość rąbka 0,92 -> 0,69 m. „Balon” w biegu z profilu to cecha oryginału (469 jest tam nawet szerszy), nie błąd.

## Ciało przez materiał: podział na przebicie i dziurę (`item_skin_check.py --split`, nowe)
Dziury są zamierzone, więc zwykły licznik skóry miesza dwie rzeczy. `--split` renderuje dodatkowo samą warstwę przedmiotu (bez zasłaniania przez ciało): piksel skóry, pod którym przedmiot jest,
to **skóra przed tkaniną** (ciało przebija materiał albo wychodzi spod brzegu), piksel bez przedmiotu to **skóra w dziurze** (lub pod rąbkiem). Na arkuszu dziury mają małe zielone kółka.

Wszystkie 35 akcji (1050 klatek), Blender 5.2, render końcowy:

| | ręce px | tułów px | nogi px |
|---|---|---|---|
| skóra przed tkaniną | 3409 (3,2 na klatkę) | **46** (0-12 na akcję) | 2904 |
| skóra w dziurach / pod rąbkiem | 309 | 0 | 7413 |

Gdzie (arkusze `--sheet`): ręce = nadgarstek między postrzępionym, zwężonym mankietem a dłonią (dłonie mają być widoczne; tak samo w czarnej szacie: 1,8 px na klatkę przy gładkim mankiecie);
tułów = pojedyncze piksele przy kołnierzu i w ataku konno; nogi przed tkaniną = stopy leżącej postaci w upadkach (21: 567, 22: 1521 px; tkanina jest za nimi, w kliencie to 60 / 23 px)
i nogi jeźdźca. Tułów w dziurach 0 px: dziury tułowia mają ok. 1 px, a `uo_despeckle` 28 zaciera je w warstwie ubrania; w dziurach widać głównie nogi (dół jest najbardziej podarty).
`item_body_holes.py` (warstwa `clothing` na oryginalnym body400, czyli to, co pokazuje klient; liczy też zamierzone dziury): ręka 269, tułów 91, nogi 769 px na 1050 klatek (dłonie 4673 i głowa 3911 rysowane celowo).

## Ruch tkaniny
Symulacja Blendera (`uo_cloth_sim.py`, cel = kształt z powłoki nóg, kolizja z ciałem) na wszystkich akcjach pieszych; jazda: dół za nogami jak skóra; upadki: szata wzdłuż nóg (`uo_cloth_lie`).
Arkusze klienta (bieg z profilu, upadek do tyłu): rąbek idzie za wykrokiem, w upadku wcięcie między nogami, brak skoków między klatkami.

## Odrzucone
- **Zaszycie dziur** (`FILL_HOLES` w `uo_import_item.py`: pętle brzegowe < 1,5 m zamknięte błoną, 113 dziur): działało, ale użytkownik chce, żeby ciało prześwitywało przez dziury. Kod usunięty.

## Otwarte
- Nadgarstek między postrzępionym mankietem a dłonią (3 px na klatkę); dłuższy rękaw zasłania dłoń.
- Sznur z pasa zwisa jako część tkaniny (nie ma własnej fizyki).
- Kaptur na plecach owinięty jak reszta tkaniny (bez osobnego ruchu).
