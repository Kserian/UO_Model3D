# Geometria slotów: dynamika oryginałów, gęstość siatki, wagi (sesja 13)

Pytanie: jak mają zachowywać się wygenerowane przedmioty, żeby „miały fizykę oryginałów” i nie były kanciaste. Dane: `docs/qa/slot_dynamics.json`,
`docs/qa/density.json`, `docs/qa/bind_sweep.json`. Narzędzia: `pipeline/slot_dynamics.py`, `test_density.py`, `test_bind_sweep.py`.
Zakres: 12 sprite'ów w `pipeline/body13/mul/` (nie cały klient: jego pobranie nie było możliwe w tej sesji), repliki ze skóry ciała.

## 1. Dynamika oryginałów (`slot_dynamics.py`, klatki przedmiotu obok klatek ciała 400)

`cover` = udział przedmiotu wewnątrz sylwetki ciała; `off` = piksele przedmiotu poza sylwetką; `swing` = odchylenie standardowe (px) środka tych pikseli
w animacji; `area_cv` = zmienność pola przedmiotu w animacji. Wybrane (walk/run, fight, die):

| klasa | przedmiot | cover | off px | swing px | area_cv |
|---|---|---|---|---|---|
| ciasne | koszula, spodnie, buty, rękawice, hełm | 0,72-0,93 | 2-14 | 0,8-7 | 0,02-0,19 |
| twarde (pancerz) | płytówka, naramienniki, nogawice | 0,74-0,87 | 16-34 | 0,9-4,7 | 0,02-0,16 |
| luźne | spódnica | 0,54-0,66 | 130-264 | 1,1-4,0 | 0,01-0,11 |
| luźne | płaszcz | 0,25-0,44 | 288-688 | 1,4-5,2 | 0,06-0,30 |

Wnioski: tkanina luźna wystaje 10-50 razy więcej niż ciasna i faluje w ruchu (płaszcz przy śmierci zmienia pole o 30%); ciasne przedmioty trzymają
kształt skóry. **Szablony tkaniny ciała** (łańcuchy spódnicy i płaszcza, bez symulacji) odtwarzają to w tym samym rzędzie wielkości: spódnica wystaje o 10-25% więcej
(278-330 px vs 252-264), swing 1,6-4,1 vs 1,7-4,0; płaszcz: swing w walce i przy śmierci o ok. 40% większy (7,0 / 7,1 vs 4,9 / 5,2 px), reszta zgodna. Brak podstaw, by je stroić.

## 2. Kanciastość = za mało wierzchołków do gięcia (`test_density.py`)

Replika (skóra ciała) zubożona do 10% i 3% ścian (stand-in obcego low-poly), wiązana jak zwykle; `ref_diff` = piksele różnicy sylwetki względem repliki o pełnej gęstości,
średnia na klatkę (6 akcji × 5 kierunków):

| przedmiot | pełna (wierzch.) | 10% bez zagęszczenia | 10% po zagęszczeniu slotu | 3% bez | 3% po zagęszczeniu |
|---|---|---|---|---|---|
| koszula | 1808 | 207 w., 11,9 px | 1066 w., **4,2 px** | 69 w., 29,0 px | 1288 w., 5,9 px |
| spodnie | 1348 | 156 w., 25,6 px | 3097 w., **6,1 px** | 53 w., 62,4 px | 3799 w., 11,4 px |
| rękawice | 3498 | 359 w., 17,8 px | 7748 w., **5,8 px** | 111 w., 38,4 px | 2462 w., 10,9 px |
| buty | 2594 | 276 w., 14,1 px | 1486 w., **6,3 px** | 93 w., 27,8 px | 1840 w., 11,3 px |

IoU ze sprite'em wraca do poziomu repliki pełnej (np. spodnie 0,793 -> 0,809 przy ref 0,808; rękawice 0,541 -> 0,549 przy 0,554). Zagęszczenie (`SIMPLE`, kształt bez zmian)
usuwa łamanie w stawach; to, co zostaje (4-6 px), to płaskie fasety zubożonej siatki w spoczynku, których zagęszczenie nie odtworzy (ekstremalnie zgrubna siatka, 3%, traci
informację i zostaje 6-11 px). Długość krawędzi: koszula, spodnie, buty osiągają wynik pełny przy średniej krawędzi <= 5 cm (poniżej nie ma zysku, a wierzchołków jest
2-4 razy więcej), **rękawice potrzebują 2 cm** (palce: przy 5 cm nic się nie dzieli i zostaje 16 px). `SMOOTH` (Catmull-Clark) wypada GORZEJ niż `SIMPLE` (np. spodnie 0,788
vs 0,800): kurczy powierzchnię; zostaje opcją dla odzieży organicznej, nie jest domyślny.

## 3. Wagi (`test_bind_sweep.py`, 11 akcji z dużym zgięciem, 8 przedmiotów × 8 ustawień)

`SMOOTH` 0 / 4 / 12 i nowy `STIFF` (wyostrzenie wag, 0,5 / 1 / 2 / 4) zmieniają IoU ze sprite'em o **najwyżej ±0,002** na każdym slocie (płytówka 0,7158-0,7195, spodnie 0,810-0,812, rękawice 0,549-0,550).
Sylwetki sprite'ów nie odróżniają polityk wag, więc **zostaje domyślna** (waga jak skóra pod przedmiotem, SMOOTH 4, STIFF 1). `STIFF` jest dostępny, ale nic go nie uzasadnia.
Czego sylwetki nie sprawdzą: zgięcia w środku sylwetki (fałdy, zachodzenie płyt), do tego potrzebne byłyby przekroje albo prawdziwy model przedmiotu.

## 4. Co weszło do potoku

- `uo_densify_item.py` (nowy, w `.blend`): poziom podziału z długości krawędzi (`EDGE_BY_KIND`), limit 30 tys. wierzchołków, `SMOOTH` opcjonalnie.
- `uo_prepare_item.py` (nowy, w `.blend`): `KIND` -> densify -> fit -> bind (tabela `SLOTS`: PART, czy zagęszczać, klasa). Sloty sztywne na kości (włosy, broda, czapka) nie są zagęszczane.
- `uo_bind_item.py`: parametr `STIFF` (domyślnie 1, bez zmiany zachowania).
- Zmierzone: koszula, spodnie, buty, rękawice. **Nie zmierzone, ustawione przez analogię:** płytówka, naramienniki, nogawice, hełm, szyja, szata, spódnica, płaszcz, włosy, broda (wartości w `EDGE_BY_KIND`).
- Nie zrobione: pełna analiza 385 animacji (wymaga klienta), symulacja tkaniny `uo_cloth_bake.py` na przedmiocie ze spódnicą/płaszczem w tym teście, prawdziwy obcy model.
