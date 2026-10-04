# Autodopasowanie wielkości i miejsca przedmiotu (`uo_autofit_item.py`, sesja 15)

Problem: `uo_import_item.py` skalował obcy model z **jednej liczby na slot** (wysokość typowego oryginału z `EXTENTS`). To pasuje tylko do przedmiotów podobnych do wzorca
(audyt `AUDYT_2026-10-03.md`, pkt 2). Zmierzone na modelu użytkownika: napierśnik Void Knight (0,56 m wysokości, naramienniki 0,995 m szerokości) dostawał skalę **1,84**,
czyli 1,8 m szerokości. Krótka kamizelka, kurtka kończąca się na żebrach i szerokie naramienniki są normalne w darmowych modelach.

## Metoda

Dla slotu (`PARTS_BY_KIND`: koszula = miednica, kręgosłup, klatka, szyja; spodnie = miednica, uda, golenie...) bierze 3500 punktów skóry (rest pose) z normalnymi (zewnętrznymi: uzwojenie
siatki ciała, ustalone raz dla całego ciała; orientacja względem środka części psuła pary nóg i rąk) i szuka skali (jednolitej), przesunięcia i ewentualnie obrotu o 180° tak, żeby:
- powierzchnia przedmiotu leżała ok. `GAP` od skóry tam, gdzie ją przykrywa (odległość od każdego punktu skóry do najbliższej powierzchni przedmiotu, ze znakiem względem normalnej skóry), przy wąskim paśmie
  bez kosztu (±3 mm) i z karą 3x za skórę wystającą z przedmiotu;
- tam, gdzie przedmiot skóry nie przykrywa (krótka kurtka, otwór na szyję), nic nie jest wymagane: oceniane są tylko wysokości zajmowane przez przedmiot, uśrednione po punktach (większy przedmiot nie wygrywa liczbą pokrytych punktów);
- przedmiot nie wystawał za bardzo (`OUT_BY_KIND`, p90 wystawania oryginałów z `docs/qa/layer_analysis.md` z zapasem) i nie uciekał ze strefy slotu (`ZONE_BY_KIND`);
- skala była bliska rozmiaru autorskiego modelu (`SCALE_PRIOR`; modele są prawie zawsze robione 1:1), wyjątek: pary (rękawice, ramiona), gdzie priorytet ściągał rozwiązanie na jedną z dwóch rąk;
- jednostki (cm, mm) znajduje przed optymalizacją: taka, która daje najdłuższy bok 0,15-3 m;
- siatka startów (skala x wysokość x przesunięcie x obrót), 10 najlepszych dopracowanych w dwóch etapach (szeroki cap 40 cm, potem 10 cm); wynik z pokryciem skóry < 90% jest sortowany za lepiej pokrywającym.

Przy niejednoznaczności (obrót 0/180°, skala) skrypt pisze `AMBIGUOUS`. Krok `uo_fit_item.py` potem wypycha resztę ze skóry (`MIN_GAP`) i **miękko ogranicza grubość** (`LIMIT`: części dalsze niż limit slotu
są ściągane `S -> LIMIT + (S - LIMIT) * 0,35`, wygładzone po siatce, potem wypychane z ciała ponownie): naramienniki Void Knighta przy 8 cm limicie (do 13,5 cm ściągnięcia na 3971 wierzchołkach) przestają być „skrzydłami”.

## Walidacja (`pipeline/test_autofit.py`, wyniki: `docs/qa/autofit.json`)

Repliki oryginalnych przedmiotów UO (skóra pokryta przedmiotem odsunięta o jego grubość) zamienione w „obcy” plik (inna skala 0,8-1,3, inne położenie, przedmioty **przycięte** do krótkich),
przywrócone starą metodą (`height`) i nową (`wrap`); błąd = średnia odległość wierzchołka repliki od najbliższego wierzchołka wyniku, mm:

| przypadek | `height` mm | `wrap` mm | wysokość / oryg. (height) | wysokość / oryg. (wrap) |
|---|---|---|---|---|
| shirt | 25.7 | 18.2 | 1.092 | 1.105 |
| shirt_small | 25.7 | 7.4 | 1.092 | 0.969 |
| shirt_short | 68.4 | 4.4 | 1.681 | 1.009 |
| plate | 22.1 | 8.3 | 1.040 | 0.972 |
| plate_short | 104.8 | 14.0 | 1.649 | 1.063 |
| pants | 38.5 | 32.0 | 1.254 | 1.222 |
| pants_short | 106.9 | 15.4 | 2.413 | 1.050 |
| legs | 52.7 | 14.6 | 1.400 | 1.035 |
| boots | 23.1 | 14.5 | 1.204 | 1.100 |
| gloves | 100.7 | 7.3 | 1.431 | 1.005 |
| helm | 14.9 | 15.4 | 1.255 | 1.105 |
| arms | 57.2 | 12.1 | 1.216 | 1.029 |
| **średnia** | **53.4** | **13.6** | | |

Uwagi: (1) stara metoda ignoruje skalę pliku (shirt i shirt_small mają ten sam błąd), a przedmioty przycięte rozciąga do wysokości wzorca (spodnie krótkie 2,4x). (2) Spodnie
i buty mają błąd 15-32 mm: skala wzdłuż osi rury (nogi) jest słabo identyfikowalna (10% skali = 7 mm odstępu), a replika spodni ma górę na 1,02 m, gdy sprite ma 1,17 m. (3) `SCALE_PRIOR = 0` (sama funkcja celu): średnia 14,1 mm,
domyślne 0,04: 13,6 mm (prior pomaga na hełmie 36,6 -> 15,4 mm, kosztuje na spodniach). (4) Replika nie ma własnej grubości ani własnej luźności, więc test mierzy zdolność odzyskania, nie jakość modelu.
Zmienne środowiskowe `UO_AUTOFIT_<NAZWA>` pozwalają stroić parametry (`test_autofit.py --env`).

## Modele użytkownika (`pipeline/uo_make_item.py`)

| model | slot | jednostki | skala | luz | uwagi |
|---|---|---|---|---|---|
| medieval_shirt (gambeson, siatka `guy` pominięta) | shirt | 1 | 1,04 | 18 mm | rękawy w T-pozie obrócone na ręce UO (`MATCH_ARMS`: -14 deg w górę, +57 deg łokieć) |
| void_knight_chest | plate | 1 | 1,125 | 17 mm | naramienniki ściągnięte do limitu 8 cm |
| Dread_Dragon_Armor (OBJ, 144 tys. wierzch.) | plate | 0,01 (cm) | 0,93 | 43 mm | zmniejszony do 30 tys., materiał szary (`METAL`, `BRIGHTNESS` 0,5), gładkie cieniowanie |
| helmet (kolczuga na szyi) | helm | 0,1 | 1,07 | 12 mm | poprzednio 1,41 bez priorytetu skali; obrót nie jest wymuszany |
| miecz | broń 1H (`weapon1h`) | n/d | długość 1,0 m | n/d | `uo_orient_weapon.py`: miecz leżał wzdłuż Y, czubek po stronie -Y |
| muszkiet (7 siatek) | `bow` (kusza) | n/d | długość 1,3 m | n/d | lufa w górę, kolba na dole; ruch kuszy/łuku |

Sloty dodane w tej sesji z zakresów oryginałów (`layer_analysis.md`), ustawienia przez analogię, przetestowane tylko pod kątem działania łańcucha na kurtce zastępczej (bez błędów): `waist` (pas: strefa 0,74-1,19 m, miednica i kręgosłup, `PART torso`), `vest` (kamizelka/dublet, MiddleTorso: 0,68-1,66 m, `PART chest`), `robe`/`skirt` (luźne, `docs/qa/robe_physics.md`), `harness` (paski na tułowiu).
`item_qa.py` (uruchamiany przez `uo_make_item.py`) mierzy, ile wierzchołków jest w ciele w ruchu i jak daleko przedmiot stoi od skóry (wiersze: akcje): gambeson 4,8% w ciele (do 74 mm), stand-off p90 4,8 cm; Void Knight 3,7% (do 113 mm), p90 10,3 cm; Dread Dragon 3,0% (128 mm), 10,9 cm; hełm 0,0% (17 mm), 11,0 cm; uprząż 1,9% (60 mm). Render wypycha te wierzchołki z ciała (`BODY_GAP`).

Ograniczenia: nie ma jeszcze testu na prawdziwym obcym modelu spodni/butów/rękawic; jakość ruchu naramienników (rozciągają się z ramieniem w czarach, bo model jest jedną ciągłą siatką: wagi „jak skóra”) nie jest mierzona;
miecz i muszkiet nie mają sprite'a odniesienia (zgodność z UO nie jest zmierzona, tylko wizualna).
