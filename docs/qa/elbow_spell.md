# Łokieć w czarze obszarowym (17_spell_area): pomiar, 2026-10-09

Zgłoszenie: przy czarowaniu, gdy postać unosi ręce, jedna ręka jest zgięta w łokciu nienaturalnie w dół. Wzorzec: oryginalne body 400 (`client/body_0x190_frames`, plik użytkownika `anim_0400.vd` jest z nim identyczny, 0 różnych klatek z 1050).

## Co jest
Kąt łokcia z kości (`upper_arm`/`forearm`, pozy wszystkich 35 akcji):
- `17_spell_area`, **lewa ręka**, klatki 0-4: **149 / 163 / 162 / 160 / 156°** (anatomicznie max ok. 145°). Klatka 2: bark z = 1,56 m, łokieć 1,80 m, nadgarstek **1,48 m**: ramię prosto w górę, przedramię złożone prosto w dół wzdłuż ramienia. Prawa ręka w tych samych klatkach: 45-70°, przedramię w górę (nadgarstek 1,81 m).
- Lewy bark jest też o 17 cm wyżej niż prawy w klatce 2 (obojczyk podciągnięty); możliwe, że to ten sam błąd dopasowania (niezmierzone).
- Pojedyncze klatki z łokciem >160° poza czarem: `26_mounted_attack_1h` klatka 0 (prawa 162°), `29_mounted_attack_2h` klatka 1 (lewa 161°). Reszta ≤145°.
- Sylwetka vs oryginał (IoU, 5 kierunków): 16_spell_directed 0,86-0,93; 17_spell_area klatki 1-4 **0,79-0,84** (najgorsze w całym ciele). W nakładkach brakuje zaciśniętych pięści (czerwone plamy na końcach rąk) i dłoń lewej ręki wisi poniżej łokcia, tam gdzie oryginał ma pięść w górze (kierunki 1 i 3).

## Dlaczego tak wyszło
Sylwetka z jednej strony nie wyznacza zgięcia łokcia (raport, pkt „6 póz: łokcie i kolana różnią się o ok. 6 px”): złożone przedramię i wyprostowane w górę dają prawie tę samą sylwetkę przy rzucie z boku, a stare dopasowanie miało limit obrotów i wpadło w ten minimalnie lepszy lokalny kształt.

## Próby naprawy (nie wdrożone)
Narzędzia: `pipeline/arm_refit.py` (lokalne, losowe starty), `pipeline/arm_grid.py` (cała sfera kierunków ramienia × obrót × zgięcie 20-120°, potem dopracowanie). Cel: 1 − IoU sylwetki modelu vs sprite, 5 kierunków naraz, podwójna waga nad barkiem.

| klatka | koszt stary (łokieć ok. 160°) | koszt nowy, łokieć ≤120° | łokieć nowy |
|---|---|---|---|
| 1 | 0,381 | 0,357 | 64° |
| 2 | 0,363 | 0,368 | 104° |
| 3 | 0,407 | 0,414 | 111° |
| 4 | 0,391 | 0,354 | 74° |

Wniosek: **sylwetki akceptują łokieć anatomiczny tak samo dobrze jak złożony** (różnica ±0,006, w 2 klatkach lepiej), czyli złożony łokieć jest błędem dopasowania, nie wiedzą z oryginału. Ale same sylwetki nie wybierają sensownego rozwiązania: w klatkach 1-2 najlepsze „anatomiczne” przedramię zawija się nad głową w widoku od tyłu (kierunki 3-4), więc **żadnej pozy nie wgrano do `.blend`**. Zmieniona mierzona wielkość (koszt) jest za mało czuła na to, co widać na oko.

## Decyzja użytkownika i wdrożenie (2026-10-09)
Użytkownik: w grze ręce w tym czarze ruszają się symetrycznie, lewa ma robić to samo co prawa, nic nie jest skręcone (oryginalne klatki body 400 nie mają skrętu tułowia), sprite'y mają się pokrywać. Wdrożone w `model/UO_Body_0x190.blend`, **tylko akcja `17_spell_area`, 7 kluczy**.

**Błąd w starych kluczach.** Oprócz złożonego lewego łokcia dopasowanie z sesji budowy ciała zostawiło w akcji 17 skręt (kręgosłup do -30° wokół własnej osi, klatka piersiowa 20-28° przechyłu, szyja 25° skrętu, miednica -15°), który prawie się znosił, a lewy bark był o 17 cm wyżej niż prawy. Pierwsza próba tego dnia (samo odbicie prawej ręki na lewą przy starym tułowiu) dawała IoU 0,797-0,831, bo odbijała ręce na skręcony tułów; to była zła droga i została porzucona.

**Metoda** (`pipeline/arm_sym_fit.py --torso upper`, per klatka, Powell z losowymi startami, cel = 1 − IoU sylwetki modelu vs sprite z 5 kierunków naraz, podwójna waga nad barkami):
- lewa ręka = **dokładne odbicie** prawej względem klatki piersiowej: obojczyk, ramię, przedramię, dłoń i palce, `q = (w, x, -y, -z)`, skala bez zmian, przesunięcie obojczyka z odwróconym x (macierze spoczynkowe kości L/R są lustrami `M·B·M`, `M = diag(-1,1,1)`; `arm_mirror_action.py`); wspólna poza obu rąk jest szukana (12 parametrów),
- miednica, kręgosłup, klatka piersiowa, szyja, głowa: **tylko pochylenie** (obrót wokół lokalnego X = osi bocznej), skręt i przechył = 0; uda są ustawiane tak, żeby nogi zachowały orientację w świecie,
- kara za duże kąty szyi i głowy (`NECK_PRIOR` 0,4): bez niej wychodził zygzak szyi -53° / głowa +39° o tej samej sylwetce, z nią szyja ≤ 13°, głowa ≤ 4°,
- etap 2 i 3 (`EXTRA=1`, start z wyniku poprzedniego): przesunięcie miednicy (kara) i symetryczna długość ramienia / przedramienia (skala 0,96-1,09), 2 rundy; to dało pokrycie sprite'ów.
Odrzucone: tułów „keep” (stary skręcony) z symetrycznymi rękami (koszt 0,5-0,6 vs 0,36-0,41); tułów „sym” bez korekty miednicy, szyi i głowy; szerokie losowe starty (gorsze).

**Pomiar** (przed -> po):
- łokcie akcji 17: lewy 149-163° -> **7-70°, identyczny z prawym** w każdej klatce (błąd odbicia 0,0000 m); nadgarstek nad łokciem w klatkach z uniesionymi rękami; barki na tej samej wysokości; skręt i przechył tułowia 0,
- IoU sylwetki akcji 17: 0,8618 -> **0,8641** (klatki: 0,911 / 0,866 / 0,866 / 0,834 / 0,833 / 0,851 / 0,888), czyli lepiej niż stara asymetryczna poza,
- IoU sylwetki ciała 1050 klatek 0,8922 -> 0,8923; pozostałe 34 akcje identyczne co do bitu (różnica wszystkich krzywych: zmieniła się tylko akcja 17), `test_items` 0,718 -> 0,718, `test_canvas` 16/16 OK (`body_parts_after_sym17.json`, `items_after_sym17.json`),
- nogi: sztywne przesunięcie z miednicą do 9 cm (klatka 3), 1-6 cm w pozostałych, gładko między klatkami.
- Oglądane nakładki sprite / model we wszystkich 5 kierunkach i renderu z cieniowaniem: ręce w górze pokrywają się z oryginałem, bez zawinięć; zostają 1-pikselowe obrzeża (grubość siatki ciała) i końcówki pięści.

Nie ruszone: `26_mounted_attack_1h` (prawa 162°, klatka 0) i `29_mounted_attack_2h` (lewa 161°, klatka 1) mają ten sam typ błędu; dla jazdy symetria nie jest znana. Ten sam skręt tułowia w kluczach mogą mieć inne akcje (nie sprawdzano poza 16 i 17).
Zmieniony binarny `model/UO_Body_0x190.blend`: klucze akcji 17 (miednica, kręgosłup, klatka, szyja, głowa, uda, obojczyki, ręce, palce); osadzone skrypty bez zmian. Poprzedni stan: commit `40dbcf7`.

## Dłonie i palce w akcji 17 (2026-10-09, po prośbie „popraw ułożenie dłoni i palców”)
Stan wyjściowy: palce 2-5 w kluczach akcji 17 były wyprostowane (zgięcie 1-2°, jak deska), kciuk 20-36°; w widoku z tyłu i z boku model miał wąskie dłonie zwężające się w szpic, oryginał ma bryłowate, lekko zaciśnięte dłonie z kciukiem.
Pomiar (okolica dłoni = koła o promieniu 11 px wokół obu dłoni, 5 kierunków, miara 1 − IoU sylwetki vs sprite, `pipeline/hand_fit.py`, `pipeline/hand_fit_joint.py`):
- powierzchnia dłoni modelu vs sprite 0,96-1,03 (ok. 1000-1300 px, niezgodne 100-180 px po każdej stronie): sylwetka dłoni zgadza się w granicy rozdzielczości (1 px = 2,8 cm, palec ma ok. 1 px),
- obrót dłoni: siatka 105 orientacji (obrót wokół osi przedramienia, zgięcie, odchylenie nadgarstka) – klucz jest już najlepszy, każda zmiana pogarsza (0,171 -> 0,18-0,19),
- zgięcie i rozstaw palców dopasowane osobno dla klatki: zmiany o kilka stopni, o różnych znakach dla różnych palców, zysk 0,005-0,02 (szum); rozstaw palców i skala dłoni (1,00) nie dają nic; miara krawędzi (obrys + skoki głębi vs ciemne piksele sprite'a) jest równie płaska,
- wspólna poza palców dla klatek 1-4 (jedna, bez drżenia między klatkami): koszt 0,2182 (stary klucz) -> 0,2183 (zgięcie 20-35°), całkowita pięść (69°) gorsza o 0,03: sylwetka nie odróżnia otwartej dłoni od lekko zgiętej, ale wyklucza zaciśniętą pięść,
- odbicie lewej ręki bez błędu: kości L/R są dokładnymi lustrami (0,0 cm), końce palców po odbiciu 0,0 cm.
Wdrożone: jedna wspólna poza dla wszystkich 7 kluczy: palce 2-5 zgięte o 22 / 34 / 21 / 21° (stawy 1:1:0,8), kciuk bez zmian, skala dłoni 1,045, obrót dłoni bez zmian; lewa = lustro prawej. Wybrana, bo przy tej samej mierzonej zgodności (średni koszt 0,1999 vs 0,2000) usuwa szpiczaste, wyprostowane dłonie i daje zaokrąglone, bryłowate dłonie jak w oryginale (ocena na kafelkach oryginał/model, kierunki 0 i 3, klatki 1-4).
Pomiar po zmianie: IoU akcji 17 0,8641 -> 0,8637, ciało 1050 klatek 0,89226 -> 0,89225, `test_items` 0,718 -> 0,718, `test_canvas` 16/16 OK, pozostałe 34 akcje bez zmian (`body_parts_after_hands17.json`, `items_after_hands17.json`). Zmieniony binarny `model/UO_Body_0x190.blend`: klucze palców i dłoni akcji 17; poprzedni stan: commit `7536a44`.
Czego nie da się ustalić z sylwetek: dokładnego ułożenia palców (otwarte / zgięte 20-35° są nierozróżnialne). Jeśli użytkownik widzi w konkretnej klatce i kierunku inny kształt dłoni, trzeba to ustawić ręcznie na podstawie tej klatki.
