# Czarna kamizelka garniturowa (darmowy model, slot `vest` / MiddleTorso)

Model: „Black Suit Vest” (prestonboy132, https://sketchfab.com/3d-models/black-suit-vest-cbc97be2ca064abfb190b8090b37d233), **CC BY 4.0**. Plik `.glb` (2,2 MB) nie jest w repo.
Jedna siatka (11 331 wierzchołków, 1 materiał, tekstura), rozmiar w jednostkach pliku 1,61 x 0,70 x 1,99 (kamizelka ma ok. 0,6 m wysokości, czyli plik jest 3,3 razy za duży).

```
python -I pipeline/stretch_glb.py black_suit_vest.glb black_suit_vest_pre.glb 0.3 0.8,1.25,0.77
python pipeline/uo_make_item.py docs/qa/black_vest_recipe.json --preview          # z katalogu z black_suit_vest_pre.glb; --vd = pełny render
```

## Metoda: kamizelka jako powłoka skóry ciała (`uo_skin_shell.py`)
Obce modele odzieży obejmującej tułów (tu kamizelka z manekina) nie pasują do ciała UO: wypychanie ich wierzchołków ze skóry (`uo_fit_item.py`) i z ramion w pozach (`uo_pose_clear.py`) rozrywa siatkę na kolce i poszarpane krawędzie (8-14 cm przesunięć bez wygładzenia), a to, co zostaje w ciele, widać jako skórę w materiale.
Dlatego z modelu zostaje **obrys** (wysokość, dekolt, otwory na ręce, dół), a sama kamizelka jest zbudowana ze skóry ciała:
1. `stretch_glb.py`: skala 0,3 do metrów i nierówne rozciągnięcie (szerokość x0,8, głębokość x1,25, wysokość x0,77), potem zwykłe dopasowanie (`fit`, odstęp 35 mm): daje ustawienie i obrys modelu na ciele.
2. `uo_skin_shell.py`: skóra tułowia (grupy pelvis, spine, chest, clavicle, neck, udział >= 70% wagi), która leży w odległości < 8,5 cm od dopasowanego modelu, poniżej 1,59 m, z wolnym walcem wokół szyi (promień 9 cm) i wyciętym V z przodu (apeks 1,30 m, górny półszerokość 11 cm), zostaje jako powłoka;
   odsunięta od skóry o 3 cm wzdłuż normalnych, podzielona (Catmull-Clark x1), wygładzona (6 przebiegów, brzegi 16 przebiegów); siatka modelu jest zastępowana tą powłoką.
3. Wiązanie `torso` (pelvis, spine, chest, neck) jak skóra pod spodem (wagi wygładzone SMOOTH 4); materiał: jeden płaski kolor (0,035; 0,033; 0,033 liniowo, średnia tekstury modelu 0,027), bo powłoka nie ma UV.
4. `no_body_gap` (renderer nie gnie kamizelki wokół ramion klatka po klatce), `behind_torso` (tułów zasłania tylny panel w dekolcie V), `min_piece` 24 (renderer usuwa kawałki mniejsze niż 24 px, które ramię odcina od ramiączek).

## Historia prób (z pomiarami; nie powtarzać)
| Próba | Wynik |
|---|---|
| Autodopasowanie `vest` bez zmian | plik wzięty za metry: kamizelka 1,2 m do ud, „skrzydła” na ramionach; `ITEM_QA` 3,3% w ciele, do 12 cm |
| Skala + rozciągnięcie + `fit` (odstęp 35 mm) + `PART torso` + `cut_above` + `behind_torso` | gładka siatka w spoczynku, ale w pozach: tułów 4% -> 0,4-1,0% (odstęp 35 mm), skóra w obrębie kamizelki na klatkach 5,6% -> 1,2% (`behind_torso`) |
| `pose_clear` (ramiona, potem też tułów) | **rozerwał siatkę na kolce** (kolce na ramionach i szyi w sprite'ach); nawet łagodny (`CAP` 12 mm, `SMOOTH` 25) zostawia zmarszczki |
| Wycięcie otworów na ręce tam, gdzie ramiona przemiatają pozy | zaznaczało 49% siatki (boczne panele leżą w strefie ramion) |
| `smooth_mesh` + `no_body_gap` na modelu | czystsze, ale nadal zmarszczki, kolce przy szyi i „rogi” na ramionach; uwaga użytkownika: „wygląda okropnie” |
| **Powłoka skóry** (ta metoda) | patrz niżej |
| Wiązanie powłoki `all` (kości ramion) | psuje zasłanianie: kości ramion trafiają do „własnych części” przedmiotu, ramię przestaje go zasłaniać i kamizelka jest rysowana na ramionach (skóra w kamizelce 14%); zostaje `torso` |
| `MIN_GAP` po wygładzeniu, `SMOOTH` 0 wag, `GAP` 4 cm | bez poprawy (przebicia tułowia 0,2-0,7%) |
| `INSIDE` 0,5 / 0,6 / 0,7 (udział wag w grupach tułowia) | 0,5-0,6: ramiączka sięgają barku, ale przebicia 0,3-0,8% do 57 mm; **0,7: 0-0,2%, do 32 mm** |

## Wynik (pełny `.vd`, 35 akcji x 5 kierunków = 1050 klatek, 360 KB; w repo go nie ma)
- **Przebicia tułowia (siatka w pozach, `vgap2`)**: stand 0%, bieg 0%, atak 0%, czar 0,04%, chód 0,10% (do 32 mm), upadek 0,20% (do 25 mm), jazda 0,20%; `ITEM_QA`: średnio 2,9% wierzchołków w ciele (to kończyny w bocznych panelach: ramię wisi przy tułowiu, do 5 cm; w klatce je zasłania),
  najgłębiej 48 mm (czar; wcześniej 76-84 mm).
- **Skóra widoczna w obrębie kamizelki na klatkach: 0,47% pikseli ogółem** (poprzednia wersja 1,0-1,3%, przed `behind_torso` 5,6%), najgorsze: 21_die_forward 1,68%, 29_mounted_attack_2h 1,24%, 26_mounted_attack_1h 1,20%.
- **Grubość** (odstęp od sylwetki ciała): p50 2,8 cm, p90 5,6 cm (oryginalna koszula 3,9, płytówka 5,6).
- **Gładkość obrysu** (warstwa przedmiotu, 1026 klatek z widoczną kamizelką): obwód / sqrt(pole) **4,34** (wersja z kolcami 6,08; `smooth_mesh` 5,68), kawałków na klatkę 1,06, pyłków < 12 px **0,00** (było 0,13-0,05).
- Żadna z 1050 klatek nie jest pusta ani nie dotyka krawędzi płótna.

## Nowe w narzędziach
`pipeline/uo_skin_shell.py` (kamizelka / gorset jako powłoka skóry: `"skin_shell": {...}` w części przepisu; parametry w nagłówku skryptu), `pipeline/stretch_glb.py` (skala i rozciąganie pliku), `uo_import_item.py` `STRETCH`,
opcje części w `uo_make_item.py`: `skin_shell`, `cut_above`, `behind_torso`, `no_body_gap`, `smooth_mesh`, `min_piece`; `render_uo_layer.py`: własność sceny `uo_min_piece` (domyślnie 8 px); `uo_pose_clear.py`: `AVOID` może być listą.
Wnioski ogólne: (1) **odzież obejmująca tułów** (pas, kamizelka) potrzebuje `behind_torso`, inaczej klient rysuje tylny panel na piersi; (2) przedmiot nie może być wiązany z kośćmi ramion, jeśli ramię ma go zasłaniać (`OWN_PARTS_NEVER_HIDE`); (3) obcy model na innym manekinie: obrys z modelu, powierzchnia ze skóry.

## Otwarte
- Ramiączka z przodu cienkie (dekolt V + otwory na ręce zabierają większość skóry w obszarze barku przy `INSIDE` 0,7).
- Płaski kolor zamiast tekstury (prążki i guziki modelu giną przy 36 px/m; guziki można dorysować, jeśli mają być widoczne).
- Przebicia tułowia w upadku i chodzie do 3 cm na kilku wierzchołkach; ramiona w bocznych panelach zasłania klatka.
