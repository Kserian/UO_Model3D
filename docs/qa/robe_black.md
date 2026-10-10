# Czarna szata z haftem (darmowy model z symulatora tkaniny, slot `robe`), sesja 21

Model: plik `.glb` od użytkownika (Google Drive, licencja nieznana; pliku nie ma w repo). Długa czarna szata ze stójką, zapięciem na pętle, pasem z klamrą, rękawami dzwonowymi
i złotym haftem; pod spodem panel tuniki. Jedna siatka: 616 278 wierzchołków, 1 141 616 trójkątów, jeden materiał z teksturą.
Zlecenie: zbudować środowisko na Blenderze 5.2+, dopasować szatę do postaci i zanimować; żadnych przebić ciała, materiał ma się ruszać naturalnie, nogi nie mogą przebijać szaty.
Po pierwszej wersji (uwagi użytkownika): szata za duża, nie widać dłoni, stopy przebijają w biegu, rękawy rozdarte przy pachach. Wolno częściowo skalować elementy szaty.

Przepis `docs/qa/robe_black_recipe.json` (z katalogu z `robe_black.glb`; `--preview` = 6 akcji ok. 19 min, `--vd` = wszystkie 35 ok. 44 min: symulacja 177 klatek 26 min w 4 procesach, render):
```
{"name": "robe_black", "file": "robe_black.glb", "kind": "robe", "outer_shell": 0.006, "decimate": 20000,
 "materials": {"GREY_CLOTH": {"value": 0.6, "contrast": 0.5, "fill": 0.04, "flatten": 0.05}},
 "prepare": {"HEM": 0.15, "HEM_BAND": {"height": 0.15, "fade": 0.02, "skip_front": 20, "edge": 5}},
 "conform": {"CLOTH_KAPPA": 1.0, "CLOTH_MARGIN": 0.06, "SPACE_SMOOTH": 0.04, "SLEEVE_END": 0.02},
 "sim": {"arm_goal": 0.95, "smooth": 0.04},
 "scene": {"uo_outline": 0.6, "uo_hide_erode": 1, "uo_legs_under": 1, "uo_despeckle": 28}}
```

## Środowisko: Blender 5.2
`pip install "bpy==5.2.*" numpy scipy pillow` w Pythonie 3.13 (bpy 5.2.2). Potok `uo_make_item.py` działa na 5.2 bez zmian, poza `uo_cloth_sim.py` (`Action.fcurves` usunięte w 5.0: teraz `bpy_compat.action_fcurves`).
Plik `model/UO_Body_0x190.blend` nadal zapisujemy `bpy 4.2` (`sync_blend_scripts.py`); `item.blend` przedmiotu zapisany w 5.2 otwiera się tylko w 5.x.

## Co było nie tak i co zmieniłem (zmierzone)
| Problem | Przyczyna | Zmiana |
|---|---|---|
| Pęknięcia, dziury, prześwitująca podszewka po decymacji | model to **zamknięta bryła ok. 1,5 cm grubości** (warstwa zewnętrzna + wewnętrzna; grubość wzdłuż normalnej p50 15,6 mm); decymacja zlewa obie warstwy | `uo_import_item.py` `OUTER_SHELL`: zostaje warstwa zewnętrzna (każda ściana patrzy w niebo 8 promieniami, partner pod nią w 6 cm, wygrywa ta, która widzi więcej; głosy wygładzone po sąsiadach; drobne odpryski < 0,2% ścian usunięte) |
| Szwy (rękaw / tułów, pacha) rozchodziły się przy dopasowaniu: rozdarcia pod pachami | model to **284 osobne panele** (wykroje), które w pliku tylko się stykają; każde przestawienie rękawa albo owinięcie przesuwa je osobno | `OUTER_REMESH` (przepis `"outer_shell": 0.006`): najpierw remesh wokselowy 6 mm (bryła ciągła, 2 s), potem warstwa zewnętrzna; 1 spójna powłoka zamiast 284 paneli |
| Tekstura w smugi po decymacji | decymacja przeciąga UV | `BAKE_TEXTURE` (przepis `"bake_texture": 2048`, przy `OUTER_REMESH` zawsze): nowe UV (smart project) i tekstura wypalona z oryginału (Cycles, 5 s) |
| Szwy glTF (duplikaty wierzchołków) rozjeżdżają się w decymacji | import glTF dzieli wierzchołki na szwach UV / normalnych | `WELD` 1e-6 m przed decymacją (domyślnie) |
| Szata dłuższa od ciała (rąbek 15 cm pod podłogą), płaty rąbka wypchnięte w dół przez stopy | manekin modelu jest wyższy; rąbek przy podłodze wchodzi w stopy (skóra stóp do z = 0,14 m), owinięcie pcha go wzdłuż normalnych podeszwy | `uo_prepare_item.py` `HEM` (przepis `"prepare": {"HEM": 0.15}`): część poniżej 0,70 m skrócona tak, by rąbek był na 0,15 m (oryginalna szata 469: ok. 0,19 m); stopy widać pod rąbkiem jak w grze |
| Szata za duża, dłonie schowane | pierwsza wersja: zwykły `fit` + `stretch` 1,2 / 1,15 (manekin węższy od ciała UO), rękawy dzwonowe na całą dłoń | `"conform"` (`uo_conform_item.py`): rękawy na osie rąk, tułów owinięty 1,5 cm od skóry (+ do 3 cm luzu modelu), dół poniżej krocza wisi; bez `stretch` |
| Zapięcie na piersi podarte, kołnierz zgnieciony | owinięcie ciągnie każdy panel (klapy, pętle) osobno, klapy się przecinają | `uo_conform_item.py` `SPACE_SMOOTH` 0,04 m: przesunięcie owinięcia uśrednione w przestrzeni (nie po siatce), nakładające się części przesuwają się razem; `FINAL_ITERS` 40 (było 10) i wypychanie od kości w ręce: po owinięciu 0 wierzchołków w skórze |
| Symulacja tkaniny nie trzymała celu (rękawy zjeżdżały, przedramię gołe) | **przypięte wierzchołki zostawały na celu pierwszej klatki** (odchyłka 0,000 od `T[0]`, 6-8 cm od `T[i]`): współrzędne siatki zmieniane w handlerze klatki nie docierają do pinu Cloth; ten sam test na samej siatce daje to samo w **bpy 4.2.23 i 5.2.2** (więc symulacja z sesji 16 też nie trzymała celu) | `uo_cloth_sim.py`: cel każdej klatki to klucz kształtu animowany krzywymi F (1 na swojej klatce, 0 na innych, liniowo); pin trzyma cel dokładnie (0,0000 m), wolny rąbek 2-3,5 cm od celu. Koszt: ok. 0,7 s na klatkę zamiast 0,1 (tkanina naprawdę pracuje) |
| Stopy przez spódnicę w biegu | (1) powłoka nóg `kappa` 0,8 pokrywa tylko 80% zasięgu nogi; (2) symulowany rąbek zostaje w tyle i stopa wychodzi przed niego | `CLOTH_KAPPA` 1,0 i `CLOTH_MARGIN` 0,06 (osobne linie w `uo_bind_item.py`, nadpisywane w przepisie); w symulacji kolizja grubsza (`thick` 0,02 m: piksele nóg przez szatę w biegu 466 -> 196) i **`in_max` 0,01 m**: poniżej pasa tkanina może się cofnąć do osi miednicy najwyżej o 1 cm względem celu |
| Rękawy pomięte w symulacji | rękawy dzwonowe zderzają się z ręką | rękawy rozpoznane po atrybucie `uo_region` z `conform` (było: `|x| > 0,19 m` nad pasem), `arm_goal` 0,95 |

## Pomiary
`item_skin_check.py` (piksele skóry ręki / tułowia widoczne przez przedmiot; nowa kolumna: nogi, także stopy pod rąbkiem, które są widoczne zgodnie z modelem), akcje stand, marsz, bieg, atak, czar, upadek (205 klatek):

| wersja | ręce px | tułów px | nogi px |
|---|---|---|---|
| pierwsza (fit, symulacja z błędem pinu) | 2942 | 1678 | - |
| fit + `stretch`, symulacja naprawiona, `HEM` | 157 | 36 | 930 |
| `conform` na ciągłej powłoce (t4), symulacja bez `in_max` | 478 | 0 | 1108 |

| **końcowa** (`outer_shell` 0,006 + `conform` + `SPACE_SMOOTH` + symulacja z `in_max`), te same 6 akcji | 395 | **0** | 863 |
| **końcowa, wszystkie 35 akcji (1050 klatek)** | 1845 (1,8 px na klatkę) | **0** | 4353 |

Gdzie są te piksele (arkusze `--sheet`): ręce = nadgarstek przy mankiecie obok dłoni (rękaw kończy się nad dłonią, dłonie widać); nogi = stopy pod rąbkiem (rąbek na 0,15 m, jak w oryginałach),
nogi jeźdźca w akcjach konnych (szata leży na udach, stopy wystają) i nogi w upadkach. Stopy przez spódnicę w biegu (widoczne w pierwszej wersji): brak.
`item_clearance.py` (35 akcji, 210 klatek, po pchnięciu renderu): materiał w skórze własnej strefy średnio 0,012% wierzchołków, najgorsza klatka 0,18%, najgłębiej 13 mm; w nogach 0,00%;
dłonie / głowa 0,01%; rozciągnięcie krawędzi p99 3,72 (skóra 2,83). Dla porównania tunika Jedi: 0,03% / 0,33% / 29 mm.
Owinięcie w spoczynku: po nim 0 wierzchołków w skórze (było 23, najgłębiej 64,8 mm przy 284 panelach), odstęp od skóry p50 / p90 5,7 / 15,3 cm (model 6,6 / 15,3).
Regresja repo (bpy 4.2): `test_items` 0,719, `run_qa.py` (canvas 16/16, autofit 13,6 mm, szata 0,757, peleryna 0,508, materiały, import) bez zmian.

## Zgłoszenia użytkownika z klatek (21 zgłoszeń, druga runda)
Użytkownik ogląda `clothing.vd` nałożone na **oryginalne `body400.vd`** (VD Animation Viewer). Tam przez dziury warstwy ubrania widać oryginalne ciało, czego `item_skin_check.py`
(podgląd 3D) nie łapie. Nowa miara: **`pipeline/item_body_holes.py`**: warstwa `clothing` na oryginalnych klatkach (`client/body_0x190_frames`, zaczepy wyrównane),
dziura = piksel ciała wewnątrz zamkniętego (2 px) i wypełnionego obrysu przedmiotu, z etykietą części ciała z renderu 3D (dłonie i głowa osobno: dłoń przed szatą
jest rysowana celowo); arkusz `--sheet akcja:kierunek` jak w viewerze. Odtwarza zgłoszenia (np. Walk Armed kier. 1 kl. 1, 5, 10: noga na dole przodu).
Skąd dziury (13 zgłoszonych akcji, 395 klatek, przed: ręka 303, tułów 163, nogi 402 px):
- **ręce i barki: zasłanianie przez dłoń i głowę** (bez dłoni wśród zasłaniających ręka 96, bez głowy tułów 92). Dłoń / głowa 3D stoją 1-2 px obok oryginalnego sprite'a: tam, gdzie wycinają rękaw lub kołnierz, w oryginale jest przedramię lub bark.
  Zmiana: `render_uo_layer.py` **`HIDE_ERODE`** (właściwość sceny `uo_hide_erode`): obszar, w którym dłoń / głowa zasłania przedmiot, zwężony o 1 px (dłoń tylko przy rękawie, gdy przedmiot ma `uo_region`). 1 px: ręka 303 -> 109, tułów 163 -> 61; 2 px chowało krawędzie dłoni przed szatą.
- **nogi: szczeliny w spódnicy z symulacji** (bez zasłaniania przez nogi nadal 380 px; bez symulacji Walk Armed 21 zamiast 44): sąsiednie fałdy przesuwają się w symulacji różnie i przechodzą przez siebie.
  Zmiana: `uo_cloth_sim.py` **`smooth`** 0,04 m (przesunięcie symulacji uśrednione w przestrzeni, 2 przejścia): marsz 44 -> 12, bieg 25 -> 10, czar 51 -> 3 px. `goal` 0,7 (54 px) i samokolizja (77 px, 2x wolniej) gorsze.
- **nogi w upadkach** (21, 22: 314 / 237 px także bez symulacji): leżąca postać ma nogi skierowane do widza, stopa / goleń 3D przed tkaniną wycina dziurę. Zmiana: **`LEGS_UNDER`** (`uo_legs_under`): nogi nie zasłaniają przedmiotu (długa szata zawsze je kryje): 314 -> 9, 237 -> 5; stopy pod rąbkiem nadal widać.
- **rękaw zasłaniał dłoń** (Stand kier. 0): oba rękawy kończyły się 9 cm za nadgarstkiem. `uo_conform_item.py` **`SLEEVE_END`** 0,02 m (ostatnie 25 cm rękawu ściśnięte wzdłuż ręki): dłonie widać.
- **złoty haft rąbka niepełny**: haft w kwiaty na ciemnym tle; na szarej tkaninie przerwy rozbijają pas. `uo_materials.py` **`GREY_CLOTH`** z `fill` 0,04 m (przerwy w złocie domknięte złotem w przestrzeni tekstury).
Na 6 akcjach podglądu (205 klatek): ręka 164 -> 39, tułów 65 -> 11, nogi 520 -> 34 px.
**Wszystkie 35 akcji (1050 klatek), `item_body_holes.py`, przed -> po: ręka 753 -> 152, tułów 300 -> 64, nogi 1447 -> 423 px, klatek z wadą 636 -> 317.** Reszta: stopy pod rąbkiem
(na koniu 49-50 px na akcję, zgodnie z modelem: szata kończy się nad stopą) i 1-3 px nadgarstka przy dłoni na wodzach. Zgłoszone klatki po zmianie: nogi 0 we wszystkich (zgłoszenia 2-6, 12, 15),
ręka / tułów 0-2 px. `item_clearance.py`: 0,011% / 0,11% / 13 mm (było 0,012% / 0,18%). Przebudowa na aktualnym modelu (`5127dec`, nowe pozy rąk 23 klatek innej sesji).
Ciemne piksele przy dłoniach to wnętrze rękawa dzwonowego widoczne przez mankiet (cień w środku tkaniny), nie obrys: osobny obrys dla wewnętrznych brzegów nic nie zmienił, nie wdrożony.

## Kolor: szarość jak zwykła szata UO, złoto zostaje
Oryginał 469 (akcje 0, 1, 2, 4, 9, 16): tkanina nasycenie 0, jasność p5 / p25 / p50 / p75 / p95 = 74 / 115 / 139 / 156 / 180, krawędź / wnętrze 0,29. Szata była czarna (mediana 32).
`uo_materials.py` **`GREY_CLOTH`** (przepis `"materials"`): piksele tekstury o nasyceniu < 0,25 lub poza odcieniem złota (18-72°) -> szarość, mediana tkaniny na `value`, kontrast tekstury zachowany
(stosunek do mediany), złoto bez zmian, łagodne przejście; tekstele poza wyspami UV (czarne tło wypalenia) nie liczą się do mediany. Render liniowo zależny od `value`; `value` 0,6 na teksturze 2048 px.
Uwaga użytkownika: z tyłu (i z przodu) wyróżniał się jaśniejszy pasek, czyli środkowy panel z innej tkaniny (czarny adamaszek na czarnym). Zmiana: `flatten` 0,05 m (szarość liczona względem tkaniny
dookoła, Gauss w teksturze, zamiast jednej mediany) i `contrast` 0,5 (wzór tkaniny słabszy; fałdy cieniuje światło): pasek znika. Tkanina w renderze (marsz + stanie) p5 / p50 / p95 = 108 / 141 / 160 (469: 74 / 139 / 180),
krawędź / wnętrze 0,43 przy `uo_outline` 0,6 (469: 0,29).
Obrys: **`uo_outline`** 0,6 (właściwość sceny, zamiast `OUTLINE` 0,38) zmiękcza czarne piksele brzegu; pojedyncze czarne piksele w środku (cienie fałd z tekstury) usuwa `uo_despeckle` 28 (dla tkanin było 0).
Przepis: nowa sekcja **`"scene"`** w `uo_make_item.py` ustawia właściwości sceny przedmiotu, które czyta renderer.

## Złoty pas rąbka (trzecia runda)
Uwaga użytkownika: złote zdobienie na dole w wielu miejscach znika przy nogach (Walk Armed kier. 4 kl. 1: środek tyłu). Przyczyna w modelu: **środkowe panele nie mają haftu na dole**
(z tyłu pas adamaszku ok. 13 cm, z przodu panel tuniki w rozcięciu), a reszta pasa to haft w kwiaty z przerwami; środek wypada między nogami. `fill` domyka tylko przerwy w hafcie.
Decyzja użytkownika: pas jak obecny haft, na całym obwodzie, **oprócz wycięcia z przodu**.
Zmiana: `uo_prepare_item.py` **`HEM_BAND`** (przepis `"prepare": {"HEM_BAND": {"height": 0.15, "fade": 0.02, "skip_front": 20, "edge": 5}}`): po `HEM` wysokość każdego wierzchołka nad
**lokalnym** rąbkiem (najniższy punkt w 36 przedziałach kąta wokół osi spódnicy, wygładzony), waga 1 do `height`, zanik przez `fade`, 0 w ±`skip_front`° od przodu (−Y; krawędzie klap
ze złotymi listwami leżą przy ±25°); atrybut punktu `uo_hem_band`, w materiale mieszanie ze złotem własnej tekstury (jasne / ciemne złoto p20 / p80, plamki szumem jak haft; tekstele już złote zostają).
Wysokość z podglądu 3D w spoczynku: obecny haft sięga ok. 0,15-0,18 m nad rąbek (po `HEM` x0,64). `uo_make_item.py` przepuszcza teraz ustawienia `prepare` będące słownikiem (`HEM_BAND`).
Pomiar (35 akcji, udział złotych pikseli w dolnych 3 px każdej kolumny sylwetki sięgającej rąbka): **0,727 -> 0,811** (np. marsz 0,75 -> 0,87, bieg 0,66 -> 0,77; reszta to celowo szary panel
w wycięciu, obrys i stopy). `item_body_holes.py` bez zmian: ręka 152, tułów 64, nogi 423 px, klatek z wadą 317.

## Odrzucone (zmierzone, nie powtarzać)
- Zwykły `fit` z `stretch` 1,2 / 1,15: zakrywa ciało, ale szata wychodzi za duża (bufiaste barki), rękawy zasłaniają dłonie; użytkownik odrzucił.
- `CLOTH_KAPPA` 1,0 bez ograniczenia `in_max`: kinematycznie nogi zakryte, ale symulowany rąbek zostaje w tyle i stopa wychodzi przez spódnicę w biegu.
- `arm_goal` 0,7 dla rękawów `conform`: rękawy dzwonowe marszczą się na ręce w biegu; 0,95 gładkie.
- Sklejanie szwów po odległości (`remove_doubles` 0,5-4 mm): szczeliny między panelami mają medianę ok. 1 cm, sklejanie zjada gęstą siatkę zanim zszyje panele; remesh wokselowy zlewa je w 2 s.
- Grubsza kolizja z `dist` 0,02 (nie tylko `thick`): bieg 147 zamiast 196 px nóg, ale symulacja 3 razy wolniejsza.

## Otwarte
- W biegu z profilu szata rozkłada się szeroko (powłoka nóg `kappa` 1,0 pokrywa cały wykrok); węższa = stopy przez materiał.
- Tekstura po remeshu jest wypalona 2048 px: haft rozmyty (przy 36 px/m niewidoczny).
- Symulacja kosztuje ok. 0,7 s na klatkę na 24 tys. wierzchołków (pełne `.vd` ok. 44 min).
