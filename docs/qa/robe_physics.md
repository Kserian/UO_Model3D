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
469 robe 0,697 -> 0,725; 447 sukienka 0,676 -> 0,700; 970 całun 0,709 -> 0,715 (błąd szerokości brzegu 4,2/4,2/5,7 -> 3,9/4,1/4,0 px). Kilt 455 nie oceniony (replika-rura się nie dopasowuje).
Sprawdzone i odrzucone: stałe śledzenie ud (`alpha`) przy włączonej powłoce (0 najlepsze), solver więzów odległości (PBD) z kolizją kapsuł (prawie bez efektu, 0,654), „grawitacja” (zdjęcie pochylenia miednicy z zawisłej tkaniny: upadek wypada gorzej, leżąca szata nie wisi),
promień kapsuły w centylu 85 (za gruby: szata za szeroka w stand).

## Czego model nie robi (znane różnice)

- Bez pamięci poprzedniej klatki: nie ma bezwładności („lecenia” szaty za biegnącym: oryginał wystaje w biegu do 28 px poza stopy, my do kilku). Dodanie dryfu zależnego od akcji (marsz/bieg) wymaga wyboru wzorca i nie jest zrobione.
- Upadek (`die_*`) wypada najsłabiej (IoU 0,69): leżąca postać, tkanina powinna leżeć na ziemi.
- Rękawy, kaptur, peleryna (zawieszona na ramionach, inna fizyka) nie mają tego modelu.
- Test na replice, nie na prawdziwym obcym modelu szaty (w repo nie ma darmowego modelu szaty); na gambesonie (kurtka do połowy uda) jako `robe` ruch jest poprawny wizualnie (marsz, bieg).
