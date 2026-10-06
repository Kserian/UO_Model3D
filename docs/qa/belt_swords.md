# Pas z mieczem i sztyletem (darmowy model, test ramek)

Model: „Cinto de armas” (idemotts, https://sketchfab.com/3d-models/cinto-de-armas-9f70d7d64cb4413e95300e892724052d), **CC BY 4.0**. Pliku `.glb` nie ma w repo (8,7 MB); przepis: `belt_swords_recipe.json`
(`python pipeline/uo_make_item.py docs/qa/belt_swords_recipe.json --preview --no-qa`, plik `cinto_de_armas.glb` obok).

Model ma 16 siatek: pas z paskami i uchwytami (`Object_4,6,8,10,12,14,34`), rapier z pochwą (`Object_16-24`, na lewym biodrze: rękojeść z przodu, czubek z tyłu w dół), sztylet (`Object_26-32`, na prawym).

## Przepis (nowe opcje)
- `reference` = siatki pasa dopasowane do ciała (slot `waist`), ta sama transformacja idzie na miecz i sztylet. `"turn_back": false`: pas jest prawie symetryczny i autofit obracał go o 180°
  (miecz lądował czubkiem do przodu); front modelu jest znany, więc półobrót wyłączony.
- Pas = slot `waist`, PART `belt` (nowy w `uo_bind_item.py`: pelvis, spine, chest + uda). Paski i uchwyty zwisające poniżej talii idą za skórą uda pod nimi
  (wcześniej tylko pelvis/spine/chest: uda przebijały paski, w chodzie do 8 cm).
- Miecz = sztywny na `thigh.L` (`hip.L`), sztylet na `thigh.R` (`hip.R`). `pelvis_share`: część wagi na miednicy. Sztywno tylko na udzie (share 0) wbijało rękojeść w biodro przy zamachu uda:
  w biegu 22% wierzchołków miecza w ciele (do 7,7 cm), w ataku 33%. Miecz 0,4 (60% ruchu uda) i sztylet 0,6 jako kompromis „trzyma się nogi” / „nie wchodzi w ciało”.
- Pas stoi 1,5-2 cm od skóry w spoczynku (`GAP` waist 15 mm; po dopasowaniu najbliższy punkt 14,8 mm, p10 20 mm, p50 36 mm).

## Pomiar (przed render, `item_qa`-podobny, skóra = UO_Body w pozie)
Wierzchołki w ciele >2 mm / najgłębiej (mm), run3 (wagi: pas z udami, miecz 0,4, sztylet 0,6):

| akcja | pas | miecz | sztylet |
|---|---|---|---|
| stand | 0% / 3 | 3% / 17 | 0% / 0 |
| walk | 11% / 49 (było 84) | 2% / 30 | 17% / 51 |
| run | 0,3% / 63 | 1,4% / 28 (było 77) | 13% / 24 |
| attack 1H | 0,2% / 41 | 0% / 0 (było 71) | 19% / 53 |
| spell | 1% / 36 | 55% / 102 (ręka i tułów na mieczu) | 3% / 12 |

Render dodatkowo wypycha pas z nóg (`BODY_GAP` 6 mm); miecz i sztylet są sztywne (`uo_no_body_gap`), więc tam, gdzie ręka lub tułów wchodzą w pochwę (czar, atak), zasłania je głębia. `test_items` po zmianie: 0,718 (bez zmian).
Ograniczenie: pochwa rapiera ma ok. 3 cm, czyli ok. 1 px przy 36 px/m: na ramkach to cienka czarna linia.
