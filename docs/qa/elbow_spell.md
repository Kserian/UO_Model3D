# Łokieć w czarze obszarowym (17_spell_area): pomiar, 2026-10-09

Zgłoszenie: przy czarowaniu, gdy postać unosi ręce, jedna ręka jest zgięta w łokciu nienaturalnie w dół. Wzorzec: oryginalne body 400 (`client/body_0x190_frames`, plik użytkownika `anim_0400.vd` jest z nim identyczny, 0 różnych klatek z 1050).

## Co jest
Kąt łokcia z kości (`upper_arm`/`forearm`, pozy wszystkich 35 akcji):
- `17_spell_area`, **lewa ręka**, klatki 0-4: **149 / 163 / 162 / 160 / 156°** (anatomicznie max ok. 145°). Klatka 2: bark z = 1,56 m, łokieć 1,80 m, nadgarstek **1,48 m**: ramię prosto w górę, przedramię złożone prosto w dół wzdłuż ramienia. Prawa ręka w tych samych klatkach: 45-70°, przedramię w górę (nadgarstek 1,81 m).
- Lewy bark jest też o 17 cm wyżej niż prawy w klatce 2 (obojczyk podciągnięty); możliwe, że to ten sam błąd dopasowania (niezmierzone).
- Pojedyncze klatki z łokciem >160° poza czarem: `26_mounted_attack_1h` klatka 0 (prawa 162°), `29_mounted_attack_2h` klatka 1 (lewa 161°). Reszta ≤145°.
- Sylwetka vs oryginał (IoU, 5 kierunków): 16_spell_directed 0,86-0,93; 17_spell_area klatki 1-4 **0,79-0,84** (najgorsze w całym ciele). W nakładkach brakuje zaciśniętych pięści (czerwone plamy na końcach rąk) i dłoń lewej ręki wisi poniżej łokcia, tam gdzie oryginał ma pięść w górze (kierunki 1 i 3).

## Dlaczego tak wyszło
Sylwetka z jednej strony nie wyznacza zgięcia łokcia (raport, pkt „6 póz: łokcie i kolana różnią się o ok. 6 px”): złożone przedramię i wyprostowane w górę dają prawie tę samą sylwetkę przy rzucie z boku, a stare dopasowanie miało limit obrotów i wpadło w ten minimalnie lepszy lokalny kształt.

## Próby naprawy (nie wdrożone)
Narzędzia: `pipeline/arm_refit.py` (lokalne, losowe starty), `pipeline/arm_grid.py` (cała sfera kierunków ramienia × obrót × zgięcie 20-120°, potem dopracowanie). Cel: 1 − IoU sylwetki modelu vs sprite, 5 kierunków naraz, podwójna waga nad barkiem.

| klatka | koszt stary (łokieć ok. 160°) | koszt nowy, łokieć ≤120° | łokieć nowy |
|---|---|---|---|
| 1 | 0,381 | 0,357 | 64° |
| 2 | 0,363 | 0,368 | 104° |
| 3 | 0,407 | 0,414 | 111° |
| 4 | 0,391 | 0,354 | 74° |

Wniosek: **sylwetki akceptują łokieć anatomiczny tak samo dobrze jak złożony** (różnica ±0,006, w 2 klatkach lepiej), czyli złożony łokieć jest błędem dopasowania, nie wiedzą z oryginału. Ale same sylwetki nie wybierają sensownego rozwiązania: w klatkach 1-2 najlepsze „anatomiczne” przedramię zawija się nad głową w widoku od tyłu (kierunki 3-4), więc **żadnej pozy nie wgrano do `.blend`**. Zmieniona mierzona wielkość (koszt) jest za mało czuła na to, co widać na oko.

## Decyzja użytkownika i wdrożenie (ten sam dzień)
Użytkownik: w grze ręce w tym czarze ruszają się symetrycznie, lewa ma robić to samo co prawa; wierność ruchu ważniejsza niż dopasowanie sylwetki. Wdrożone w `model/UO_Body_0x190.blend` (akcja `17_spell_area`, 7 kluczy):
- lewa ręka = **dokładne odbicie** prawej względem klatki piersiowej: obojczyk, ramię, przedramię, dłoń i palce, rotacja `q = (w, x, -y, -z)`, skala bez zmian, przesunięcie obojczyka z odwróconym x (macierze spoczynkowe kości L/R są dokładnymi lustrami `M·B·M`, `M = diag(-1,1,1)`; błąd odbicia w układzie klatki piersiowej 0,0000 m we wszystkich 7 klatkach; `pipeline/arm_mirror_action.py`),
- wspólna poza obu rąk dopasowana do sprite'ów (5 kierunków naraz) razem z kręgosłupem i klatką piersiową (obrót dowolny, mała kara za odejście od starego klucza): `pipeline/arm_sym_fit.py --torso free`. Samo odbicie bez dopasowania daje IoU 0,797; wariant z tułowiem bez skrętu / przechyłu wypada znacznie gorzej (miednica, szyja i głowa są w tych klatkach skręcone, więc odkręcenie samego kręgosłupa rozjeżdża ciało); szersze losowe starty nic nie poprawiły.

Pomiar (przed -> po):
- łokcie akcji 17 klatki 0-4: lewy 149-163° -> **44-70°, identyczny z prawym**; nadgarstek 24-32 cm nad łokciem (był poniżej),
- IoU sylwetki akcji 17: **0,862 -> 0,831** (klatki 1-4: 0,85/0,85/0,82/0,83 -> 0,82/0,79/0,78/0,80; klatki 0, 6 bez zmiany ok. 0,91 / 0,90), czyli symetria kosztuje ok. 0,03 IoU w tej akcji; reszta akcji identyczna co do bitu (tylko `17_spell_area` ma inne klucze, sprawdzone różnicą wszystkich krzywych),
- IoU sylwetki ciała 1050 klatek 0,8922 -> 0,8912 (`body_parts_after_sym17.json`), `test_items` 0,718 -> 0,718, `test_canvas` OK.
- Na oko (kierunek 3, klatki 1-2) oryginał ma pięść przy głowie, a model ramię wyprostowane wyżej: najlepsza pozę symetryczną, jaką znalazło dopasowanie, nie trafia w ten kształt; dopasowanie jest ograniczone sylwetką.

Nie ruszone: `26_mounted_attack_1h` (prawa 162°, klatka 0) i `29_mounted_attack_2h` (lewa 161°, klatka 1) mają ten sam typ błędu; dla jazdy symetria nie jest znana, do zdecydowania.
Zmieniony binarny `model/UO_Body_0x190.blend`: tylko klucze akcji 17 (chest, spine, clavicle, upper_arm, forearm, hand, palce L/R); osadzone skrypty bez zmian. Poprzedni stan: commit `40dbcf7`.
