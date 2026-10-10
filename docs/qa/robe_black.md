# Czarna szata z haftem (darmowy model z symulatora tkaniny, slot `robe`), sesja 21

Model: plik `.glb` od użytkownika (Google Drive, licencja nieznana; pliku nie ma w repo). Długa czarna szata ze stójką, zapięciem na pętle, pasem z klamrą, rękawami dzwonowymi
i złotym haftem; pod spodem panel tuniki. Jedna siatka: 616 278 wierzchołków, 1 141 616 trójkątów, jeden materiał z teksturą.
Zlecenie: zbudować środowisko na Blenderze 5.2+, dopasować szatę do postaci i zanimować; żadnych przebić ciała, materiał ma się ruszać naturalnie, nogi nie mogą przebijać szaty.
Po pierwszej wersji (uwagi użytkownika): szata za duża, nie widać dłoni, stopy przebijają w biegu, rękawy rozdarte przy pachach. Wolno częściowo skalować elementy szaty.

Przepis (`--preview` = 6 akcji, `--vd` = wszystkie 35):
```
{"name": "robe_black", "file": "robe_black.glb", "kind": "robe", "outer_shell": 0.006, "decimate": 20000,
 "prepare": {"HEM": 0.15},
 "conform": {"CLOTH_KAPPA": 1.0, "CLOTH_MARGIN": 0.06, "SPACE_SMOOTH": 0.04},
 "sim": {"arm_goal": 0.95}}
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

(końcowe liczby: niżej)
