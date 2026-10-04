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
