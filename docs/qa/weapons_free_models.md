# Broń z darmowych modeli (`uo_orient_weapon.py`, sesja 15)

Darmowe modele broni leżą wzdłuż X albo Y, czubkiem w którąś stronę, w dowolnej skali. `uo_place_weapon.py` wymaga broni stojącej: trzon wzdłuż +Z, czubek do góry, głowica płaska w płaszczyźnie XZ (szeroką stroną na +X).
`uo_orient_weapon.py` robi to samo automatycznie: oś długa z SVD wierzchołków -> Z; **czubek** = koniec z mniejszym przekrojem na 4% długości (ostrze, lufa, grot są węższe niż głowica miecza czy kolba; dla maczugi,
młota, topora `TIP = "heavy"` albo oś `"+y"`); najszersza strona prostopadła do trzonu -> +X; skala do długości klasy (`LENGTHS`, **zmierzone na oryginałach z klienta**: najdłuższa przekątna obrysu klatki po wszystkich klatkach animacji broni, m): miecze 1H 0,83 (katana) / 0,97 (cutlass) / 1,12 (scimitar) / 1,21 (broadsword) / 1,31 (viking), maczugi, młoty, pałki 1,06-1,29, topory 1H 1,34-1,39, topory 2H 1,39-1,65, bardysz 2,37, halabarda 2,51, długa włócznia 2,70, kostur 2,27-2,78, łuk 1,34, kusza 1,09, ciężka kusza 1,44;
stąd miecz 1,1, maczuga 1,2, topór 1,35 (2H 1,4), drzewcowa 2,5, kostur 2,4, włócznia 2,7, łuk 1,34, kusza 1,1, broń palna 1,2 m (sztylet 0,5 nie zmierzony); dolny koniec na początku układu.

Modele użytkownika:
- `miecz.glb` (4954 wierzchołków, 0,47 x 1,99 x 0,09 w jednostkach pliku): leżał wzdłuż Y, czubek po stronie -Y; skrypt zwraca „tip flipped” (przekrój 0,0016 przy czubku vs 0,0075 przy głowicy), skala 0,553 -> 1,1 m. Klasa `weapon1h`
  (kość `weapon1h.R`, ruch skalibrowany na 13 oryginalnych broniach, `docs/qa/weapons_right_hand.json`): w idle, cięciu, pchnięciu, biegu i upadku ostrze idzie za prawą ręką.
- `muszkiet.glb` (7 siatek, 4555 wierzchołków, 5,7 jednostki długości): lufa (przekrój 0,034) w górę, kolba (0,107) na dole, skala 0,21 -> 1,2 m. Klasa `bow` (kość `bow.L`, lewa ręka): w `19_attack_crossbow` i `18_attack_bow`
  lufa celuje do przodu z ramienia, w pozostałych akcjach wisi przy lewej dłoni.

Ograniczenia: brak sprite'ów odniesienia (kuszy 651/616 i łuku 649 nie ma w repo: potrzebne wyciągi z klienta); roll wokół trzonu dla `bow` jest nieokreślony (`weapon_roll.md`); cienkie ostrze (ok. 1,8 px przy 36 px/m) rysuje się głównie
konturem (`OUTLINE`), więc jest ciemne: tak samo cienkie oryginały. `uo_materials.py` nie podnosi jasności ciemnych metali (próbowano: bez efektu na tych modelach, więc wycofane).
