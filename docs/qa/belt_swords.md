# Pas z mieczem (darmowy model, test ramek)

Model: „Cinto de armas” (idemotts, https://sketchfab.com/3d-models/cinto-de-armas-9f70d7d64cb4413e95300e892724052d), **CC BY 4.0**. Pliku `.glb` nie ma w repo (8,7 MB); przepis: `belt_swords_recipe.json`
(najpierw `python -I docs/qa/belt_swords_prep.py cinto_de_armas.glb belt_split.glb`, potem `python pipeline/uo_make_item.py docs/qa/belt_swords_recipe.json --preview --no-qa`).

Model ma 16 siatek: pas z paskami i uchwytami (`Object_4,6,8,10,12,14,34`), rapier z pochwą (`Object_16-24`, na lewym biodrze: rękojeść z przodu, czubek z tyłu w dół). Sztylet (`Object_26-32`, prawe biodro) usunięty na prośbę użytkownika (osobno nie ma sensu).

## Przepis (nowe opcje)
- `reference` = siatki pasa dopasowane do ciała (slot `waist`), ta sama transformacja idzie na miecz i sztylet. `"turn_back": false`: pas jest prawie symetryczny i autofit obracał go o 180°
  (miecz lądował czubkiem do przodu); front modelu jest znany, więc półobrót wyłączony.
- Pas = slot `waist`, PART `belt` (nowy w `uo_bind_item.py`: pelvis, spine, chest + uda). Paski i uchwyty zwisające poniżej talii idą za skórą uda pod nimi
  (wcześniej tylko pelvis/spine/chest: uda przebijały paski, w chodzie do 8 cm).
- Miecz = sztywny na `thigh.L` (`hip.L`). `pelvis_share`: część wagi na miednicy. Sztywno tylko na udzie (share 0) wbijało rękojeść w biodro przy zamachu uda:
  w biegu 22% wierzchołków miecza w ciele (do 7,7 cm), w ataku 33%. Miecz 0,4 (60% ruchu uda) jako kompromis „trzyma się nogi” / „nie wchodzi w ciało”.
- Pas stoi 1,5-2 cm od skóry w spoczynku (`GAP` waist 15 mm; po dopasowaniu najbliższy punkt 14,8 mm, p10 20 mm, p50 36 mm).

## Miecz widoczny i do barwienia (partial hue)
- `thicken` {`width`: 0.06}: przekrój pochwy i klingi powiększony wokół osi miecza tak, by oba kierunki miały >= 6 cm (było 3,9 x 1,6 cm, czyli x1,5 / x3,8); jelec i rękojeść osobną częścią x1,3 na tej samej osi (`own_axis: false`).
  Przy 36 px/m pochwa 3 cm = 1 px (cienka linia, w ruchu się gubiła), 6 cm = ok. 2 px.
- Części modelu (siatki): `Object_16` ostrze przy jelcu, `Object_24` pochwa, `Object_18` oplot rękojeści, `Object_20` jelec (mosiądz) **razem ze złotymi pierścieniami przy wlocie pochwy**, `Object_22` pomel.
  `belt_swords_prep.py` wydziela pierścienie z jelca jako `Object_20b` (kawałki luźne dalej niż -0,47 m na osi pochwy), żeby były szare razem z ostrzem.
- **Cały rapier w szarościach, bez bieli** (ostatnie prośby użytkownika): `METAL` false wszędzie (był już wyłączony przy poprzedniej próbie, biel zostawała). Prawdziwa przyczyna: oświetlona ściana renderuje się jako **sRGB(albedo)**
  (liniowo 0,98 = 250/255, 0,6 = 203, 0,5 = 188, 0,22 = 130), a przy ciemnym obrysie 188-199 wygląda jak biel. Dlatego sufit jasności: nowe ustawienie `uo_materials.py` `CLAMP_MAX` (górna granica albedo).
  Ostrze, pochwa, pierścienie: `FLAT_GREY` 0,30, `CLAMP_MAX` 0,32; oplot `FLAT_GREY` 0,32, `CLAMP_MAX` 0,34; jelec i pomel: tekstura modelu zdesaturowana (`SATURATION` 0, `BRIGHTNESS` 1,2, `CLAMP_MAX` 0,34).
  Próby: 0,5 (max 199, 1,4% pikseli > 180 = biel), 0,22 (max 145, ale mediana 43: prawie czarny). `FLAT_COLOR` zostaje w `uo_materials.py` (brązowy oplot: (0,80; 0,58; 0,40) jasny brąz).
- Przy 2 px szerokości każdy piksel ostrza jest brzegowy i dostaje obrys renderera (x0,38): ostrze wygląda na ciemniejsze niż jego albedo (mediana ok. 49/255), jaśniejsze są tylko oświetlone fragmenty przy jelcu.
- Pomiar na całym rapierze (stand, walk, run, atak 1H, 140 klatek, bez pasa): 7258 pikseli, **100%** dokładnie szarych (R=G=B), p10 / p50 / p90 / p99 / max = 33 / 49 / 57 / 147 / 159, 0% pikseli > 160. Przed pogrubieniem miecz miał 2889 widocznych pikseli (z rękojeścią).
  Strona w cieniu (miecz za ciałem) zostaje ciemnoszara (ok. 60/255), jak w UO.

## Tył pasa nie może być widoczny (klient rysuje przedmiot na ciele)
Warstwa przedmiotu (`.vd`) idzie na oryginalne ciało, a tułów domyślnie niczego nie zasłania (`TORSO_HIDE_MARGIN` działa tylko dla przedmiotów z własnością `uo_behind_torso`), więc tylna połowa pasa
(pierścień!) była rysowana na piersi w widoku od przodu, a przednia na plecach. Slot `waist` ustawia teraz `uo_behind_torso` (`uo_prepare_item.py`): tułów zasłania to, co jest >= 12 cm za nim. Widok z przodu: tylko przednia taśma, z tyłu: tylko tylna, boki bez zmian
(sprawdzone na składance ciało + warstwa przedmiotu, stoi / chód, 5 kierunków). Miecz zostaje bez tej własności (wisi z boku).

## Wersje (ostatnie prośby)
- **A** (`belt_swords_recipe.json`): ostrze o 1 px grubsze: `thicken` {`width`: 0,105} (miara: pole / długość klatki z samym ostrzem 1,54 -> 2,57 px, 5486 -> 10039 pikseli; szerokości 0,06 / 0,085 dawały 1,54 / 2,12 px).
- **B** (`belt_swords_recipe_thin.json`): o 1 px cieńsze niż A: `width` 0,06 (1,54 px).
- Oplot w obu: brąz o 20% ciemniejszy (liniowe albedo x0,8): `FLAT_COLOR` (0,272; 0,144; 0,06), `CLAMP_MAX` 0,32, `METAL` false; oświetlony piksel (145, 108, 71), mediana (48, 35, 23). Wcześniejsze wersje: (0,34; 0,18; 0,075) za jasna,
  (0,55; 0,30; 0,13) i (0,85; 0,55; 0,32) pomarańczowa / brzoskwiniowa. Ostrze, pochwa, pierścienie, jelec, pomel bez zmian (szarości, najjaśniejszy piksel 152).

## Pomiar (przed render, `item_qa`-podobny, skóra = UO_Body w pozie)
Wierzchołki w ciele >2 mm / najgłębiej (mm), run3 (wagi: pas z udami, miecz 0,4, sztylet 0,6):

| akcja | pas | miecz (przed pogrubieniem) | sztylet (usunięty) |
|---|---|---|---|
| stand | 0% / 3 | 3% / 17 | 0% / 0 |
| walk | 11% / 49 (było 84) | 2% / 30 | 17% / 51 |
| run | 0,3% / 63 | 1,4% / 28 (było 77) | 13% / 24 |
| attack 1H | 0,2% / 41 | 0% / 0 (było 71) | 19% / 53 |
| spell | 1% / 36 | 55% / 102 (ręka i tułów na mieczu) | 3% / 12 |

Render dodatkowo wypycha pas z nóg (`BODY_GAP` 6 mm); miecz i sztylet są sztywne (`uo_no_body_gap`), więc tam, gdzie ręka lub tułów wchodzą w pochwę (czar, atak), zasłania je głębia. `test_items` po zmianie: 0,718 (bez zmian).
Ograniczenie: pochwa rapiera ma ok. 3 cm, czyli ok. 1 px przy 36 px/m: na ramkach to cienka czarna linia.
