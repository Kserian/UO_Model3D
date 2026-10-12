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
