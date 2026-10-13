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

## Czwarta runda (uwagi użytkownika z przeglądu v5)
1. **Chód z bronią, kierunek 4: „ręka zasłania broń, choć jest za nią”.** Kierunek 4 to widok z tyłu. Trzonek celował do przodu i do środka, więc łańcuch z kulą wisiał przed brzuchem i z tyłu zasłaniał go tułów (zasłanianie było poprawne, zły był kąt chwytu).
   W oryginale cep odchodzi na zewnątrz i kula wisi przy prawej nodze. Nowe `GRIP_TWIST` (obrót trzonka wokół osi dłoni przez chwyt). Przegląd -40 / -20 / 0 / +20 / +40° na stand / walk / run / combat idle: kula 10,1 / 9,2 / 9,7 / 10,5 / 11,7 px, przedmiot 6,1 / 5,7 / 5,2 / 5,2 / 5,7 px;
   +20° wyprowadza cep na bok w widoku z tyłu, z przodu i z boku bez zmian. Dla wszystkich akcji pogarszał ataki (cięcie: kula +4,9 px, czar kierowany +3,1, blok +2,9), więc tylko chód (0, 1) przez `ACTION_SET`.
2. **Czar obszarowy (17): cep obraca się wokół osi ręki.** W oryginale cep jest zebrany i celuje w górę, przedłużając przedramię. Nowe `ALIGN_ACTIONS` (trzonek w linii przedramienia, chwyt w dłoni, skręt nadgarstka nie obraca cepa) i `HANG_ACTIONS` (łańcuch nie huśta się: w każdej klatce zwisa z końca trzonka w dół, kula z boku, na zewnątrz). 17: kula 13,9 -> 13,8 px, przedmiot 6,6 -> 5,9.
3. **Atak jednoręczny konno (26): cep dziwnie się obraca, kula leci do postaci, zamiast od niej.** Trzonek w linii przedramienia (`ALIGN_ACTIONS`), przechylony do przodu ciała (`ALIGN_FWD` 0,7: w klatkach 3-4 przedramię opada w dół i do tyłu, oryginał celuje w przeciwnika), łańcuch trzyma linię trzonka (`STIFF` 20), słabsze tłumienie (`DAMP` 2).
   Przegląd (kula / przedmiot px): kość broni (v5) 19,8 / 10,9; przedramię 17,2 / 9,4; + `DAMP` 2: 16,5 / 9,0; + `STIFF` 20: 18,4 / 8,4; `STIFF` 60: 24,0 / 10,8; + `ALIGN_FWD` 0,7: 18,1 / 8,5 (kula wylatuje na zewnątrz we wszystkich kierunkach, też w 1); `ALIGN_FWD` 1,5: 20,8 / 8,9.
4. **Salut (33), jedzenie (34): cep wycięty przez ciało, kręci się przy głowie; ma być statyczny: uchwyt w dłoni, łańcuch z kulą zwisa wzdłuż niego.** `UP_ACTIONS` (trzonek pionowo w dłoni) + `HANG_ACTIONS`. Salut: kula 19,7 -> 11,0 px, przedmiot 7,2 -> 4,2; jedzenie: 17,0 -> 12,0, 6,6 -> 5,3.
Poprawka (uwaga użytkownika: w 1. klatce jedzenia broń przechodzi przez ciało): pionowy trzonek z dłoni przy biodrze szedł w górę przez bok tułowia i wychodził na plecy. `ALIGN_FWD` działa też dla `UP_ACTIONS`; jedzenie (34) 0 / 0,4 / 0,8: kula 12,0 / 9,9 / 9,1 px, przedmiot 5,3 / 4,5 / 4,6; wybrane 0,8 (przed piersią jak w oryginale, z tyłu schowany za ciałem jak w oryginale).
Nowe: `ACTION_SET` (ustawienia per akcja: `STIFF`, `DAMP`, `FRAME_TIME`, `ALIGN_FWD`, `GRIP_TWIST`). Wynik (35 akcji): kula 11,0 -> 10,6 px, przedmiot 5,3 -> 5,1 px (z poprawką jedzenia 10,56 / 5,09), szybkość kuli 9,8 px/klatkę (oryginał 10,9). Przepis: `docs/qa/flail_recipe.json`.
Poprawka (uwaga użytkownika: chód w trybie walki, akcja 15: odbicie lustrzane broni, żeby łańcuch wisiał na zewnątrz postaci): uniesiony trzonek pochylał się końcem do środka (do głowy), łańcuch z kulą wisiał między trzonkiem a głową.
Pierwsza próba (v8, `MIRROR`: kierunek trzonka odbity względem płaszczyzny przód-tył tułowia) **nie zadziałała**: w tej akcji tułów jest skręcony o ok. 70° od kierunku postaci, więc lustro przesunęło kulę w głąb obrazu (do tyłu), a w kierunku 0 nadal wisiała przy głowie (użytkownik: „nic się nie zmieniło”; rysunek: ma zwisać na lewo od postaci widzianej z przodu i w stronę pleców).
Pomiar w 3D (klatka 0, układ tułowia: prawo / przód / góra): v7 trzonek (0,01; -0,44; 0,90), v8 (0,47; -0,44; 0,76); w układzie postaci (rig) v8 = (-0,27; 0,59; 0,76) w osiach świata, czyli koniec trzonka w prawo na ekranie w kierunku 0, kula zwisała pionowo w dół od końca, więc po stronie głowy.
Poprawka (v9): akcja 15 w `UP_ACTIONS` (trzonek pionowo w dłoni, jak w oryginale) + nowe `LEAN_OUT` / `LEAN_BACK` (pochylenie w układzie kierunku postaci, nie tułowia) = 0,5 / 0,3; wolny łańcuch zwisa z końca pochylonego trzonka, więc kula jest na zewnątrz (prawa strona postaci, na ekranie w kierunku 0 lewa) i z tyłu.
Przegląd `LEAN_OUT` / `LEAN_BACK` 0 / 0, 0,35 / 0,2, 0,5 / 0,3, 0,7 / 0,3: kula 7,6 / 8,3 / 8,7 / 10,0 px, przedmiot 4,2 / 5,0 / 5,3 / 6,2 px względem oryginału (oryginał ma kulę po wewnętrznej, to życzenie użytkownika). Wybrane 0,5 / 0,3 (kula wyraźnie odsunięta od trzonka jak na rysunku);
w kierunkach 1-2 kula wisi za trzonkiem, w 3-4 (widok z tyłu) na zewnątrz ręki. 35 akcji: kula 10,7 px, przedmiot 5,2 px. `MIRROR` usunięty.
Pliki v8 i v9 złożone z klatek v7 z podmienioną akcją 15 (`vdtool.py pack`; spakowanie niezmienionych klatek v7 daje plik identyczny bajt w bajt), bez ponownego renderu pozostałych akcji.

## Art przedmiotu i gumpy paperdolla (prośba użytkownika: jasna szarość jak inne bronie UO, ładne farbowanie, rękojeść drewniana)
Narzędzia: `pipeline/uo_render_weapon_gump.py ITEM.blend OUT` (render z tego samego modelu 3D co animacja: `gump_male.png` / `gump_female.png` 260 x 237, `art.png` / `art_mirror.png`, wpisy mul `*.bin`),
`pipeline/uo_hue_preview.py` (podgląd farbowania prawdziwymi hue z `hues.mul`, tak jak robi to klient), `pipeline/uo_grey_metal.py` (metal klatek animacji dokładnie szary).
Wzorce z klienta Nelderim (`tiledata.mul`, `art.mul`, `Gumpart.mul`): mace 0xF5C (anim 631), war mace 0x1406 (642), hammer pick 0x143C (625), war hammer 0x1438 (646), club 0x13B3 (620), maul 0x143A (633).
- Gumpy broni: 260 x 237 jak ciało 12, broń pionowo w prawej dłoni (na obrazku po lewej), trzonek mace / war mace / maul w kolumnie x 47,5, środek pięści y 114; pięść ciała damskiego 13 jest ok. 1,5 px wyżej.
  Żadna z 16 sprawdzonych broni nie ma gumpu damskiego (60000 + AnimID nie istnieje, klient bierze męski); damski jest zrobiony mimo to, chwyt na pięści ciała 13.
- Skala gumpu 90,5 px/m: trzonek animacji (7,5 cm, w animacji musi być gruby) dawał w gumpie deskę 7 px (oryginały 3-5 px). W gumpie przekrój trzonka x0,7, łańcucha x0,8, kula x0,9 (`THIN`; 0,5 dawało linię 2 px).
  Uwagi użytkownika: cep pochylony na zewnątrz ciała, łańcuch ma swobodnie zwisać, trzonek wycięty w miejscu chwytu („niby jest w ręce”). `TILT` 20° (porównane 10 / 15 / 20: łańcuch z kulą ma 0,4 m pod
  trzonkiem 0,5 m, więc kula kończy się na wysokości pięści i przy 10° i 15° leżała na niej; przy 20° wisi obok dłoni), łańcuch pionowo w dół (`DRAPE` puste; wcześniej łuk na zewnątrz przy pionowym trzonku).
  `HOLD_CUT`: piksele trzonka (tylko trzonek, z przebiegu części) tam, gdzie leży pięść ciała 12 / 13 (okno wokół chwytu), są wycięte: męski 43 px w wierszach 109-117, damski 37 px w 109-116.
  Oryginalne gumpy broni wycinają trzonek nad palcami (męski wiersze 109-113). Gump: x 23-49, y 72-119 (męski), 452 px.
  Dalej (uwaga użytkownika: „malutka broń jak dla dzieci”, trzonek o 1 px grubszy i o 30% dłuższy, „postać nie musi trzymać samego końca”): przekrój trzonka x0,9 (`THIN`; szerokość 3,8 -> 4,7 px),
  trzonek x1,3 (`HAFT_LEN`: 9 cm z okuciem przy końcu bez zmian, reszta rozciągnięta, łańcuch i kula idą za końcem), chwyt 15 cm nad końcem (`GRIP_AT`; w animacji 6 cm), więc koniec z okuciem
  wystaje pod pięścią jak pierścień mace. Gump męski x 21-53, y 65-127, 574 px; wycięte pod pięścią 51 px (wiersze 109-119), damski 43 px. Art bez zmian.
  Potem („niech trzyma gdzieś powyżej końca”): przy 15 cm pod pięścią było widać tylko okucie; `GRIP_AT` 0,22 / 0,25 / 0,28 m porównane, wybrane 0,22 (kawałek drewna między pięścią a okuciem;
  od 0,25 kula sięga pięści). Gump męski x 23-55, y 71-133, 575 px.
  Potem („jeszcze dłuższy o 20%”): `HAFT_LEN` 1,56 (1,3 x 1,2), chwyt dalej 22 cm nad końcem, więc przybyło u góry: koniec trzonka na wysokości głowy, kula wisi nad dłonią. Gump męski x 19-55, y 59-133, 637 px.
  Potem („niech się lekko w dłoni przebija ten kij”): wycięcie tylko w górnych 5 wierszach pięści (`HOLD_ROWS`, palce; jak oryginały: męski 109-113), niżej trzonek prześwituje przez dłoń: męski 28 px wyciętych (wiersze 109-113), damski 27.
  Art: nowe `ART_HAFT_LEN` (jak `HAFT_LEN`); domyślnie 1,0 (art 32 x 18 px), wariant 1,56 jak w gumpie: 40 x 25 px (do wyboru użytkownika).
- Art: cep leżący, widziany z góry, trzonek po przekątnej (koniec na dole po lewej, jak mace), łańcuch skręca o 90° (`ART_CURL`; 35 / 60 / 90 porównane, przy 90 kula i łańcuch odstają od trzonka i w skali 1:1 widać cep),
  34 px/m, przekrój trzonka x1,0, łańcucha x0,8, kula x1,4, ciemna obwódka 1 px na zewnątrz (szarość 16, bez czystej czerni; oryginały mają 2-8). Drugi art = odbicie lustrzane (jak pary 0xF5C / 0xF5D). Art 44 x 18, cep 32 x 18 px.
- Kolory: metal (łańcuch, kula, okucia trzonka) dokładnie szary R = G = B, każda część najpierw sprowadzona do jednej mediany (drewno w renderze miało 2 x jaśniejszą lumę niż metal: biała deska), potem poziomy:
  gump: metal p10 / p50 / p90 / max 15 / 63 / 152 / 207 (z obwódką; mace 24 / 62 / 98 / 186), art 15 / 56 / 159 / 207. Drewno (uwaga użytkownika: „rękojeść ma być drewniana”): kolor jak trzonki klienta
  (war hammer, hammer pick, club: luma 42-58, R : G : B / luma 1,38-1,52 / 0,84-0,89 / 0,42-0,57; u nas `WOOD_TINT` 1,45 / 0,86 / 0,50), mediana gumpu (64, 40, 16), artu (96, 56, 32).
- Farbowanie (`uo_hue_preview.py`, hue rud RunUO 2419, 2406, 2413, 2213, 2425, 2219 + 33, 1153): klient wybiera kolor hue po czerwonym kanale piksela. Bez flagi PartialHue (0x00040000 w tiledata; mace, war hammer jej nie mają)
  farbuje się całość, drewno też (jak war hammer). Z flagą tylko piksele szare: nasz metal farbuje się w całości, drewno zostaje drewnem; mace z flagą ma plamy (6% jego pikseli nie jest dokładnie szare).
- Animacja: z flagą klient farbuje też klatki animacji, a w v9 tylko 74% pikseli metalu było dokładnie szarych (odcień do 8/255): przy farbowaniu zostawały szare plamki (podgląd). v10 = v9 po `uo_grey_metal.py`
  (piksel z rozrzutem kanałów <= 0,25 x luma -> szarość tej samej lumy): 99,7% metalu dokładnie szare, kształty klatek identyczne, luma +-9,5/255 (zaokrąglenie do 15 bitów), najwięcej 117 kolorów w bloku (paleta bez kwantyzacji).
