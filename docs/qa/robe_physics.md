# Fizyka szat i spódnic: nogi wypychają tkaninę (sesja 15)

Cel (prośba użytkownika): luźne ubranie (szata, sukienka, spódnica) ma poruszać się jak w grze: nogi popychają materiał, ale umiarkowanie i zgodnie z ruchem nóg; bez błędów graficznych
(nogi wypychające tkaninę za daleko, przeskoki między klatkami). Poprzednia próba (łańcuchy kości + symulacja Blendera `uo_cloth_bake.py`, 30-60 min na przedmiot) została usunięta (CLAUDE.md, sesja 14).

## Co robią oryginały (klient: `anim.mul`, szata 469; ciało 400, te same klatki)

Zmierzone na klatkach marszu i biegu (kierunki 1-3, ciało i szata na tym samym płótnie):
- brzeg szaty wystaje poza zewnętrzną krawędź stóp średnio o **3-5 px** w marszu (min -3, max 14), w biegu średnio 5-11 px (max 28 px, tkanina „leci” za biegnącym);
- szerokość dolnego brzegu śledzi rozstaw nóg słabo (nachylenie 0,6-0,8 w marszu, ~0 w biegu), a samo przypięcie cienia ud do wag (jak spodnie) zawęża brzeg (-3 px), bo tkanina z przodu popychana jest przez nogę, która jest z przodu, a średnia dwóch ud jest zerem;
- poniżej bioder szata nie jest przyklejona do nóg (stoi 8-9 cm od skóry w udach i goleniach, `layer_analysis.md`) i wisi od pasa.
To jest zachowanie powłoki wypukłej wokół nóg zawieszonej na pasie, nie śledzenia kości.

## Model (`pipeline/cloth_lib.py`, numpy; użyty w `render_uo_layer.py`)

Jedna klatka, bez pamięci poprzedniej (żadnych przeskoków, klatkę można policzyć osobno), bez iteracji (brak niestabilności):
1. **Zawieszenie**: wagi `PART = "robe"` / `"skirt"` (`uo_bind_item.py`): od bioder w górę jak skóra (tułów, rękawy), poniżej wszystko na **miednicy** (udo, goleń, stopa -> miednica).
2. **Pole zasięgu nóg**: nogi to 6 kapsuł (uda, golenie, stopy; promień = mediana odległości skóry kości od jej osi: udo 0,10, goleń 0,07); stopy nie liczą się do powłoki (szata je zakrywa). Dla każdej wysokości
   i kąta wokół osi pasa: `h(kąt, z)` = jak daleko nogi sięgają w tym kierunku na tej wysokości (funkcja podparcia kół, którymi kapsuły tną płaszczyznę), wygładzone po kącie i wysokości.
3. **Namiot**: tkanina to jedna płachta od pasa. Gdzie nisko musi sięgnąć daleko, **każda wyższa warstwa też** (prosta od pasa do tego punktu), a poniżej punktu zwisa i zwęża się o najwyżej `drop` = 1 m promienia na metr wysokości.
   Bez tego powstawał „bąbel” na samym dole.
4. **Pchnięcie**: wierzchołek o promieniu `rho` < `h + margin` jest wypychany promieniowo o `kappa * (h + margin - rho)` (`margin` 5 cm, `kappa` 0,8), od pasa w dół (rampa 15 cm).
5. Potem zwykłe `BODY_GAP` (6 mm od skóry), więc nic nie przenika.
Przedmiot dostaje własność `uo_cloth` (oś, wysokość pasa, wysokość brzegu, parametry) przy `PART = "robe"` / `"skirt"`; KIND `robe` / `skirt` w `uo_make_item.py` robi to samo z pliku obcego modelu.

## Kalibracja (miara: dolna część repliki szaty poniżej bioder vs sprite)

Replika szaty: skóra od bioder w górę odsunięta o 3,5 cm + rura (promienie zmierzone na oryginale 469 w stand: półszerokość 0,215 -> 0,30 m, półgłębokość 0,22 m).

Prawdziwy potok (Cycles, `pipeline/test_robe.py`, 205 klatek: stand, marsz, bieg, atak, czar, upadek, 5 kierunków):

| wariant | IoU dolnej części | błąd szerokości brzegu (px, wartość bezwzgl.) |
|---|---|---|
| `legs` (rura wiązana jak spodnie, stan sprzed zmiany) | 0,641 | 11,1 |
| `robe` z udami (0,3 wagi) | 0,647 | 9,4 |
| tylko miednica | 0,613 | 4,6 |
| **miednica + powłoka nóg (domyślne: margin 5 cm, kappa 0,8, drop 1,0)** | **0,757** | **3,4** |
| margin 8 cm, kappa 0,8 | 0,761 | 3,6 (szerszy brzeg) |
| margin 3 cm, kappa 0,6 | 0,717 | 3,0 |

Margin i kappa to „jak mocno nogi pchają”: wyżej = szerzej i lepsze IoU, niżej = mniej. Wybrane 5 cm / 0,8 (kolano wyników), zmiana: stałe `CLOTH_MARGIN`, `CLOTH_KAPPA`, `CLOTH_DROP` w `uo_bind_item.py`.

Wariant numpy (`pipeline/robe_calib.py`, 1 s na ustawienie; kształt spoczynkowy dopasowany do klatek stand każdej szaty, żeby mierzyć ruch, nie kształt), IoU bez powłoki -> z powłoką:
469 robe 0,697 -> 0,725; 447 sukienka 0,676 -> 0,700; 970 całun 0,709 -> 0,715 (błąd szerokości brzegu 4,2/4,2/5,7 -> 3,9/4,1/4,0 px). Kilt 455 i spódnica 971: sekcja „Długość” niżej.
Sprawdzone i odrzucone: stałe śledzenie ud (`alpha`) przy włączonej powłoce (0 najlepsze), solver więzów odległości (PBD) z kolizją kapsuł (prawie bez efektu, 0,654), „grawitacja” (zdjęcie pochylenia miednicy z zawisłej tkaniny: upadek wypada gorzej, leżąca szata nie wisi),
promień kapsuły w centylu 85 (za gruby: szata za szeroka w stand), dryf tkaniny za idącym / biegnącym (przesunięcie brzegu do tyłu 3-15 cm: IoU 0,700 -> 0,689-0,699, nic nie poprawia), margines narastający z tym, jak daleko noga wystaje za tkaninę (miał zmniejszyć
szerokość brzegu w stand o 6 px: IoU 0,691-0,696 < 0,700, stand 5,2-6,9 px zamiast 6,4). Brzeg w stand zostaje o ok. 6 px (17 cm) za szeroki: poza stand (pozycja nóg w klatce stand 0 jest rozstawiona szerzej niż w spoczynku) kierunki marszu i biegu wypadają dobrze.

## Długość: dłuższe szaty i krótkie spódnice (`robe_calib.py`, numpy, kształt spoczynkowy dopasowany do stand każdej)

Stałe 5 cm / 0,8 psują kilt (455: IoU 0,715 bez powłoki -> 0,704) i spódnicę do kolan (971: 0,723 -> 0,705): sięgają ich tylko uda, a mniejsza tkanina jest sztywniejsza. Przegląd na tych dwóch:
margin 0-0,02 i kappa 0,3-0,5 dają 0,745-0,764. Reguła w `uo_bind_item.py` (`mark_cloth`): od wysokości brzegu 0,15 m (długa szata: 5 cm / 0,8) do 0,30 m (krótka: 2 cm / 0,5) wartości płynnie przechodzą.

| oryginał | wysokość brzegu | bez powłoki IoU / błąd brzegu px | stałe 0,8/5 cm | wg długości |
|---|---|---|---|---|
| 469 szata | 0,19 | 0,697 / 6,4 | 0,725 / 3,8 | **0,732** / 3,9 |
| 447 sukienka | 0,09 | 0,676 / 4,2 | 0,684 / 5,5 | **0,684** / 5,5 |
| 970 całun | 0,23 | 0,709 / 5,7 | 0,711 / 4,0 | **0,724** / 4,2 |
| 455 kilt | 0,62 | 0,715 / 4,9 | 0,704 / 3,7 | **0,758** / 2,4 |
| 971 spódnica do kolan | 0,26 | 0,723 / 4,3 | 0,705 / 4,8 | **0,742** / 3,3 |

Z regułą powłoka poprawia IoU na wszystkich pięciu oryginałach (+0,008...+0,043). Parametry dobrane na tych samych pięciu, więc to nie jest test na niezależnych danych.

## Przeskoki między klatkami (liczone na 31 akcjach z co najmniej 3 klatkami, replika-rura, pozycje jak w grze)

Największy skok wierzchołka szaty między kolejnymi klatkami / największy skok końca kapsuły nogi: mediana 0,72, maks. 1,15 (akcja 12, `attack_2h_bash`: 20,5 vs 17,9 cm); marsz 0,58 (25,7 vs 44,7 cm), bieg 0,37; koniec -> początek pętli
marszu 14 cm, biegu 24 cm (mniej niż typowy krok 26-27 cm). Czyli tkanina nigdy nie skacze o więcej niż nogi (z tolerancją 15%), pętle chodu i biegu się zamykają. Model nie ma pamięci klatek: nie ma czego akumulować.
Pole zasięgu jest ciągłą funkcją położenia nóg (gładkie w kącie i wysokości), więc nie ma progów, na których tkanina mogłaby przeskoczyć.

## Jazda konna (akcje 23-29)

Na koniu nogi są rozstawione i wysunięte do przodu: powłoka nóg robiła z dołu szaty „worek", a szata zawieszona tylko na miednicy zostawiała uda gołe, podczas gdy oryginał układa się wzdłuż nóg do stóp.
Dlatego w akcjach konnych (`CLOTH_MOUNTED` w `render_uo_layer.py`, 1 = śledź nogi, 0 = jak pieszo) szata porusza się tak, jak poruszałaby ją skóra pod nią: `uo_bind_item.py` zapisuje przed wysłaniem udziału nóg na miednicę
wagi ud, goleni i stóp w atrybutach `uo_leg_*` (stary przedmiot bez nich: podział lewa/prawa i udo/goleń). Pomiar `test_robe.py` na replice (akcje 23, 25, 26; cała sylwetka replika vs sprite 469, klatki bez konia):
miednica + powłoka nóg jak pieszo 0,622 (dolna część 0,113), udo/goleń z podziałem lewa/prawa 0,564, **wagi nóg jak skóra 0,678 (dolna część 0,230)**. Kształt jest „kiełbasą" grubszą niż oryginał (replika-rura, nie prawdziwa szata), ale pokrywa nogi bez dziur; koń przesłania dolną część.

## Czego model nie robi (znane różnice)

- Bez pamięci poprzedniej klatki: nie ma bezwładności („lecenia” szaty za biegnącym: oryginał wystaje w biegu do 28 px poza stopy, my do kilku). Dodanie dryfu zależnego od akcji (marsz/bieg) wymaga wyboru wzorca i nie jest zrobione.
- Upadek (`die_*`) wypada najsłabiej (IoU 0,69): leżąca postać, tkanina powinna leżeć na ziemi.
- **Peleryna (Cloak, oryginał 468)**: zmierzone `pipeline/cloak_calib.py` (replika wisząca z ramion, IoU poza sylwetką ciała, kształt dopasowany do stand): powłoka nóg **nic nie zmienia** (IoU 0,395 -> 0,393-0,395; nogi prawie nie dotykają peleryny),
  a oryginał w ataku, czarze i upadku jest większy o 175-307 px niż replika (tkanina leci i faluje, bezwładność). Peleryna ma własny model: pochylenie do tyłu wokół ramion per akcja i klatka (`PART cloak`, `docs/qa/cloak_physics.md`); `PART robe` ani `skirt` nie nadają się do niej.
- Rękawy, kaptur, płaszcz (zawieszona na ramionach, inna fizyka) nie mają tego modelu.
- Test na replice, nie na prawdziwym obcym modelu szaty (w repo nie ma darmowego modelu szaty); na gambesonie (kurtka do połowy uda) jako `robe` ruch jest poprawny wizualnie (marsz, bieg).

## Sesja 16: czy da się lepiej? Pomiary (nic nie zmieniono w renderze)

Prośba użytkownika: fizyka szaty ma odtwarzać grę, także w ruchach nóg; dopuszczona symulacja i pola sił. Zmierzone na pięciu oryginałach (469 szata, 447 sukienka, 970 całun, 455 kilt, 971 spódnica), wszystko na klatkach z `anim.mul`
(wzorce w `pipeline/body13/mul/`, narzędzie `pipeline/robe_hull_eval.py`, protokół jak wyżej: kształt spoczynkowy repliki dopasowany do stand bez powłoki):

| wariant | 469 | 447 | 970 | 455 | 971 | średnia IoU dolnej części | błąd szerokości rąbka |
|---|---|---|---|---|---|---|---|
| bez powłoki | 0,724 | 0,699 | 0,736 | 0,515 | 0,644 | 0,664 | 5,55 px |
| powłoka produkcyjna (bezwzględna, reguła długości) | 0,756 | 0,729 | 0,751 | 0,462 | 0,676 | 0,675 | 4,69 px |
| powłoka względem pozycji spoczynkowej nóg, kappa 0,25 | 0,764 | 0,734 | 0,750 | 0,516 | 0,675 | **0,688** | **4,03 px** |

- **Powłoka względem spoczynku** (`hull_push_rel` w `robe_hull_eval.py`: pchają tylko nogi poza zasięgiem spoczynkowym, kappa·nadmiar, namiot od pasa) jest fizycznie czystsza (szata zrobiona wokół nóg w spoczynku nic nie dostaje w spoczynku, kilt nie jest psuty) i na replikach z dopasowanym kształtem lepsza o 0,013.
  **Nie wdrożona:** w prawdziwym potoku (Cycles, `test_robe.py`, replika zmierzona na 469) remisuje z obecną: kappa 0,25 → 0,673, 0,55 → 0,740, 0,7 → 0,756, 0,85 → 0,758, 1,0 → 0,748 (obecna: 0,757). Optymalna kappa zależy od tego, jak szeroką replikę zbudujemy (0,25 dla dopasowanej do stand, 0,7-0,85 dla zmierzonej ręcznie),
  więc przejście nie ma uzasadnienia w mierze głównej. Do rozważenia, gdy będzie prawdziwy darmowy model szaty.
- **Tabela ruchu rąbka per akcja i klatka (jak dla peleryny)**: 5 współczynników na klatkę (rąbek szerszy, przesunięty, wydłużony wzdłuż kroku) dopasowanych wspólnie na 469+447+970 dała IoU 0,739 → 0,798, a dopasowania z osobnych szat korelowały 0,8-0,97. **To był fałszywy trop:** współczynniki w stand są niezerowe (c0 -0,10, c1 +0,12)
  i poprawiają kształt repliki we wszystkich klatkach naraz (replika-rura nie ma kształtu prawdziwej szaty). Po odjęciu wartości ze stand (tak jak działałby nowy model z własnym kształtem) tabela **pogarsza**: 0,755 → 0,723 (469), 0,716 → 0,666 (447), 0,747 → 0,710 (970); także na kilcie i spódnicy. Wynik wysokiej korelacji
  między szatami to wspólny błąd kształtu, nie wspólna fizyka. Nie wdrożona.
- **Bezwładność (sprężyna z tłumieniem, rąbek goni cel z powłoki)**: z powłoką bezwzględną daje +0,02 (marsz 0,735 → 0,79), ale to tylko osłabia jej nadmiar; z powłoką względną: 0,753 → 0,755 (4 szaty, 24 ustawienia ω, ζ, profil). Nic nie dodaje.
- **Prędkość nóg i miednicy jako regresory** współczynników wychylenia rąbka: CV po akcjach R² ujemne (prędkość nie tłumaczy wychylenia), pozycje kolan i kostek tłumaczą tylko drugą harmoniczną (R² 0,46).
- Co wynika: reszta błędu (IoU 0,76 z możliwych ok. 0,80+) to w większości kształt rąbka prawdziwej szaty (fałdy, rozkloszowanie w biegu do 15 px poza nogami), którego powłoka z nóg ani proste dynamiki nie odtwarzają. Dalszy ruch wymaga **prawdziwego darmowego modelu szaty**
  (kształt własny, test zamiast repliki-rury) albo pełnej symulacji tkaniny z kolizją, której zysk trzeba by zmierzyć na takim modelu.

### Test na prawdziwym darmowym modelu szaty (użytkownik, `robe_free.glb`, licencja nieznana: plik nie jest w repo)
Jedna siatka 34 924 wierzchołków, długa wąska szata z rękawami. `uo_make_item.py` z `kind: robe`, bez ręcznych ustawień: autofit skala x1,26, przesunięcie -0,25 m w pionie, pokrycie skóry 96%, w ciele po dopasowaniu 0 wierzchołków, w ruchu w ciele średnio 3,6% (najgorzej atak, do 15 cm, wypychane przez `BODY_GAP`), 3 min 45 s z podglądem.
Podgląd (stand, marsz, bieg, atak, czar, upadek, 3 kierunki) wygląda poprawnie. Porównanie powłoki nóg na tym modelu (podglądy marszu i biegu, 3 kierunki):
- **bez powłoki** (kappa 0) i **względna kappa 0,25**: nogi wystają spod wąskiej szaty w marszu i biegu (stopa i łydka widoczne na zewnątrz): zły wynik;
- **względna 0,5**: nogi zakryte poza skrajnym wykrokiem biegu (stopy wystają na boki);
- **obecna (bezwzględna 5 cm / 0,8) i względna 0,8**: nogi zawsze zakryte, marsz = gładki stożek jak w oryginale; w biegu w profilu rąbek rozkłada się w stożek (jak w oryginale 469), ale na wysokości uda powstają wybrzuszenia (kolano uniesione do przodu, noga wyprostowana do tyłu).
Wniosek: na wąskiej szacie obecna powłoka daje to, czego trzeba (szata zakrywa nogi i układa się w stożek); powłoka względna z niższą kappa jej nie dorównuje. Zostaje bez zmian. Do poprawy zostaje wygładzenie wybrzuszeń uda w biegu (kandydat: mniejszy `drop` albo wygładzenie pola w wysokości).

## Sesja 16, symulacja tkaniny Blendera na replice 469 (`pipeline/robe_cloth_sim_test.py`, eksperyment)
Użytkownik dopuścił prawdziwą fizykę i kolizje. Stan: render nie ma symulacji (powłoka nóg jest quasi-statyczna, kolizja z ciałem tylko przez `BODY_GAP`); dawny `uo_cloth_bake.py` (Blender Cloth na łańcuchach kości, 30-60 min na przedmiot) usunięto w sesji 14 razem z łańcuchami.
Test: replika-rura 469 (1,1 tys. wierzchołków, kształt dopasowany do stand), 2 górne pierścienie przypięte do miednicy, Cloth Blendera (quality 8, kolizja z poruszanym UO_Body, tarcie 0), każda akcja osobno (preroll 40 klatek, pętle 3 cykle, bierze się ostatni), ok. 1,5 min na akcję pętlową; miara jak wyżej (IoU dolnej części vs sprite 469):

| akcja | symulacja (cotton) | powłoka nóg | sztywno na miednicy |
|---|---|---|---|
| stand | **0,815** | 0,770 | 0,763 |
| marsz | 0,298 | 0,737 | 0,787 |
| bieg | 0,303 | 0,723 | 0,704 |
| atak | 0,649 | 0,726 | 0,675 |
| czar | 0,616 | 0,720 | 0,681 |

W marszu i biegu tkanina **wspina się po nogach** (rąbek z z 0,19 m na 0,7-0,87 m, promień 0,09 m): wąska rura bez zapasu materiału nie może opłynąć wykroczonych nóg, więc się marszczy do góry. Zmiękczenie (naprężenie i ściskanie 1 zamiast 15) podnosi marsz do 0,607, ale to już rozciąganie, nie fizyka tkaniny;
mniejsza grawitacja i grubsza kolizja (3 cm) nie pomagają. Oryginał ma zapas materiału (rozkloszowanie do 15 px poza nogami), którego replika-rura (i wąski model szaty z darmowych plików) nie ma. Wniosek: czysta symulacja bez dopasowania gorsza od powłoki; sensowne jest tylko podejście hybrydowe (cel = kształt z powłoki, symulacja dodaje ruch wtórny i kolizje, jak dawne `GOAL`).

### Dalsze próby (sesja 16): więcej materiału w symulacji, wygładzenie pola nóg
- **Zapas materiału** (`robe_cloth_sim_test.py sim ... wx= wy=`: poszerzenie rąbka repliki od pasa w dół): marsz 0,298 → 0,309 (×1,5 / ×1,3) → 0,469 (×2 / ×1,5), bieg 0,303 → 0,468 → 0,593 (powłoka nóg 0,754 / 0,731). Zapas pomaga (tkanina wspina się mniej), ale nawet przy dwukrotnie szerszej rurze symulacja jest daleko za powłoką, a szeroki rąbek psuje stand.
- **Wygładzenie pola zasięgu nóg** (więcej przejść po kącie i wysokości, `robe_hull_eval`-owa próba na 5 oryginałach): IoU bez zmian (0,675 → 0,679), a na modelu użytkownika wybrzuszenia uda w biegu zostają (podgląd bieg, profil i przód): to nie szum pola, tylko prawdziwy wykrok z uniesionym kolanem. Nie wdrożone. `drop` 0,5 / 0,25 pogarsza (0,670 / 0,663).

### Nogi: sylwetka modelu użytkownika wobec oryginału 469 (`pipeline/item_vs_original.py`, sesja 16)
Render `clothing` szaty `robe_free` porównany klatka po klatce z sprite'em 469 (część poniżej bioder, 5 kierunków): marsz IoU 0,775 (rąbek -1,5 px węższy), bieg 0,749 (-3,7 px), stand 0,712 (+1,2 px), atak 0,718 (-6,8 px). Sylwetka marszu i standu pokrywa się z oryginałem; różnice:
- szata `robe_free` jest dłuższa (czerwony pas na dole: rąbek poniżej podłoża -0,025 m, w 469 0,19 m): to cecha modelu, nie nóg;
- **w biegu oryginał ma ostre „skrzydła" w rogach rąbka** (do 15-28 px poza stopy), a nasz rąbek jest zaokrąglony i kończy się na zasięgu nóg + 5 cm.
Ustawienia powłoki na tym modelu (średnia IoU z 4 akcji): obecne 0,739; margines 0,12: 0,748; 0,18: 0,715; 0,25: 0,680; `drop` 0,3: 0,724; kappa 1,0 + margines 0,1 + drop 0,3: 0,708; margines 0,12 + kappa 0,6: 0,741. Na replikach 5 oryginałów (`robe_hull_eval.py`) optimum to obecne 5 cm / 0,8, więc różnica 0,009 jest w granicach szumu i nie ma podstaw do zmiany.
Sprawdzone na replikach (IoU 5 oryginałów, obecne 0,675), żadne nie pomaga: stożek (kontynuacja linii od pasa poniżej najdalszego punktu nóg, także tylko dla nóg wykraczających poza zasięg w spoczynku): 0,59-0,64 (bieg 0,666 → 0,53-0,59); wygładzenie pola nóg mniejsze lub większe (0-10 przejść): 0,672-0,679; większy margines lub kappa: 0,657-0,664.
Wniosek: nogi są ustawione na optimum tego, co tłumaczy geometria nóg. Brakujący element to **boczne „skrzydła" rąbka w biegu poza zasięgiem nóg**: ruch tkaniny niezależny od położenia nóg. Tabela ruchu (`robe_flare`, odrzucona wyżej) ani bezwładność tego nie uchwyciły.

## Sesja 16: symulacja hybrydowa (`pipeline/uo_cloth_sim.py`), wdrożona
Użytkownik zażądał prawdziwie układającej się tkaniny z kolizją z ciałem (nie tylko powłoki). Czysta symulacja zapadała się w marszu i biegu (wyżej), więc **hybryda**: kopia przedmiotu (zwykła siatka) w Cloth Blendera, każdy wierzchołek trzymany sprężyną ("goal", waga pinu) przy celu danej klatki = to, co rysował render bez symulacji (skinning + pchnięcie nóg `hull_push`), siła 1,0 od pasa w górę, 0,4 w rąbku
(rampa 0,30 m), rękawy własny cel 0,7; ciało `UO_Body` jest colliderem (nogi, ręce, dłonie), każda akcja osobno (preroll 40 klatek, pętle 3 cykle, bierze się ostatni). Wynik zapisany jako **różnica względem celu** (`cloth_sim.npz` obok `item.blend`, miękki limit 0,12 m: szybki upadek zostawiał szatę 0,8 m za ciałem i odsłaniał je), `render_uo_layer.py` (`CLOTH_SIM = 1`) dodaje ją do pchnięcia nóg, potem `BODY_GAP` jak dotąd.
Pomiar na replice oryginału 469 (`robe_cloth_sim_test.py ... hybrid=1`, IoU dolnej części vs sprite): marsz 0,754 -> 0,765, bieg 0,731 -> 0,735 (cel 0,3-0,7 i dodatkowe strojenie bez wpływu), stabilnie, bez zapadania. Zysk sylwetki mały; zysk to naturalny ruch rąbka (fałdy, opóźnienie), kolizja z nogami i rękoma, bez przenikania.
Czas: 177 klatek (28 akcji pieszych) w 4 procesach ok. 70 s dla 8 tys. wierzchołków (`--jobs 4`); akcje konne (23-29) bez symulacji (rąbek idzie za nogami). `test_robe` 0,757 bez zmian (bez pliku symulacji render jest identyczny), `test_canvas` OK.
Przykład (Myrddin_robe.fbx, T-poza z własnym szkieletem Daz): `arms_down` ustawia ramiona kośćmi modelu (`pose_own_arms`, wagi autora), `drop_materials` wycina pas, `materials.TEXTURE_PX` uśrednia teksturę (tweed 5120 px dawał białe kropki przy 36 px/m).
