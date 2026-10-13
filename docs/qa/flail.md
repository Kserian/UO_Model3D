# Cep (kiścień): łańcuch z fizyką (sesja 23, 2026-10-12)

Prośba użytkownika: maczuga na łańcuchu, której łańcuch poddaje się fizyce. Wzorzec: oryginalna animacja cepa z klienta, którą przysłał użytkownik (`.vd`, 35 akcji × 5 kierunków, poza repo).
Model: Meshy AI według promptu z proporcjami z oryginału (147 tys. wierzchołków, jedna siatka, poza repo, licencja nieznana). Przepis: `docs/qa/flail_recipe.json`.

## Oryginał (pomiar na klatkach, 36 px/m)
Łańcuch naprawdę się huśta: w ataku kula wlecze się za ręką i wygina łańcuch w łuk, w chodzie dynda. Stojąc: trzonek ok. 11 px, zwis łańcucha ok. 13 px, kula z kolcami ok. 8×8 px; najdłuższy zasięg w klatce 46 px.
Kolor: ciemnoszary metal, mediana jasności 57/255 (p90 98, p99 148), brązowy tylko uchwyt.

## Jak działa
1. `uo_make_item.py` jak dla broni jednoręcznej (`weapon1h`, sztywno na `weapon1h.R`). Nowe `"butt"` w `"weapon"` (`uo_place_weapon.py` `BUTT`): chwyt 6 cm od końca trzonka (prośba użytkownika; klasa trzyma 19 cm od końca, czyli przy łańcuchu).
2. `pipeline/uo_flail.py` (przepis `"flail": {...}`): części wzdłuż osi broni: trzonek (cienki, mało wierzchołków na cm; gałka na końcu pominięta), łańcuch (cienki, dużo wierzchołków), kula (szerokie przekroje w dalszej połowie). `BALL_SCALE`, `CHAIN_SCALE`, `HAFT_SCALE`.
   Łańcuch = `SEGMENTS` (6) sztywnych odcinków + kula. Symulacja Verleta w przestrzeni szkieletu (kierunek = obrót wokół z, grawitacja ta sama): węzeł 0 niesie kość, reszta spada, traci prędkość (`DAMP`), trzyma odległości, kula `MASS` razy cięższa od ogniwa,
   węzły poza kapsułami ciała (miednica, kręgosłup, klatka, szyja, głowa, uda, golenie, lewa ręka). Dłoń między klatkami UO interpolowana (slerp), `FRAME_TIME` 0,1 s na klatkę UO, 36 kroków na klatkę.
   Akcje w pętli: 3 cykle, zostaje ostatni (bez skoku na styku); pozostałe: 1,5 s wiszenia w pierwszej pozie. Wynik: `flail_sim.npz` obok `item.blend`.
3. `render_uo_layer.py` `flail_fix`: odcinki łańcucha i kula obrócone jak ich odcinki, obrót przenoszony od trzonka w dół (bez skoków skrętu); trzonek jak związany. Własność `uo_flail` na obiekcie, `uo_no_body_gap` (sztywne części nie są wyginane).
4. Pomiar: `pipeline/flail_fit.py` (kula = największa gruba plama, odległość środków; przedmiot = symetryczna średnia odległość zbiorów pikseli; wspólny punkt zaczepienia).

## Pomiary (6 akcji: stand, walk_armed, run_armed, combat_idle_1h, attack slash / bash, 5 kierunków; px)
| wariant | kula | przedmiot |
|---|---|---|
| sztywny cep (bez fizyki) | 22,0 | 9,3 |
| fizyka, łańcuch ×0,65 (wybrany) | 13,7 | 6,4 |
| łańcuch ×0,8 / ×1,0 | 15,4 / 16,0 | 6,9 / 6,9 |
| łańcuch ×0,5 / ×0,4 | 12,2 / 11,4 | 6,0 / 5,6 |
| `FRAME_TIME` 0,07 / 0,14 | 15,6 / 14,2 | 7,3 / 6,7 |
| `DAMP` 0,5 / 4; `MASS` 2 | 13,4 / 13,8; 13,1 | 6,2 / 6,3; 6,1 |
| sztywność łańcucha `STIFF` 10 / 40 / 120 (trzonek ×1,4) | 15,5 / 18,2 / 18,0 | 7,3 / 8,0 / 7,8 |
| trzonek ×1,4 (bez sztywności) | 13,3 | 6,3 |

Krótszy łańcuch obniża średnią, bo krótki łańcuch mniej karze ruch, który nie trafia w fazę rysunku (w granicy to sztywna maczuga). Długość ustalona na klatce stojącej, gdzie łańcuch zwisa i porównanie jest jednoznaczne:
kula od oryginału ×0,65 2,7 px, ×0,8 5,0 px, ×1,0 10,8 px. Sztywny łańcuch (trzyma linię trzonka) pogarsza: oryginał zachowuje się jak swobodny łańcuch.
Wszystkie 35 akcji (1046 klatek): kula 13,5 px, przedmiot 5,8 px; najgorsze: jazda z atakiem (26) 22,3 / 10,4, jedzenie (34) 23,7 / 8,7, cięcie (9) 18,3 / 8,2.
Kolor: `BRIGHTNESS` 2,5 i obrys 0,7 (łańcuch ma ok. 1 px, przy obrysie 0,38 cały robił się czarny): mediana jasności 24 -> 62 (oryginał 57), p90 55 -> 93 (98), p99 97 -> 143 (148), piksele ≤ 20: 40 % -> 2 %.

## Czego model nie robi
Brak zderzeń kuli z prawą ręką i dłonią (trzyma broń); łańcuch nie zderza się sam ze sobą; ruch nie zależy od kierunku (oryginał bywa rysowany inaczej w różnych kierunkach); `item_qa` liczy kształt związany, bez symulacji.

## Druga runda (uwagi użytkownika: trzonek za krótki, kula lata jak oszalała, broń wycinana przez ciało)
**Trzonek.** Zmierzone na stojących klatkach oryginału (8× powiększenie, kierunki 1-3, chód): trzonek wystaje z dłoni o 18-19 px (ok. 0,5 m), poziomo do przodu; łańcuch do środka kuli ok. 14 px, kula ok. 8 px.
Było: trzonek 0,27 m, z dłoni ok. 7 px. Teraz `HAFT_SCALE` 2,07 (0,56 m, chwyt 6 cm od końca), `CHAIN_SCALE` 0,48 (łańcuch 0,30 m), `BALL_SCALE` 0,65. Wcześniejszy wybór długości pod średnią z pomiaru był błędem (patrz wyżej: krótszy łańcuch obniża średnią, bo mniej karze ruch nie w fazie).
**Szalejąca kula.** Nowa miara w `flail_fit.py`: przesunięcie kuli między klatkami (px/klatkę), nasze i oryginału. Pierwsza wersja: średnio 14,6 wobec 10,9; jazda stępa 16,8 / 3,2, jedzenie 23,1 / 6,6, salut 20,9 / 7,6, kusza konno 28,6 / 7,7, czar 22,0 / 10,0.
Przyczyny (zmierzone na węzłach symulacji): (1) koniec trzonka skakał 0,4-0,8 m między klatkami: kość `weapon1h.R` jest dopasowana per klatka do krótkich oryginalnych broni i jej drobne obroty na końcu 0,5 m trzonka są ogromne; (2) obrót naszego nadgarstka też się trzęsie (z sylwetek słabo określony); (3) wypchnięcie z ciała zamieniało się w prędkość (kula odbijała się od głowy, piersi, siodła).
Zmiany: `HOLD` hand.R (trzonek sztywno na dłoni), `HAND_SMOOTH` 2 (obrót dłoni wygładzony w czasie wokół chwytu; render rysuje trzonek z tym samym obrotem: klucze `<a>_<i>_M` w npz), `INELASTIC` (zderzenie zabiera prędkość), `DAMP` 6.
W oryginale część akcji ma cep zebrany (kula przy trzonku): jazda, salut, jedzenie, czary. Na prośbę użytkownika sztywno tylko tam, gdzie konieczne: `RIGID` (łańcuch ułożony w pierwszej pozie, potem sztywno w dłoni) wybrany pomiarem: tylko akcje, w których swobodna kula jest > 1,4-1,6× szybsza od oryginału, a sztywna bliżej:
17 czar obszarowy (kula 17,8 -> 13,6 px, szybkość 19,7 -> 14,6, oryginał 13,0), 18 łuk (13,3 -> 9,9; 19,0 -> 11,7, oryginał 9,3). Kusza konno (28) i jedzenie (34): sztywny tryb nic nie daje, zostaje fizyka.

| wariant (wszystkie 35 akcji) | kula px | przedmiot px | szybkość kuli (oryginał 10,9) |
|---|---|---|---|
| pierwsza wersja | 13,5 | 5,8 | 14,6 |
| nowe wymiary, `DAMP` 6, weapon1h.R | 13,4 | 6,1 | 14,3 |
| + `HOLD` hand.R | 12,1 | 5,6 | 13,5 |
| + `HAND_SMOOTH` 2 (4: 11,7 / 5,5 / 9,2) | 11,6 | 5,4 | 10,1 |
| + `RIGID` 17,18 | 11,4 | 5,3 | 9,7 |
| sztywno wszędzie (dla porównania) | 10,8 | 5,1 | 11,7 |

**Wycinanie przez ciało.** Liczba pikseli cepa nasza / oryginału: mediana 0,72, w 134 z 1031 klatek < 0,5 (ręka i dłoń, które trzymają cep, zasłaniały go). Bez zasłaniania przez ręce i dłonie (`uo_occluders` = head, thigh, shin, foot; nowa własność sceny czytana przez `render_uo_layer.py`): 0,85 i 39 klatek, przedmiot 5,3 -> 4,6 px;
bez zasłaniania w ogóle 0,89, 17 klatek, 4,5 px. Wybrane: bez rąk (głowa i nogi zasłaniają kulę za nimi). Wynik końcowy: kula 11,1 px, przedmiot 4,6 px, szybkość 9,8 px/klatkę.
**Atak jednoręczny konno (26), uwaga użytkownika: cep leci przez ciało, powinien po zewnętrznej.** Z dłonią (`hand.R`) trzonek przecinał tułów w klatkach 3-4 (dłoń skręcona do środka), w oryginale cep schodzi łukiem z boku konia.
`weapon1h.R` ma kierunek dopasowany do oryginalnych broni per klatka (też w tej akcji); z wygładzeniem (`HAND_SMOOTH` 2) już nie drga. Porównanie akcja po akcji (dłoń / kość broni, kula px): kość broni wyraźnie lepsza (kula ≥ 1,5 px i przedmiot ≥ 0,5 px bliżej)
tylko w 18 (10,4 -> 8,8), 23 jazda stępa (14,8 -> 11,7), 26 (24,6 -> 19,9); wszędzie poza tym dłoń lepsza lub równa (sama kość broni w sumie 12,1 px wobec 11,1). Nowe `WEAPON_BONE_ACTIONS` "18,23,26" (render rysuje trzonek z zapisanym nośnikiem).
Wynik końcowy (35 akcji): kula 10,9 px, przedmiot 4,5 px, szybkość kuli 9,8 px/klatkę (oryginał 10,9), piksele cepa nasze / oryginału mediana 0,85, klatki < 0,5: 32 z 1031.

## Trzecia runda (uwagi użytkownika: broń przebija ciało w chodzie, w ataku konno broń ucieka z ręki)
**Zasłanianie.** Zasada użytkownika: tam, gdzie ciało zasłania broń, ma ją zasłaniać, nawet jeśli broń będzie prawie niewidoczna. `uo_occluders` = całe ciało, także tułów
(head, upper_arm, forearm, hand, thigh, shin, foot, pelvis, spine, chest, neck, clavicle). W chodzie z bronią za plecami (kierunki 3, 4) cep prawie znika, jak w oryginale.
Liczba pikseli cepa nasza / oryginału: mediana 0,85 -> 0,70, klatki < 0,5: 32 -> 193 z 1031 (to celowe: zasłania ciało); przedmiot 4,5 -> 5,3 px.
**Broń ucieka z ręki (26).** `weapon1h.R` ma per klatka także przesunięcie (dopasowane do oryginalnych broni): chwyt trzonka odjeżdżał od dłoni do 0,62 m (klatka 3). Teraz z kości broni brany jest tylko obrót,
chwyt zawsze w dłoni (`hand.R`): odległość chwytu od dłoni we wszystkich klatkach 0,0000 m. Wynik (35 akcji): kula 11,0 px, przedmiot 5,3 px, szybkość kuli 9,7 px/klatkę (oryginał 10,9).
Zostaje: w ataku konno w klatkach 3-4 cep jest teraz w dużej części za tułowiem (zasłonięty), w oryginale kierunek 1 klatka 3 ma kulę daleko na zewnątrz.
